"""Run command - execute tasks."""

import os
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn

from vps_dev_agent.core.executor import TaskExecutor, ExecutionResult
from vps_dev_agent.core.para_models import DatabaseManager, Task, TaskStatus
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
def task(
    task_id: str = typer.Argument(..., help="Task ID to execute"),
    database_url: Optional[str] = typer.Option(None, "--database-url", "-d", help="Database URL"),
    yolo: bool = typer.Option(False, "--yolo", "-y", help="Enable YOLO mode (auto-approve)"),
):
    """Execute a specific task by ID."""
    db_url = database_url or get_database_url()
    
    console.print(Panel(
        f"[bold blue]Executing Task[/bold blue]\n"
        f"Task ID: {task_id}",
        border_style="blue"
    ))
    
    try:
        # Create executor
        executor = TaskExecutor(database_url=db_url)
        
        # Execute task
        result = executor.execute(task_id)
        
        if result == ExecutionResult.SUCCESS:
            console.print("[bold green]✓ Task completed successfully[/bold green]")
        elif result == ExecutionResult.RETRY:
            console.print("[yellow]⚠ Task failed but will be retried[/yellow]")
        elif result == ExecutionResult.CANCELLED:
            console.print("[yellow]⚠ Task was cancelled by user[/yellow]")
        else:
            console.print("[bold red]✗ Task failed[/bold red]")
            raise typer.Exit(1)
            
    except Exception as e:
        console.print(f"[bold red]✗ Execution failed: {e}[/bold red]")
        logger.error(f"Task execution failed: {e}")
        raise typer.Exit(1)


@app.command()
def spec(
    spec_path: Path = typer.Argument(..., help="Path to spec YAML file", exists=True),
    project_name: Optional[str] = typer.Option(None, "--project", "-p", help="Project name (required if not in spec)"),
    database_url: Optional[str] = typer.Option(None, "--database-url", "-d", help="Database URL"),
    yolo: bool = typer.Option(False, "--yolo", "-y", help="Enable YOLO mode"),
    priority: int = typer.Option(5, "--priority", help="Task priority (1-10, lower is higher)"),
):
    """Execute a task directly from a spec file."""
    import uuid
    from vps_dev_agent.core.spec_parser import SpecParser
    from vps_dev_agent.core.para_models import Project
    
    db_url = database_url or get_database_url()
    
    # Parse spec first
    parser = SpecParser(spec_path)
    try:
        spec = parser.load()
    except Exception as e:
        console.print(f"[red]Failed to parse spec: {e}[/red]")
        raise typer.Exit(1)
    
    # Get database session
    db = DatabaseManager(db_url)
    session = db.get_session()
    
    try:
        # Find or use project
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
        )
        
        session.add(task)
        session.commit()
        
        console.print(f"[green]✓ Task created: {task_id}[/green]")
        
        # Execute
        session.close()  # Close before execution
        
        executor = TaskExecutor(database_url=db_url)
        result = executor.execute(str(task_id))
        
        if result == ExecutionResult.SUCCESS:
            console.print("[bold green]✓ Task completed successfully[/bold green]")
        elif result == ExecutionResult.CANCELLED:
            console.print("[yellow]⚠ Task was cancelled[/yellow]")
        else:
            console.print("[bold red]✗ Task failed[/bold red]")
            raise typer.Exit(1)
            
    except Exception as e:
        session.rollback()
        console.print(f"[bold red]✗ Failed: {e}[/bold red]")
        raise typer.Exit(1)
    
    finally:
        session.close()


@app.command()
def next(
    database_url: Optional[str] = typer.Option(None, "--database-url", "-d", help="Database URL"),
    yolo: bool = typer.Option(False, "--yolo", "-y", help="Enable YOLO mode"),
):
    """Execute the next pending task from the queue."""
    db_url = database_url or get_database_url()
    db = DatabaseManager(db_url)
    session = db.get_session()
    
    try:
        # Find next pending task with highest priority
        task = session.query(Task).filter_by(
            status=TaskStatus.PENDING
        ).order_by(
            Task.priority.asc(),
            Task.created_at.asc()
        ).first()
        
        if not task:
            console.print("[yellow]No pending tasks in queue[/yellow]")
            raise typer.Exit(0)
        
        console.print(f"[blue]Found task: {task.id} (priority: {task.priority})[/blue]")
        session.close()
        
        # Execute
        executor = TaskExecutor(database_url=db_url)
        result = executor.execute(str(task.id))
        
        if result == ExecutionResult.SUCCESS:
            console.print("[bold green]✓ Task completed successfully[/bold green]")
        elif result == ExecutionResult.CANCELLED:
            console.print("[yellow]⚠ Task was cancelled[/yellow]")
        else:
            console.print("[bold red]✗ Task failed[/bold red]")
            raise typer.Exit(1)
            
    except Exception as e:
        console.print(f"[bold red]✗ Failed: {e}[/bold red]")
        raise typer.Exit(1)
    
    finally:
        session.close()
