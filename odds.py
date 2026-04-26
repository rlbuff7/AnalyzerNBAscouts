import time
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

import requests

import config

log = logging.getLogger(__name__)


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

    if _quota_state["remaining"] is not None and _quota_state["remaining"] < 10:
        log.warning(f"quota low ({_quota_state['remaining']} left), skipping prop request")
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

    out = []
    bookmakers_list = data.get("bookmakers", [])

    chosen = None
    if bookmakers_list:
        for preferred in config.BOOKMAKER_PRIORITY:
            for bm in bookmakers_list:
                if normalize_bookmaker_name(bm.get("key", "")) == preferred:
                    chosen = bm
                    break
            if chosen:
                break
        if not chosen:
            chosen = bookmakers_list[0]

    if not chosen:
        return []

    bm_key = normalize_bookmaker_name(chosen.get("key", ""))

    for market in chosen.get("markets", []):
        market_key = market.get("key")
        outcomes = market.get("outcomes", [])
        pairs: dict = {}
        for oc in outcomes:
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

            key = (player_name, point)
            pairs.setdefault(key, {})[direction] = price

        for (player_name, point), sides in pairs.items():
            for direction, odd in sides.items():
                out.append({
                    "player_name": player_name,
                    "market": market_key,
                    "line": float(point),
                    "direction": direction,
                    "odd_decimal": float(odd),
                    "bookmaker": bm_key,
                    "pair": sides,
                })
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
    return n
