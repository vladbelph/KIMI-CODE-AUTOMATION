"""Tests for spec parser."""

import pytest
from pathlib import Path
import tempfile
import yaml

from vps_dev_agent.core.spec_parser import SpecParser, TaskSpec, SecurityMode


class TestSpecParser:
    """Test spec parser functionality."""
    
    def test_load_valid_spec(self):
        """Test loading a valid spec file."""
        spec_data = {
            "spec": {
                "goal": "Test goal",
                "instructions": "Test instructions",
                "security_mode": "conservative",
            }
        }
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            yaml.dump(spec_data, f)
            f.flush()
            
            parser = SpecParser(f.name)
            spec = parser.load()
            
            assert isinstance(spec, TaskSpec)
            assert spec.goal == "Test goal"
            assert spec.security_mode == SecurityMode.CONSERVATIVE
            
            Path(f.name).unlink()
    
    def test_load_flat_spec(self):
        """Test loading spec without nested 'spec' key."""
        spec_data = {
            "goal": "Test goal",
            "security_mode": "yolo",
        }
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            yaml.dump(spec_data, f)
            f.flush()
            
            parser = SpecParser(f.name)
            spec = parser.load()
            
            assert spec.goal == "Test goal"
            assert spec.security_mode == SecurityMode.YOLO
            
            Path(f.name).unlink()
    
    def test_load_missing_file(self):
        """Test loading non-existent file."""
        parser = SpecParser("/nonexistent/path/spec.yaml")
        
        with pytest.raises(FileNotFoundError):
            parser.load()
    
    def test_load_invalid_yaml(self):
        """Test loading invalid YAML."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write("invalid: yaml: content: [")
            f.flush()
            
            parser = SpecParser(f.name)
            
            with pytest.raises(ValueError):
                parser.load()
            
            Path(f.name).unlink()
    
    def test_empty_goal_validation(self):
        """Test that empty goal is rejected."""
        spec_data = {
            "spec": {
                "goal": "",
            }
        }
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            yaml.dump(spec_data, f)
            f.flush()
            
            parser = SpecParser(f.name)
            
            with pytest.raises(ValueError):
                parser.load()
            
            Path(f.name).unlink()
    
    def test_get_goal_summary(self):
        """Test goal summary generation."""
        spec_data = {
            "spec": {
                "goal": "This is a very long goal that should be truncated for commit messages",
            }
        }
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            yaml.dump(spec_data, f)
            f.flush()
            
            parser = SpecParser(f.name)
            parser.load()
            
            summary = parser.get_goal_summary()
            assert len(summary) <= 72
            assert summary.endswith("...")
            
            Path(f.name).unlink()
    
    def test_get_context_prompt(self):
        """Test context prompt generation."""
        spec_data = {
            "spec": {
                "goal": "Test goal",
                "instructions": "Do this and that",
                "constraints": ["Use Python", "Follow PEP8"],
                "expected_output": "Working code",
            }
        }
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            yaml.dump(spec_data, f)
            f.flush()
            
            parser = SpecParser(f.name)
            parser.load()
            
            prompt = parser.get_context_prompt()
            
            assert "Goal: Test goal" in prompt
            assert "Instructions:" in prompt
            assert "Do this and that" in prompt
            assert "Constraints:" in prompt
            assert "Use Python" in prompt
            assert "Expected Output:" in prompt
            assert "Working code" in prompt
            
            Path(f.name).unlink()


class TestSpecValidation:
    """Test spec validation."""
    
    def test_short_goal_warning(self):
        """Test warning for short goal."""
        spec_data = {
            "spec": {
                "goal": "Short",
            }
        }
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            yaml.dump(spec_data, f)
            f.flush()
            
            parser = SpecParser(f.name)
            parser.load()
            
            issues = parser.validate_for_execution()
            assert any("too short" in issue for issue in issues)
            
            Path(f.name).unlink()
