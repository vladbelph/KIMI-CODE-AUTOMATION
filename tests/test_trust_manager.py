"""Tests for trust manager."""

import pytest

from vps_dev_agent.core.trust_manager import TrustManager, SecurityMode, SecurityPolicy


class TestTrustManager:
    """Test trust manager functionality."""
    
    def test_default_mode(self):
        """Test default security mode."""
        tm = TrustManager()
        assert tm.mode == SecurityMode.CONSERVATIVE
    
    def test_switch_mode(self):
        """Test mode switching."""
        tm = TrustManager()
        
        tm.switch_mode(SecurityMode.YOLO)
        assert tm.mode == SecurityMode.YOLO
        
        tm.switch_mode(SecurityMode.CONSERVATIVE)
        assert tm.mode == SecurityMode.CONSERVATIVE
    
    def test_conservative_shell_commands(self):
        """Test shell command policy in conservative mode."""
        tm = TrustManager(SecurityMode.CONSERVATIVE)
        
        allowed, requires_approval = tm.can_execute_shell("ls -la")
        assert allowed is True
        assert requires_approval is True
    
    def test_yolo_shell_commands(self):
        """Test shell command policy in YOLO mode."""
        tm = TrustManager(SecurityMode.YOLO)
        
        allowed, requires_approval = tm.can_execute_shell("ls -la")
        assert allowed is True
        assert requires_approval is False
    
    def test_blocked_commands(self):
        """Test blocked dangerous commands."""
        tm = TrustManager(SecurityMode.YOLO)
        
        blocked_commands = [
            "rm -rf /",
            "rm -rf /*",
            "dd if=/dev/zero",
        ]
        
        for cmd in blocked_commands:
            allowed, _ = tm.can_execute_shell(cmd)
            assert allowed is False, f"Command should be blocked: {cmd}"
    
    def test_git_push_always_requires_approval(self):
        """Test that git push always requires approval."""
        # Conservative mode
        tm = TrustManager(SecurityMode.CONSERVATIVE)
        allowed, requires_approval = tm.can_push_git()
        assert allowed is True
        assert requires_approval is True
        
        # YOLO mode - git push should still require approval
        tm.switch_mode(SecurityMode.YOLO)
        allowed, requires_approval = tm.can_push_git()
        assert allowed is True
        assert requires_approval is True
    
    def test_network_requests_conservative(self):
        """Test network policy in conservative mode."""
        tm = TrustManager(SecurityMode.CONSERVATIVE)
        
        allowed, requires_approval = tm.can_make_network_request("https://api.example.com")
        assert allowed is True
        assert requires_approval is True
    
    def test_network_requests_yolo(self):
        """Test network policy in YOLO mode."""
        tm = TrustManager(SecurityMode.YOLO)
        
        allowed, requires_approval = tm.can_make_network_request("https://api.example.com")
        assert allowed is True
        assert requires_approval is False
    
    def test_approval_cache(self):
        """Test approval caching."""
        tm = TrustManager()
        
        # Initially not approved
        assert tm.check_approval("test_action") is False
        
        # Set approval
        tm.set_approval("test_action", True)
        assert tm.check_approval("test_action") is True
        
        # Clear cache
        tm.clear_approval_cache()
        assert tm.check_approval("test_action") is False
    
    def test_write_outside_project_blocked(self):
        """Test that write outside project is blocked in both modes."""
        for mode in [SecurityMode.CONSERVATIVE, SecurityMode.YOLO]:
            tm = TrustManager(mode)
            assert tm.can_write_outside_project() is False
    
    def test_mode_description(self):
        """Test mode description."""
        tm = TrustManager(SecurityMode.CONSERVATIVE)
        desc = tm.get_mode_description()
        assert "Conservative" in desc
        
        tm.switch_mode(SecurityMode.YOLO)
        desc = tm.get_mode_description()
        assert "YOLO" in desc
