import json
import os
from typing import Optional

import questionary
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.text import Text
from rich import box

import config
import stats as stats_mod
from scout import analyze_day, PARTIAL_RESULTS_FILE
from report import print_report, export_json

console = Console()

_MARKET_CHOICES = [
    ("Todos", "all"),
    ("Pontos", "points"),
    ("Rebotes", "rebounds"),
    ("Assistências", "assists"),
    ("3 Pontos", "threes"),
    ("Bloqueios", "blocks"),
    ("Roubos", "steals"),
    ("PRA  (Pts+Reb+Ast)", "pra"),
    ("Pts+Reb", "pr"),
    ("Pts+Ast", "pa"),
    ("Reb+Ast", "ra"),
    ("Blk+Stl  (Stocks)", "stocks"),
]

_MARKET_TO_LABEL = {
    "points":   config.MARKET_LABELS.get("player_points",  "Pontos"),
    "rebounds": config.MARKET_LABELS.get("player_rebounds", "Rebotes"),
    "assists":  config.MARKET_LABELS.get("player_assists",  "Assistências"),
    "threes":   config.MARKET_LABELS.get("player_threes",   "3 Pontos"),
    "blocks":   config.MARKET_LABELS.get("player_blocks",   "Bloqueios"),
    "steals":   config.MARKET_LABELS.get("player_steals",   "Roubos"),
    "pra":      config.MARKET_LABELS.get("player_points_rebounds_assists", "PRA"),
    "pr":       config.MARKET_LABELS.get("player_points_rebounds",  "Pts+Reb"),
    "pa":       config.MARKET_LABELS.get("player_points_assists",   "Pts+Ast"),
    "ra":       config.MARKET_LABELS.get("player_rebounds_assists", "Reb+Ast"),
    "stocks":   config.MARKET_LABELS.get("player_blocks_steals",    "Blk+Stl"),
}


def _load_partial() -> list[dict]:
    try:
        if os.path.isfile(PARTIAL_RESULTS_FILE):
            with open(PARTIAL_RESULTS_FILE, encoding="utf-8") as f:
                return json.load(f).get("entries", [])
    except Exception:
        pass
    return []


def _safe_num(v, fmt: str = ".0f") -> str:
    try:
        return format(float(v), fmt)
    except Exception:
        return "0"


