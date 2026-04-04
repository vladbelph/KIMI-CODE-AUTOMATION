"""Initialize command."""

import os
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn

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


@app.command(name="db")
def init_database(
    database_url: Optional[str] = typer.Option(None, "--database-url", "-d", help="PostgreSQL database URL"),
    force: bool = typer.Option(False, "--force", "-f", help="Drop existing tables"),
):
    """Initialize PostgreSQL database with PARA schema."""
    db_url = database_url or get_database_url()
    
    console.print(Panel(
        f"[bold blue]Initializing Database[/bold blue]\n"
        f"URL: {db_url.replace('://', '://***:***@') if '://' in db_url else db_url}",
        border_style="blue"
    ))
    
    try:
        db = DatabaseManager(db_url)
        
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            
            if force:
                task = progress.add_task("Dropping existing tables...", total=None)
                db.drop_tables()
                progress.update(task, completed=True)
            
            task = progress.add_task("Creating tables...", total=None)
            db.create_tables()
            progress.update(task, completed=True)
        
        console.print("[bold green]✓ Database initialized successfully[/bold green]")
        
    except Exception as e:
        console.print(f"[bold red]✗ Failed to initialize database: {e}[/bold red]")
        logger.error(f"Database initialization failed: {e}")
        raise typer.Exit(1)


@app.command(name="project")
def init_project(
    name: str = typer.Argument(..., help="Project name"),
    repo_path: Path = typer.Option(Path("."), "--repo", "-r", help="Repository path"),
    spec_path: Optional[Path] = typer.Option(None, "--spec", "-s", help="Default spec path"),
    database_url: Optional[str] = typer.Option(None, "--database-url", "-d", help="Database URL"),
):
    """Register a new project in the database."""
    import uuid
    from vps_dev_agent.core.para_models import Project
    
    db_url = database_url or get_database_url()
    db = DatabaseManager(db_url)
    
    session = db.get_session()
    
    try:
        # Check if project exists
        existing = session.query(Project).filter_by(name=name).first()
        if existing:
            console.print(f"[yellow]Project '{name}' already exists (ID: {existing.id})[/yellow]")
            raise typer.Exit(0)
        
        # Resolve repo path
        repo_path = repo_path.resolve()
        
        # Create project
        project = Project(
            id=uuid.uuid4(),
            name=name,
            repo_path=str(repo_path),
            spec_path=str(spec_path) if spec_path else None,
            status="active",
        )
        
        session.add(project)
        session.commit()
        
        console.print(Panel(
            f"[bold green]✓ Project created[/bold green]\n\n"
            f"Name: {name}\n"
            f"ID: {project.id}\n"
            f"Path: {repo_path}",
            border_style="green"
        ))
        
    except Exception as e:
        session.rollback()
        console.print(f"[bold red]✗ Failed to create project: {e}[/bold red]")
        raise typer.Exit(1)
    
    finally:
        session.close()


@app.command(name="area")
def init_area(
    project_name: str = typer.Argument(..., help="Project name"),
    name: str = typer.Argument(..., help="Area name"),
    description: Optional[str] = typer.Option(None, "--description", "-d", help="Area description"),
    scope: Optional[str] = typer.Option(None, "--scope", "-s", help="Responsibility scope"),
    database_url: Optional[str] = typer.Option(None, "--database-url", help="Database URL"),
):
    """Create a new area in a project."""
    import uuid
    from vps_dev_agent.core.para_models import Project, Area
    
    db_url = database_url or get_database_url()
    db = DatabaseManager(db_url)
    session = db.get_session()
    
    try:
        # Find project
        project = session.query(Project).filter_by(name=project_name).first()
        if not project:
            console.print(f"[red]Project '{project_name}' not found[/red]")
            raise typer.Exit(1)
        
        # Create area
        area = Area(
            id=uuid.uuid4(),
            project_id=project.id,
            name=name,
            description=description,
            responsibility_scope=scope,
        )
        
        session.add(area)
        session.commit()
        
        console.print(f"[green]✓ Area '{name}' created in project '{project_name}'[/green]")
        
    except Exception as e:
        session.rollback()
        console.print(f"[red]Failed to create area: {e}[/red]")
        raise typer.Exit(1)
    
    finally:
        session.close()
