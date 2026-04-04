"""Kimi CLI authentication checker."""

import os
import json
import subprocess
from pathlib import Path
from typing import Optional, Dict, Any
from dataclasses import dataclass
from datetime import datetime

from vps_dev_agent.utils.logger import get_logger

logger = get_logger()


@dataclass
class AuthStatus:
    """Authentication status."""
    is_authenticated: bool
    username: Optional[str] = None
    email: Optional[str] = None
    expires_at: Optional[datetime] = None
    raw_data: Optional[Dict[str, Any]] = None


class KimiAuthChecker:
    """Checks and manages Kimi CLI authentication."""
    
    CREDENTIALS_PATH = Path.home() / ".config" / "kimi" / "credentials.json"
    
    def __init__(self, credentials_path: Optional[Path] = None):
        self.credentials_path = credentials_path or self.CREDENTIALS_PATH
    
    def check_auth(self) -> AuthStatus:
        """Check if authenticated with Kimi CLI."""
        try:
            result = subprocess.run(
                "kimi auth status",
                shell=True,
                capture_output=True,
                text=True,
                timeout=10,
            )
            
            # Parse output
            if result.returncode == 0:
                # Try to parse structured data
                data = self._parse_auth_output(result.stdout)
                
                return AuthStatus(
                    is_authenticated=True,
                    username=data.get("username"),
                    email=data.get("email"),
                    expires_at=data.get("expires_at"),
                    raw_data=data,
                )
            else:
                return AuthStatus(
                    is_authenticated=False,
                    raw_data={"error": result.stderr},
                )
                
        except subprocess.TimeoutExpired:
            logger.error("Auth check timed out")
            return AuthStatus(is_authenticated=False)
        except Exception as e:
            logger.error(f"Auth check failed: {e}")
            return AuthStatus(is_authenticated=False)
    
    def _parse_auth_output(self, output: str) -> Dict[str, Any]:
        """Parse auth status output."""
        data = {}
        
        # Try JSON first
        try:
            return json.loads(output)
        except json.JSONDecodeError:
            pass
        
        # Parse line by line
        for line in output.strip().split('\n'):
            if ':' in line:
                key, value = line.split(':', 1)
                key = key.strip().lower().replace(' ', '_')
                value = value.strip()
                
                if key == 'expires_at':
                    try:
                        value = datetime.fromisoformat(value.replace('Z', '+00:00'))
                    except:
                        pass
                
                data[key] = value
        
        return data
    
    def read_credentials_file(self) -> Optional[Dict[str, Any]]:
        """Read credentials from file."""
        if not self.credentials_path.exists():
            return None
        
        try:
            with open(self.credentials_path, 'r') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Failed to read credentials: {e}")
            return None
    
    def is_session_valid(self) -> bool:
        """Check if current session is valid (not expired)."""
        status = self.check_auth()
        
        if not status.is_authenticated:
            return False
        
        if status.expires_at and status.expires_at < datetime.utcnow():
            logger.warning("Session expired")
            return False
        
        return True
    
    def ensure_authenticated(self) -> bool:
        """Ensure user is authenticated, prompt if not."""
        if self.is_session_valid():
            return True
        
        logger.warning("Not authenticated with Kimi CLI")
        
        # Check if credentials file exists
        creds = self.read_credentials_file()
        if creds:
            logger.info("Found credentials file, attempting refresh...")
            # Could implement refresh logic here
        
        return False
    
    def get_installation_status(self) -> Dict[str, Any]:
        """Get full installation and auth status."""
        status = {
            'installed': False,
            'version': None,
            'authenticated': False,
            'username': None,
            'tier': None,
        }
        
        # Check if installed
        try:
            result = subprocess.run(
                "kimi --version",
                shell=True,
                capture_output=True,
                text=True,
                timeout=10,
            )
            
            if result.returncode == 0:
                status['installed'] = True
                status['version'] = result.stdout.strip()
            else:
                return status
                
        except Exception as e:
            logger.error(f"Kimi CLI not found: {e}")
            return status
        
        # Check auth
        auth = self.check_auth()
        status['authenticated'] = auth.is_authenticated
        status['username'] = auth.username
        
        return status


def check_kimi_installation() -> tuple[bool, str]:
    """Quick check if Kimi CLI is installed.
    
    Returns:
        (is_installed, version_or_error)
    """
    try:
        result = subprocess.run(
            "kimi --version",
            shell=True,
            capture_output=True,
            text=True,
            timeout=10,
        )
        
        if result.returncode == 0:
            return True, result.stdout.strip()
        else:
            return False, result.stderr.strip()
            
    except FileNotFoundError:
        return False, "Kimi CLI not found. Install: https://kimi.moonshot.cn/download"
    except Exception as e:
        return False, str(e)
