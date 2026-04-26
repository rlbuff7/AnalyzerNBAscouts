import json
import logging
import os
import re
import time
import unicodedata
from typing import Optional

import requests
import pandas as pd  # type: ignore

from nba_api.live.nba.endpoints import scoreboard  # type: ignore
from nba_api.stats.static import teams  # type: ignore

import config

log = logging.getLogger(__name__)

ESPN_BASE_SITE = "https://site.api.espn.com/apis/site/v2/sports/basketball/nba"
ESPN_BASE_WEB = "https://site.web.api.espn.com/apis/common/v3/sports/basketball/nba"
ESPN_BASE_CORE = "https://sports.core.api.espn.com/v3/sports/basketball/nba"
ESPN_TEAM_STATS = ("https://sports.core.api.espn.com/v2/sports/basketball/leagues/nba/"
                   "seasons/{season}/types/2/teams/{team}/statistics")

HEADERS = {
    "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                   "AppleWebKit/537.36 (KHTML, like Gecko) "
                   "Chrome/120.0.0.0 Safari/537.36"),
    "Accept": "application/json",
}

CACHE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".cache")
PLAYER_INDEX_CACHE = os.path.join(CACHE_DIR, "player_index.json")
TEAM_STATS_CACHE = os.path.join(CACHE_DIR, "team_stats.json")
CACHE_TTL_SECONDS = 24 * 60 * 60

_session = requests.Session()
_session.headers.update(HEADERS)

_player_index: dict = {}
_player_index_loaded = False
_team_stats_cache: dict = {}
_league_stats_loaded = False
_team_id_to_name: dict = {}
_nba_to_espn_team: dict = {}


def stats_endpoint_blocked() -> bool:
    return False


def _ensure_cache_dir() -> None:
    try:
        os.makedirs(CACHE_DIR, exist_ok=True)
    except Exception as e:
        log.warning(f"could not create cache dir: {e}")


def _read_cache(path: str) -> Optional[dict]:
    try:
        if not os.path.isfile(path):
            return None
        if time.time() - os.path.getmtime(path) > CACHE_TTL_SECONDS:
            return None
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        log.warning(f"cache read failed for {path}: {e}")
        return None


def _write_cache(path: str, data: dict) -> None:
    _ensure_cache_dir()
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False)
    except Exception as e:
        log.warning(f"cache write failed for {path}: {e}")


def _espn_get(url: str, retries: int = 3) -> Optional[dict]:
    delay = 1.5
    for attempt in range(retries):
        try:
            r = _session.get(url, timeout=20)
            if r.status_code == 200:
                return r.json()
            if r.status_code == 429:
                log.warning(f"ESPN 429, backing off {delay}s")
                time.sleep(delay)
                delay *= 2
                continue
            log.warning(f"ESPN HTTP {r.status_code} for {url}")
            return None
        except Exception as e:
            log.warning(f"ESPN request failed (attempt {attempt + 1}): {e}")
            time.sleep(delay)
            delay *= 2
    return None


def _normalize_name(name: str) -> str:
    if not name:
        return ""
    decomposed = unicodedata.normalize("NFKD", name)
    name = "".join(c for c in decomposed if not unicodedata.combining(c))
    name = re.sub(r"[\.\,\'\-]", "", name)
    name = re.sub(r"\s+(jr|sr|ii|iii|iv)\.?$", "", name, flags=re.IGNORECASE)
    return "".join(c.lower() for c in name if c.isalnum())


def _espn_season_year() -> int:
    return int(config.NBA_SEASON.split("-")[0]) + 1


def get_todays_games() -> list[dict]:
    try:
        sb = scoreboard.ScoreBoard()
        data = sb.get_dict()
    except Exception as e:
        log.error(f"Failed to fetch today's games: {e}")
        return []

    games_raw = data.get("scoreboard", {}).get("games", [])
    out = []
    for g in games_raw:
        try:
            home = g.get("homeTeam", {})
            away = g.get("awayTeam", {})
            out.append({
                "game_id": g.get("gameId"),
                "home_team": f"{home.get('teamCity', '')} {home.get('teamName', '')}".strip(),
                "away_team": f"{away.get('teamCity', '')} {away.get('teamName', '')}".strip(),
                "game_time_et": g.get("gameTimeUTC", ""),
                "home_team_id": home.get("teamId"),
                "away_team_id": away.get("teamId"),
                "home_team_tricode": home.get("teamTricode"),
                "away_team_tricode": away.get("teamTricode"),
            })
        except Exception as e:
            log.warning(f"Skipping malformed game entry: {e}")
    return out


