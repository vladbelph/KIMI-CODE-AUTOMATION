"""Queue command - manage task queue."""

import os
import uuid
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.prompt import Confirm

from vps_dev_agent.core.para_models import DatabaseManager, Task, TaskStatus, Project
from vps_dev_agent.core.spec_parser import SpecParser
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


@app.command(name="add")
def add_task(
    spec_path: Path = typer.Argument(..., help="Path to spec YAML file", exists=True),
    project_name: Optional[str] = typer.Option(None, "--project", "-p", help="Project name"),
    priority: int = typer.Option(5, "--priority", help="Task priority (1-10)"),
    yolo: bool = typer.Option(False, "--yolo", "-y", help="Enable YOLO mode"),
    provider: str = typer.Option("kimi_cli", "--provider", help="LLM provider (kimi_cli, openai, anthropic)"),
    database_url: Optional[str] = typer.Option(None, "--database-url", "-d", help="Database URL"),
    """Add a task to the queue from a spec file."""
    db_url = database_url or get_database_url()
    
    # Validate spec
    parser = SpecParser(spec_path)
    try:
        spec = parser.load()
        issues = parser.validate_for_execution()
        if issues:
            console.print(f"[yellow]Spec validation warnings:[/yellow]")
            for issue in issues:
                console.print(f"  - {issue}")
    except Exception as e:
        console.print(f"[red]Invalid spec file: {e}[/red]")
        raise typer.Exit(1)
    
    db = DatabaseManager(db_url)
    session = db.get_session()
    
    try:
        # Find project
        project_id = spec.context.project_id
        
        if not project_id and project_name:
            project = session.query(Project).filter_by(name=project_name).first()
            if not project:
                console.print(f"[red]Project '{project_name}' not found[/red]")
                raise typer.Exit(1)
            project_id = str(project.id)
        elif not project_id:
            console.print("[red]Project must be specified via --project or spec.context.project_id[/red]")
            raise typer.Exit(1)
        
        # Create task
        task_id = uuid.uuid4()
        task = Task(
            id=task_id,
            project_id=project_id,
            spec_path=str(spec_path.resolve()),
            status=TaskStatus.PENDING,
            priority=priority,
            yolo_mode=yolo or spec.security_mode.value == "yolo",
            max_attempts=spec.execution.max_attempts,
            llm_provider=provider,
        )
        
        session.add(task)
        session.commit()
        
        console.print(Panel(
            f"[bold green]✓ Task added to queue[/bold green]\n\n"
            f"Task ID: {task_id}\n"
            f"Project ID: {project_id}\n"
            f"Priority: {priority}\n"
            f"YOLO Mode: {'Yes' if task.yolo_mode else 'No'}\n"
            f"Provider: {provider}",
            border_style="green"
        ))
        
        console.print(f"\nRun with: [cyan]agent run task {task_id}[/cyan]")
        
    except Exception as e:
        session.rollback()
        console.print(f"[red]Failed to add task: {e}[/red]")
        raise typer.Exit(1)
    
    finally:
        session.close()


@app.command(name="list")
def list_tasks(
    status: Optional[str] = typer.Option(None, "--status", "-s", help="Filter by status"),
    project_name: Optional[str] = typer.Option(None, "--project", "-p", help="Filter by project"),
    limit: int = typer.Option(20, "--limit", "-n", help="Maximum number of tasks"),
    database_url: Optional[str] = typer.Option(None, "--database-url", "-d", help="Database URL"),
):
    """List tasks in the queue."""
    db_url = database_url or get_database_url()
    db = DatabaseManager(db_url)
    session = db.get_session()
    
    try:
        query = session.query(Task)
        
        # Apply filters
        if status:
            try:
                task_status = TaskStatus(status.lower())
                query = query.filter_by(status=task_status)
            except ValueError:
                console.print(f"[red]Invalid status: {status}. Valid: pending, running, completed, failed[/red]")
                raise typer.Exit(1)
        
        if project_name:
            project = session.query(Project).filter_by(name=project_name).first()
            if project:
                query = query.filter_by(project_id=project.id)
            else:
                console.print(f"[red]Project '{project_name}' not found[/red]")
                raise typer.Exit(1)
        
        tasks = query.order_by(Task.priority.asc(), Task.created_at.asc()).limit(limit).all()
        
        if not tasks:
            console.print("[yellow]No tasks found[/yellow]")
            return
        
        table = Table(title=f"Tasks (limit: {limit})")
        table.add_column("ID", style="dim", no_wrap=True, width=12)
        table.add_column("Status", style="cyan")
        table.add_column("Prio", justify="right", width=4)
        table.add_column("YOLO", width=5)
        table.add_column("Attempts", justify="right", width=8)
        table.add_column("Created", style="dim")
        table.add_column("Spec Path")
        
        status_colors = {
            TaskStatus.PENDING: "white",
            TaskStatus.RUNNING: "yellow",
            TaskStatus.COMPLETED: "green",
            TaskStatus.FAILED: "red",
            TaskStatus.CANCELLED: "dim",
        }
        
        for task in tasks:
            color = status_colors.get(task.status, "white")
            created = task.created_at.strftime("%m-%d %H:%M") if task.created_at else "N/A"
            
            table.add_row(
                str(task.id)[:8] + "...",
                f"[{color}]{task.status.value}[/{color}]",
                str(task.priority),
                "Yes" if task.yolo_mode else "No",
                f"{task.attempt_count}/{task.max_attempts}",
                created,
                task.spec_path[:30] + "..." if len(task.spec_path) > 30 else task.spec_path,
            )
        
        console.print(table)
        
    except Exception as e:
        console.print(f"[red]Failed to list tasks: {e}[/red]")
    
    finally:
        session.close()


@app.command(name="remove")
def remove_task(
    task_id: str = typer.Argument(..., help="Task ID to remove"),
    force: bool = typer.Option(False, "--force", "-f", help="Skip confirmation"),
    database_url: Optional[str] = typer.Option(None, "--database-url", "-d", help="Database URL"),
):
    """Remove a task from the queue."""
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
            raise typer.Exit(1)
        
        # Confirm if running
        if task.status == TaskStatus.RUNNING and not force:
            if not Confirm.ask(f"Task {task.id[:8]} is currently running. Remove anyway?"):
                console.print("[yellow]Cancelled[/yellow]")
                return
        
        session.delete(task)
        session.commit()
        
        console.print(f"[green]✓ Task {task.id[:8]}... removed from queue[/green]")
        
    except Exception as e:
        session.rollback()
        console.print(f"[red]Failed to remove task: {e}[/red]")
        raise typer.Exit(1)
    
    finally:
        session.close()


@app.command(name="clear")
def clear_queue(
    status: str = typer.Option("failed", "--status", "-s", help="Clear tasks with this status"),
    force: bool = typer.Option(False, "--force", "-f", help="Skip confirmation"),
    database_url: Optional[str] = typer.Option(None, "--database-url", "-d", help="Database URL"),
):
    """Clear tasks with a specific status from the queue."""
    db_url = database_url or get_database_url()
    db = DatabaseManager(db_url)
    session = db.get_session()
    
    try:
        try:
            task_status = TaskStatus(status.lower())
        except ValueError:
            console.print(f"[red]Invalid status: {status}[/red]")
            raise typer.Exit(1)
        
        tasks = session.query(Task).filter_by(status=task_status).all()
        
        if not tasks:
            console.print(f"[yellow]No tasks with status '{status}' found[/yellow]")
            return
        
        if not force:
            if not Confirm.ask(f"Remove {len(tasks)} tasks with status '{status}'?"):
                console.print("[yellow]Cancelled[/yellow]")
                return
        
        for task in tasks:
            session.delete(task)
        
        session.commit()
        
        console.print(f"[green]✓ Cleared {len(tasks)} tasks[/green]")
        
    except Exception as e:
        session.rollback()
        console.print(f"[red]Failed to clear queue: {e}[/red]")
        raise typer.Exit(1)
    
    finally:
        session.close()
