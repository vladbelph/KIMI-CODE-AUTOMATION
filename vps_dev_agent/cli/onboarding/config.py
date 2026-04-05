"""Config initializer for onboarding."""

import os
import stat
from pathlib import Path
from typing import Optional, Dict, Any
from dataclasses import dataclass

from rich.console import Console
from rich.prompt import Prompt, Confirm
from rich.panel import Panel

from vps_dev_agent.utils.logger import get_logger

logger = get_logger()


@dataclass
class DatabaseConfig:
    """Database configuration."""
    host: str = "localhost"
    port: int = 5432
    database: str = "vps_dev_agent"
    username: str = "postgres"
    password: str = ""
    
    @property
    def connection_string(self) -> str:
        """Generate PostgreSQL connection string."""
        if self.password:
            return f"postgresql://{self.username}:{self.password}@{self.host}:{self.port}/{self.database}"
        else:
            return f"postgresql://{self.username}@{self.host}:{self.port}/{self.database}"


class ConfigInitializer:
    """Initializes configuration files for VPS Dev Agent."""
    
    CONFIG_DIR = Path.home() / ".vps_dev_agent"
    ENV_FILE = CONFIG_DIR / "config.env"
    YAML_FILE = CONFIG_DIR / "config.yaml"
    
    def __init__(self, console: Optional[Console] = None):
        self.console = console or Console()
    
    def ensure_config_dir(self):
        """Ensure config directory exists."""
        self.CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        # Set permissions to 700 (owner only)
        os.chmod(self.CONFIG_DIR, stat.S_IRWXU)
    
    def is_first_run(self) -> bool:
        """Check if this is the first run (no config exists)."""
        return not self.ENV_FILE.exists() and not self.YAML_FILE.exists()
    
    def setup_database_interactive(self) -> Optional[DatabaseConfig]:
        """Interactive database setup.
        
        Returns:
            DatabaseConfig if successful, None if cancelled
        """
        self.console.print(Panel(
            "[bold cyan]🗄️  Database Configuration[/bold cyan]\n\n"
            "Please enter your PostgreSQL connection details.",
            border_style="cyan"
        ))
        
        # Prompt for database details
        host = Prompt.ask(
            "Database host",
            default="localhost",
            console=self.console
        )
        
        database = Prompt.ask(
            "Database name",
            default="vps_dev_agent",
            console=self.console
        )
        
        username = Prompt.ask(
            "Username",
            default="postgres",
            console=self.console
        )
        
        password = Prompt.ask(
            "Password",
            password=True,
            console=self.console
        )
        
        port_str = Prompt.ask(
            "Port",
            default="5432",
            console=self.console
        )
        
        try:
            port = int(port_str)
        except ValueError:
            port = 5432
        
        config = DatabaseConfig(
            host=host,
            port=port,
            database=database,
            username=username,
            password=password,
        )
        
        # Test connection
        if self._test_database_connection(config):
            self.console.print("[bold green]✓ Database connection successful[/bold green]")
            return config
        else:
            self.console.print("[bold red]✗ Could not connect to database[/bold red]")
            if Confirm.ask("Try again?", console=self.console):
                return self.setup_database_interactive()
            return None
    
    def _test_database_connection(self, config: DatabaseConfig) -> bool:
        """Test database connection."""
        try:
            from sqlalchemy import create_engine, text
            
            engine = create_engine(
                config.connection_string,
                connect_args={'connect_timeout': 5},
            )
            
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
                return True
                
        except Exception as e:
            logger.error(f"Database connection failed: {e}")
            return False
    
    def save_env_file(self, config: DatabaseConfig):
        """Save configuration to env file."""
        self.ensure_config_dir()
        
        env_content = f"""# VPS Dev Agent Configuration
# Generated automatically

DATABASE_URL={config.connection_string}

# Optional: Default LLM provider
DEFAULT_PROVIDER=kimi_cli

# Optional: API keys for fallback providers
# OPENAI_API_KEY=your_key_here
# ANTHROPIC_API_KEY=your_key_here
# DEEPSEEK_API_KEY=your_key_here
"""
        
        self.ENV_FILE.write_text(env_content)
        # Set permissions to 600 (owner read/write only)
        os.chmod(self.ENV_FILE, stat.S_IRUSR | stat.S_IWUSR)
        
        logger.info(f"Configuration saved to {self.ENV_FILE}")
    
    def load_env_file(self) -> Dict[str, str]:
        """Load configuration from env file.
        
        Returns:
            Dictionary of environment variables
        """
        config = {}
        
        if self.ENV_FILE.exists():
            with open(self.ENV_FILE) as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#') and '=' in line:
                        key, value = line.split('=', 1)
                        config[key] = value
        
        return config
    
    def get_database_url(self) -> Optional[str]:
        """Get database URL from env file or environment."""
        # First check environment
        db_url = os.getenv("DATABASE_URL")
        if db_url:
            return db_url
        
        # Then check env file
        config = self.load_env_file()
        return config.get("DATABASE_URL")
    
    def create_sample_spec(self, project_path: Path) -> Path:
        """Create sample task spec in project.
        
        Args:
            project_path: Path to project directory
            
        Returns:
            Path to created spec file
        """
        spec_content = '''spec:
  goal: "Create a hello world API endpoint"
  
  instructions: |
    1. Create a simple HTTP server (Flask or FastAPI)
    2. Add /hello endpoint returning JSON {"message": "Hello, World!"}
    3. Add basic tests
    4. Include requirements.txt
  
  constraints:
    - "Use Python 3.11+"
    - "Follow PEP 8 style"
    - "Add type hints"
  
  expected_output: |
    - app.py - Main application file
    - test_app.py - Unit tests
    - requirements.txt - Dependencies
  
  security_mode: "conservative"
  
  validation:
    commands:
      - name: "install"
        command: "pip install -r requirements.txt"
        required: true
        timeout: 60
      - name: "test"
        command: "python -m pytest test_app.py -v"
        required: true
        timeout: 60
'''
        
        spec_path = project_path / "example-task.yaml"
        spec_path.write_text(spec_content)
        
        return spec_path
    
    def has_database_config(self) -> bool:
        """Check if database is configured."""
        return self.get_database_url() is not None
