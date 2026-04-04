"""Prompt formatter for various LLM providers."""

from typing import Dict, Any, Optional, List
from dataclasses import dataclass
from pathlib import Path

from vps_dev_agent.utils.logger import get_logger

logger = get_logger()


# Default Kimi CLI prompt template
KIMI_PROMPT_TEMPLATE = '''# Task ID: {task_id}
# Project: {project_name}
# Provider: Kimi Code CLI

## Goal
{goal}

## Instructions
{instructions}

{constraints_section}

{context_section}

{expected_output_section}

---
Mode: {mode_instruction}
'''


@dataclass
class PromptContext:
    """Context for prompt formatting."""
    task_id: str
    project_name: str
    goal: str
    instructions: str
    constraints: List[str]
    expected_output: Optional[str] = None
    areas: Optional[List[Dict]] = None
    resources: Optional[List[Dict]] = None
    archives: Optional[List[Dict]] = None
    relevant_files: Optional[List[str]] = None
    auto_apply: bool = False


class PromptFormatter:
    """Formats prompts for different LLM providers."""
    
    def __init__(self):
        self.templates = {
            'kimi': KIMI_PROMPT_TEMPLATE,
        }
    
    def format_kimi_prompt(
        self,
        task,
        project,
        spec,
        context: Dict[str, Any],
        auto_apply: bool = False,
    ) -> str:
        """Format a prompt for Kimi CLI.
        
        Args:
            task: Task object
            project: Project object
            spec: Parsed spec
            context: PARA context dict
            auto_apply: Whether to auto-apply changes
            
        Returns:
            Formatted prompt string
        """
        task_id = str(task.id)
        
        # Build constraints section
        constraints_section = ""
        if spec.constraints:
            constraints_section = "## Constraints\n" + "\n".join(
                f"- {c}" for c in spec.constraints
            )
        
        # Build context section from PARA
        context_section = self._build_context_section(context)
        
        # Build expected output section
        expected_output_section = ""
        if spec.expected_output:
            expected_output_section = f"## Expected Output\n{spec.expected_output}"
        
        # Mode instruction
        if auto_apply:
            mode_instruction = (
                "Instructions: Execute task and apply changes immediately. "
                "Respond with a summary of changes made."
            )
        else:
            mode_instruction = (
                "Instructions: Execute task but ask for confirmation before applying changes. "
                "Show a diff of proposed changes."
            )
        
        # Format template
        prompt = KIMI_PROMPT_TEMPLATE.format(
            task_id=task_id,
            project_name=project.name,
            goal=spec.goal,
            instructions=spec.instructions or "Complete the goal using best practices.",
            constraints_section=constraints_section,
            context_section=context_section,
            expected_output_section=expected_output_section,
            mode_instruction=mode_instruction,
        )
        
        return prompt
    
    def _build_context_section(self, context: Dict[str, Any]) -> str:
        """Build context section from PARA data."""
        lines = []
        
        # Project description
        if context.get('project_description'):
            lines.append(f"**Project Description:** {context['project_description']}")
            lines.append("")
        
        # Areas
        areas = context.get('areas', [])
        if areas:
            lines.append("## Areas of Responsibility")
            for area in areas:
                name = area.get('name', 'Unnamed')
                desc = area.get('description', '')
                if desc:
                    lines.append(f"- **{name}**: {desc}")
                else:
                    lines.append(f"- {name}")
            lines.append("")
        
        # Resources
        resources = context.get('resources', [])
        if resources:
            lines.append("## Relevant Resources")
            for res in resources:
                res_type = res.get('type', 'unknown')
                title = res.get('title') or res.get('file_path', 'Untitled')
                lines.append(f"- [{res_type}] {title}")
                
                content = res.get('content')
                if content:
                    lines.append(f"  ```")
                    lines.append(f"  {content[:500]}{'...' if len(content) > 500 else ''}")
                    lines.append(f"  ```")
            lines.append("")
        
        # Archives (lessons learned)
        archives = context.get('archives', [])
        if archives:
            lines.append("## Lessons Learned from Previous Tasks")
            for archive in archives:
                lessons = archive.get('lessons', [])
                for lesson in lessons[:3]:  # Limit to 3 lessons per archive
                    lines.append(f"- {lesson}")
            lines.append("")
        
        return "\n".join(lines)
    
    def format_simple_prompt(
        self,
        goal: str,
        instructions: Optional[str] = None,
        context: Optional[str] = None,
    ) -> str:
        """Format a simple prompt without template."""
        lines = [f"# Goal\n{goal}"]
        
        if instructions:
            lines.append(f"\n# Instructions\n{instructions}")
        
        if context:
            lines.append(f"\n# Context\n{context}")
        
        return "\n".join(lines)


class Jinja2PromptFormatter(PromptFormatter):
    """Prompt formatter using Jinja2 templates."""
    
    def __init__(self, template_dir: Optional[Path] = None):
        super().__init__()
        
        try:
            from jinja2 import Environment, FileSystemLoader, BaseLoader
            
            if template_dir and template_dir.exists():
                self.env = Environment(loader=FileSystemLoader(template_dir))
            else:
                self.env = Environment(loader=BaseLoader())
            
            self.jinja_available = True
            
        except ImportError:
            self.jinja_available = False
            logger.warning("Jinja2 not installed, using basic formatter")
    
    def format_from_template(
        self,
        template_name: str,
        context: Dict[str, Any],
    ) -> str:
        """Format prompt from Jinja2 template."""
        if not self.jinja_available:
            # Fallback to basic formatter
            return self.format_simple_prompt(
                goal=context.get('goal', ''),
                instructions=context.get('instructions'),
            )
        
        try:
            template = self.env.get_template(template_name)
            return template.render(**context)
        except Exception as e:
            logger.error(f"Template rendering failed: {e}")
            return self.format_simple_prompt(
                goal=context.get('goal', ''),
                instructions=context.get('instructions'),
            )
    
    def format_from_string(self, template_string: str, context: Dict[str, Any]) -> str:
        """Format prompt from template string."""
        if not self.jinja_available:
            return self.format_simple_prompt(
                goal=context.get('goal', ''),
                instructions=context.get('instructions'),
            )
        
        try:
            from jinja2 import Template
            template = Template(template_string)
            return template.render(**context)
        except Exception as e:
            logger.error(f"Template rendering failed: {e}")
            return self.format_simple_prompt(
                goal=context.get('goal', ''),
                instructions=context.get('instructions'),
            )
