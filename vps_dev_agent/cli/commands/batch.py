"""Batch execution command."""

import os
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table

from vps_dev_agent.bridges.kimi_cli import KimiBatchExecutor, ExecutionMode
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


@app.command()
def run(
    project: Optional[str] = typer.Option(None, "--project", "-p", help="Project name to filter by"),
    provider: str = typer.Option("kimi_cli", "--provider", help="LLM provider to use"),
    mode: str = typer.Option("native_batch", "--mode", "-m", help="Execution mode: native_batch or interactive"),
    max_tasks: Optional[int] = typer.Option(None, "--max-tasks", "-n", help="Maximum number of tasks to execute"),
    continuous: bool = typer.Option(False, "--continuous", "-c", help="Keep running until queue is empty"),
    auto_apply: bool = typer.Option(False, "--auto-apply", "-y", help="Auto-apply changes (YOLO mode)"),
    timeout: int = typer.Option(30, "--timeout", "-t", help="Timeout per task in minutes"),
    database_url: Optional[str] = typer.Option(None, "--database-url", "-d", help="Database URL"),
):
    """Run batch execution loop until queue is exhausted."""
    db_url = database_url or get_database_url()
    
    # Map mode string to enum
    try:
        exec_mode = ExecutionMode(mode)
    except ValueError:
        console.print(f"[red]Invalid mode: {mode}. Use 'native_batch' or 'interactive'[/red]")
        raise typer.Exit(1)
    
    console.print(Panel(
        f"[bold blue]Batch Execution[/bold blue]\n"
        f"Provider: {provider}\n"
        f"Mode: {mode}\n"
        f"Project: {project or 'all'}\n"
        f"Auto-apply: {auto_apply}",
        border_style="blue"
    ))
    
    if provider == "kimi_cli":
        executor = KimiBatchExecutor(
            database_url=db_url,
            mode=exec_mode,
            auto_apply=auto_apply,
            timeout_minutes=timeout,
        )
        
        try:
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                console=console,
            ) as progress:
                progress.add_task("Running batch execution...", total=None)
                
                results = executor.run_batch_loop(
                    project_name=project,
                    max_tasks=max_tasks,
                    continuous=continuous,
                )
            
            # Show results
            if results:
                table = Table(title="Batch Results")
                table.add_column("Task ID", style="dim")
                table.add_column("Status")
                table.add_column("Exit Code", justify="right")
                table.add_column("Tokens", justify="right")
                table.add_column("Summary")
                
                for result in results:
                    status = "[green]✓[/green]" if result.success else "[red]✗[/red]"
                    table.add_row(
                        result.task_id[:8] + "...",
                        status,
                        str(result.exit_code),
                        str(result.tokens_used or "-"),
                        (result.summary or "")[:40] + "..." if result.summary and len(result.summary) > 40 else (result.summary or ""),
                    )
                
                console.print(table)
                
                # Summary
                success_count = sum(1 for r in results if r.success)
                console.print(f"\n[bold]{success_count}/{len(results)} tasks completed successfully[/bold]")
                
                if success_count < len(results):
                    raise typer.Exit(1)
            else:
                console.print("[yellow]No tasks were executed[/yellow]")
                
        except KeyboardInterrupt:
            console.print("\n[yellow]Batch execution interrupted[/yellow]")
            raise typer.Exit(130)
    else:
        console.print(f"[red]Provider '{provider}' not yet implemented[/red]")
        raise typer.Exit(1)