def _show_player(player_name: str) -> None:
    console.print(f"[cyan]Buscando {player_name}...[/]")
    pid = stats_mod.get_player_id(player_name)
    if not pid:
        console.print(f"[red]Jogador '{player_name}' não encontrado.[/]")
        return

    pstats = stats_mod.get_player_recent_stats(pid, config.LOOKBACK_GAMES)
    n = pstats.get("games_played", 0)
    if n == 0:
        console.print("[yellow]Nenhuma estatística encontrada.[/]")
        return

    in_playoffs = pstats.get("is_playoffs", False)
    po_games = pstats.get("playoff_games", 0)
    season_label = f"[bold magenta]PLAYOFFS ({po_games} jogos)[/]" if in_playoffs else "Temporada regular"

    summary = Text()
    summary.append(f"{player_name}  —  últimos {n} jogos  ", style="bold cyan")
    summary.append(f"({season_label})\n")
    summary.append(
        f"PTS {pstats['avg_pts']:.1f}   "
        f"REB {pstats['avg_reb']:.1f}   "
        f"AST {pstats['avg_ast']:.1f}   "
        f"3PM {pstats['avg_3pm']:.1f}   "
        f"BLK {pstats.get('avg_blk', 0):.1f}   "
        f"STL {pstats.get('avg_stl', 0):.1f}   "
        f"MIN {pstats['minutes_avg']:.0f}\n"
    )
    summary.append(
        f"PRA {pstats.get('avg_pra', 0):.1f}   "
        f"P+R {pstats.get('avg_pr', 0):.1f}   "
        f"P+A {pstats.get('avg_pa', 0):.1f}   "
        f"R+A {pstats.get('avg_ra', 0):.1f}   "
        f"Blk+Stl {pstats.get('avg_stocks', 0):.1f}",
        style="dim",
    )
    console.print(Panel(summary, border_style="cyan"))

    # Historical playoff stats
    ph = stats_mod.get_player_playoff_history(pid)
    if ph.get("games", 0) >= 3:
        ph_text = Text()
        ph_text.append(
            f"Hist. playoffs ({ph['games']}j): "
            f"PTS {ph['avg_pts']:.1f}  "
            f"REB {ph['avg_reb']:.1f}  "
            f"AST {ph['avg_ast']:.1f}  "
            f"3PM {ph['avg_3pm']:.1f}  "
            f"BLK {ph['avg_blk']:.1f}  "
            f"STL {ph['avg_stl']:.1f}",
            style="dim magenta",
        )
        console.print(ph_text)

    df = pstats.get("df")
    if df is not None and not df.empty:
        tbl = Table(title="Histórico recente", box=box.SIMPLE, header_style="bold cyan",
                    show_lines=False)
        display_cols = [
            ("Data",  "Date",  "left"),
            ("MIN",   "MIN",   "right"),
            ("PTS",   "PTS",   "right"),
            ("REB",   "REB",   "right"),
            ("AST",   "AST",   "right"),
            ("3PM",   "FG3M",  "right"),
            ("BLK",   "BLK",   "right"),
            ("STL",   "STL",   "right"),
        ]
        present = [(hdr, col, just) for hdr, col, just in display_cols
                   if col in df.columns or col == "Date"]
        for hdr, _, just in present:
            tbl.add_column(hdr, justify=just)

        for i, (_, row) in enumerate(df.iterrows()):
            is_po = row.get("IsPlayoff", False)
            vals = []
            for _, col, _ in present:
                if col == "Date":
                    date_str = str(row.get("Date") or f"G{i+1}")
                    vals.append(f"[magenta]{date_str}[/]" if is_po else date_str)
                else:
                    vals.append(_safe_num(row.get(col, 0)))
            tbl.add_row(*vals)
        console.print(tbl)
        if in_playoffs:
            console.print("[dim magenta]Datas em roxo = jogo de playoffs[/]")

    # Props from cache
    cached = _load_partial()
    norm = player_name.lower()
    props = [e for e in cached
             if norm in e["player"].lower() or e["player"].lower() in norm]
    if props:
        console.print()
        pt = Table(title="Props hoje (último cache)", box=box.SIMPLE, header_style="bold cyan")
        pt.add_column("Mercado")
        pt.add_column("Vs", style="dim")
        pt.add_column("Linha", justify="right")
        pt.add_column("Direção", justify="center")
        pt.add_column("Odd", justify="right")
        pt.add_column("EV%", justify="right")
        pt.add_column("Prob Real", justify="right")
        pt.add_column("Rating", justify="center")
        for e in props:
            c = "bold green" if e["ev_percent"] >= 8 else (
                "green" if e["ev_percent"] >= 3 else (
                "yellow" if e["ev_percent"] > 0 else "red"))
            dir_style = "green" if e["direction"] == "over" else "magenta"
            pt.add_row(
                e["market"],
                e.get("opponent", ""),
                f"{e['line']:.1f}",
                f"[{dir_style}]{e['direction'].upper()}[/]",
                f"{e['odd_decimal']:.2f}",
                f"[{c}]{e['ev_percent']:+.2f}%[/]",
                f"{e['true_probability'] * 100:.1f}%",
                e["classification"].upper(),
            )
        console.print(pt)
    else:
        console.print("[dim]Nenhuma prop no cache para este jogador. "
                      "Rode 'Analisar o dia' primeiro.[/]")


def _pick_market() -> str:
    ans = questionary.select(
        "Mercado:",
        choices=[questionary.Choice(label, value=val) for label, val in _MARKET_CHOICES],
    ).ask()
    return ans or "all"


def _filter_entries(entries: list[dict], market: str, min_ev: float,
                    only_strong: bool) -> list[dict]:
    if market != "all":
        label = _MARKET_TO_LABEL[market]
        entries = [e for e in entries if e["market"] == label]
    if only_strong:
        entries = [e for e in entries if e["classification"] == "strong"]
    return [e for e in entries if e["ev_percent"] >= min_ev]


