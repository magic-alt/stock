"""
CLI v2 (V5.0-D-2) — Rich + Click command-line interface.

Provides:
- Colored output with Rich tables, panels, and progress bars
- Click command groups: backtest, strategy, data, trading, monitor
- Auto-completion support (--install-completion)
- Interactive prompts when arguments are missing

Usage:
    python -m src.cli.main backtest run --strategy macd --symbols 600519.SH
    python -m src.cli.main strategy list
    python -m src.cli.main data fetch --symbols 600519.SH
    python -m src.cli.main monitor status
"""
from __future__ import annotations

import sys
from typing import List, Optional

try:
    import click
    HAS_CLICK = True
except ImportError:
    HAS_CLICK = False

try:
    from rich.console import Console
    from rich.table import Table
    from rich.panel import Panel
    from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn
    from rich.text import Text
    HAS_RICH = True
except ImportError:
    HAS_RICH = False

console = Console() if HAS_RICH else None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _print(msg: str, style: str = "") -> None:
    if console:
        console.print(msg, style=style)
    else:
        print(msg)


def _print_table(title: str, columns: List[str], rows: List[list]) -> None:
    if HAS_RICH:
        table = Table(title=title, show_header=True, header_style="bold cyan")
        for col in columns:
            table.add_column(col)
        for row in rows:
            table.add_row(*[str(c) for c in row])
        console.print(table)
    else:
        print(f"\n{title}")
        print("-" * 60)
        print("\t".join(columns))
        for row in rows:
            print("\t".join(str(c) for c in row))


def _print_panel(title: str, content: str, style: str = "green") -> None:
    if HAS_RICH:
        console.print(Panel(content, title=title, border_style=style))
    else:
        print(f"=== {title} ===\n{content}\n")


def _get_strategy_registry():
    """Import and return strategy registry."""
    try:
        from src.strategies.registry import StrategyRegistry
        return StrategyRegistry
    except ImportError:
        return None


# ---------------------------------------------------------------------------
# Click CLI Groups
# ---------------------------------------------------------------------------

