"""Task execution engine."""

import os
import sys
import json
import subprocess
from pathlib import Path
from typing import List, Optional, Dict, Any, Callable
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn

from vps_dev_agent.core.para_models import (
    DatabaseManager, Task, TaskStatus, Project, 
    Resource, Archive, Area
)
from vps_dev_agent.core.spec_parser import SpecParser, TaskSpec
from vps_dev_agent.core.trust_manager import TrustManager, SecurityMode
from vps_dev_agent.adapters.llm_proxy import LLMAdapter, FileChange
from vps_dev_agent.safety.git_guardian import GitGuardian, BackupInfo
from vps_dev_agent.safety.sandbox import Sandbox, SecurityManager
from vps_dev_agent.utils.logger import get_logger

logger = get_logger()
console = Console()


class ExecutionResult(Enum):
    """Task execution result."""
    SUCCESS = "success"
    FAILED = "failed"
    CANCELLED = "cancelled"
    RETRY = "retry"


@dataclass
class ExecutionContext:
    """Context for task execution."""
    task: Task
    project: Project
    spec: TaskSpec
    backup_info: Optional[BackupInfo] = None
    changes_made: List[str] = field(default_factory=list)
    validation_results: List[Dict] = field(default_factory=list)
    execution_log: List[str] = field(default_factory=list)