def _load_player_index() -> None:
    global _player_index_loaded, _player_index
    if _player_index_loaded:
        return

    cached = _read_cache(PLAYER_INDEX_CACHE)
    if cached:
        _player_index.update(cached)
        log.info(f"loaded {len(_player_index)} players from cache")
        _player_index_loaded = True
        return

    url = f"{ESPN_BASE_CORE}/athletes?limit=2000&active=true"
    data = _espn_get(url)
    if not data:
        log.warning("could not load ESPN player index")
        _player_index_loaded = True
        return

    items = data.get("items", [])
    count = 0
    for p in items:
        if not isinstance(p, dict):
            continue
        pid = p.get("id")
        name = p.get("displayName") or p.get("fullName") or ""
        if not pid or not name:
            continue
        norm = _normalize_name(name)
        if norm and norm not in _player_index:
            _player_index[norm] = str(pid)
            count += 1

    log.info(f"loaded {count} active players from ESPN")
    if count > 0:
        _write_cache(PLAYER_INDEX_CACHE, _player_index)
    _player_index_loaded = True


def get_player_id(player_name: str) -> Optional[str]:
    if not player_name:
        return None
    _load_player_index()

    norm = _normalize_name(player_name)
    if norm in _player_index:
        return _player_index[norm]

    for indexed_norm, pid in _player_index.items():
        if norm and (norm in indexed_norm or indexed_norm in norm):
            if abs(len(norm) - len(indexed_norm)) <= 4:
                return pid

    log.info(f"player not found on ESPN: {player_name}")
    return None


def _parse_made_attempted(val: str) -> int:
    if not isinstance(val, str):
        return 0
    m = re.match(r"^\s*(\d+)\s*-\s*(\d+)\s*$", val)
    if m:
        return int(m.group(1))
    try:
        return int(float(val))
    except Exception:
        return 0


def _parse_event_date(ev: dict) -> str:
    """Try multiple ESPN API field names for game date."""
    for key in ("gameDate", "date", "eventDate"):
        v = ev.get(key)
        if v and isinstance(v, str) and len(v) >= 8:
            return v[:10]  # keep YYYY-MM-DD
    # fallback: extract from $ref URL if present (e.g. .../events/401741897/...)
    ref = ev.get("$ref", "")
    if ref:
        import re as _re
        m = _re.search(r"/events/(\d{9,})", ref)
        if m:
            return m.group(1)  # game ID as proxy for ordering
    return ""


def _parse_game_rows(data: dict, labels: list,
                     pts_i, reb_i, ast_i, three_i, min_i, blk_i, stl_i,
                     playoff_only: bool = False) -> tuple[list, list]:
    """Return (regular_rows, playoff_rows) parsed from ESPN gamelog data."""
    regular_rows: list = []
    playoff_rows: list = []

    for st in data.get("seasonTypes", []):
        display = str(st.get("displayName", ""))
        is_playoffs_type = any(x in display for x in ("Playoff", "Post Season", "Postseason"))
        is_regular = "Regular Season" in display

        if not is_regular and not is_playoffs_type:
            continue
        if playoff_only and not is_playoffs_type:
            continue

        for cat in st.get("categories", []):
            if cat.get("type") != "event":
                continue
            for ev in cat.get("events", []):
                stats_arr = ev.get("stats")
                if not stats_arr or len(stats_arr) < len(labels):
                    continue
                row = {
                    "PTS": _safe_int(stats_arr[pts_i]) if pts_i is not None else 0,
                    "REB": _safe_int(stats_arr[reb_i]) if reb_i is not None else 0,
                    "AST": _safe_int(stats_arr[ast_i]) if ast_i is not None else 0,
                    "FG3M": (_parse_made_attempted(stats_arr[three_i])
                             if three_i is not None else 0),
                    "BLK": _safe_int(stats_arr[blk_i]) if blk_i is not None else 0,
                    "STL": _safe_int(stats_arr[stl_i]) if stl_i is not None else 0,
                    "MIN": _safe_float(stats_arr[min_i]) if min_i is not None else 0.0,
                    "Date": _parse_event_date(ev),
                    "IsPlayoff": is_playoffs_type,
                }
                if is_playoffs_type:
                    playoff_rows.append(row)
                else:
                    regular_rows.append(row)

    return regular_rows, playoff_rows