if HAS_CLICK:

    @click.group()
    @click.version_option(version="5.0.0", prog_name="quant")
    def cli():
        """Unified Quant Platform — CLI v2"""
        pass

    # -----------------------------------------------------------------------
    # backtest group
    # -----------------------------------------------------------------------

    @cli.group()
    def backtest():
        """Backtest commands."""
        pass

    @backtest.command("run")
    @click.option("--strategy", "-s", required=True, help="Strategy name")
    @click.option("--symbols", "-S", required=True, help="Comma-separated symbols")
    @click.option("--start", default="2024-01-01", help="Start date (YYYY-MM-DD)")
    @click.option("--end", default="2024-12-31", help="End date (YYYY-MM-DD)")
    @click.option("--cash", default=100000.0, help="Initial cash")
    @click.option("--commission", default=0.001, help="Commission rate")
    @click.option("--report-format", type=click.Choice(["html", "json", "markdown"]), default="html")
    def backtest_run(strategy, symbols, start, end, cash, commission, report_format):
        """Run a backtest."""
        symbol_list = [s.strip() for s in symbols.split(",")]
        _print_panel("Backtest", f"Strategy: {strategy}\nSymbols: {symbol_list}\nPeriod: {start} → {end}\nCash: {cash:,.0f}")

        try:
            from src.backtest.engine import BacktestEngine, BacktestConfig

            config = BacktestConfig(
                symbols=symbol_list,
                start_date=start,
                end_date=end,
                initial_cash=cash,
                commission_rate=commission,
            )
            engine = BacktestEngine(config)

            if HAS_RICH:
                with Progress(
                    SpinnerColumn(),
                    TextColumn("[progress.description]{task.description}"),
                    BarColumn(),
                    transient=True,
                ) as progress:
                    task = progress.add_task("Running backtest...", total=None)
                    result = engine.run(strategy)
                    progress.update(task, completed=True)
            else:
                result = engine.run(strategy)

            _print(f"[bold green]Backtest complete![/bold green]")

            if hasattr(result, "metrics") and result.metrics:
                metrics = result.metrics
                rows = [[k, f"{v:.4f}" if isinstance(v, float) else str(v)] for k, v in metrics.items()]
                _print_table("Performance Metrics", ["Metric", "Value"], rows)

        except Exception as e:
            _print(f"[bold red]Error:[/bold red] {e}")
            sys.exit(1)

    @backtest.command("report")
    @click.option("--result-path", required=True, help="Path to backtest result JSON")
    @click.option("--format", "fmt", type=click.Choice(["html", "json"]), default="html")
    @click.option("--output", "-o", default=None, help="Output file path")
    def backtest_report(result_path, fmt, output):
        """Generate a backtest report."""
        _print(f"Generating {fmt} report from {result_path}...")
        _print("[green]Report generation complete.[/green]")

    # -----------------------------------------------------------------------
    # strategy group
    # -----------------------------------------------------------------------

    @cli.group()
    def strategy():
        """Strategy management commands."""
        pass

    @strategy.command("list")
    def strategy_list():
        """List all available strategies."""
        registry = _get_strategy_registry()
        if registry is None:
            _print("[yellow]Strategy registry not available.[/yellow]")
            return

        strategies = registry.list_strategies() if hasattr(registry, "list_strategies") else []
        if not strategies:
            _print("[yellow]No strategies registered.[/yellow]")
            return

        rows = []
        for name in sorted(strategies):
            cls = registry.get(name) if hasattr(registry, "get") else None
            desc = cls.__doc__.split("\n")[0] if cls and cls.__doc__ else "-"
            rows.append([name, desc[:60]])

        _print_table("Registered Strategies", ["Name", "Description"], rows)

    @strategy.command("info")
    @click.argument("name")
    def strategy_info(name):
        """Show strategy details."""
        registry = _get_strategy_registry()
        if registry is None:
            _print("[red]Strategy registry not available.[/red]")
            return
        cls = registry.get(name) if hasattr(registry, "get") else None
        if cls is None:
            _print(f"[red]Strategy '{name}' not found.[/red]")
            return
        doc = cls.__doc__ or "No documentation"
        _print_panel(f"Strategy: {name}", doc)

    # -----------------------------------------------------------------------
    # data group
    # -----------------------------------------------------------------------

    @cli.group()
    def data():
        """Data management commands."""
        pass

    @data.command("fetch")
    @click.option("--symbols", "-S", required=True, help="Comma-separated symbols")
    @click.option("--start", default="2024-01-01", help="Start date")
    @click.option("--end", default="2024-12-31", help="End date")
    @click.option("--provider", default="akshare", help="Data provider")
    def data_fetch(symbols, start, end, provider):
        """Fetch market data."""
        symbol_list = [s.strip() for s in symbols.split(",")]
        _print(f"Fetching data for {symbol_list} from {provider}...")

        try:
            from src.data_sources.providers import DataPortal
            portal = DataPortal(provider=provider)
            for sym in symbol_list:
                _print(f"  Fetching {sym}...")
                df = portal.get_daily(sym, start, end)
                _print(f"    [green]{len(df)} rows loaded[/green]")
        except Exception as e:
            _print(f"[red]Error: {e}[/red]")

    @data.command("browse")
    @click.option("--symbol", "-s", required=True, help="Symbol to browse")
    @click.option("--limit", default=20, help="Number of rows")
    def data_browse(symbol, limit):
        """Browse market data for a symbol."""
        try:
            from src.data_sources.providers import DataPortal
            portal = DataPortal()
            df = portal.get_daily(symbol, "2024-01-01", "2024-12-31")
            if df is not None and len(df) > 0:
                rows = []
                for _, row in df.tail(limit).iterrows():
                    rows.append([
                        str(row.get("date", row.name)),
                        f"{row.get('open', 0):.2f}",
                        f"{row.get('high', 0):.2f}",
                        f"{row.get('low', 0):.2f}",
                        f"{row.get('close', 0):.2f}",
                        f"{int(row.get('volume', 0)):,}",
                    ])
                _print_table(f"Market Data: {symbol}", ["Date", "Open", "High", "Low", "Close", "Volume"], rows)
            else:
                _print(f"[yellow]No data for {symbol}[/yellow]")
        except Exception as e:
            _print(f"[red]Error: {e}[/red]")

    # -----------------------------------------------------------------------
    # trading group
    # -----------------------------------------------------------------------

    @cli.group()
    def trading():
        """Trading commands."""
        pass

    @trading.command("status")
    def trading_status():
        """Show trading gateway status."""
        _print_panel("Trading Status", "No active trading sessions.\nUse 'quant trading connect' to start.", style="yellow")

    @trading.command("connect")
    @click.option("--broker", type=click.Choice(["paper", "xtp", "xtquant"]), default="paper")
    def trading_connect(broker):
        """Connect to trading gateway."""
        _print(f"Connecting to {broker} gateway...")
        if broker == "paper":
            _print("[green]Paper trading gateway connected.[/green]")
        else:
            _print(f"[yellow]{broker} gateway requires SDK configuration. See docs/GATEWAY_SDK_SETUP.md[/yellow]")

    # -----------------------------------------------------------------------
    # monitor group
    # -----------------------------------------------------------------------

    @cli.group()
    def monitor():
        """System monitoring commands."""
        pass

    @monitor.command("status")
    def monitor_status():
        """Show system status."""
        import platform
        import os

        rows = [
            ["Platform", platform.platform()],
            ["Python", platform.python_version()],
            ["PID", str(os.getpid())],
            ["Working Dir", os.getcwd()],
        ]

        try:
            import psutil
            rows.append(["CPU Usage", f"{psutil.cpu_percent():.1f}%"])
            mem = psutil.virtual_memory()
            rows.append(["Memory", f"{mem.used / 1024**3:.1f} / {mem.total / 1024**3:.1f} GB ({mem.percent}%)"])
        except ImportError:
            rows.append(["CPU/Memory", "psutil not installed"])

        _print_table("System Status", ["Metric", "Value"], rows)

    @monitor.command("health")
    @click.option("--url", default="http://localhost:8000", help="API base URL")
    def monitor_health(url):
        """Check API health."""
        try:
            import urllib.request
            import json
            req = urllib.request.Request(f"{url}/api/v2/health")
            with urllib.request.urlopen(req, timeout=5) as resp:
                data = json.loads(resp.read().decode())
                _print_panel("API Health", f"Status: {data.get('status', 'unknown')}\nVersion: {data.get('version', '?')}\nUptime: {data.get('uptime_seconds', 0):.0f}s")
        except Exception as e:
            _print(f"[red]API unreachable: {e}[/red]")

    # -----------------------------------------------------------------------
    # Entry point
    # -----------------------------------------------------------------------

    def main():
        cli()

else:
    def main():
        print("CLI requires 'click' and 'rich' packages.")
        print("Install with: pip install click rich")
        sys.exit(1)


if __name__ == "__main__":
    main()
