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
                # home/away e margem de placar para contexto de blowout
                ha_raw = ev.get("homeAway", "") or ev.get("atVs", "") or ""
                if ha_raw == "@":
                    ha_raw = "away"
                elif ha_raw == "vs":
                    ha_raw = "home"

                team_score_val = 0
                opp_score_val = 0
                score_str = str(ev.get("score", "") or "")
                score_m = re.match(r"^([WL])\s+(\d+)-(\d+)", score_str.strip())
                if score_m:
                    team_score_val = int(score_m.group(2))
                    opp_score_val = int(score_m.group(3))
                elif ev.get("teamScore") is not None:
                    team_score_val = _safe_int(ev.get("teamScore", 0))
                    opp_score_val = _safe_int(ev.get("opponentScore", 0))

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
                    "HomeAway": ha_raw,
                    "TeamScore": team_score_val,
                    "OppScore": opp_score_val,
                    "Margin": team_score_val - opp_score_val,
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


def get_player_recent_stats(player_id, n_games: int = config.LOOKBACK_GAMES) -> dict:
    empty = {
        "avg_pts": 0.0, "avg_reb": 0.0, "avg_ast": 0.0, "avg_3pm": 0.0,
        "avg_blk": 0.0, "avg_stl": 0.0,
        "avg_pra": 0.0, "avg_pr": 0.0, "avg_pa": 0.0,
        "avg_ra": 0.0, "avg_stocks": 0.0,
        "std_pts": 0.0, "std_reb": 0.0, "std_ast": 0.0,
        "std_3pm": 0.0, "std_blk": 0.0, "std_stl": 0.0,
        "std_pra": 0.0, "std_pr": 0.0, "std_pa": 0.0,
        "std_ra": 0.0, "std_stocks": 0.0,
        "last_5_pts": [],
        "minutes_avg": 0.0,
        "games_played": 0,
        "df": None,
        "is_playoffs": False,
        "playoff_games": 0,
        # Médias da temporada completa — usadas como âncora no cálculo de EV
        "season_avg_pts": 0.0, "season_avg_reb": 0.0, "season_avg_ast": 0.0,
        "season_avg_3pm": 0.0, "season_avg_blk": 0.0, "season_avg_stl": 0.0,
        "season_avg_pra": 0.0, "season_avg_pr": 0.0, "season_avg_pa": 0.0,
        "season_avg_ra": 0.0, "season_avg_stocks": 0.0,
        "season_games": 0,
        "team_abbr": "",
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

    # O endpoint de gamelog retorna team como $ref; usa endpoint de atleta como fallback.
    team_abbr = (data.get("athlete") or {}).get("team", {}).get("abbreviation", "") or ""
    if not team_abbr:
        team_abbr = get_player_team_abbr(str(player_id))

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

    # --- Médias da temporada completa (todos os jogos de regular season, sem filtros) ---
    # Usadas como âncora de longo prazo para evitar over-fit em hot/cold streaks.
    season_df = pd.DataFrame(regular_rows) if regular_rows else pd.DataFrame()
    if not season_df.empty:
        _add_combo_cols(season_df)

    def _season_mean(col: str) -> float:
        if season_df.empty or col not in season_df.columns:
            return 0.0
        s = pd.to_numeric(season_df[col], errors="coerce").dropna()
        return float(s.mean()) if not s.empty else 0.0

    season_avgs = {
        "season_avg_pts":    _season_mean("PTS"),
        "season_avg_reb":    _season_mean("REB"),
        "season_avg_ast":    _season_mean("AST"),
        "season_avg_3pm":    _season_mean("FG3M"),
        "season_avg_blk":    _season_mean("BLK"),
        "season_avg_stl":    _season_mean("STL"),
        "season_avg_pra":    _season_mean("PRA"),
        "season_avg_pr":     _season_mean("PR"),
        "season_avg_pa":     _season_mean("PA"),
        "season_avg_ra":     _season_mean("RA"),
        "season_avg_stocks": _season_mean("STOCKS"),
        "season_games":      len(season_df),
    }

    # --- Filtro de minutos: descarta jogos com MIN < 80% da média da temporada ---
    # Evita que jogos de load management distorçam a frequência histórica.
    season_min_avg = _season_mean("MIN")
    min_threshold = season_min_avg * config.MIN_MINUTES_FRACTION
    if season_min_avg > 0:
        filtered_reg = [r for r in regular_rows if r.get("MIN", 0.0) >= min_threshold]
    else:
        filtered_reg = list(regular_rows)

    # --- Pular tail da regular season (período de load management no fim da temporada) ---
    tail = config.REGULAR_SEASON_SKIP_TAIL
    clean_reg = filtered_reg[:-tail] if len(filtered_reg) > tail else []

    # --- Hierarquia para montar o lookback ---
    # a) Jogos de playoffs da temporada atual (máxima prioridade, todos incluídos)
    lookback = list(playoff_rows)

    # b) Histórico de playoffs anteriores — só se houver dados suficientes
    #    Evita contaminar o lookback com amostras esparsas de playoffs passados.
    if in_playoffs and len(lookback) < n_games:
        prior_rows = _get_prior_playoff_rows(player_id)
        if len(prior_rows) >= config.PLAYOFF_HIST_MIN_GAMES:
            fill = n_games - len(lookback)
            prior_sorted = sorted(prior_rows, key=lambda r: r.get("Date", "") or "")
            lookback = prior_sorted[-fill:] + lookback

    # c) Regular season filtrada (sem low-minute games, sem tail de load management)
    #    Nunca preencher com jogos do tail de regular season.
    if len(lookback) < n_games:
        fill = n_games - len(lookback)
        lookback = clean_reg[-fill:] + lookback

    # Limita ao tamanho do lookback e ordena cronologicamente
    lookback = lookback[-n_games:]
    lookback.sort(key=lambda r: r.get("Date", "") or "")

    # Atribui rótulos sequenciais para jogos sem data
    has_dates = any(r.get("Date") for r in lookback)
    if not has_dates:
        for i, r in enumerate(lookback):
            r["Date"] = f"G{i + 1}"

    df = pd.DataFrame(lookback)
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

    # Home/Away splits
    def _split_mean(col: str, loc: str) -> float:
        if "HomeAway" not in df.columns or col not in df.columns:
            return 0.0
        sub = df[df["HomeAway"] == loc]
        if sub.empty:
            return 0.0
        s = pd.to_numeric(sub[col], errors="coerce").dropna()
        return float(s.mean()) if not s.empty else 0.0

    home_away_splits = {
        "home_games": int((df["HomeAway"] == "home").sum()) if "HomeAway" in df.columns else 0,
        "away_games": int((df["HomeAway"] == "away").sum()) if "HomeAway" in df.columns else 0,
        "home_avg_pts": _split_mean("PTS", "home"),
        "away_avg_pts": _split_mean("PTS", "away"),
        "home_avg_reb": _split_mean("REB", "home"),
        "away_avg_reb": _split_mean("REB", "away"),
        "home_avg_ast": _split_mean("AST", "home"),
        "away_avg_ast": _split_mean("AST", "away"),
        "home_avg_pra": _split_mean("PRA", "home"),
        "away_avg_pra": _split_mean("PRA", "away"),
    }

    result = {
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
        "std_3pm": _std("FG3M"),
        "std_blk": _std("BLK"),
        "std_stl": _std("STL"),
        "std_pra": _std("PRA"),
        "std_pr":  _std("PR"),
        "std_pa":  _std("PA"),
        "std_ra":  _std("RA"),
        "std_stocks": _std("STOCKS"),
        "last_5_pts": last5_pts,
        "minutes_avg": _mean("MIN"),
        "games_played": len(df),
        "df": df,
        "is_playoffs": in_playoffs,
        "playoff_games": len(playoff_rows),
        "team_abbr": team_abbr,
        "home_away_splits": home_away_splits,
    }
    result.update(season_avgs)
    return result


def _get_prior_playoff_rows(player_id, n_seasons: int = 2) -> list:
    """Fetch and cache raw playoff game rows from the last n_seasons prior seasons.

    Shared by get_player_recent_stats (lookback hierarchy) and
    get_player_playoff_history (aggregate averages).
    """
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

    return all_rows


def get_player_playoff_history(player_id, n_seasons: int = 2) -> dict:
    """Return avg playoff stats for player over the last n_seasons previous seasons."""
    empty = {"avg_pts": 0.0, "avg_reb": 0.0, "avg_ast": 0.0, "avg_3pm": 0.0,
             "avg_blk": 0.0, "avg_stl": 0.0,
             "avg_pra": 0.0, "avg_pr": 0.0, "avg_pa": 0.0,
             "avg_ra": 0.0, "avg_stocks": 0.0, "games": 0}
    if not player_id:
        return empty

    all_rows = _get_prior_playoff_rows(player_id, n_seasons)
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
    """Frequência ponderada de jogos em que o jogador superou a linha.

    Usa decay exponencial: jogo mais recente tem peso 1.0, cada jogo anterior
    multiplica por DECAY_FACTOR (0.9^i). Evita que desempenhos antigos pesem
    tanto quanto os recentes no cálculo de probabilidade.
    """
    df = player_stats.get("df")
    if df is None or df.empty or stat_key not in df.columns:
        return 0.0
    # df é ordenado cronologicamente; index 0 = mais antigo, -1 = mais recente
    series = pd.to_numeric(df[stat_key], errors="coerce").dropna().reset_index(drop=True)
    if series.empty:
        return 0.0
    n = len(series)
    # Peso i = DECAY_FACTOR^(n-1-i): índice 0 (mais antigo) → menor peso
    weights = pd.Series([config.DECAY_FACTOR ** (n - 1 - i) for i in range(n)])
    over_flags = (series > line).astype(float)
    total_weight = weights.sum()
    if total_weight == 0:
        return 0.0
    return float((weights * over_flags).sum() / total_weight)


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


def _compute_dvp_ranks() -> dict:
    """Retorna {team_name: rank} onde rank 1 = pior defesa (melhor para atacante), 30 = melhor defesa."""
    if not _team_stats_cache:
        return {}
    teams_with_rating = [
        (name, d.get("def_rating", config.LEAGUE_AVG_DEF_RATING))
        for name, d in _team_stats_cache.items()
        if isinstance(d, dict)
    ]
    # Ordena do pior (maior def_rating = concede mais) para melhor
    teams_with_rating.sort(key=lambda x: x[1], reverse=True)
    return {name: (i + 1) for i, (name, _) in enumerate(teams_with_rating)}


def get_matchup_defense(team_id, position: str = "") -> dict:
    _load_league_team_stats()

    result = {
        "opp_pts_per_game": 0.0,
        "def_rating": config.LEAGUE_AVG_DEF_RATING,
        "pace": config.LEAGUE_AVG_PACE,
        "pts_allowed_to_position": 0.0,
        "dvp_rank": 0,
        "dvp_total": 0,
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
        ranks = _compute_dvp_ranks()
        result["dvp_rank"] = ranks.get(team_name, 0)
        result["dvp_total"] = len(ranks)

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


def get_player_team_abbr(player_id: str) -> str:
    """Retorna a abreviação do time atual do jogador (ex: 'ORL'). Resultado cacheado por 24h."""
    if not player_id:
        return ""
    cache_path = os.path.join(CACHE_DIR, f"player_team_{player_id}.json")
    cached = _read_cache(cache_path)
    if cached is not None:
        return cached.get("abbr", "")

    url = f"{ESPN_BASE_SITE}/athletes/{player_id}"
    data = _espn_get(url)
    abbr = ""
    if data:
        athlete = data.get("athlete") or {}
        abbr = (athlete.get("team") or {}).get("abbreviation", "") or ""

    _write_cache(cache_path, {"abbr": abbr})
    return abbr


INJURY_CACHE_TTL = 60 * 60  # 1h — mais fresco que o cache padrão de 24h


def get_team_injuries(team_abbr: str) -> list[dict]:
    """Retorna lista de {name, status} para jogadores lesionados do time.
    Status: 'Out', 'Questionable', 'Probable', 'Day-To-Day'.
    Cache de 1h."""
    if not team_abbr:
        return []
    cache_path = os.path.join(CACHE_DIR, f"injuries_{team_abbr.upper()}.json")
    # TTL curto: verifica mtime manualmente
    if os.path.isfile(cache_path):
        if time.time() - os.path.getmtime(cache_path) < INJURY_CACHE_TTL:
            try:
                with open(cache_path, "r", encoding="utf-8") as f:
                    return json.load(f).get("injuries", [])
            except Exception:
                pass

    url = f"{ESPN_BASE_SITE}/teams/{team_abbr.lower()}/roster"
    data = _espn_get(url)
    injuries: list[dict] = []
    if data:
        for athlete in (data.get("athletes") or []):
            inj_list = athlete.get("injuries") or []
            if not inj_list:
                continue
            status = inj_list[0].get("status", "") if inj_list else ""
            if not status:
                continue
            name = athlete.get("displayName") or athlete.get("fullName") or ""
            pid = str(athlete.get("id", ""))
            injuries.append({"name": name, "status": status, "player_id": pid})

    try:
        _ensure_cache_dir()
        with open(cache_path, "w", encoding="utf-8") as f:
            json.dump({"injuries": injuries}, f, ensure_ascii=False)
    except Exception as e:
        log.warning(f"could not cache injuries for {team_abbr}: {e}")

    return injuries


def get_team_player_ids(team_abbr: str) -> set:
    """Retorna o conjunto de ESPN player IDs do elenco atual de um time (pela sigla, ex: 'ORL').
    Resultado cacheado por 24h."""
    return set(get_team_roster(team_abbr).keys())


def get_team_roster(team_abbr: str) -> dict:
    """Retorna {player_id: display_name} do elenco atual de um time. Cacheado por 24h."""
    if not team_abbr:
        return {}
    cache_path = os.path.join(CACHE_DIR, f"roster_{team_abbr.upper()}.json")
    cached = _read_cache(cache_path)
    if cached is not None:
        names = cached.get("names", {})
        if names:
            return names
        # Cache antigo só com IDs — converte para o novo formato
        return {str(i): "" for i in cached.get("ids", [])}

    url = f"{ESPN_BASE_SITE}/teams/{team_abbr.lower()}/roster"
    data = _espn_get(url)
    roster: dict = {}
    if data:
        for athlete in (data.get("athletes") or []):
            pid = str(athlete.get("id", ""))
            name = athlete.get("displayName") or athlete.get("fullName") or ""
            if pid:
                roster[pid] = name

    _write_cache(cache_path, {"ids": list(roster.keys()), "names": roster})
    log.info(f"roster {team_abbr.upper()}: {len(roster)} jogadores carregados")
    return roster
