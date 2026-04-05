"""Prerequisite checker for onboarding."""

import re
import subprocess
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass
from enum import Enum

from rich.console import Console
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn

from vps_dev_agent.utils.logger import get_logger

logger = get_logger()


class CheckStatus(Enum):
    """Status of a prerequisite check."""
    PASS = "pass"
    FAIL = "fail"
    WARNING = "warning"
    SKIP = "skip"


@dataclass
class PrerequisiteResult:
    """Result of a prerequisite check."""
    name: str
    status: CheckStatus
    version: Optional[str] = None
    message: Optional[str] = None
    fix_command: Optional[str] = None
    fix_message: Optional[str] = None
    optional: bool = False


class PrerequisiteChecker:
    """Checks system prerequisites for VPS Dev Agent."""
    
    # Minimum required versions
    MIN_PYTHON_VERSION = (3, 11)
    
    def __init__(self, console: Optional[Console] = None):
        self.console = console or Console()
        self.results: List[PrerequisiteResult] = []
    
    def run_all_checks(self) -> List[PrerequisiteResult]:
        """Run all prerequisite checks."""
        self.results = []
        
        checks = [
            ("Python 3.11+", self._check_python, False),
            ("PostgreSQL", self._check_postgresql, False),
            ("Git", self._check_git, False),
            ("Kimi Code CLI", self._check_kimi, True),
        ]
        
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=self.console,
        ) as progress:
            for name, check_func, optional in checks:
                task = progress.add_task(f"Checking {name}...", total=None)
                result = check_func()
                result.optional = optional
                self.results.append(result)
                progress.update(task, completed=True)
        
        return self.results
    
    def display_results(self):
        """Display check results in a table."""
        table = Table(title="🔍 Prerequisites Check")
        table.add_column("Component", style="cyan")
        table.add_column("Status", style="bold")
        table.add_column("Version/Info", style="green")
        table.add_column("Required", style="dim")
        
        for result in self.results:
            # Status icon and color
            if result.status == CheckStatus.PASS:
                status_text = "[green]✓ PASS[/green]"
            elif result.status == CheckStatus.WARNING:
                status_text = "[yellow]! WARN[/yellow]"
            elif result.optional:
                status_text = "[dim]○ SKIP[/dim]"
            else:
                status_text = "[red]✗ FAIL[/red]"
            
            # Required column
            required_text = "Optional" if result.optional else "Yes"
            if not result.optional and result.status == CheckStatus.FAIL:
                required_text = "[red]REQUIRED[/red]"
            
            version_text = result.version or result.message or "-"
            
            table.add_row(
                result.name,
                status_text,
                version_text,
                required_text,
            )
        
        self.console.print(table)
        
        # Show fix instructions for failed checks
        failed_required = [
            r for r in self.results 
            if r.status == CheckStatus.FAIL and not r.optional
        ]
        
        if failed_required:
            self.console.print("\n[bold red]Fix required:[/bold red]")
            for result in failed_required:
                if result.fix_message:
                    self.console.print(f"  [red]• {result.name}:[/red] {result.fix_message}")
                if result.fix_command:
                    self.console.print(f"    [dim]Run: {result.fix_command}[/dim]")
    
    def all_required_passed(self) -> bool:
        """Check if all required prerequisites passed."""
        if not self.results:
            self.run_all_checks()
        
        for result in self.results:
            if not result.optional and result.status != CheckStatus.PASS:
                return False
        return True
    
    def _check_python(self) -> PrerequisiteResult:
        """Check Python version."""
        try:
            result = subprocess.run(
                ["python", "--version"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            
            output = result.stdout.strip() or result.stderr.strip()
            
            # Parse version (e.g., "Python 3.11.4")
            version_match = re.search(r'(\d+)\.(\d+)\.(\d+)', output)
            if version_match:
                major = int(version_match.group(1))
                minor = int(version_match.group(2))
                version = f"{major}.{minor}.{version_match.group(3)}"
                
                if (major, minor) >= self.MIN_PYTHON_VERSION:
                    return PrerequisiteResult(
                        name="Python 3.11+",
                        status=CheckStatus.PASS,
                        version=version,
                    )
                else:
                    return PrerequisiteResult(
                        name="Python 3.11+",
                        status=CheckStatus.FAIL,
                        version=version,
                        message=f"Found {version}, need 3.11+",
                        fix_message="Please upgrade Python to 3.11 or higher",
                    )
            else:
                return PrerequisiteResult(
                    name="Python 3.11+",
                    status=CheckStatus.FAIL,
                    message="Could not parse version",
                )
                
        except FileNotFoundError:
            return PrerequisiteResult(
                name="Python 3.11+",
                status=CheckStatus.FAIL,
                message="Python not found",
                fix_message="Install Python 3.11 or higher",
            )
        except Exception as e:
            return PrerequisiteResult(
                name="Python 3.11+",
                status=CheckStatus.FAIL,
                message=str(e),
            )
    
    def _check_postgresql(self) -> PrerequisiteResult:
        """Check PostgreSQL installation."""
        try:
            result = subprocess.run(
                ["psql", "--version"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            
            if result.returncode == 0:
                output = result.stdout.strip()
                # Parse version (e.g., "psql (PostgreSQL) 14.5")
                version_match = re.search(r'(\d+\.\d+)', output)
                version = version_match.group(1) if version_match else "installed"
                
                return PrerequisiteResult(
                    name="PostgreSQL",
                    status=CheckStatus.PASS,
                    version=version,
                )
            else:
                return PrerequisiteResult(
                    name="PostgreSQL",
                    status=CheckStatus.FAIL,
                    message="PostgreSQL client returned error",
                    fix_command="apt install postgresql postgresql-contrib",
                    fix_message="Install PostgreSQL",
                )
                
        except FileNotFoundError:
            return PrerequisiteResult(
                name="PostgreSQL",
                status=CheckStatus.FAIL,
                message="psql not found",
                fix_command="apt install postgresql postgresql-contrib",
                fix_message="Install PostgreSQL",
            )
        except Exception as e:
            return PrerequisiteResult(
                name="PostgreSQL",
                status=CheckStatus.FAIL,
                message=str(e),
            )
    
    def _check_git(self) -> PrerequisiteResult:
        """Check Git installation."""
        try:
            result = subprocess.run(
                ["git", "--version"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            
            if result.returncode == 0:
                output = result.stdout.strip()
                # Parse version (e.g., "git version 2.34.1")
                version_match = re.search(r'(\d+\.\d+\.\d+)', output)
                version = version_match.group(1) if version_match else "installed"
                
                return PrerequisiteResult(
                    name="Git",
                    status=CheckStatus.PASS,
                    version=version,
                )
            else:
                return PrerequisiteResult(
                    name="Git",
                    status=CheckStatus.FAIL,
                    message="Git returned error",
                    fix_command="apt install git",
                )
                
        except FileNotFoundError:
            return PrerequisiteResult(
                name="Git",
                status=CheckStatus.FAIL,
                message="Git not found",
                fix_command="apt install git",
            )
        except Exception as e:
            return PrerequisiteResult(
                name="Git",
                status=CheckStatus.FAIL,
                message=str(e),
            )
    
    def _check_kimi(self) -> PrerequisiteResult:
        """Check Kimi Code CLI installation."""
        try:
            result = subprocess.run(
                ["kimi", "--version"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            
            if result.returncode == 0:
                output = result.stdout.strip()
                # Try to extract version
                version_match = re.search(r'(\d+\.\d+\.?\d*)', output)
                version = version_match.group(1) if version_match else "installed"
                
                return PrerequisiteResult(
                    name="Kimi Code CLI",
                    status=CheckStatus.PASS,
                    version=version,
                )
            else:
                return PrerequisiteResult(
                    name="Kimi Code CLI",
                    status=CheckStatus.WARNING,
                    message="Installed but returned error",
                    fix_message="Run 'kimi login' to authenticate",
                )
                
        except FileNotFoundError:
            return PrerequisiteResult(
                name="Kimi Code CLI",
                status=CheckStatus.WARNING,
                message="Not installed (optional)",
                fix_command="curl -fsSL https://kimi.moonshot.cn/install.sh | sh",
                fix_message="Install from https://kimi.moonshot.cn/download",
                optional=True,
            )
        except Exception as e:
            return PrerequisiteResult(
                name="Kimi Code CLI",
                status=CheckStatus.WARNING,
                message=str(e),
                optional=True,
            )
    
    def get_kimi_status(self) -> Tuple[bool, Optional[str]]:
        """Get Kimi CLI status separately.
        
        Returns:
            (installed, version or error message)
        """
        for result in self.results:
            if result.name == "Kimi Code CLI":
                installed = result.status in (CheckStatus.PASS, CheckStatus.WARNING)
                return installed, result.version or result.message
        
        # Check if not already in results
        result = self._check_kimi()
        installed = result.status in (CheckStatus.PASS, CheckStatus.WARNING)
        return installed, result.version or result.message
