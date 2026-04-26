import config


def implied_probability(odd_decimal: float) -> float:
    if odd_decimal <= 0:
        return 0.0
    return 1.0 / odd_decimal


def remove_vig(over_odd: float, under_odd: float) -> tuple[float, float]:
    if over_odd <= 0 or under_odd <= 0:
        return 0.5, 0.5
    p_over = 1.0 / over_odd
    p_under = 1.0 / under_odd
    total = p_over + p_under
    if total == 0:
        return 0.5, 0.5
    return p_over / total, p_under / total


_STAT_COL = {
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

_AVG_KEY = {
    "PTS": "avg_pts",
    "REB": "avg_reb",
    "AST": "avg_ast",
    "FG3M": "avg_3pm",
    "BLK": "avg_blk",
    "STL": "avg_stl",
    "PRA": "avg_pra",
    "PR": "avg_pr",
    "PA": "avg_pa",
    "RA": "avg_ra",
    "STOCKS": "avg_stocks",
}


def estimate_true_probability(player_stats: dict, line: float, direction: str,
                              matchup: dict, market_key: str,
                              playoff_history: dict | None = None) -> float:
    from stats import games_over_line

    stat_col = _STAT_COL.get(market_key, "PTS")
    avg_key = _AVG_KEY.get(stat_col, "avg_pts")

    # Base: fraction of last-N games the player beat this line
    base = games_over_line(player_stats, line, stat_col)
    avg_stat = player_stats.get(avg_key, 0.0)

    # Fallback when no game matched the line (edge-case: all games same value)
    if avg_stat > 0 and base == 0:
        ratio = avg_stat / line if line > 0 else 1.0
        if ratio >= 1.10:
            base = 0.65
        elif ratio >= 1.0:
            base = 0.55
        elif ratio >= 0.90:
            base = 0.45
        else:
            base = 0.35

    p_over = base

    # Blend with historical playoff averages when in playoffs
    is_playoffs = player_stats.get("is_playoffs", False)
    if is_playoffs and playoff_history and playoff_history.get("games", 0) >= 3:
        hist_avg = playoff_history.get(avg_key, 0.0)
        if hist_avg > 0 and line > 0:
            ratio = hist_avg / line
            if ratio >= 1.10:
                hist_p = 0.68
            elif ratio >= 1.0:
                hist_p = 0.58
            elif ratio >= 0.90:
                hist_p = 0.45
            elif ratio >= 0.80:
                hist_p = 0.37
            else:
                hist_p = 0.28
            # Weight: 35% history, 65% current-season window
            p_over = p_over * 0.65 + hist_p * 0.35

    # Opponent defensive adjustment
    def_rating = matchup.get("def_rating", config.LEAGUE_AVG_DEF_RATING)
    pace = matchup.get("pace", config.LEAGUE_AVG_PACE)

    if def_rating >= config.LEAGUE_AVG_DEF_RATING + 4:
        p_over += 0.04
    elif def_rating >= config.LEAGUE_AVG_DEF_RATING:
        p_over += 0.02
    elif def_rating <= config.LEAGUE_AVG_DEF_RATING - 6:
        p_over -= 0.05
    elif def_rating <= config.LEAGUE_AVG_DEF_RATING - 2:
        p_over -= 0.03

    if pace > 105:
        p_over += 0.03
    elif pace > 102:
        p_over += 0.02
    elif pace < 96:
        p_over -= 0.02

    minutes_avg = player_stats.get("minutes_avg", 0.0)
    if market_key == "player_points" and 0 < minutes_avg < 28:
        p_over -= 0.03

    games_played = player_stats.get("games_played", 0)
    if games_played < 5:
        p_over = (p_over + 0.5) / 2

    p_over = max(0.25, min(0.85, p_over))

    if direction == "over":
        return p_over
    return 1.0 - p_over


def calculate_ev(true_prob: float, odd_decimal: float) -> float:
    if odd_decimal <= 1.0:
        return 0.0
    profit_if_win = odd_decimal - 1.0
    ev = (true_prob * profit_if_win) - (1.0 - true_prob)
    return ev * 100.0


def kelly_fraction(true_prob: float, odd_decimal: float, kelly_divisor: float = 4.0) -> float:
    if odd_decimal <= 1.0 or kelly_divisor <= 0:
        return 0.0
    b = odd_decimal - 1.0
    q = 1.0 - true_prob
    kelly = (true_prob * b - q) / b
    return max(0.0, kelly / kelly_divisor)


def classify_bet(ev_percent: float, true_prob: float) -> str:
    if ev_percent >= 8.0 and true_prob >= 0.60:
        return "strong"
    if ev_percent >= 3.0:
        return "value"
    if ev_percent >= -1.0:
        return "neutral"
    return "avoid"
