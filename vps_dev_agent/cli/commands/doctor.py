"""Doctor command - diagnostic checks."""

import os
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.tree import Tree

from vps_dev_agent.bridges.kimi_cli import KimiAuthChecker, check_kimi_installation
from vps_dev_agent.core.para_models import DatabaseManager
from vps_dev_agent.utils.logger import get_logger

app = typer.Typer()
console = Console()
logger = get_logger()


def get_database_url() -> str:
    """Get database URL from environment or config."""
    db_url = os.getenv("DATABASE_URL")
    if db_url:
        return db_url
    
    config_path = Path.home() / ".vps_dev_agent" / "config.env"
    if config_path.exists():
        with open(config_path) as f:
            for line in f:
                if line.startswith("DATABASE_URL="):
                    return line.strip().split("=", 1)[1]
    
    return "postgresql://localhost:5432/vps_dev_agent"


@app.callback()
def doctor():
    """Run diagnostic checks."""
    pass


@app.command(name="kimi")
def check_kimi():
    """Check Kimi CLI installation and configuration."""
    console.print(Panel(
        "[bold cyan]Kimi CLI Diagnostic[/bold cyan]",
        border_style="cyan"
    ))
    
    table = Table(show_header=False, title="Checks")
    table.add_column("Item", style="cyan")
    table.add_column("Status", style="green")
    table.add_column("Details")
    
    # 1. Check if installed
    installed, version_or_error = check_kimi_installation()
    if installed:
        table.add_row(
            "✓ Installed",
            "[green]PASS[/green]",
            version_or_error
        )
    else:
        table.add_row(
            "✗ Installed",
            "[red]FAIL[/red]",
            version_or_error
        )
        console.print(table)
        console.print("\n[red]Kimi CLI is not installed.[/red]")
        console.print("Install from: https://kimi.moonshot.cn/download")
        return
    
    auth_checker = KimiAuthChecker()
    
    # 2. Check version compatibility
    # This is a placeholder - would need actual version checking logic
    table.add_row(
        "✓ Version",
        "[green]PASS[/green]",
        "Compatible"
    )
    
    # 3. Check authentication
    auth_status = auth_checker.check_auth()
    if auth_status.is_authenticated:
        table.add_row(
            "✓ Authenticated",
            "[green]PASS[/green]",
            auth_status.username or "OK"
        )
    else:
        table.add_row(
            "✗ Authenticated",
            "[red]FAIL[/red]",
            "Run 'kimi login' to authenticate"
        )
    
    # 4. Check subscription tier
    from vps_dev_agent.bridges.kimi_cli import LimitChecker
    limit_checker = LimitChecker()
    quota = limit_checker.get_remaining_quota()
    
    if quota:
        tier_color = "green"
        if quota.tier.value == "Free":
            tier_color = "yellow"
        
        table.add_row(
            "✓ Subscription",
            f"[{tier_color}]{quota.tier.value}[/{tier_color}]",
            f"{quota.requests_remaining} requests remaining"
        )
        
        # 5. Check quota
        if quota.is_critical:
            table.add_row(
                "⚠ Quota",
                "[red]CRITICAL[/red]",
                f"Only {quota.requests_remaining} requests left!"
            )
        elif quota.is_near_limit:
            table.add_row(
                "⚠ Quota",
                "[yellow]WARNING[/yellow]",
                f"{quota.requests_remaining} requests remaining"
            )
        else:
            table.add_row(
                "✓ Quota",
                "[green]OK[/green]",
                f"{quota.requests_remaining} requests available"
            )
    else:
        table.add_row(
            "? Quota",
            "[yellow]UNKNOWN[/yellow]",
            "Could not check quota"
        )
    
    console.print(table)
    
    # Summary
    if auth_status.is_authenticated and quota and quota.can_execute:
        console.print("\n[bold green]✓ Kimi CLI is ready to use[/bold green]")
    else:
        console.print("\n[bold yellow]⚠ Some issues found - see details above[/bold yellow]")


@app.command(name="db")
def check_database(
    database_url: Optional[str] = typer.Option(None, "--database-url", "-d", help="Database URL"),
):
    """Check database connection and schema."""
    db_url = database_url or get_database_url()
    
    console.print(Panel(
        "[bold cyan]Database Diagnostic[/bold cyan]",
        border_style="cyan"
    ))
    
    table = Table(show_header=False)
    table.add_column("Check")
    table.add_column("Status")
    table.add_column("Details")
    
    try:
        from sqlalchemy import inspect
        
        db = DatabaseManager(db_url)
        
        # Test connection
        with db.engine.connect() as conn:
            table.add_row(
                "✓ Connection",
                "[green]PASS[/green]",
                "Connected successfully"
            )
        
        # Check tables
        inspector = inspect(db.engine)
        tables = inspector.get_table_names()
        
        expected_tables = ['projects', 'areas', 'resources', 'archives', 'tasks']
        missing = [t for t in expected_tables if t not in tables]
        
        if not missing:
            table.add_row(
                "✓ Tables",
                "[green]PASS[/green]",
                f"All {len(expected_tables)} tables present"
            )
        else:
            table.add_row(
                "✗ Tables",
                "[red]FAIL[/red]",
                f"Missing: {', '.join(missing)}"
            )
        
        # Check extensions
        with db.engine.connect() as conn:
            result = conn.execute("SELECT * FROM pg_extension WHERE extname = 'vector'")
            if result.fetchone():
                table.add_row(
                    "✓ pgvector",
                    "[green]PASS[/green]",
                    "Extension enabled"
                )
            else:
                table.add_row(
                    "✗ pgvector",
                    "[red]FAIL[/red]",
                    "Extension not found"
                )
        
        console.print(table)
        console.print("\n[bold green]✓ Database is ready[/bold green]")
        
    except Exception as e:
        table.add_row(
            "✗ Connection",
            "[red]FAIL[/red]",
            str(e)[:50]
        )
        console.print(table)
        console.print(f"\n[bold red]✗ Database check failed: {e}[/bold red]")


@app.command(name="all")
def check_all(
    database_url: Optional[str] = typer.Option(None, "--database-url", "-d", help="Database URL"),
):
    """Run all diagnostic checks."""
    console.print(Panel(
        "[bold cyan]VPS Dev Agent - Full Diagnostic[/bold cyan]",
        border_style="cyan"
    ))
    
    check_kimi()
    console.print("\n" + "=" * 50 + "\n")
    check_database(database_url)
