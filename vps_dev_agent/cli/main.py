"""Main CLI entry point."""

import os
import sys
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

# Import commands
from vps_dev_agent.cli.commands import init, run, status, queue, doctor, batch
from vps_dev_agent import __version__

# Create main app
app = typer.Typer(
    name="agent",
    help="VPS Dev Agent - Autonomous AI development agent",
    rich_markup_mode="rich",
)

console = Console()

# Add subcommands
app.add_typer(init.app, name="init", help="Initialize database and projects")
app.add_typer(run.app, name="run", help="Execute tasks")
app.add_typer(status.app, name="status", help="Check system status")
app.add_typer(queue.app, name="queue", help="Manage task queue")
app.add_typer(doctor.app, name="doctor", help="Run diagnostic checks")
app.add_typer(batch.app, name="batch", help="Batch execution")


@app.callback()
def main(
    version: Optional[bool] = typer.Option(
        None, "--version", "-v",
        help="Show version and exit",
        is_eager=True,
    ),
):
    """VPS Dev Agent - Autonomous AI development for VPS."""
    if version:
        console.print(f"[bold cyan]VPS Dev Agent[/bold cyan] version {__version__}")
        raise typer.Exit()


@app.command()
def config(
    show: bool = typer.Option(False, "--show", "-s", help="Show current configuration"),
    database_url: Optional[str] = typer.Option(None, "--database-url", help="Set database URL"),
):
    """Manage agent configuration."""
    config_path = Path.home() / ".vps_dev_agent" / "config.env"
    config_path.parent.mkdir(parents=True, exist_ok=True)
    
    if show:
        table = Table(title="Configuration")
        table.add_column("Setting", style="cyan")
        table.add_column("Value", style="green")
        
        # Show environment variables
        env_vars = [
            "DATABASE_URL",
            "MOONSHOT_API_KEY",
            "DEEPSEEK_API_KEY",
            "OPENAI_API_KEY",
            "ANTHROPIC_API_KEY",
        ]
        
        for var in env_vars:
            value = os.getenv(var, "Not set")
            # Mask API keys
            if "API_KEY" in var and value != "Not set":
                value = value[:8] + "..." + value[-4:]
            table.add_row(var, value)
        
        console.print(table)
        return
    
    if database_url:
        # Save to config file
        with open(config_path, "w") as f:
            f.write(f"DATABASE_URL={database_url}\n")
        console.print(f"[green]Database URL saved to {config_path}[/green]")
        return
    
    console.print(Panel(
        "[bold]Configuration Help[/bold]\n\n"
        "Set environment variables:\n"
        "  export DATABASE_URL=postgresql://user:pass@localhost/agent_db\n"
        "  export MOONSHOT_API_KEY=your_key\n\n"
        "Or use:\n"
        "  agent config --database-url <url>",
        border_style="blue"
    ))


def get_database_url() -> str:
    """Get database URL from environment or config file."""
    # Check environment first
    db_url = os.getenv("DATABASE_URL")
    if db_url:
        return db_url
    
    # Check config file
    config_path = Path.home() / ".vps_dev_agent" / "config.env"
    if config_path.exists():
        with open(config_path) as f:
            for line in f:
                if line.startswith("DATABASE_URL="):
                    return line.strip().split("=", 1)[1]
    
    # Default fallback
    return "postgresql://localhost:5432/vps_dev_agent"


# Entry point
if __name__ == "__main__":
    app()
