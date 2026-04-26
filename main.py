import argparse
import logging
import sys

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
        sys.stderr.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
    except Exception:
        pass

from rich.console import Console

import config
import stats as stats_mod
from scout import analyze_day
from report import print_report, export_json

console = Console()


def main() -> int:
    parser = argparse.ArgumentParser(description="NBA Scout — EV Analyzer")
    parser.add_argument("--min-ev", type=float, default=config.MIN_EV_PERCENT,
                        help="EV mínimo para exibir (default: 3.0)")
    parser.add_argument("--market", type=str, default="all",
                        choices=["all", "points", "rebounds", "assists", "threes",
                                 "blocks", "steals",
                                 "pra", "pr", "pa", "ra", "stocks"],
                        help="Filtrar por mercado")
    parser.add_argument("--interactive", "-i", action="store_true",
                        help="Modo interativo com menu")
    parser.add_argument("--export", action="store_true", help="Exporta JSON")
    parser.add_argument("--only-strong", action="store_true",
                        help="Só mostra strong bets")
    parser.add_argument("--verbose", "-v", action="store_true",
                        help="Logging detalhado")
    args = parser.parse_args()

    log_level = logging.INFO if args.verbose else logging.WARNING
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )

    if not config.ODDS_API_KEY:
        console.print("[red]Erro: ODDS_API_KEY não configurada. "
                      "Crie um .env com a chave (veja .env.example).[/]")
        return 1

    if args.interactive:
        from interactive import run_interactive
        run_interactive()
        return 0

    console.print("[cyan]Buscando jogos e odds...[/]")
    try:
        entries = analyze_day()
    except KeyboardInterrupt:
        console.print("[yellow]Análise interrompida pelo usuário.[/]")
        return 130
    except Exception as e:
        console.print(f"[red]Erro inesperado durante análise: {e}[/]")
        if args.verbose:
            raise
        return 1

    if not entries:
        console.print("[yellow]Nenhum jogo NBA encontrado ou nenhuma prop disponível "
                      "para hoje.[/]")
        return 0

    if args.market != "all":
        market_map = {
            "points":   "Pontos",
            "rebounds": "Rebotes",
            "assists":  "Assistências",
            "threes":   "3 Pontos",
            "blocks":   "Bloqueios",
            "steals":   "Roubos",
            "pra":      "PRA",
            "pr":       "Pts+Reb",
            "pa":       "Pts+Ast",
            "ra":       "Reb+Ast",
            "stocks":   "Blk+Stl",
        }
        target = market_map[args.market]
        entries = [e for e in entries if e["market"] == target]

    if args.only_strong:
        entries = [e for e in entries if e["classification"] == "strong"]

    entries = [e for e in entries if e["ev_percent"] >= args.min_ev]

    print_report(entries)

    if stats_mod.stats_endpoint_blocked():
        console.print()
        console.print("[red]stats.nba.com está inacessível do seu IP "
                      "(geoblock ou bloqueio de cloud).[/]")
        console.print("[yellow]Workarounds:[/]")
        console.print("  • Use VPN com saída nos EUA e rode novamente")
        console.print("  • Ou configure proxy no .env: HTTPS_PROXY=http://user:pass@host:port")
        console.print("  • Verifique se sua rede não bloqueia stats.nba.com")

    if args.export:
        export_json(entries)

    return 0


if __name__ == "__main__":
    sys.exit(main())
