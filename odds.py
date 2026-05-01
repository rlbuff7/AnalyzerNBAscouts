import json
import os
import time
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

import requests

import config

log = logging.getLogger(__name__)

_CACHE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".cache")
_LINE_HISTORY_FILE = os.path.join(_CACHE_DIR, "line_history.json")


def _load_line_history() -> dict:
    try:
        if os.path.isfile(_LINE_HISTORY_FILE):
            with open(_LINE_HISTORY_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception:
        pass
    return {}


def _save_line_history(hist: dict) -> None:
    try:
        os.makedirs(_CACHE_DIR, exist_ok=True)
        with open(_LINE_HISTORY_FILE, "w", encoding="utf-8") as f:
            json.dump(hist, f, ensure_ascii=False)
    except Exception as e:
        log.warning(f"could not save line history: {e}")


_quota_state = {
    "remaining": None,
    "used": None,
}


def get_quota_remaining() -> Optional[int]:
    return _quota_state["remaining"]


def _request_with_retry(url: str, params: dict, retries: int = 3) -> Optional[dict]:
    delay = 2.0
    for attempt in range(retries):
        try:
            r = requests.get(url, params=params, timeout=20)
            remaining = r.headers.get("x-requests-remaining")
            used = r.headers.get("x-requests-used")
            if remaining is not None:
                try:
                    _quota_state["remaining"] = int(remaining)
                except ValueError:
                    pass
            if used is not None:
                try:
                    _quota_state["used"] = int(used)
                except ValueError:
                    pass
            log.info(f"OddsAPI quota: used={used} remaining={remaining}")

            if r.status_code == 401:
                log.warning("Odds API: 401 Unauthorized — chave inválida ou plano sem player props")
                return None  # sem retry
            if r.status_code == 422:
                log.warning(f"Odds API: 422 Unprocessable — parâmetros inválidos")
                return None  # sem retry
            if r.status_code == 429:
                log.warning(f"rate limited (429), backing off {delay}s")
                time.sleep(delay)
                delay *= 2
                continue
            if r.status_code >= 500:
                log.warning(f"server error {r.status_code}, retrying")
                time.sleep(delay)
                delay *= 2
                continue
            r.raise_for_status()
            return r.json()
        except requests.RequestException as e:
            log.warning(f"odds request failed (attempt {attempt + 1}): {e}")
            time.sleep(delay)
            delay *= 2
    return None


def get_todays_events() -> list[dict]:
    if not config.ODDS_API_KEY:
        log.error("ODDS_API_KEY not set")
        return []

    url = f"{config.ODDS_API_BASE}/sports/{config.SPORT}/events"
    params = {
        "apiKey": config.ODDS_API_KEY,
        "dateFormat": "iso",
    }
    data = _request_with_retry(url, params)
    if not data:
        return []

    now = datetime.now(timezone.utc)
    cutoff = now + timedelta(hours=24)
    events = []
    for ev in data:
        try:
            commence = datetime.fromisoformat(ev["commence_time"].replace("Z", "+00:00"))
            if now <= commence <= cutoff:
                events.append({
                    "event_id": ev["id"],
                    "home_team": ev.get("home_team", ""),
                    "away_team": ev.get("away_team", ""),
                    "commence_time": ev["commence_time"],
                })
        except Exception as e:
            log.warning(f"skipping malformed event: {e}")
    return events


def get_props_for_game(event_id: str, markets: Optional[str] = None,
                       bookmakers: Optional[str] = None) -> list[dict]:
    if not config.ODDS_API_KEY:
        log.error("ODDS_API_KEY not set")
        return []

    if _quota_state["remaining"] is not None and _quota_state["remaining"] < 1:
        log.warning(f"quota esgotada ({_quota_state['remaining']} left), skipping prop request")
        return []

    markets = markets or config.MARKETS
    url = f"{config.ODDS_API_BASE}/sports/{config.SPORT}/events/{event_id}/odds"
    params = {
        "apiKey": config.ODDS_API_KEY,
        "regions": config.REGIONS,
        "markets": markets,
        "oddsFormat": "decimal",
    }
    if bookmakers:
        params["bookmakers"] = bookmakers

    data = _request_with_retry(url, params)
    if not data:
        return []

    bookmakers_list = data.get("bookmakers", [])
    if not bookmakers_list:
        return []

    # Coleta odds de TODAS as casas: {(player, market, direction, line): {bookmaker: odd}}
    all_data: dict = {}
    for bm in bookmakers_list:
        bm_key = normalize_bookmaker_name(bm.get("key", ""))
        for market in bm.get("markets", []):
            market_key = market.get("key")
            for oc in market.get("outcomes", []):
                name = oc.get("name", "")
                description = oc.get("description") or oc.get("participant") or ""
                point = oc.get("point")
                price = oc.get("price")
                player_name = description if description else name

                direction = None
                if name.lower() == "over":
                    direction = "over"
                elif name.lower() == "under":
                    direction = "under"
                else:
                    continue

                if point is None or price is None:
                    continue

                k = (player_name, market_key, direction, float(point))
                all_data.setdefault(k, {})[bm_key] = float(price)

    # Line movement: compara com a linha de abertura guardada em cache
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    line_hist = _load_line_history()
    updated = False

    out = []
    for (player_name, market_key, direction, line), bm_odds in all_data.items():
        best_bm = max(bm_odds, key=lambda b: bm_odds[b])
        best_odd = bm_odds[best_bm]
        all_odds_list = sorted(
            [{"bookmaker": b, "odd": o} for b, o in bm_odds.items()],
            key=lambda x: x["odd"], reverse=True,
        )

        hist_key = f"{event_id}|{player_name}|{market_key}|{direction}|{today}"
        if hist_key not in line_hist:
            line_hist[hist_key] = line
            updated = True
        opening_line = line_hist[hist_key]
        line_movement = round(line - opening_line, 1)

        out.append({
            "player_name": player_name,
            "market": market_key,
            "line": line,
            "direction": direction,
            "odd_decimal": best_odd,
            "bookmaker": best_bm,
            "all_odds": all_odds_list,
            "pair": {},
            "line_opened": opening_line,
            "line_movement": line_movement,
        })

    if updated:
        # Limpa entradas de dias anteriores para não crescer indefinidamente
        pruned = {k: v for k, v in line_hist.items() if today in k}
        _save_line_history(pruned)

    return out


def normalize_bookmaker_name(name: str) -> str:
    if not name:
        return ""
    n = name.lower().replace("_", "").replace("-", "").replace(" ", "")
    if "bet365" in n:
        return "bet365"
    if "betfair" in n:
        return "betfair"
    if "pinnacle" in n:
        return "pinnacle"
    if "draftkings" in n:
        return "draftkings"
    if "fanduel" in n:
        return "fanduel"
    if "betonlineag" in n or "betonline" in n:
        return "betonlineag"
    return n