_COMBO_DEFS = [
    ("PRA",    ["PTS", "REB", "AST"]),
    ("PR",     ["PTS", "REB"]),
    ("PA",     ["PTS", "AST"]),
    ("RA",     ["REB", "AST"]),
    ("STOCKS", ["BLK", "STL"]),
]


def _add_combo_cols(df: "pd.DataFrame") -> None:
    for combo, src_cols in _COMBO_DEFS:
        if all(c in df.columns for c in src_cols):
            numeric = df[src_cols].apply(pd.to_numeric, errors="coerce").fillna(0)
            df[combo] = numeric.sum(axis=1)


def get_player_recent_stats(player_id, n_games: int = 10) -> dict:
    empty = {
        "avg_pts": 0.0, "avg_reb": 0.0, "avg_ast": 0.0, "avg_3pm": 0.0,
        "avg_blk": 0.0, "avg_stl": 0.0,
        "avg_pra": 0.0, "avg_pr": 0.0, "avg_pa": 0.0,
        "avg_ra": 0.0, "avg_stocks": 0.0,
        "std_pts": 0.0, "std_reb": 0.0, "std_ast": 0.0,
        "last_5_pts": [],
        "minutes_avg": 0.0,
        "games_played": 0,
        "df": None,
        "is_playoffs": False,
        "playoff_games": 0,
    }
    if not player_id:
        return empty

    url = f"{ESPN_BASE_WEB}/athletes/{player_id}/gamelog"
    data = _espn_get(url)
    if not data:
        return empty

    labels = data.get("labels", [])
    if not labels:
        return empty

    def _idx(label: str) -> Optional[int]:
        try:
            return labels.index(label)
        except ValueError:
            return None

    pts_i = _idx("PTS")
    reb_i = _idx("REB")
    ast_i = _idx("AST")
    three_i = _idx("3PT")
    min_i = _idx("MIN")
    blk_i = _idx("BLK")
    stl_i = _idx("STL")

    regular_rows, playoff_rows = _parse_game_rows(
        data, labels, pts_i, reb_i, ast_i, three_i, min_i, blk_i, stl_i
    )

    if not regular_rows and not playoff_rows:
        return empty

    regular_rows.sort(key=lambda r: r.get("Date", "") or "")
    playoff_rows.sort(key=lambda r: r.get("Date", "") or "")
    in_playoffs = len(playoff_rows) > 0

    # Prioritise playoff games: take all playoff games + fill with recent regular season
    if in_playoffs:
        fill = max(0, n_games - len(playoff_rows))
        combined = regular_rows[-fill:] + playoff_rows if fill > 0 else playoff_rows[-n_games:]
        rows = sorted(combined, key=lambda r: r.get("Date", "") or "")
    else:
        rows = regular_rows

    rows = rows[-n_games:]

    # Number rows that have no date so they display as G1, G2...
    has_dates = any(r.get("Date") for r in rows)
    if not has_dates:
        for i, r in enumerate(rows):
            r["Date"] = f"G{i + 1}"

    df = pd.DataFrame(rows)
    _add_combo_cols(df)

    def _mean(col: str) -> float:
        if col not in df.columns:
            return 0.0
        s = pd.to_numeric(df[col], errors="coerce").dropna()
        return float(s.mean()) if not s.empty else 0.0

    def _std(col: str) -> float:
        if col not in df.columns:
            return 0.0
        s = pd.to_numeric(df[col], errors="coerce").dropna()
        return float(s.std()) if len(s) > 1 else 0.0

    last5_pts = (pd.to_numeric(df["PTS"], errors="coerce")
                 .dropna().tail(5).tolist()) if "PTS" in df.columns else []

    return {
        "avg_pts": _mean("PTS"),
        "avg_reb": _mean("REB"),
        "avg_ast": _mean("AST"),
        "avg_3pm": _mean("FG3M"),
        "avg_blk": _mean("BLK"),
        "avg_stl": _mean("STL"),
        "avg_pra": _mean("PRA"),
        "avg_pr": _mean("PR"),
        "avg_pa": _mean("PA"),
        "avg_ra": _mean("RA"),
        "avg_stocks": _mean("STOCKS"),
        "std_pts": _std("PTS"),
        "std_reb": _std("REB"),
        "std_ast": _std("AST"),
        "last_5_pts": last5_pts,
        "minutes_avg": _mean("MIN"),
        "games_played": len(df),
        "df": df,
        "is_playoffs": in_playoffs,
        "playoff_games": len(playoff_rows),
    }


