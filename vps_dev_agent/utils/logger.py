"""Structured logging utilities."""

import logging
import sys
from datetime import datetime
from typing import Optional

from rich.console import Console
from rich.logging import RichHandler
from rich.theme import Theme

# Custom theme for different log levels
theme = Theme({
    "info": "cyan",
    "warning": "yellow",
    "error": "red bold",
    "critical": "red bold reverse",
    "success": "green",
})

console = Console(theme=theme)


class AgentLogger:
    """Structured logger for VPS Dev Agent."""
    
    def __init__(self, name: str = "vps_dev_agent", level: int = logging.INFO):
        self.logger = logging.getLogger(name)
        self.logger.setLevel(level)
        
        # Clear existing handlers
        self.logger.handlers.clear()
        
        # Rich handler for pretty console output
        rich_handler = RichHandler(
            console=console,
            rich_tracebacks=True,
            show_path=False,
            show_time=True,
        )
        rich_handler.setLevel(level)
        
        # File handler for persistent logs
        file_handler = logging.FileHandler(f"agent_{datetime.now():%Y%m%d}.log")
        file_handler.setLevel(logging.DEBUG)
        file_formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(funcName)s:%(lineno)d - %(message)s"
        )
        file_handler.setFormatter(file_formatter)
        
        self.logger.addHandler(rich_handler)
        self.logger.addHandler(file_handler)
    
    def info(self, message: str, **kwargs):
        """Log info message."""
        self._log(logging.INFO, message, **kwargs)
    
    def debug(self, message: str, **kwargs):
        """Log debug message."""
        self._log(logging.DEBUG, message, **kwargs)
    
    def warning(self, message: str, **kwargs):
        """Log warning message."""
        self._log(logging.WARNING, message, **kwargs)
    
    def error(self, message: str, **kwargs):
        """Log error message."""
        self._log(logging.ERROR, message, **kwargs)
    
    def critical(self, message: str, **kwargs):
        """Log critical message."""
        self._log(logging.CRITICAL, message, **kwargs)
    
    def success(self, message: str, **kwargs):
        """Log success message (custom level)."""
        self._log(logging.INFO, f"[success]✓[/success] {message}", **kwargs)
    
    def _log(self, level: int, message: str, **kwargs):
        """Internal log method with extra context."""
        if kwargs:
            extra_str = " | ".join(f"{k}={v}" for k, v in kwargs.items())
            message = f"{message} [{extra_str}]"
        self.logger.log(level, message)


# Global logger instance
_logger: Optional[AgentLogger] = None


def get_logger() -> AgentLogger:
    """Get or create global logger instance."""
    global _logger
    if _logger is None:
        _logger = AgentLogger()
    return _logger
