"""
Modo demo — gera props sintéticas a partir dos dados reais da ESPN.
Usado automaticamente quando a Odds API não retorna player props (plano gratuito / quota).
"""

import logging
import random

import config
import ev
import stats as stats_module

log = logging.getLogger(__name__)

MAX_PLAYERS_PER_TEAM = 6   # top-N por média de pontos
MIN_GAMES_REQUIRED = 8
MIN_AVG_PTS = 6.0          # descarta reservas irrelevantes
MIN_AVG_MIN = 14.0         # descarta jogadores com poucos minutos (lesionados/G-League)

DEMO_MARKETS = [
    "player_points",
    "player_rebounds",
    "player_assists",
    "player_threes",
    "player_points_rebounds_assists",
]

# Matchup neutro (média da liga) para não distorcer o cálculo de EV no demo
_NEUTRAL_MATCHUP = {
    "def_rating": config.LEAGUE_AVG_DEF_RATING,
    "pace": config.LEAGUE_AVG_PACE,
    "dvp_rank": 15,
    "dvp_total": 30,
}

_AVG_KEY = {
    "player_points":                    "avg_pts",
    "player_rebounds":                  "avg_reb",
    "player_assists":                   "avg_ast",
    "player_threes":                    "avg_3pm",
    "player_points_rebounds_assists":   "avg_pra",
}

_STAT_COL = {
    "player_points":                    "PTS",
    "player_rebounds":                  "REB",
    "player_assists":                   "AST",
    "player_threes":                    "FG3M",
    "player_points_rebounds_assists":   "PRA",
}


def _round_half(value: float) -> float:
    """Arredonda para o 0,5 mais próximo (ex: 24.3 → 24.5, 6.8 → 7.0)."""
    return round(value * 2) / 2


def _synthetic_line(avg: float) -> float:
    """Gera linha sintética próxima da média, com leve desconto para simular bookmaker."""
    factor = random.uniform(0.90, 0.97)
    return _round_half(avg * factor)


def _synthetic_odds() -> float:
    """Gera odd decimal em torno de -110 americano (1.82–2.05)."""
    return round(random.uniform(1.82, 2.05), 2)


def _team_abbr_from_name(name: str) -> str:
    from scout import _team_abbr
    return _team_abbr(name)


def _get_active_players(roster: dict) -> list[tuple[str, dict]]:
    """
    Busca stats de todos os jogadores do roster e retorna apenas os ativos
    (suficientes jogos + minutos mínimos), ordenados por avg_pts desc.
    Jogadores com 404 na ESPN (sem gamelog) são automaticamente descartados.
    """
    candidates: list[tuple[str, dict, float]] = []  # (pid, pstats, avg_pts)

    for pid in roster:
        pstats = stats_module.get_player_recent_stats(pid, n_games=config.LOOKBACK_GAMES)

        if pstats.get("games_played", 0) < MIN_GAMES_REQUIRED:
            continue
        avg_pts = pstats.get("avg_pts", 0.0)
        if avg_pts < MIN_AVG_PTS:
            continue
        avg_min = pstats.get("minutes_avg", 0.0)
        if avg_min < MIN_AVG_MIN:
            continue  # provavelmente lesionado ou com muito pouco tempo de jogo

        candidates.append((pid, pstats, avg_pts))

    # Ordena pelo maior scorers primeiro — garante os titulares no topo
    candidates.sort(key=lambda x: x[2], reverse=True)
    return [(pid, pstats) for pid, pstats, _ in candidates[:MAX_PLAYERS_PER_TEAM]]


def generate_demo_entries(nba_games: list[dict]) -> list[dict]:
    """
    Para cada jogo, busca os principais jogadores de cada time via ESPN
    (filtrados por minutos e pontos médios, ordenados por relevância) e gera
    props sintéticas com EV calculado sobre stats reais.
    Retorna entries no mesmo formato que scout.analyze_day().
    """
    entries: list[dict] = []
    rng = random.Random(42)  # seed fixo para reprodutibilidade no mesmo dia

    for game in nba_games:
        home_name = game.get("home_team", "")
        away_name = game.get("away_team", "")

        for player_team_name, opp_team_name in [
            (home_name, away_name),
            (away_name, home_name),
        ]:
            team_abbr = _team_abbr_from_name(player_team_name)
            opp_abbr  = _team_abbr_from_name(opp_team_name)

            roster = stats_module.get_team_roster(team_abbr)
            if not roster:
                log.warning(f"[demo] sem roster para {team_abbr}")
                continue

            active_players = _get_active_players(roster)
            if not active_players:
                log.warning(f"[demo] nenhum jogador ativo encontrado para {team_abbr}")
                continue

            log.info(f"[demo] {team_abbr}: {len(active_players)} jogadores ativos — "
                     f"{[roster.get(pid, pid) for pid, _ in active_players]}")

            for pid, pstats in active_players:
                player_name = roster.get(pid) or f"Player {pid}"

                for market_key in DEMO_MARKETS:
                    avg_key = _AVG_KEY[market_key]
                    avg_val = pstats.get(avg_key, 0.0)
                    if avg_val < 1.0:
                        continue  # mercado sem relevância para este jogador

                    line      = _synthetic_line(avg_val)
                    odd       = _synthetic_odds()
                    direction = "over"

                    true_prob = ev.estimate_true_probability(
                        pstats, line, direction, _NEUTRAL_MATCHUP, market_key
                    )
                    ev_pct   = ev.calculate_ev(true_prob, odd)
                    kelly    = ev.kelly_fraction(true_prob, odd)
                    classif  = ev.classify_bet(ev_pct, true_prob)
                    hit_rate = stats_module.games_over_line(pstats, line, _STAT_COL[market_key])

                    entries.append({
                        "player":              player_name,
                        "team":                team_abbr,
                        "opponent":            opp_abbr,
                        "game_time":           "",
                        "market":              config.MARKET_LABELS.get(market_key, market_key),
                        "market_key":          market_key,
                        "line":                line,
                        "direction":           direction,
                        "odd_decimal":         odd,
                        "odd_implied_prob":    round(ev.implied_probability(odd), 4),
                        "true_probability":    round(true_prob, 4),
                        "ev_percent":          round(ev_pct, 2),
                        "kelly_fraction":      round(kelly, 4),
                        "classification":      classif,
                        "avg_stat_last10":     round(avg_val, 2),
                        "games_over_line_pct": round(hit_rate, 3),
                        "def_rating_opponent": config.LEAGUE_AVG_DEF_RATING,
                        "pace":                config.LEAGUE_AVG_PACE,
                        "minutes_avg":         round(pstats.get("minutes_avg", 0.0), 1),
                        "bookmaker":           rng.choice(["draftkings", "fanduel", "bet365"]),
                        "all_odds":            [],
                        "team_injuries":       [],
                        "dvp_rank":            15,
                        "dvp_total":           30,
                        "line_movement":       0.0,
                        "line_opened":         line,
                    })

    entries.sort(key=lambda e: e["ev_percent"], reverse=True)
    log.info(f"[demo] geradas {len(entries)} props sintéticas para {len(nba_games)} jogos")
    return entries