def get_player_playoff_history(player_id, n_seasons: int = 2) -> dict:
    """Return avg playoff stats for player over the last n_seasons previous seasons."""
    empty = {"avg_pts": 0.0, "avg_reb": 0.0, "avg_ast": 0.0, "avg_3pm": 0.0,
             "avg_blk": 0.0, "avg_stl": 0.0,
             "avg_pra": 0.0, "avg_pr": 0.0, "avg_pa": 0.0,
             "avg_ra": 0.0, "avg_stocks": 0.0, "games": 0}
    if not player_id:
        return empty

    current_year = _espn_season_year()
    all_rows: list = []

    for offset in range(1, n_seasons + 1):
        year = current_year - offset
        cache_path = os.path.join(CACHE_DIR, f"po_hist_{player_id}_{year}.json")
        cached = _read_cache(cache_path)
        if cached is not None:
            all_rows.extend(cached.get("rows", []))
            continue

        url = f"{ESPN_BASE_WEB}/athletes/{player_id}/gamelog?season={year}"
        data = _espn_get(url)
        if not data:
            _write_cache(cache_path, {"rows": []})
            continue

        labels = data.get("labels", [])
        if not labels:
            _write_cache(cache_path, {"rows": []})
            continue

        def _idx(lbl: str) -> Optional[int]:
            try:
                return labels.index(lbl)
            except ValueError:
                return None

        pts_i = _idx("PTS"); reb_i = _idx("REB"); ast_i = _idx("AST")
        three_i = _idx("3PT"); blk_i = _idx("BLK"); stl_i = _idx("STL")
        min_i = _idx("MIN")

        _, po_rows = _parse_game_rows(
            data, labels, pts_i, reb_i, ast_i, three_i, min_i, blk_i, stl_i,
            playoff_only=True,
        )
        _write_cache(cache_path, {"rows": po_rows})
        all_rows.extend(po_rows)

    if not all_rows:
        return empty

    pdf = pd.DataFrame(all_rows)
    _add_combo_cols(pdf)

    def _avg(col: str) -> float:
        if col not in pdf.columns:
            return 0.0
        s = pd.to_numeric(pdf[col], errors="coerce").dropna()
        return float(s.mean()) if not s.empty else 0.0

    return {
        "avg_pts": _avg("PTS"),
        "avg_reb": _avg("REB"),
        "avg_ast": _avg("AST"),
        "avg_3pm": _avg("FG3M"),
        "avg_blk": _avg("BLK"),
        "avg_stl": _avg("STL"),
        "avg_pra": _avg("PRA"),
        "avg_pr": _avg("PR"),
        "avg_pa": _avg("PA"),
        "avg_ra": _avg("RA"),
        "avg_stocks": _avg("STOCKS"),
        "games": len(all_rows),
    }


def _safe_int(v) -> int:
    try:
        return int(float(v))
    except Exception:
        return 0


def _safe_float(v) -> float:
    try:
        return float(v)
    except Exception:
        return 0.0


def games_over_line(player_stats: dict, line: float, stat_key: str) -> float:
    df = player_stats.get("df")
    if df is None or df.empty or stat_key not in df.columns:
        return 0.0
    series = pd.to_numeric(df[stat_key], errors="coerce").dropna()
    if series.empty:
        return 0.0
    over_count = (series > line).sum()
    return float(over_count) / len(series)


def _build_team_id_maps() -> None:
    global _team_id_to_name, _nba_to_espn_team
    if _team_id_to_name and _nba_to_espn_team:
        return

    try:
        for t in teams.get_teams():
            _team_id_to_name[t["id"]] = t["full_name"]
    except Exception as e:
        log.warning(f"failed to load static NBA team data: {e}")

    data = _espn_get(f"{ESPN_BASE_SITE}/teams")
    if not data:
        return

    espn_teams = []
    for sport in data.get("sports", []):
        for league in sport.get("leagues", []):
            for tw in league.get("teams", []):
                t = tw.get("team", {})
                if t:
                    espn_teams.append(t)

    nba_static_by_norm = {}
    try:
        for t in teams.get_teams():
            nba_static_by_norm[_normalize_name(t["full_name"])] = t["id"]
            nba_static_by_norm[_normalize_name(t["nickname"])] = t["id"]
    except Exception:
        pass

    for et in espn_teams:
        name = et.get("displayName", "")
        nick = et.get("name", "")
        norm_full = _normalize_name(name)
        norm_nick = _normalize_name(nick)
        nba_id = nba_static_by_norm.get(norm_full) or nba_static_by_norm.get(norm_nick)
        if nba_id:
            _nba_to_espn_team[nba_id] = str(et.get("id"))


