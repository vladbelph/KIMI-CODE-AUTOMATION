"""Tests for sandbox file system guards."""

import pytest
import tempfile
from pathlib import Path

from vps_dev_agent.safety.sandbox import Sandbox, PathValidation


class TestSandbox:
    """Test sandbox functionality."""
    
    def test_valid_path_within_project(self):
        """Test validation of path within project."""
        with tempfile.TemporaryDirectory() as tmpdir:
            sandbox = Sandbox(project_root=tmpdir)
            
            result = sandbox.validate_write_path("src/main.py")
            assert result.is_valid is True
            assert result.resolved_path == Path(tmpdir) / "src/main.py"
    
    def test_path_with_parent_traversal(self):
        """Test blocking parent directory traversal."""
        with tempfile.TemporaryDirectory() as tmpdir:
            sandbox = Sandbox(project_root=tmpdir)
            
            result = sandbox.validate_write_path("../outside.py")
            assert result.is_valid is False
            assert "dangerous" in result.reason.lower()
    
    def test_absolute_path_outside_project(self):
        """Test blocking absolute path outside project."""
        with tempfile.TemporaryDirectory() as tmpdir:
            sandbox = Sandbox(project_root=tmpdir)
            
            result = sandbox.validate_write_path("/etc/passwd")
            assert result.is_valid is False
    
    def test_dangerous_system_paths(self):
        """Test blocking dangerous system paths."""
        with tempfile.TemporaryDirectory() as tmpdir:
            sandbox = Sandbox(project_root=tmpdir)
            
            dangerous_paths = [
                "/bin/malicious",
                "/etc/config",
                "/sbin/script",
            ]
            
            for path in dangerous_paths:
                result = sandbox.validate_write_path(path)
                assert result.is_valid is False, f"Should block: {path}"
    
    def test_allowed_outside_paths_with_permission(self):
        """Test allowing write outside project with permission."""
        with tempfile.TemporaryDirectory() as tmpdir:
            outside_dir = tempfile.mkdtemp()
            
            sandbox = Sandbox(
                project_root=tmpdir,
                allow_write_outside_project=True,
            )
            
            result = sandbox.validate_write_path(f"{outside_dir}/file.txt")
            assert result.is_valid is True
    
    def test_safe_write_and_read(self):
        """Test safe file write and read operations."""
        with tempfile.TemporaryDirectory() as tmpdir:
            sandbox = Sandbox(project_root=tmpdir)
            
            # Write file
            success = sandbox.safe_write("test.txt", "Hello World")
            assert success is True
            
            # Read file
            content = sandbox.safe_read("test.txt")
            assert content == "Hello World"
    
    def test_safe_read_nonexistent(self):
        """Test reading non-existent file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            sandbox = Sandbox(project_root=tmpdir)
            
            content = sandbox.safe_read("nonexistent.txt")
            assert content is None
    
    def test_safe_delete(self):
        """Test safe file deletion."""
        with tempfile.TemporaryDirectory() as tmpdir:
            sandbox = Sandbox(project_root=tmpdir)
            
            # Create file
            sandbox.safe_write("to_delete.txt", "content")
            assert (Path(tmpdir) / "to_delete.txt").exists()
            
            # Delete file
            success = sandbox.safe_delete("to_delete.txt")
            assert success is True
            assert not (Path(tmpdir) / "to_delete.txt").exists()
    
    def test_list_project_files(self):
        """Test listing project files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            sandbox = Sandbox(project_root=tmpdir)
            
            # Create some files
            (Path(tmpdir) / "file1.py").write_text("# file1")
            (Path(tmpdir) / "subdir").mkdir()
            (Path(tmpdir) / "subdir" / "file2.py").write_text("# file2")
            (Path(tmpdir) / "__pycache__").mkdir()
            (Path(tmpdir) / "__pycache__" / "cache.pyc").write_text("# cache")
            
            files = sandbox.list_project_files(pattern="*.py")
            
            assert "file1.py" in files
            assert "subdir/file2.py" in files
            assert "__pycache__/cache.pyc" not in files  # Excluded
    
    def test_nested_directory_creation(self):
        """Test creating nested directories."""
        with tempfile.TemporaryDirectory() as tmpdir:
            sandbox = Sandbox(project_root=tmpdir)
            
            success = sandbox.safe_write("deep/nested/path/file.txt", "content")
            assert success is True
            assert (Path(tmpdir) / "deep/nested/path/file.txt").exists()


class TestSecurityManager:
    """Test security manager."""
    
    def test_conservative_requires_approval(self):
        """Test conservative mode approval requirements."""
        from vps_dev_agent.safety.sandbox import SecurityManager
        
        sm = SecurityManager(mode="conservative")
        
        assert sm.requires_approval("shell_command") is True
        assert sm.requires_approval("git_push") is True
        assert sm.requires_approval("network_request") is True
    
    def test_yolo_auto_approval(self):
        """Test YOLO mode auto-approval."""
        from vps_dev_agent.safety.sandbox import SecurityManager
        
        sm = SecurityManager(mode="yolo")
        
        assert sm.requires_approval("shell_command") is False
        assert sm.requires_approval("git_push") is True  # Always requires approval
        assert sm.requires_approval("network_request") is False
