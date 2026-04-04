"""YAML spec parser and validator."""

import yaml
from pathlib import Path
from typing import List, Optional, Dict, Any, Union
from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field, field_validator


class ValidationCommand(BaseModel):
    """Validation command model."""
    name: str
    command: str
    required: bool = True
    timeout: int = 300


class SecurityMode(str, Enum):
    """Security mode enum."""
    CONSERVATIVE = "conservative"
    YOLO = "yolo"


class SpecMetadata(BaseModel):
    """Spec metadata section."""
    version: str = "1.0.0"
    author: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    tags: List[str] = Field(default_factory=list)


class SpecContext(BaseModel):
    """Spec context section - PARA references."""
    project_id: Optional[str] = None
    area_ids: List[str] = Field(default_factory=list)
    resource_ids: List[str] = Field(default_factory=list)
    include_archives: bool = False
    archive_limit: int = 5


class SpecExecution(BaseModel):
    """Spec execution configuration."""
    timeout_minutes: int = 30
    max_attempts: int = 3
    auto_retry: bool = True
    parallel_tasks: bool = False


class SpecValidation(BaseModel):
    """Spec validation section."""
    commands: List[ValidationCommand] = Field(default_factory=list)
    require_all_pass: bool = True
    rollback_on_failure: bool = True


class TaskSpec(BaseModel):
    """Main task specification model."""
    
    # Required fields
    goal: str = Field(..., description="Clear description of what needs to be done")
    
    # Optional fields with defaults
    metadata: SpecMetadata = Field(default_factory=SpecMetadata)
    context: SpecContext = Field(default_factory=SpecContext)
    execution: SpecExecution = Field(default_factory=SpecExecution)
    validation: SpecValidation = Field(default_factory=SpecValidation)
    
    # Additional configuration
    security_mode: SecurityMode = SecurityMode.CONSERVATIVE
    
    # Instructions for the LLM
    instructions: Optional[str] = None
    constraints: List[str] = Field(default_factory=list)
    expected_output: Optional[str] = None
    
    # Files context
    relevant_files: List[str] = Field(default_factory=list)
    exclude_patterns: List[str] = Field(default_factory=list)
    
    # LLM configuration
    model: Optional[str] = None  # Override default model
    temperature: float = Field(default=0.7, ge=0.0, le=2.0)
    
    @field_validator('goal')
    @classmethod
    def goal_not_empty(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("Goal cannot be empty")
        return v.strip()
    
    @field_validator('temperature')
    @classmethod
    def validate_temperature(cls, v: float) -> float:
        if v < 0 or v > 2:
            raise ValueError("Temperature must be between 0 and 2")
        return v


class SpecParser:
    """Parser for YAML specification files."""
    
    def __init__(self, spec_path: Union[str, Path]):
        self.spec_path = Path(spec_path)
        self.raw_content: Optional[str] = None
        self.parsed_data: Optional[Dict[str, Any]] = None
        self.spec: Optional[TaskSpec] = None
    
    def load(self) -> TaskSpec:
        """Load and validate spec from YAML file."""
        if not self.spec_path.exists():
            raise FileNotFoundError(f"Spec file not found: {self.spec_path}")
        
        with open(self.spec_path, 'r', encoding='utf-8') as f:
            self.raw_content = f.read()
        
        try:
            self.parsed_data = yaml.safe_load(self.raw_content)
        except yaml.YAMLError as e:
            raise ValueError(f"Invalid YAML format: {e}")
        
        if not isinstance(self.parsed_data, dict):
            raise ValueError("Spec must be a YAML dictionary")
        
        # Support both flat and nested 'spec' structure
        if 'spec' in self.parsed_data:
            data = self.parsed_data['spec']
        else:
            data = self.parsed_data
        
        self.spec = TaskSpec.model_validate(data)
        return self.spec
    
    def get_goal_summary(self) -> str:
        """Get a summary of the goal for commit messages."""
        if not self.spec:
            self.load()
        
        goal = self.spec.goal
        # Truncate if too long for commit message
        if len(goal) > 72:
            goal = goal[:69] + "..."
        return goal
    
    def get_context_prompt(self) -> str:
        """Generate context prompt for LLM from spec."""
        if not self.spec:
            self.load()
        
        lines = [
            f"Goal: {self.spec.goal}",
            "",
        ]
        
        if self.spec.instructions:
            lines.extend([
                "Instructions:",
                self.spec.instructions,
                "",
            ])
        
        if self.spec.constraints:
            lines.extend([
                "Constraints:",
                *[f"- {c}" for c in self.spec.constraints],
                "",
            ])
        
        if self.spec.expected_output:
            lines.extend([
                "Expected Output:",
                self.spec.expected_output,
                "",
            ])
        
        if self.spec.relevant_files:
            lines.extend([
                "Relevant Files:",
                *[f"- {f}" for f in self.spec.relevant_files],
                "",
            ])
        
        lines.extend([
            f"Security Mode: {self.spec.security_mode.value}",
            f"Max Attempts: {self.spec.execution.max_attempts}",
        ])
        
        return "\n".join(lines)
    
    def validate_for_execution(self) -> List[str]:
        """Validate spec is ready for execution. Returns list of issues."""
        issues = []
        
        if not self.spec:
            try:
                self.load()
            except Exception as e:
                return [str(e)]
        
        # Check goal is meaningful
        if len(self.spec.goal) < 10:
            issues.append("Goal is too short (minimum 10 characters)")
        
        # Check spec path is within project
        if self.spec.context.project_id:
            # Would need to verify project exists in DB
            pass
        
        # Check relevant files exist
        for file_path in self.spec.relevant_files:
            full_path = self.spec_path.parent / file_path
            if not full_path.exists():
                issues.append(f"Relevant file not found: {file_path}")
        
        return issues


def load_spec(spec_path: Union[str, Path]) -> TaskSpec:
    """Convenience function to load a spec file."""
    parser = SpecParser(spec_path)
    return parser.load()
