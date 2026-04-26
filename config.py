import os
from dotenv import load_dotenv

load_dotenv()

ODDS_API_KEY = os.getenv("ODDS_API_KEY", "")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")

ODDS_API_BASE = "https://api.the-odds-api.com/v4"
SPORT = "basketball_nba"
REGIONS = "eu"
MARKETS = (
    "player_points,player_rebounds,player_assists,player_threes,"
    "player_blocks,player_steals,"
    "player_points_rebounds_assists,player_points_rebounds,"
    "player_points_assists,player_rebounds_assists,player_blocks_steals"
)

BOOKMAKER_PRIORITY = ["bet365", "betfair", "pinnacle", "draftkings"]

MIN_EV_PERCENT = 3.0
MIN_CONFIDENCE = 0.55
LOOKBACK_GAMES = 10

NBA_API_TIMEOUT = 30


def _current_nba_season() -> str:
    from datetime import date
    today = date.today()
    if today.month >= 10:
        start = today.year
    else:
        start = today.year - 1
    end = (start + 1) % 100
    return f"{start}-{end:02d}"


NBA_SEASON = os.getenv("NBA_SEASON", _current_nba_season())

HTTPS_PROXY = os.getenv("HTTPS_PROXY") or os.getenv("https_proxy")
HTTP_PROXY = os.getenv("HTTP_PROXY") or os.getenv("http_proxy")

LEAGUE_AVG_DEF_RATING = 112.0
LEAGUE_AVG_PACE = 100.0

MARKET_LABELS = {
    "player_points": "Pontos",
    "player_rebounds": "Rebotes",
    "player_assists": "Assistências",
    "player_threes": "3 Pontos",
    "player_blocks": "Bloqueios",
    "player_steals": "Roubos",
    "player_points_rebounds_assists": "PRA",
    "player_points_rebounds": "Pts+Reb",
    "player_points_assists": "Pts+Ast",
    "player_rebounds_assists": "Reb+Ast",
    "player_blocks_steals": "Blk+Stl",
}

MARKET_TO_STAT = {
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

TEAM_NAME_MAP = {
    "Atlanta Hawks": ["Hawks", "ATL"],
    "Boston Celtics": ["Celtics", "BOS"],
    "Brooklyn Nets": ["Nets", "BKN", "BRK"],
    "Charlotte Hornets": ["Hornets", "CHA", "CHO"],
    "Chicago Bulls": ["Bulls", "CHI"],
    "Cleveland Cavaliers": ["Cavaliers", "Cavs", "CLE"],
    "Dallas Mavericks": ["Mavericks", "Mavs", "DAL"],
    "Denver Nuggets": ["Nuggets", "DEN"],
    "Detroit Pistons": ["Pistons", "DET"],
    "Golden State Warriors": ["Warriors", "GSW", "Golden State"],
    "Houston Rockets": ["Rockets", "HOU"],
    "Indiana Pacers": ["Pacers", "IND"],
    "LA Clippers": ["Clippers", "LAC", "Los Angeles Clippers"],
    "Los Angeles Lakers": ["Lakers", "LAL", "LA Lakers"],
    "Memphis Grizzlies": ["Grizzlies", "MEM"],
    "Miami Heat": ["Heat", "MIA"],
    "Milwaukee Bucks": ["Bucks", "MIL"],
    "Minnesota Timberwolves": ["Timberwolves", "Wolves", "MIN"],
    "New Orleans Pelicans": ["Pelicans", "NOP", "NO"],
    "New York Knicks": ["Knicks", "NYK"],
    "Oklahoma City Thunder": ["Thunder", "OKC"],
    "Orlando Magic": ["Magic", "ORL"],
    "Philadelphia 76ers": ["76ers", "Sixers", "PHI"],
    "Phoenix Suns": ["Suns", "PHX", "PHO"],
    "Portland Trail Blazers": ["Trail Blazers", "Blazers", "POR"],
    "Sacramento Kings": ["Kings", "SAC"],
    "San Antonio Spurs": ["Spurs", "SAS", "SA"],
    "Toronto Raptors": ["Raptors", "TOR"],
    "Utah Jazz": ["Jazz", "UTA"],
    "Washington Wizards": ["Wizards", "WAS", "WSH"],
}
