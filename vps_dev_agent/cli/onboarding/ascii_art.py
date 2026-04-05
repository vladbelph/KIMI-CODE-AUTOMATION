"""ASCII art renderer for onboarding."""

from typing import Optional
from rich.console import Console
from rich.panel import Panel
from rich.text import Text
from rich.align import Align

# Full logo ASCII art
FULL_LOGO = r"""
╔══════════════════════════════════════════════════════════╗
║                                                          ║
║   ██╗   ██╗██████╗ ███████╗    ██████╗ ███████╗██╗   ██╗ ║
║   ██║   ██║██╔══██╗██╔════╝    ██╔══██╗██╔════╝██║   ██║ ║
║   ██║   ██║██████╔╝███████╗    ██║  ██║█████╗  ██║   ██║ ║
║   ╚██╗ ██╔╝██╔═══╝ ╚════██║    ██║  ██║██╔══╝  ╚██╗ ██╔╝ ║
║    ╚████╔╝ ██║     ███████║    ██████╔╝███████╗ ╚████╔╝  ║
║     ╚═══╝  ╚═╝     ╚══════╝    ╚═════╝ ╚══════╝  ╚═══╝   ║
║                                                          ║
║         Autonomous AI Agent for Your VPS                 ║
║                                                          ║
╚══════════════════════════════════════════════════════════╝
"""

# Compact logo for brief mode
COMPACT_LOGO = r"""
┌─────────────────────────────────────┐
│  ██╗   ██╗██████╗ ███████╗     ██████╗ ███████╗██╗   ██╗ │
│  ╚██╗ ██╔╝██╔═══╝ ╚════██║     ██╔══██╗██╔════╝██║   ██║ │
│   ╚████╔╝ ██║     ███████║     ██████╔╝███████╗██║   ██║ │
│    ╚═══╝  ╚═╝     ╚══════╝     ╚═════╝ ╚══════╝╚═╝   ╚═╝ │
│              VPS Dev Agent v{version:8}              │
└─────────────────────────────────────┘
"""

# Minimal text logo
MINIMAL_LOGO = "[bold cyan]VPS[/bold cyan] [bold magenta]Dev[/bold magenta] [bold green]Agent[/bold green]"

# Taglines
TAGLINES = [
    "Your AI developer that never sleeps",
    "Write specs, not code",
    "Kimi Code CLI integration ready",
    "PARA methodology powered",
]

# Tips for brief mode
TIPS = [
    "Use --yolo flag to skip confirmations",
    "Set up areas to organize your project knowledge",
    "Check 'agent status limits' to monitor Kimi quota",
    "Use 'agent doctor' to troubleshoot issues",
    "Use 'agent batch run --continuous' for unattended execution",
    "Create areas like 'Database', 'API', 'Frontend' to organize knowledge",
    "Add validation commands to your specs for automatic testing",
]


class ASCIIRenderer:
    """Renders ASCII art and styled text for onboarding."""
    
    def __init__(self, console: Optional[Console] = None):
        self.console = console or Console()
    
    def clear_screen(self):
        """Clear the terminal screen."""
        self.console.clear()
    
    def render_logo(self, style: str = "full", version: str = "1.3.0"):
        """Render the logo in specified style.
        
        Args:
            style: 'full', 'compact', or 'minimal'
            version: Version string for compact logo
        """
        if style == "full":
            self.console.print(FULL_LOGO, style="cyan")
        elif style == "compact":
            logo = COMPACT_LOGO.format(version=version)
            self.console.print(logo, style="cyan")
        else:  # minimal
            self.console.print(MINIMAL_LOGO)
    
    def render_box(self, text: str, title: Optional[str] = None, border_style: str = "cyan"):
        """Render text in a styled box.
        
        Args:
            text: Content to display
            title: Optional title for the box
            border_style: Color for the border
        """
        panel = Panel(
            text,
            title=title,
            border_style=border_style,
            padding=(1, 2),
        )
        self.console.print(panel)
    
    def render_welcome(self, version: str = "1.3.0"):
        """Render full welcome screen."""
        self.clear_screen()
        self.render_logo("full")
        
        welcome_text = Text()
        welcome_text.append(f"\nWelcome to VPS Dev Agent v{version}\n", style="bold cyan")
        welcome_text.append(
            "\nThis tool will help you automate software development using AI.\n",
            style="white"
        )
        welcome_text.append(
            "It works with Kimi Code CLI, OpenAI, Anthropic, and other providers.\n",
            style="dim white"
        )
        
        self.console.print(Align.center(welcome_text))
    
    def render_step_header(self, step_number: int, total_steps: int, title: str):
        """Render step header with progress.
        
        Args:
            step_number: Current step (1-based)
            total_steps: Total number of steps
            title: Step title
        """
        from rich.progress import Progress, TextColumn, BarColumn
        
        progress_text = f"Step {step_number}/{total_steps}: {title}"
        self.console.print(f"\n[bold cyan]{progress_text}[/bold cyan]")
        
        # Progress bar
        progress = Progress(
            TextColumn("[progress.description]{task.description}"),
            BarColumn(bar_width=40),
            console=self.console,
        )
        
        with progress:
            task = progress.add_task("", total=total_steps)
            progress.update(task, completed=step_number)
    
    def render_success(self, message: str):
        """Render success message."""
        self.console.print(f"[bold green]✓ {message}[/bold green]")
    
    def render_warning(self, message: str):
        """Render warning message."""
        self.console.print(f"[bold yellow]⚠ {message}[/bold yellow]")
    
    def render_error(self, message: str):
        """Render error message."""
        self.console.print(f"[bold red]✗ {message}[/bold red]")
    
    def render_info(self, message: str):
        """Render info message."""
        self.console.print(f"[cyan]ℹ {message}[/cyan]")
    
    def render_tip(self, tip: Optional[str] = None):
        """Render a tip. If no tip provided, pick random one."""
        import random
        
        if tip is None:
            tip = random.choice(TIPS)
        
        self.console.print(f"\n[dim]💡 Tip: {tip}[/dim]")
    
    def render_finish_screen(self, version: str = "1.3.0"):
        """Render finish screen."""
        self.clear_screen()
        self.render_logo("compact", version)
        
        finish_text = """
[bold green]🚀 You're All Set![/bold green]

Next steps:

1. Create a task:    [bold cyan]agent queue add example-task.yaml[/bold cyan]
2. Run batch:        [bold cyan]agent batch run --continuous[/bold cyan]
3. Check status:     [bold cyan]agent status dashboard[/bold cyan]

Documentation: https://github.com/vladbelph/KIMI-CODE-AUTOMATION
"""
        self.console.print(finish_text)


def get_random_tagline() -> str:
    """Get a random tagline."""
    import random
    return random.choice(TAGLINES)


def get_random_tip() -> str:
    """Get a random tip."""
    import random
    return random.choice(TIPS)
