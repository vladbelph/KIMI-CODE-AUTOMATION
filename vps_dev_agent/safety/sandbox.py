"""File system guards and sandbox restrictions."""

import os
import re
from pathlib import Path
from typing import List, Optional, Set
from dataclasses import dataclass

from vps_dev_agent.utils.logger import get_logger

logger = get_logger()


@dataclass
class PathValidation:
    """Path validation result."""
    is_valid: bool
    reason: Optional[str] = None
    resolved_path: Optional[Path] = None


class Sandbox:
    """File system sandbox for safe file operations."""
    
    # Dangerous paths that should never be touched
    DANGEROUS_PATHS = [
        "/", "/bin", "/boot", "/dev", "/etc", "/lib", "/lib64",
        "/proc", "/root", "/sbin", "/sys", "/usr", "/var",
        "C:\\Windows", "C:\\Program Files", "C:\\ProgramData",
    ]
    
    # Dangerous patterns in file paths
    DANGEROUS_PATTERNS = [
        r"\.\.",  # Parent directory traversal
        r"^~",    # Home directory expansion
        r"^\/",  # Absolute Unix paths (unless allowed)
    ]
    
    def __init__(
        self,
        project_root: str,
        allow_write_outside_project: bool = False,
        allowed_paths: Optional[List[str]] = None,
        blocked_patterns: Optional[List[str]] = None,
    ):
        self.project_root = Path(project_root).resolve()
        self.allow_write_outside_project = allow_write_outside_project
        self.allowed_paths: Set[Path] = set()
        self.blocked_patterns: List[re.Pattern] = []
        
        # Add allowed paths
        if allowed_paths:
            for path in allowed_paths:
                self.allowed_paths.add(Path(path).resolve())
        
        # Add custom blocked patterns
        if blocked_patterns:
            for pattern in blocked_patterns:
                self.blocked_patterns.append(re.compile(pattern))
    
    def _resolve_path(self, path: str) -> Path:
        """Resolve a path relative to project root."""
        input_path = Path(path)
        
        # If absolute, use as-is
        if input_path.is_absolute():
            return input_path.resolve()
        
        # Otherwise, resolve relative to project root
        return (self.project_root / input_path).resolve()
    
    def _is_path_within_project(self, path: Path) -> bool:
        """Check if path is within project root."""
        try:
            path.relative_to(self.project_root)
            return True
        except ValueError:
            return False
    
    def _is_dangerous_path(self, path: Path) -> bool:
        """Check if path is in dangerous system locations."""
        path_str = str(path).lower()
        
        for dangerous in self.DANGEROUS_PATHS:
            if path_str.startswith(dangerous.lower()):
                return True
        
        # Check dangerous patterns
        for pattern in self.DANGEROUS_PATTERNS:
            if re.search(pattern, str(path)):
                return True
        
        # Check custom blocked patterns
        for pattern in self.blocked_patterns:
            if pattern.search(str(path)):
                return True
        
        return False
    
    def validate_write_path(self, path: str) -> PathValidation:
        """Validate a path for write operations."""
        try:
            resolved = self._resolve_path(path)
        except Exception as e:
            return PathValidation(
                is_valid=False,
                reason=f"Invalid path: {e}"
            )
        
        # Check for dangerous paths
        if self._is_dangerous_path(resolved):
            return PathValidation(
                is_valid=False,
                reason=f"Path is in a dangerous system location: {resolved}"
            )
        
        # Check if outside project
        if not self._is_path_within_project(resolved):
            if not self.allow_write_outside_project:
                # Check if in explicitly allowed paths
                allowed = any(
                    resolved == allowed_path or resolved.is_relative_to(allowed_path)
                    for allowed_path in self.allowed_paths
                )
                if not allowed:
                    return PathValidation(
                        is_valid=False,
                        reason=f"Path outside project not allowed: {resolved}"
                    )
        
        # Ensure parent directory exists or can be created
        parent = resolved.parent
        if not parent.exists():
            try:
                # Check if we can create the parent
                parent.relative_to(self.project_root)
            except ValueError:
                if not self.allow_write_outside_project:
                    return PathValidation(
                        is_valid=False,
                        reason=f"Cannot create directory outside project: {parent}"
                    )
        
        return PathValidation(
            is_valid=True,
            resolved_path=resolved
        )
    
    def validate_read_path(self, path: str) -> PathValidation:
        """Validate a path for read operations."""
        try:
            resolved = self._resolve_path(path)
        except Exception as e:
            return PathValidation(
                is_valid=False,
                reason=f"Invalid path: {e}"
            )
        
        # Check if file exists
        if not resolved.exists():
            return PathValidation(
                is_valid=False,
                reason=f"File not found: {resolved}"
            )
        
        # Check for dangerous paths
        if self._is_dangerous_path(resolved):
            return PathValidation(
                is_valid=False,
                reason=f"Cannot read from dangerous path: {resolved}"
            )
        
        return PathValidation(
            is_valid=True,
            resolved_path=resolved
        )
    
    def safe_write(self, path: str, content: str, mode: str = "w") -> bool:
        """Safely write content to a file."""
        validation = self.validate_write_path(path)
        
        if not validation.is_valid:
            logger.error(f"Write validation failed: {validation.reason}")
            return False
        
        try:
            resolved = validation.resolved_path
            
            # Create parent directories if needed
            resolved.parent.mkdir(parents=True, exist_ok=True)
            
            # Write file
            with open(resolved, mode, encoding='utf-8') as f:
                f.write(content)
            
            logger.debug(f"Successfully wrote file: {resolved}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to write file: {e}")
            return False
    
    def safe_read(self, path: str) -> Optional[str]:
        """Safely read content from a file."""
        validation = self.validate_read_path(path)
        
        if not validation.is_valid:
            logger.error(f"Read validation failed: {validation.reason}")
            return None
        
        try:
            resolved = validation.resolved_path
            
            with open(resolved, 'r', encoding='utf-8') as f:
                content = f.read()
            
            logger.debug(f"Successfully read file: {resolved}")
            return content
            
        except Exception as e:
            logger.error(f"Failed to read file: {e}")
            return None
    
    def safe_delete(self, path: str) -> bool:
        """Safely delete a file."""
        validation = self.validate_read_path(path)
        
        if not validation.is_valid:
            logger.error(f"Delete validation failed: {validation.reason}")
            return False
        
        try:
            resolved = validation.resolved_path
            
            if resolved.is_file():
                resolved.unlink()
                logger.info(f"Deleted file: {resolved}")
                return True
            elif resolved.is_dir():
                # Only allow deleting empty directories within project
                if not self._is_path_within_project(resolved):
                    logger.error(f"Cannot delete directory outside project: {resolved}")
                    return False
                resolved.rmdir()
                logger.info(f"Deleted directory: {resolved}")
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"Failed to delete: {e}")
            return False
    
    def list_project_files(
        self,
        pattern: str = "*",
        exclude_dirs: Optional[List[str]] = None,
    ) -> List[str]:
        """List files in project matching pattern."""
        exclude_dirs = exclude_dirs or [".git", "__pycache__", ".venv", "venv", "node_modules"]
        files = []
        
        try:
            for path in self.project_root.rglob(pattern):
                # Skip excluded directories
                if any(excluded in path.parts for excluded in exclude_dirs):
                    continue
                
                if path.is_file():
                    # Return relative path
                    rel_path = path.relative_to(self.project_root)
                    files.append(str(rel_path))
            
            return sorted(files)
            
        except Exception as e:
            logger.error(f"Failed to list files: {e}")
            return []


