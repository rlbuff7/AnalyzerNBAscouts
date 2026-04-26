import json
import logging
import os
from datetime import datetime
from typing import Optional

import config
import stats
import odds
import ev

PARTIAL_RESULTS_FILE = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), ".cache", "partial_results.json"
)

log = logging.getLogger(__name__)


def _normalize_team_name(name: str) -> str:
    if not name:
        return ""
    return "".join(c.lower() for c in name if c.isalnum())


def _build_team_alias_index() -> dict:
    idx = {}
    for canonical, aliases in config.TEAM_NAME_MAP.items():
        idx[_normalize_team_name(canonical)] = canonical
        for a in aliases:
            idx[_normalize_team_name(a)] = canonical
    return idx


_TEAM_ALIAS_INDEX = _build_team_alias_index()


def canonical_team_name(name: str) -> str:
    norm = _normalize_team_name(name)
    if norm in _TEAM_ALIAS_INDEX:
        return _TEAM_ALIAS_INDEX[norm]
    for key, canonical in _TEAM_ALIAS_INDEX.items():
        if norm and (norm in key or key in norm):
            return canonical
    return name


def _team_abbr(name: str) -> str:
    canonical = canonical_team_name(name)
    aliases = config.TEAM_NAME_MAP.get(canonical, [])
    for a in aliases:
        if len(a) == 3 and a.isupper():
            return a
    return canonical[:3].upper() if canonical else ""


def _format_game_time(iso: str) -> str:
    if not iso:
        return ""
    try:
        dt = datetime.fromisoformat(iso.replace("Z", "+00:00"))
        return dt.strftime("%H:%M UTC")
    except Exception:
        return iso


def _match_games(nba_games: list[dict], odds_events: list[dict]) -> list[dict]:
    matched = []
    for ev_evt in odds_events:
        odds_home = canonical_team_name(ev_evt.get("home_team", ""))
        odds_away = canonical_team_name(ev_evt.get("away_team", ""))

        nba_match = None
        for g in nba_games:
            nba_home = canonical_team_name(g.get("home_team", ""))
            nba_away = canonical_team_name(g.get("away_team", ""))
            if nba_home == odds_home and nba_away == odds_away:
                nba_match = g
                break
            if nba_home == odds_away and nba_away == odds_home:
                nba_match = g
                break

        matched.append({
            "event_id": ev_evt["event_id"],
            "home_team": odds_home,
            "away_team": odds_away,
            "commence_time": ev_evt["commence_time"],
            "nba_game": nba_match,
        })
    return matched