class TaskExecutor:
    """Main task execution engine."""
    
    def __init__(
        self,
        database_url: str,
        llm_adapter: Optional[LLMAdapter] = None,
    ):
        self.db = DatabaseManager(database_url)
        self.llm = llm_adapter or LLMAdapter()
        self.trust_manager = TrustManager()
        self.git_guardian: Optional[GitGuardian] = None
        self.sandbox: Optional[Sandbox] = None
    
    def _log(self, message: str, level: str = "info"):
        """Log message to both logger and execution log."""
        getattr(logger, level)(message)
        # Would add to execution context log here
    
    def execute(self, task_id: str) -> ExecutionResult:
        """Execute a task by ID."""
        session = self.db.get_session()
        
        try:
            # Load task
            task = session.query(Task).filter_by(id=task_id).first()
            if not task:
                logger.error(f"Task not found: {task_id}")
                return ExecutionResult.FAILED
            
            # Load project
            project = session.query(Project).filter_by(id=task.project_id).first()
            if not project:
                logger.error(f"Project not found: {task.project_id}")
                return ExecutionResult.FAILED
            
            # Parse spec
            spec_path = Path(task.spec_path)
            if not spec_path.is_absolute():
                spec_path = Path(project.repo_path) / spec_path
            
            parser = SpecParser(spec_path)
            try:
                spec = parser.load()
            except Exception as e:
                logger.error(f"Failed to load spec: {e}")
                task.status = TaskStatus.FAILED
                task.error_log = str(e)
                session.commit()
                return ExecutionResult.FAILED
            
            # Validate spec
            issues = parser.validate_for_execution()
            if issues:
                logger.error(f"Spec validation failed: {issues}")
                task.status = TaskStatus.FAILED
                task.error_log = f"Validation issues: {issues}"
                session.commit()
                return ExecutionResult.FAILED
            
            # Check if using kimi_cli provider
            if task.llm_provider == "kimi_cli":
                session.close()
                return self._execute_with_kimi_cli(task_id)
            
            # Setup execution context
            ctx = ExecutionContext(task=task, project=project, spec=spec)
            
            # Set trust mode
            if spec.security_mode == SecurityMode.YOLO or task.yolo_mode:
                self.trust_manager.switch_mode(SecurityMode.YOLO)
            else:
                self.trust_manager.switch_mode(SecurityMode.CONSERVATIVE)
            
            # Initialize git guardian and sandbox
            self.git_guardian = GitGuardian(project.repo_path)
            self.sandbox = Sandbox(
                project_root=project.repo_path,
                allow_write_outside_project=self.trust_manager.can_write_outside_project(),
            )
            
            # Update task status
            task.status = TaskStatus.RUNNING
            task.started_at = datetime.utcnow()
            task.attempt_count += 1
            session.commit()
            
            console.print(Panel(
                f"[bold blue]Executing Task[/bold blue]\n"
                f"ID: {task_id}\n"
                f"Project: {project.name}\n"
                f"Goal: {spec.goal[:60]}...\n"
                f"Mode: {self.trust_manager.mode.value}",
                border_style="blue"
            ))
            
            # Execute
            result = self._execute_task(ctx, parser)
            
            # Update task status
            if result == ExecutionResult.SUCCESS:
                task.status = TaskStatus.COMPLETED
                task.completed_at = datetime.utcnow()
                task.result_summary = f"Completed with {len(ctx.changes_made)} changes"
                logger.success(f"Task completed: {task_id}")
                
                # Cleanup backup
                if ctx.backup_info:
                    self.git_guardian.cleanup_backup(str(task_id))
                    
            elif result == ExecutionResult.FAILED:
                if task.attempt_count < task.max_attempts:
                    task.status = TaskStatus.PENDING
                    result = ExecutionResult.RETRY
                    logger.warning(f"Task failed, will retry ({task.attempt_count}/{task.max_attempts})")
                else:
                    task.status = TaskStatus.FAILED
                    logger.error(f"Task failed permanently after {task.attempt_count} attempts")
                    
            session.commit()
            return result
            
        except Exception as e:
            logger.error(f"Unexpected error during execution: {e}")
            if task:
                task.status = TaskStatus.FAILED
                task.error_log = str(e)
                session.commit()
            return ExecutionResult.FAILED
            
        finally:
            session.close()
    
    def _execute_task(self, ctx: ExecutionContext, parser: SpecParser) -> ExecutionResult:
        """Core task execution logic."""
        
        # Step 1: Create git backup
        if self.git_guardian.is_git_repo():
            ctx.backup_info = self.git_guardian.create_backup(str(ctx.task.id))
            if not ctx.backup_info:
                logger.warning("Failed to create git backup, continuing anyway")
        
        # Step 2: Build context from PARA
        context = self._build_para_context(ctx)
        
        # Step 3: Generate code changes
        try:
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                console=console,
            ) as progress:
                progress.add_task("Generating code changes...", total=None)
                
                project_files = self.sandbox.list_project_files() if self.sandbox else []
                changes = self.llm.generate_code_changes(
                    context=context,
                    spec=parser.get_context_prompt(),
                    project_files=project_files,
                )
        except Exception as e:
            logger.error(f"Failed to generate code changes: {e}")
            self._rollback(ctx)
            return ExecutionResult.FAILED
        
        if not changes:
            logger.warning("No changes generated by LLM")
            return ExecutionResult.FAILED
        
        logger.info(f"Generated {len(changes)} file changes")
        
        # Step 4: Apply changes (with approval if needed)
        for change in changes:
            if not self._apply_change(change, ctx):
                self._rollback(ctx)
                return ExecutionResult.FAILED
        
        # Step 5: Show diff if in conservative mode
        if self.trust_manager.mode == SecurityMode.CONSERVATIVE and ctx.changes_made:
            if not self._confirm_changes(ctx):
                self._rollback(ctx)
                return ExecutionResult.CANCELLED
        
        # Step 6: Run validation commands
        if ctx.spec.validation.commands:
            if not self._run_validations(ctx):
                if ctx.spec.validation.rollback_on_failure:
                    self._rollback(ctx)
                return ExecutionResult.FAILED
        
        # Step 7: Commit changes
        if ctx.changes_made and self.git_guardian.is_git_repo():
            commit_msg = parser.get_goal_summary()
            commit_hash = self.git_guardian.commit_changes(
                message=commit_msg,
                files=ctx.changes_made,
                task_id=str(ctx.task.id),
            )
            if commit_hash:
                ctx.execution_log.append(f"Created commit: {commit_hash}")
        
        return ExecutionResult.SUCCESS
    
    def _build_para_context(self, ctx: ExecutionContext) -> str:
        """Build context from PARA structure."""
        lines = ["PARA Context:", ""]
        
        session = self.db.get_session()
        try:
            # Project info
            lines.extend([
                f"Project: {ctx.project.name}",
                f"Description: {ctx.project.description or 'N/A'}",
                "",
            ])
            
            # Areas
            areas = session.query(Area).filter_by(project_id=ctx.project.id).all()
            if areas:
                lines.append("Areas of Responsibility:")
                for area in areas:
                    lines.append(f"  - {area.name}: {area.description or 'N/A'}")
                lines.append("")
            
            # Relevant resources
            if ctx.spec.context.area_ids:
                resources = session.query(Resource).filter(
                    Resource.area_id.in_(ctx.spec.context.area_ids)
                ).all()
                if resources:
                    lines.append("Relevant Resources:")
                    for res in resources:
                        lines.append(f"  - [{res.type}] {res.title or res.file_path or 'Untitled'}")
                    lines.append("")
            
            # Recent archives (lessons learned)
            if ctx.spec.context.include_archives:
                from vps_dev_agent.core.para_models import Archive
                archives = session.query(Archive).filter_by(
                    project_id=ctx.project.id,
                    success=True,
                ).order_by(Archive.created_at.desc()).limit(
                    ctx.spec.context.archive_limit
                ).all()
                
                if archives:
                    lines.append("Lessons Learned:")
                    for archive in archives:
                        if archive.lessons_learned:
                            for lesson in archive.lessons_learned[:3]:
                                lines.append(f"  - {lesson}")
                    lines.append("")
            
            return "\n".join(lines)
            
        finally:
            session.close()
    
    def _apply_change(self, change: FileChange, ctx: ExecutionContext) -> bool:
        """Apply a single file change."""
        if not self.sandbox:
            logger.error("Sandbox not initialized")
            return False
        
        logger.info(f"Applying change: {change.operation} {change.path}")
        
        if change.operation == "create":
            if self.sandbox.safe_write(change.path, change.content or ""):
                ctx.changes_made.append(change.path)
                return True
            return False
            
        elif change.operation == "modify":
            if self.sandbox.safe_write(change.path, change.content or ""):
                ctx.changes_made.append(change.path)
                return True
            return False
            
        elif change.operation == "delete":
            if self.sandbox.safe_delete(change.path):
                ctx.changes_made.append(change.path)
                return True
            return False
        
        return False
    
    def _confirm_changes(self, ctx: ExecutionContext) -> bool:
        """Show diff and ask for confirmation in conservative mode."""
        if not self.git_guardian or not ctx.backup_info:
            return True
        
        diff = self.git_guardian.get_diff_since_backup(str(ctx.task.id))
        
        if not diff:
            return True
        
        console.print(Panel(
            f"[bold yellow]Changes to be applied:[/bold yellow]\n\n"
            f"{diff[:2000]}{'...' if len(diff) > 2000 else ''}",
            border_style="yellow"
        ))
        
        response = console.input("Apply these changes? [y/N]: ").lower().strip()
        return response in ('y', 'yes')
    
    def _run_validations(self, ctx: ExecutionContext) -> bool:
        """Run validation commands from spec."""
        all_passed = True
        
        for cmd in ctx.spec.validation.commands:
            logger.info(f"Running validation: {cmd.name}")
            
            try:
                result = subprocess.run(
                    cmd.command,
                    shell=True,
                    cwd=ctx.project.repo_path,
                    capture_output=True,
                    text=True,
                    timeout=cmd.timeout,
                )
                
                success = result.returncode == 0
                ctx.validation_results.append({
                    "name": cmd.name,
                    "command": cmd.command,
                    "success": success,
                    "stdout": result.stdout,
                    "stderr": result.stderr,
                })
                
                if success:
                    logger.success(f"Validation passed: {cmd.name}")
                else:
                    logger.error(f"Validation failed: {cmd.name}")
                    logger.debug(f"stdout: {result.stdout}")
                    logger.debug(f"stderr: {result.stderr}")
                    
                    if cmd.required:
                        all_passed = False
                        
            except subprocess.TimeoutExpired:
                logger.error(f"Validation timed out: {cmd.name}")
                if cmd.required:
                    all_passed = False
                    
            except Exception as e:
                logger.error(f"Validation error: {cmd.name} - {e}")
                if cmd.required:
                    all_passed = False
        
        return all_passed
    
    def _execute_with_kimi_cli(self, task_id: str) -> ExecutionResult:
        """Execute task using Kimi CLI batch executor."""
        from vps_dev_agent.bridges.kimi_cli import KimiBatchExecutor
        
        executor = KimiBatchExecutor(
            database_url=self.db.database_url,
            auto_apply=False,  # Use task's yolo_mode instead
        )
        
        result = executor.execute_task(task_id)
        
        if result.success:
            return ExecutionResult.SUCCESS
        elif result.exit_code == 2:  # Needs clarification
            return ExecutionResult.CANCELLED
        else:
            return ExecutionResult.FAILED
    
    def _rollback(self, ctx: ExecutionContext):
        """Rollback to backup."""
        logger.warning("Rolling back changes...")
        
        if self.git_guardian and ctx.backup_info:
            success = self.git_guardian.restore_backup(str(ctx.task.id))
            if success:
                logger.success("Rollback successful")
            else:
                logger.error("Rollback failed - manual intervention may be needed")
        else:
            logger.error("No backup available for rollback")