class SecurityManager:
    """Manages security modes and approval workflows."""
    
    def __init__(self, mode: str = "conservative"):
        self.mode = mode
        self.approvals: dict = {}
    
    def requires_approval(self, action_type: str) -> bool:
        """Check if action requires approval in current mode."""
        if self.mode == "yolo":
            # YOLO mode only requires approval for git push
            return action_type in ["git_push"]
        
        # Conservative mode requires approval for most actions
        conservative_approvals = [
            "file_write_outside_project",
            "shell_command",
            "git_push",
            "network_request",
        ]
        return action_type in conservative_approvals
    
    def request_approval(self, action: str, details: str) -> bool:
        """Request user approval for an action."""
        from rich.console import Console
        from rich.panel import Panel
        
        console = Console()
        
        console.print(Panel(
            f"[bold yellow]Approval Required[/bold yellow]\n\n"
            f"Action: [cyan]{action}[/cyan]\n"
            f"Details: {details}",
            title="Security Check",
            border_style="yellow"
        ))
        
        response = console.input("Approve? [y/N]: ").lower().strip()
        approved = response in ('y', 'yes')
        
        self.approvals[action] = {
            "approved": approved,
            "timestamp": __import__('datetime').datetime.utcnow().isoformat(),
        }
        
        return approved
