"""Status command - monitoring."""

import os
from pathlib import Path
from typing import Optional
from datetime import datetime, timedelta

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.tree import Tree

from vps_dev_agent.core.para_models import DatabaseManager, Task, TaskStatus, Project
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
def dashboard(
    database_url: Optional[str] = typer.Option(None, "--database-url", "-d", help="Database URL"),
):
    """Show system status dashboard."""
    db_url = database_url or get_database_url()
    db = DatabaseManager(db_url)
    session = db.get_session()
    
    try:
        # Count tasks by status
        pending_count = session.query(Task).filter_by(status=TaskStatus.PENDING).count()
        running_count = session.query(Task).filter_by(status=TaskStatus.RUNNING).count()
        completed_count = session.query(Task).filter_by(status=TaskStatus.COMPLETED).count()
        failed_count = session.query(Task).filter_by(status=TaskStatus.FAILED).count()
        
        # Count projects
        project_count = session.query(Project).count()
        
        # Recent tasks
        recent_tasks = session.query(Task).order_by(
            Task.created_at.desc()
        ).limit(10).all()
        
        # Display dashboard
        console.print(Panel(
            f"[bold cyan]VPS Dev Agent Dashboard[/bold cyan]",
            border_style="cyan"
        ))
        
        # Stats table
        stats_table = Table(title="Task Statistics")
        stats_table.add_column("Status", style="cyan")
        stats_table.add_column("Count", justify="right", style="green")
        
        stats_table.add_row("Pending", str(pending_count))
        stats_table.add_row("Running", f"[yellow]{running_count}[/yellow]")
        stats_table.add_row("Completed", f"[green]{completed_count}[/green]")
        stats_table.add_row("Failed", f"[red]{failed_count}[/red]")
        stats_table.add_row("Total Projects", str(project_count))
        
        console.print(stats_table)
        console.print()
        
        # Recent tasks table
        if recent_tasks:
            tasks_table = Table(title="Recent Tasks")
            tasks_table.add_column("ID", style="dim", no_wrap=True)
            tasks_table.add_column("Status", style="cyan")
            tasks_table.add_column("Priority", justify="right")
            tasks_table.add_column("Created", style="dim")
            
            status_colors = {
                TaskStatus.PENDING: "white",
                TaskStatus.RUNNING: "yellow",
                TaskStatus.COMPLETED: "green",
                TaskStatus.FAILED: "red",
                TaskStatus.CANCELLED: "dim",
            }
            
            for task in recent_tasks:
                color = status_colors.get(task.status, "white")
                created = task.created_at.strftime("%Y-%m-%d %H:%M") if task.created_at else "N/A"
                
                tasks_table.add_row(
                    str(task.id)[:8] + "...",
                    f"[{color}]{task.status.value}[/{color}]",
                    str(task.priority),
                    created,
                )
            
            console.print(tasks_table)
        
    except Exception as e:
        console.print(f"[red]Failed to get status: {e}[/red]")
        logger.error(f"Status command failed: {e}")
    
    finally:
        session.close()


@app.command()
def projects(
    database_url: Optional[str] = typer.Option(None, "--database-url", "-d", help="Database URL"),
):
    """List all projects."""
    db_url = database_url or get_database_url()
    db = DatabaseManager(db_url)
    session = db.get_session()
    
    try:
        all_projects = session.query(Project).order_by(Project.name).all()
        
        if not all_projects:
            console.print("[yellow]No projects found. Create one with: agent init project <name>[/yellow]")
            return
        
        table = Table(title="Projects")
        table.add_column("Name", style="cyan")
        table.add_column("ID", style="dim", no_wrap=True)
        table.add_column("Status", style="green")
        table.add_column("Path")
        table.add_column("Tasks", justify="right")
        
        for project in all_projects:
            task_count = session.query(Task).filter_by(project_id=project.id).count()
            
            table.add_row(
                project.name,
                str(project.id)[:8] + "...",
                project.status,
                project.repo_path,
                str(task_count),
            )
        
        console.print(table)
        
    except Exception as e:
        console.print(f"[red]Failed to list projects: {e}[/red]")
    
    finally:
        session.close()


@app.command()
def task(
    task_id: str = typer.Argument(..., help="Task ID to inspect"),
    database_url: Optional[str] = typer.Option(None, "--database-url", "-d", help="Database URL"),
):
    """Show detailed information about a specific task."""
    db_url = database_url or get_database_url()
    db = DatabaseManager(db_url)
    session = db.get_session()
    
    try:
        task = session.query(Task).filter_by(id=task_id).first()
        
        if not task:
            # Try partial match
            tasks = session.query(Task).filter(Task.id.ilike(f"%{task_id}%")).all()
            if len(tasks) == 1:
                task = tasks[0]
            elif len(tasks) > 1:
                console.print(f"[red]Multiple tasks match '{task_id}', please be more specific[/red]")
                return
        
        if not task:
            console.print(f"[red]Task not found: {task_id}[/red]")
            return
        
        # Build info panel
        info_lines = [
            f"[bold]Task ID:[/bold] {task.id}",
            f"[bold]Status:[/bold] {task.status.value}",
            f"[bold]Priority:[/bold] {task.priority}",
            f"[bold]YOLO Mode:[/bold] {'Yes' if task.yolo_mode else 'No'}",
            f"[bold]Attempts:[/bold] {task.attempt_count}/{task.max_attempts}",
            f"[bold]Spec Path:[/bold] {task.spec_path}",
            "",
            f"[bold]Created:[/bold] {task.created_at}",
        ]
        
        if task.started_at:
            info_lines.append(f"[bold]Started:[/bold] {task.started_at}")
        
        if task.completed_at:
            info_lines.append(f"[bold]Completed:[/bold] {task.completed_at}")
            if task.started_at:
                duration = task.completed_at - task.started_at
                info_lines.append(f"[bold]Duration:[/bold] {duration}")
        
        if task.result_summary:
            info_lines.extend(["", f"[bold]Result:[/bold] {task.result_summary}"])
        
        if task.error_log:
            info_lines.extend(["", f"[bold red]Error:[/bold red] {task.error_log[:500]}"])
        
        console.print(Panel(
            "\n".join(info_lines),
            title="Task Details",
            border_style="blue"
        ))
        
    except Exception as e:
        console.print(f"[red]Failed to get task info: {e}[/red]")
    
    finally:
        session.close()