def analyze_day() -> list[dict]:
    log.info("Fetching today's NBA games...")
    nba_games = stats.get_todays_games()
    log.info(f"NBA API returned {len(nba_games)} games")

    log.info("Fetching today's events from Odds API...")
    odds_events = odds.get_todays_events()
    log.info(f"Odds API returned {len(odds_events)} events")

    if not odds_events:
        log.warning("No odds events found for today")
        return []

    matched = _match_games(nba_games, odds_events)

    entries: list[dict] = []
    player_stats_cache: dict = {}
    matchup_cache: dict = {}
    playoff_history_cache: dict = {}

    for game_idx, m in enumerate(matched):
        event_id = m["event_id"]
        home_canon = m["home_team"]
        away_canon = m["away_team"]

        log.info(f"Analyzing {away_canon} @ {home_canon}")
        if game_idx > 0:
            _save_partial(entries)

        props = odds.get_props_for_game(event_id)
        if not props:
            log.warning(f"No props returned for {away_canon} @ {home_canon}")
            continue

        home_team_id = stats.find_team_id_by_name(home_canon)
        away_team_id = stats.find_team_id_by_name(away_canon)

        for prop in props:
            player_name = prop["player_name"]
            market_key = prop["market"]
            line = prop["line"]
            direction = prop["direction"]
            odd_decimal = prop["odd_decimal"]
            bookmaker = prop["bookmaker"]

            player_id = player_stats_cache.get(("__id__", player_name))
            if player_id is None:
                player_id = stats.get_player_id(player_name)
                player_stats_cache[("__id__", player_name)] = player_id

            if not player_id:
                log.info(f"Player not found in nba_api: {player_name}")
                continue

            if stats.stats_endpoint_blocked():
                log.error("stats.nba.com unreachable — aborting analysis. "
                          "Use a VPN/proxy (set HTTPS_PROXY in .env) and try again.")
                return entries

            if player_id not in player_stats_cache:
                player_stats_cache[player_id] = stats.get_player_recent_stats(
                    player_id, n_games=config.LOOKBACK_GAMES
                )
            pstats = player_stats_cache[player_id]

            if player_id not in playoff_history_cache:
                playoff_history_cache[player_id] = stats.get_player_playoff_history(player_id)

            if pstats.get("games_played", 0) == 0:
                log.info(f"No game log for {player_name}")
                continue

            opponent_team_id = away_team_id
            opponent_name = away_canon
            if home_team_id and away_team_id:
                opponent_team_id = away_team_id
                opponent_name = away_canon

            if opponent_team_id is None:
                opponent_team_id = home_team_id
                opponent_name = home_canon

            if opponent_team_id is None:
                log.warning(f"Could not resolve opponent team_id for {player_name}")
                continue

            if opponent_team_id not in matchup_cache:
                matchup_cache[opponent_team_id] = stats.get_matchup_defense(opponent_team_id)
            matchup = matchup_cache[opponent_team_id]

            true_prob = ev.estimate_true_probability(
                pstats, line, direction, matchup, market_key,
                playoff_history=playoff_history_cache.get(player_id),
            )

            ev_percent = ev.calculate_ev(true_prob, odd_decimal)
            kelly = ev.kelly_fraction(true_prob, odd_decimal)
            classification = ev.classify_bet(ev_percent, true_prob)
            implied = ev.implied_probability(odd_decimal)

            stat_avg_map = {
                "player_points": pstats.get("avg_pts", 0.0),
                "player_rebounds": pstats.get("avg_reb", 0.0),
                "player_assists": pstats.get("avg_ast", 0.0),
                "player_threes": pstats.get("avg_3pm", 0.0),
                "player_blocks": pstats.get("avg_blk", 0.0),
                "player_steals": pstats.get("avg_stl", 0.0),
                "player_points_rebounds_assists": pstats.get("avg_pra", 0.0),
                "player_points_rebounds": pstats.get("avg_pr", 0.0),
                "player_points_assists": pstats.get("avg_pa", 0.0),
                "player_rebounds_assists": pstats.get("avg_ra", 0.0),
                "player_blocks_steals": pstats.get("avg_stocks", 0.0),
            }
            stat_col_map = {
                "player_points": "PTS",
                "player_rebounds": "REB",
                "player_assists": "AST",
                "player_threes": "FG3M",
                "player_blocks": "BLK",
                "player_steals": "STL",
                "player_points_rebounds_assists": "PRA",
                "player_points_rebounds": "PR",
                "player_points_assists": "PA",
                "player_rebounds_assists": "RA",
                "player_blocks_steals": "STOCKS",
            }

            entries.append({
                "player": player_name,
                "team": "",
                "opponent": _team_abbr(opponent_name),
                "game_time": _format_game_time(m["commence_time"]),
                "market": config.MARKET_LABELS.get(market_key, market_key),
                "market_key": market_key,
                "line": line,
                "direction": direction,
                "odd_decimal": round(odd_decimal, 3),
                "odd_implied_prob": round(implied, 4),
                "true_probability": round(true_prob, 4),
                "ev_percent": round(ev_percent, 2),
                "kelly_fraction": round(kelly, 4),
                "classification": classification,
                "avg_stat_last10": round(stat_avg_map.get(market_key, 0.0), 2),
                "games_over_line_pct": round(
                    stats.games_over_line(pstats, line, stat_col_map.get(market_key, "PTS")), 3
                ),
                "def_rating_opponent": round(matchup.get("def_rating", 0.0), 2),
                "pace": round(matchup.get("pace", 0.0), 2),
                "minutes_avg": round(pstats.get("minutes_avg", 0.0), 1),
                "bookmaker": bookmaker,
            })

    entries.sort(key=lambda e: e["ev_percent"], reverse=True)
    _save_partial(entries)
    return entries


def _save_partial(entries: list[dict]) -> None:
    try:
        os.makedirs(os.path.dirname(PARTIAL_RESULTS_FILE), exist_ok=True)
        with open(PARTIAL_RESULTS_FILE, "w", encoding="utf-8") as f:
            json.dump({
                "saved_at": datetime.now().isoformat(),
                "entries": entries,
            }, f, ensure_ascii=False, indent=2)
    except Exception as e:
        log.warning(f"could not save partial results: {e}")
