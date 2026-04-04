"""Security modes and trust management."""

from enum import Enum
from typing import Dict, Any, Optional
from dataclasses import dataclass


class SecurityMode(str, Enum):
    """Security mode levels."""
    CONSERVATIVE = "conservative"
    YOLO = "yolo"


@dataclass
class SecurityPolicy:
    """Security policy configuration."""
    file_write_outside_project: bool = False
    shell_commands: str = "require_approval"  # require_approval, auto, disabled
    git_push: str = "require_approval"  # require_approval, auto, disabled
    network_requests: str = "whitelist_only"  # whitelist_only, allow, disabled
    
    # Command whitelist/blacklist
    allowed_shell_commands: Optional[list] = None
    blocked_shell_commands: Optional[list] = None


class TrustManager:
    """Manages security modes and trust levels."""
    
    # Default policies for each mode
    POLICIES = {
        SecurityMode.CONSERVATIVE: SecurityPolicy(
            file_write_outside_project=False,
            shell_commands="require_approval",
            git_push="require_approval",
            network_requests="whitelist_only",
            blocked_shell_commands=[
                "rm -rf /", "rm -rf /*", "dd if=/dev/zero",
                ":(){ :|:& };:", "> /dev/sda", "mkfs.",
            ]
        ),
        SecurityMode.YOLO: SecurityPolicy(
            file_write_outside_project=False,  # Still don't allow outside project
            shell_commands="auto",
            git_push="require_approval",  # Git push always requires approval
            network_requests="allow",
            blocked_shell_commands=[
                "rm -rf /", "rm -rf /*", "dd if=/dev/zero",
                ":(){ :|:& };:", "> /dev/sda", "mkfs.",
            ]
        ),
    }
    
    def __init__(self, mode: SecurityMode = SecurityMode.CONSERVATIVE):
        self.mode = mode
        self.policy = self.POLICIES[mode]
        self._approval_cache: Dict[str, bool] = {}
    
    def can_write_outside_project(self) -> bool:
        """Check if writing outside project is allowed."""
        return self.policy.file_write_outside_project
    
    def can_execute_shell(self, command: str) -> tuple[bool, bool]:
        """Check if shell command can be executed.
        
        Returns:
            (allowed, requires_approval)
        """
        # Check blocked commands
        if self.policy.blocked_shell_commands:
            for blocked in self.policy.blocked_shell_commands:
                if blocked in command:
                    return False, False
        
        # Check allowed commands whitelist
        if self.policy.allowed_shell_commands:
            allowed = any(
                allowed_cmd in command 
                for allowed_cmd in self.policy.allowed_shell_commands
            )
            if not allowed:
                return False, False
        
        # Determine based on policy
        if self.policy.shell_commands == "disabled":
            return False, False
        elif self.policy.shell_commands == "auto":
            return True, False
        else:  # require_approval
            return True, True
    
    def can_push_git(self) -> tuple[bool, bool]:
        """Check if git push is allowed.
        
        Returns:
            (allowed, requires_approval)
        """
        if self.policy.git_push == "disabled":
            return False, False
        elif self.policy.git_push == "auto":
            return True, False
        else:  # require_approval
            return True, True
    
    def can_make_network_request(self, url: str) -> tuple[bool, bool]:
        """Check if network request is allowed.
        
        Returns:
            (allowed, requires_approval)
        """
        if self.policy.network_requests == "disabled":
            return False, False
        elif self.policy.network_requests == "allow":
            return True, False
        else:  # whitelist_only
            # Would need to implement whitelist checking
            return True, True
    
    def check_approval(self, action_id: str) -> bool:
        """Check if action has been approved."""
        return self._approval_cache.get(action_id, False)
    
    def set_approval(self, action_id: str, approved: bool):
        """Cache approval for an action."""
        self._approval_cache[action_id] = approved
    
    def clear_approval_cache(self):
        """Clear all cached approvals."""
        self._approval_cache.clear()
    
    def switch_mode(self, mode: SecurityMode):
        """Switch to a different security mode."""
        self.mode = mode
        self.policy = self.POLICIES[mode]
        self.clear_approval_cache()
    
    def get_mode_description(self) -> str:
        """Get human-readable description of current mode."""
        descriptions = {
            SecurityMode.CONSERVATIVE: (
                "Conservative mode: All shell commands and git operations "
                "require explicit approval. Network requests are restricted."
            ),
            SecurityMode.YOLO: (
                "YOLO mode: Shell commands execute automatically. "
                "Git push still requires approval for safety."
            ),
        }
        return descriptions.get(self.mode, "Unknown mode")