def _show_available_markets(entries: list[dict]) -> None:
    if not entries:
        return
    available = sorted({e["market"] for e in entries})
    console.print(f"[dim]Mercados disponíveis hoje: {', '.join(available)}[/]")


def _ask_filters() -> tuple[str, float, bool]:
    market = _pick_market()
    min_ev_str = questionary.text("EV mínimo % (padrão 3.0):", default="3.0").ask()
    try:
        min_ev = float(min_ev_str or "3.0")
    except ValueError:
        min_ev = 3.0
    only_strong = (
        questionary.confirm("Apenas strong bets (EV >= 8%)?", default=False).ask() or False
    )
    return market, min_ev, only_strong


def _run_analysis(session_entries: list[dict]) -> list[dict]:
    """Fetch or re-use cached analysis, then filter."""
    if session_entries:
        reuse = questionary.confirm(
            f"Já há {len(session_entries)} entradas desta sessão. "
            "Reutilizar sem nova chamada à API?",
            default=True,
        ).ask()
        if reuse:
            _show_available_markets(session_entries)
            market, min_ev, only_strong = _ask_filters()
            result = _filter_entries(session_entries, market, min_ev, only_strong)
            print_report(result)
            return session_entries  # keep original for future re-use

    console.print("[cyan]Analisando... pode levar alguns minutos.[/]")
    try:
        raw = analyze_day()
    except KeyboardInterrupt:
        console.print("[yellow]Análise interrompida.[/]")
        return session_entries
    except Exception as e:
        console.print(f"[red]Erro durante análise: {e}[/]")
        return session_entries

    if not raw:
        console.print("[yellow]Nenhuma prop disponível para hoje.[/]")
        return session_entries

    _show_available_markets(raw)
    market, min_ev, only_strong = _ask_filters()

    result = _filter_entries(raw, market, min_ev, only_strong)
    if not result and market != "all":
        label = _MARKET_TO_LABEL.get(market, market)
        console.print(
            f"[yellow]Nenhuma entrada para '{label}'. "
            f"Esse mercado pode não estar disponível hoje nas casas consultadas.[/]"
        )
    print_report(result)
    return raw


def _view_saved() -> None:
    entries = _load_partial()
    if not entries:
        console.print("[yellow]Nenhum resultado salvo. Rode 'Analisar o dia' primeiro.[/]")
        return

    _show_available_markets(entries)
    market, min_ev, only_strong = _ask_filters()
    result = _filter_entries(entries, market, min_ev, only_strong)
    print_report(result)


def run_interactive() -> None:
    console.print(Panel(
        Text("NBA Scout  —  Modo Interativo", style="bold cyan"),
        subtitle="Ctrl+C para sair a qualquer momento",
        border_style="cyan",
    ))

    session_entries: list[dict] = []

    while True:
        try:
            choices = [
                questionary.Choice("Analisar o dia (props ao vivo)", value="analyze"),
                questionary.Choice("Buscar por jogador", value="player"),
                questionary.Choice("Ver resultados salvos (cache)", value="saved"),
            ]
            if session_entries:
                choices.append(
                    questionary.Choice(
                        f"Exportar resultado da sessão ({len(session_entries)} entradas) → JSON",
                        value="export",
                    )
                )
            choices.append(questionary.Choice("Sair", value="exit"))

            action = questionary.select("O que deseja fazer?", choices=choices).ask()

            if action is None or action == "exit":
                console.print("[dim]Até logo![/]")
                break
            elif action == "analyze":
                session_entries = _run_analysis(session_entries)
            elif action == "player":
                name = questionary.text("Nome do jogador:").ask()
                if name and name.strip():
                    _show_player(name.strip())
            elif action == "saved":
                _view_saved()
            elif action == "export":
                export_json(session_entries)

            if action not in ("exit", None):
                console.print()
                input("  [Enter para continuar]")
                console.print()

        except KeyboardInterrupt:
            console.print("\n[dim]Até logo![/]")
            break
