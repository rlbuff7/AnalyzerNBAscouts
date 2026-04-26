import json
from datetime import datetime

from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.text import Text
from rich import box

import odds

console = Console()


def _ev_color(ev_percent: float) -> str:
    if ev_percent >= 8.0:
        return "bold green"
    if ev_percent >= 3.0:
        return "yellow"
    if ev_percent < -1.0:
        return "red"
    return "white"


def _classification_badge(classification: str) -> Text:
    mapping = {
        "strong": ("STRONG", "bold green"),
        "value": ("VALUE", "yellow"),
        "neutral": ("NEUTRAL", "white"),
        "avoid": ("AVOID", "red"),
    }
    label, style = mapping.get(classification, (classification.upper(), "white"))
    return Text(label, style=style)


def print_report(entries: list[dict]) -> None:
    today_str = datetime.now().strftime("%Y-%m-%d")
    total = len(entries)
    ev_positive = sum(1 for e in entries if e["ev_percent"] > 0)
    strong = [e for e in entries if e["classification"] == "strong"]

    header = Text()
    header.append("NBA Scout — EV Analyzer\n", style="bold cyan")
    header.append(f"Data: {today_str}    ", style="white")
    header.append(f"Entradas: {total}    ", style="white")
    header.append(f"EV+: {ev_positive}    ", style="green")
    header.append(f"Strong: {len(strong)}", style="bold green")

    console.print(Panel(header, border_style="cyan"))

    quota = odds.get_quota_remaining()
    if quota is not None:
        quota_color = "green" if quota > 50 else "yellow" if quota > 10 else "red"
        console.print(f"[{quota_color}]Odds API quota restante: {quota}[/]")

    if total == 0:
        console.print("[yellow]Nenhuma entrada para exibir. Verifique se há jogos hoje, "
                      "se a chave da Odds API é válida e se o filtro de EV mínimo "
                      "não está alto demais.[/]")
        return

    table = Table(
        title="Análise de Player Props",
        box=box.SIMPLE_HEAVY,
        show_lines=False,
        header_style="bold cyan",
    )
    table.add_column("Jogador", style="white", no_wrap=False)
    table.add_column("Jogo", style="dim")
    table.add_column("Mercado", style="cyan")
    table.add_column("Linha", justify="right")
    table.add_column("Direção", justify="center")
    table.add_column("Odd", justify="right")
    table.add_column("Prob Real", justify="right")
    table.add_column("EV%", justify="right")
    table.add_column("Kelly%", justify="right")
    table.add_column("Rating", justify="center")
    table.add_column("Casa", style="dim")

    for e in entries:
        ev_color = _ev_color(e["ev_percent"])
        ev_str = f"[{ev_color}]{e['ev_percent']:+.2f}%[/]"
        kelly_str = f"{e['kelly_fraction'] * 100:.2f}%"
        prob_str = f"{e['true_probability'] * 100:.1f}%"
        line_str = f"{e['line']:.1f}"
        dir_str = e["direction"].upper()
        dir_style = "green" if e["direction"] == "over" else "magenta"

        table.add_row(
            e["player"],
            f"vs {e['opponent']}",
            e["market"],
            line_str,
            f"[{dir_style}]{dir_str}[/]",
            f"{e['odd_decimal']:.2f}",
            prob_str,
            ev_str,
            kelly_str,
            _classification_badge(e["classification"]),
            e["bookmaker"],
        )
    console.print(table)

    if strong:
        console.print()
        strong_text = Text()
        strong_text.append("STRONG BETS (EV >= 8% e prob real >= 60%)\n", style="bold green")
        for e in strong:
            line = (f"  • {e['player']} {e['direction'].upper()} {e['line']:.1f} "
                    f"{e['market']} @ {e['odd_decimal']:.2f}  "
                    f"→ EV {e['ev_percent']:+.2f}%  "
                    f"Prob {e['true_probability'] * 100:.1f}%  "
                    f"Kelly {e['kelly_fraction'] * 100:.2f}%\n")
            strong_text.append(line, style="green")
        console.print(Panel(strong_text, title="STRONG BETS", border_style="green"))

    if total < 3:
        console.print("[yellow]Aviso: poucas entradas analisadas. Pode ser dia leve "
                      "de jogos ou a Odds API não retornou props para Bet365.[/]")

    bookmakers_used = {e["bookmaker"] for e in entries}
    if bookmakers_used and "bet365" not in bookmakers_used:
        console.print(f"[yellow]Aviso: Bet365 não disponível, usando fallback: "
                      f"{', '.join(bookmakers_used)}[/]")


def export_json(entries: list[dict], filename: str = "scout_output.json") -> None:
    payload = {
        "generated_at": datetime.now().isoformat(),
        "total_entries": len(entries),
        "ev_positive_count": sum(1 for e in entries if e["ev_percent"] > 0),
        "strong_count": sum(1 for e in entries if e["classification"] == "strong"),
        "entries": entries,
    }
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)
    console.print(f"[green]Exported to {filename}[/]")
