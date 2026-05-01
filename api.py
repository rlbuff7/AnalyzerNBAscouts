"""
NBA Scout — servidor FastAPI.

Endpoints:
  GET /api/props           → executa scout.analyze_day() e retorna props formatadas
  GET /api/player/{name}   → retorna stats detalhadas do jogador para a página Player

Serve os arquivos estáticos de static/ na raiz (React + Babel).

Instalação das dependências extras:
  pip install fastapi uvicorn[standard]

Uso:
  python api.py
  # ou
  uvicorn api:app --reload --host 127.0.0.1 --port 8000
"""

from __future__ import annotations

import datetime
import json
import logging
import os

from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles

import config
import odds as odds_module
import stats
import scout

log = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

app = FastAPI(title="NBA Scout", version="1.0.0")

STATIC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")


def _format_entry(e: dict) -> dict:
    """Converte uma entrada de scout.analyze_day() para o formato esperado pelo frontend."""
    market_key = e.get("market_key", "")
    stat_code = config.MARKET_TO_STAT.get(market_key, market_key.upper())
    opp = e.get("opponent", "—")
    return {
        "player_name": e["player"],
        "team":        e.get("team", ""),
        "game":        f"vs {opp}",
        "market":      stat_code,
        "line":        e["line"],
        "direction":   e["direction"].upper(),
        "odd":         e["odd_decimal"],
        "prob_real":   e["true_probability"],
        "ev_pct":      round(e["ev_percent"], 2),
        "kelly_pct":   round(e["kelly_fraction"] * 100, 2),
        "rating":      e["classification"].upper(),
        "bookmaker":   e["bookmaker"],
        "games_over_line_pct": e.get("games_over_line_pct", 0.0),
        "all_odds":       e.get("all_odds", []),
        "team_injuries":  e.get("team_injuries", []),
        "dvp_rank":       e.get("dvp_rank", 0),
        "dvp_total":      e.get("dvp_total", 0),
        "line_movement":  e.get("line_movement", 0.0),
        "line_opened":    e.get("line_opened", e["line"]),
        "projected_min":  e.get("projected_min"),
        "min_boost_pct":  e.get("min_boost_pct", 0.0),
    }


_PARTIAL_CACHE = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".cache", "partial_results.json")


def _load_partial_cache() -> tuple[list[dict], str]:
    """Retorna (entries, generated_at) do cache parcial, ou ([], '') se vazio/inexistente."""
    try:
        if os.path.isfile(_PARTIAL_CACHE):
            with open(_PARTIAL_CACHE, "r", encoding="utf-8") as f:
                data = json.load(f)
            entries = data.get("entries", [])
            saved_at = data.get("saved_at", "")
            if entries:
                return entries, saved_at
    except Exception as e:
        log.warning(f"falha ao ler cache parcial: {e}")
    return [], ""


@app.get("/api/props")
def get_props() -> dict:
    """Executa análise do dia e retorna props formatadas para o frontend."""
    from_cache = False
    generated_at = datetime.datetime.now(datetime.timezone.utc).isoformat()

    try:
        entries = scout.analyze_day()
    except Exception as exc:
        log.error(f"/api/props falhou: {exc}", exc_info=True)
        entries = []

    if not entries:
        cached_entries, saved_at = _load_partial_cache()
        if cached_entries:
            log.info(f"Servindo {len(cached_entries)} props do cache parcial (salvo em {saved_at})")
            entries = cached_entries
            from_cache = True
            generated_at = saved_at if saved_at else generated_at

    is_demo = any(e.get("_demo") for e in entries)
    props = [_format_entry(e) for e in entries]

    quota_remaining = odds_module.get_quota_remaining()
    if quota_remaining is None:
        quota_remaining = max(0, 500 - len(props))

    return {
        "props":           props,
        "generated_at":    generated_at,
        "from_cache":      from_cache,
        "demo_mode":       is_demo,
        "quota_remaining": quota_remaining,
        "quota_limit":     500,
    }


@app.get("/api/player/{name:path}")
def get_player(name: str) -> dict:
    """Retorna stats detalhadas do jogador para a página Player do frontend."""
    player_id = stats.get_player_id(name)
    if not player_id:
        raise HTTPException(status_code=404, detail=f"Jogador não encontrado: {name!r}")

    pstats = stats.get_player_recent_stats(player_id)
    phist  = stats.get_player_playoff_history(player_id)

    df = pstats.get("df")
    recent_games: list[dict] = []
    if df is not None and not df.empty:
        for _, row in df.iterrows():
            recent_games.append({
                "date":       str(row.get("Date", "")),
                "opp":        "—",
                "home_away":  str(row.get("HomeAway", "")),
                "min":        int(row.get("MIN",   0) or 0),
                "pts":        int(row.get("PTS",   0) or 0),
                "reb":        int(row.get("REB",   0) or 0),
                "ast":        int(row.get("AST",   0) or 0),
                "fg3m":       int(row.get("FG3M",  0) or 0),
                "blk":        int(row.get("BLK",   0) or 0),
                "stl":        int(row.get("STL",   0) or 0),
                "is_playoff": bool(row.get("IsPlayoff", False)),
                "margin":     int(row.get("Margin", 0) or 0),
                "team_score": int(row.get("TeamScore", 0) or 0),
                "opp_score":  int(row.get("OppScore", 0) or 0),
            })

    # DataFrame é cronológico (mais antigo primeiro); inverte para newest-first
    # O frontend faz .reverse() ao construir sparklines → oldest-first ✓
    recent_games.reverse()

    splits = pstats.get("home_away_splits", {})

    return {
        "id":       player_id,
        "name":     name,
        "team":     "",
        "teamAbbr": "",
        "position": "—",
        "height":   "—",
        "age":      "—",
        "home_away_splits": splits,
        "averages": {
            "PTS":    round(pstats.get("avg_pts",    0), 1),
            "REB":    round(pstats.get("avg_reb",    0), 1),
            "AST":    round(pstats.get("avg_ast",    0), 1),
            "PRA":    round(pstats.get("avg_pra",    0), 1),
            "PR":     round(pstats.get("avg_pr",     0), 1),
            "PA":     round(pstats.get("avg_pa",     0), 1),
            "FG3M":   round(pstats.get("avg_3pm",    0), 1),
            "STOCKS": round(pstats.get("avg_stocks", 0), 1),
        },
        "spark": [g["pts"] for g in reversed(recent_games)],  # oldest-first para sparkline
        "recent_games": recent_games,
        "playoff_history": {
            "seasons":     [],
            "games_count": phist.get("games",    0),
            "avg_pts":     round(phist.get("avg_pts", 0), 1),
            "avg_reb":     round(phist.get("avg_reb", 0), 1),
            "avg_ast":     round(phist.get("avg_ast", 0), 1),
        },
    }


# Arquivos estáticos — deve ficar por último para não interceptar rotas de API
app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="static")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000, reload=False)
