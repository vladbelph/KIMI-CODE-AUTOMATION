"""Welcome/onboarding command."""

import typer
from rich.console import Console

from vps_dev_agent.cli.onboarding import run_onboarding, show_brief_mode
from vps_dev_agent.cli.onboarding.wizard import check_first_run

app = typer.Typer()
console = Console()


@app.callback()
def welcome():
    """Interactive onboarding and welcome experience."""
    pass


@app.command(name="start")
def start(
    force: bool = typer.Option(False, "--force", "-f", help="Force re-run onboarding"),
):
    """Run interactive onboarding wizard."""
    success = run_onboarding(force=force)
    
    if not success:
        raise typer.Exit(1)


@app.command(name="brief")
def brief():
    """Show brief welcome message (for subsequent runs)."""
    show_brief_mode()


def maybe_show_welcome():
    """Show welcome on first run, brief mode otherwise.
    
    This function should be called from main.py on startup.
    """
    if check_first_run():
        # First run - show full onboarding
        run_onboarding()
    else:
        # Subsequent run - show brief mode
        show_brief_mode()