def _load_league_team_stats() -> None:
    global _league_stats_loaded
    if _league_stats_loaded:
        return

    cached = _read_cache(TEAM_STATS_CACHE)
    if cached:
        _team_stats_cache.update(cached)
        log.info(f"loaded team stats for {len(_team_stats_cache)} teams from cache")
        _league_stats_loaded = True
        return

    _build_team_id_maps()

    if not _nba_to_espn_team:
        log.warning("could not build NBA->ESPN team map")
        _league_stats_loaded = True
        return

    season = _espn_season_year()
    pace_values = []
    opp_pts_values = []
    raw_team_data = {}

    standings_url = f"https://site.api.espn.com/apis/v2/sports/basketball/nba/standings?level=3"
    standings = _espn_get(standings_url)
    espn_id_to_opp_pts: dict = {}
    if standings:
        for child in standings.get("children", []):
            for entry in child.get("standings", {}).get("entries", []):
                team = entry.get("team", {})
                espn_tid = str(team.get("id", ""))
                for s in entry.get("stats", []):
                    n = s.get("name", "")
                    if n in ("avgPointsAgainst", "pointsAgainstPerGame", "avgPointsAllowed"):
                        try:
                            espn_id_to_opp_pts[espn_tid] = float(s.get("value", 0) or 0)
                        except Exception:
                            pass

    for nba_id, espn_id in _nba_to_espn_team.items():
        url = ESPN_TEAM_STATS.format(season=season, team=espn_id)
        data = _espn_get(url)
        if not data:
            continue

        pace = config.LEAGUE_AVG_PACE
        for cat in data.get("splits", {}).get("categories", []):
            for s in cat.get("stats", []):
                if s.get("name") == "paceFactor":
                    try:
                        pace = float(s.get("value", config.LEAGUE_AVG_PACE))
                    except Exception:
                        pass

        opp_pts = espn_id_to_opp_pts.get(espn_id, 0.0)

        if pace > 0 and opp_pts > 0:
            def_rating = (opp_pts * 100.0) / pace
        else:
            def_rating = config.LEAGUE_AVG_DEF_RATING

        team_name = _team_id_to_name.get(nba_id, "")
        raw_team_data[team_name] = {
            "def_rating": round(def_rating, 2),
            "pace": round(pace, 2),
            "opp_pts_per_game": round(opp_pts, 2),
        }

        if pace > 0:
            pace_values.append(pace)
        if opp_pts > 0:
            opp_pts_values.append(opp_pts)

    _team_stats_cache.update(raw_team_data)
    log.info(f"loaded team stats for {len(_team_stats_cache)} teams from ESPN")
    if _team_stats_cache:
        _write_cache(TEAM_STATS_CACHE, _team_stats_cache)
    _league_stats_loaded = True


def get_matchup_defense(team_id, position: str = "") -> dict:
    _load_league_team_stats()

    result = {
        "opp_pts_per_game": 0.0,
        "def_rating": config.LEAGUE_AVG_DEF_RATING,
        "pace": config.LEAGUE_AVG_PACE,
        "pts_allowed_to_position": 0.0,
    }

    if isinstance(team_id, str):
        team_name = team_id
    else:
        team_name = _team_id_to_name.get(team_id, "")

    if not team_name:
        return result

    if team_name in _team_stats_cache:
        cached = _team_stats_cache[team_name]
        result.update({
            "def_rating": cached.get("def_rating", config.LEAGUE_AVG_DEF_RATING),
            "pace": cached.get("pace", config.LEAGUE_AVG_PACE),
            "opp_pts_per_game": cached.get("opp_pts_per_game", 0.0),
        })

    return result


def find_team_id_by_name(name: str) -> Optional[int]:
    if not name:
        return None
    try:
        all_teams = teams.get_teams()
    except Exception:
        return None

    norm = name.lower().strip()
    for t in all_teams:
        if t["full_name"].lower() == norm:
            return t["id"]
        if t["nickname"].lower() == norm:
            return t["id"]
        if t["abbreviation"].lower() == norm:
            return t["id"]

    for t in all_teams:
        full = t["full_name"].lower()
        if norm in full or full in norm:
            return t["id"]
    return None


def get_team_roster(team_id: int) -> list[dict]:
    return []


def get_player_position(player_id) -> str:
    return ""
