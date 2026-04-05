"""Interactive onboarding wizard."""

import time
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.prompt import Prompt, Confirm
from rich.panel import Panel
from rich.align import Align

from vps_dev_agent.cli.onboarding.ascii_art import ASCIIRenderer, get_random_tagline
from vps_dev_agent.cli.onboarding.checker import PrerequisiteChecker, CheckStatus
from vps_dev_agent.cli.onboarding.config import ConfigInitializer, DatabaseConfig
from vps_dev_agent.utils.logger import get_logger

logger = get_logger()


class OnboardingWizard:
    """Interactive onboarding wizard for first-run experience."""
    
    VERSION = "1.3.0"
    TOTAL_STEPS = 7
    
    def __init__(self, console: Optional[Console] = None, force: bool = False):
        self.console = console or Console()
        self.renderer = ASCIIRenderer(self.console)
        self.checker = PrerequisiteChecker(self.console)
        self.config = ConfigInitializer(self.console)
        self.force = force
        
        self.step = 0
        self.project_created = False
        self.project_path: Optional[Path] = None
    
    def run(self) -> bool:
        """Run the full onboarding wizard.
        
        Returns:
            True if onboarding completed successfully
        """
        # Check if already configured and not forced
        if not self.force and not self.config.is_first_run():
            self.renderer.render_info("Already configured. Use --force to re-run onboarding.")
            return True
        
        try:
            # Step 1: Splash screen
            self._step_splash()
            
            # Step 2: Prerequisites check
            if not self._step_prerequisites():
                return False
            
            # Step 3: Database setup
            if not self._step_database():
                return False
            
            # Step 4: Kimi auth (optional)
            self._step_kimi_auth()
            
            # Step 5: First project (optional)
            self._step_project()
            
            # Step 6: Sample spec (if project created)
            if self.project_created:
                self._step_sample_spec()
            
            # Step 7: Finish
            self._step_finish()
            
            return True
            
        except KeyboardInterrupt:
            self.console.print("\n[yellow]Onboarding cancelled.[/yellow]")
            return False
        except Exception as e:
            logger.error(f"Onboarding failed: {e}")
            self.renderer.render_error(f"Onboarding failed: {e}")
            return False
    
    def _step_splash(self):
        """Step 1: Splash screen."""
        self.step = 1
        self.renderer.render_welcome(self.VERSION)
        
        # Show random tagline
        tagline = get_random_tagline()
        self.console.print(Align.center(f"[dim italic]{tagline}[/dim italic]"))
        
        time.sleep(0.5)
        
        # Wait for user
        self.console.print("\n")
        Confirm.ask("Press Enter to continue", default=True, show_default=False)
    
    def _step_prerequisites(self) -> bool:
        """Step 2: Prerequisites check.
        
        Returns:
            True if all required prerequisites passed
        """
        self.step = 2
        self.renderer.clear_screen()
        self.renderer.render_step_header(self.step, self.TOTAL_STEPS, "Checking Prerequisites")
        
        # Run checks
        self.checker.run_all_checks()
        self.checker.display_results()
        
        if not self.checker.all_required_passed():
            self.renderer.render_error("Some required prerequisites are missing.")
            self.renderer.render_info("Please install the missing components and try again.")
            return False
        
        self.renderer.render_success("All required prerequisites satisfied")
        time.sleep(1)
        return True
    
    def _step_database(self) -> bool:
        """Step 3: Database setup.
        
        Returns:
            True if database configured successfully
        """
        self.step = 3
        
        # Check if already configured
        if self.config.has_database_config() and not self.force:
            self.renderer.render_info("Database already configured")
            return True
        
        self.renderer.clear_screen()
        self.renderer.render_step_header(self.step, self.TOTAL_STEPS, "Database Configuration")
        
        # Interactive setup
        db_config = self.config.setup_database_interactive()
        
        if db_config is None:
            self.renderer.render_error("Database configuration is required")
            return False
        
        # Save configuration
        self.config.save_env_file(db_config)
        self.renderer.render_success(f"Configuration saved to {self.config.ENV_FILE}")
        
        time.sleep(1)
        return True
    
    def _step_kimi_auth(self):
        """Step 4: Kimi auth setup (optional)."""
        self.step = 4
        
        # Check if Kimi is installed
        installed, message = self.checker.get_kimi_status()
        
        if not installed:
            self.renderer.render_info("Kimi CLI not installed (optional). Skipping auth setup.")
            return
        
        self.renderer.clear_screen()
        self.renderer.render_step_header(self.step, self.TOTAL_STEPS, "Kimi Code CLI Setup")
        
        # Check if already authenticated
        from vps_dev_agent.bridges.kimi_cli import KimiAuthChecker
        auth_checker = KimiAuthChecker()
        
        if auth_checker.is_session_valid():
            self.renderer.render_success("Kimi CLI already authenticated")
            return
        
        # Show auth instructions
        self.console.print(Panel(
            "[yellow]Kimi CLI detected but not authenticated[/yellow]\n\n"
            "To use Kimi Code CLI integration, you need to authenticate.\n\n"
            "[bold]Instructions:[/bold]\n"
            "1. Visit: https://kimi.moonshot.cn/auth/device\n"
            "2. Or run: [cyan]kimi login[/cyan] in another terminal\n\n"
            "Would you like to authenticate now?",
            border_style="yellow"
        ))
        
        if Confirm.ask("Authenticate now?", default=True):
            self.console.print("\n[cyan]Waiting for authentication...[/cyan]")
            self.console.print("[dim]Run 'kimi login' in another terminal if not opened automatically[/dim]\n")
            
            # Try to open browser or run login
            import subprocess
            try:
                subprocess.Popen(["kimi", "login"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            except:
                pass
            
            # Wait with spinner
            from rich.progress import Progress, SpinnerColumn, TextColumn
            
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                console=self.console,
            ) as progress:
                task = progress.add_task("Waiting for authentication...", total=None)
                
                # Poll for auth status
                import time
                for _ in range(60):  # Max 60 seconds
                    time.sleep(1)
                    if auth_checker.is_session_valid():
                        progress.update(task, completed=True)
                        break
            
            if auth_checker.is_session_valid():
                self.renderer.render_success("Authentication successful!")
            else:
                self.renderer.render_warning("Authentication not completed. You can run 'kimi login' later.")
        
        time.sleep(1)
    
    def _step_project(self):
        """Step 5: First project setup (optional)."""
        self.step = 5
        
        self.renderer.clear_screen()
        self.renderer.render_step_header(self.step, self.TOTAL_STEPS, "First Project Setup")
        
        self.console.print(Panel(
            "Would you like to set up your first project now?\n\n"
            "A project represents a codebase that the agent will work on.",
            border_style="cyan"
        ))
        
        if not Confirm.ask("Set up a project?", default=True):
            return
        
        # Get project details
        name = Prompt.ask(
            "Project name",
            console=self.console
        )
        
        if not name:
            self.renderer.render_warning("Project name cannot be empty. Skipping.")
            return
        
        # Get project path
        import os
        default_path = str(Path.cwd() / name)
        
        path_str = Prompt.ask(
            "Repository path",
            default=default_path,
            console=self.console
        )
        
        path = Path(path_str).expanduser().resolve()
        
        # Validate path
        if not path.exists():
            self.console.print(f"[yellow]Path does not exist. Create it?[/yellow]")
            if Confirm.ask("Create directory?", default=True):
                path.mkdir(parents=True, exist_ok=True)
            else:
                self.renderer.render_warning("Skipping project setup")
                return
        
        # Create project using CLI command
        try:
            import subprocess
            result = subprocess.run(
                ["agent", "init", "project", name, "--repo", str(path)],
                capture_output=True,
                text=True,
            )
            
            if result.returncode == 0:
                self.project_created = True
                self.project_path = path
                self.renderer.render_success(f"Project '{name}' created successfully")
            else:
                self.renderer.render_warning(f"Could not create project: {result.stderr}")
                
        except Exception as e:
            self.renderer.render_warning(f"Could not create project: {e}")
        
        time.sleep(1)
    
    def _step_sample_spec(self):
        """Step 6: Create sample task spec."""
        self.step = 6
        
        if not self.project_path:
            return
        
        self.renderer.clear_screen()
        self.renderer.render_step_header(self.step, self.TOTAL_STEPS, "Sample Task")
        
        self.console.print("Creating a sample task spec in your project...")
        
        try:
            spec_path = self.config.create_sample_spec(self.project_path)
            self.renderer.render_success(f"Sample spec created: {spec_path}")
        except Exception as e:
            logger.error(f"Could not create sample spec: {e}")
    
    def _step_finish(self):
        """Step 7: Finish screen."""
        self.step = 7
        
        self.renderer.render_finish_screen(self.VERSION)
        
        # Show tip
        self.renderer.render_tip()
        
        time.sleep(1)


def run_onboarding(force: bool = False) -> bool:
    """Run onboarding wizard.
    
    Args:
        force: Force re-run even if already configured
        
    Returns:
        True if onboarding completed successfully
    """
    wizard = OnboardingWizard(force=force)
    return wizard.run()


def show_brief_mode():
    """Show brief welcome for subsequent runs."""
    from rich.console import Console
    from rich.text import Text
    
    console = Console()
    
    # Minimal logo
    console.print("\n[bold cyan]VPS[/bold cyan] [bold magenta]Dev[/bold magenta] [bold green]Agent[/bold green] [dim]v1.3.0[/dim]\n")
    
    # Quick stats
    try:
        from vps_dev_agent.core.para_models import DatabaseManager, Task, TaskStatus, Project
        from vps_dev_agent.cli.onboarding.config import ConfigInitializer
        
        config = ConfigInitializer()
        db_url = config.get_database_url()
        
        if db_url:
            db = DatabaseManager(db_url)
            session = db.get_session()
            
            try:
                pending = session.query(Task).filter_by(status=TaskStatus.PENDING).count()
                projects = session.query(Project).count()
                
                stats = Text()
                stats.append("Queue: ", style="dim")
                stats.append(str(pending), style="cyan" if pending == 0 else "yellow")
                stats.append(" pending | ", style="dim")
                stats.append("Projects: ", style="dim")
                stats.append(str(projects), style="green")
                
                console.print(stats)
            finally:
                session.close()
    except:
        pass
    
    # Tip
    renderer = ASCIIRenderer(console)
    renderer.render_tip()
    
    console.print()


def check_first_run() -> bool:
    """Check if this is the first run.
    
    Returns:
        True if first run (no config exists)
    """
    config = ConfigInitializer()
    return config.is_first_run()
