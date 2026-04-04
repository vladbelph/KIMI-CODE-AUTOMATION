"""Kimi CLI batch executor - main execution engine."""

import os
import re
import json
import tempfile
import subprocess
from pathlib import Path
from typing import Optional, List, Dict, Any, Union
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

from vps_dev_agent.bridges.kimi_cli.limit_checker import LimitChecker, LimitManager
from vps_dev_agent.bridges.kimi_cli.auth import KimiAuthChecker
from vps_dev_agent.bridges.kimi_cli.expect_driver import KimiExpectDriver, ExecutionResult as InteractiveResult
from vps_dev_agent.core.para_models import Task, TaskStatus, Project, DatabaseManager
from vps_dev_agent.safety.git_guardian import GitGuardian
from vps_dev_agent.utils.logger import get_logger

logger = get_logger()


class ExecutionMode(str, Enum):
    """Execution mode for Kimi CLI."""
    NATIVE_BATCH = "native_batch"
    INTERACTIVE = "interactive"


@dataclass
class BatchResult:
    """Result of batch execution."""
    task_id: str
    success: bool
    exit_code: int
    files_modified: List[str] = field(default_factory=list)
    summary: Optional[str] = None
    tokens_used: Optional[int] = None
    error_message: Optional[str] = None
    validation_passed: bool = False


class KimiBatchExecutor:
    """Executes tasks using Kimi Code CLI."""
    
    def __init__(
        self,
        database_url: str,
        mode: ExecutionMode = ExecutionMode.NATIVE_BATCH,
        auto_apply: bool = False,
        timeout_minutes: int = 30,
    ):
        self.database_url = database_url
        self.db = DatabaseManager(database_url)
        self.mode = mode
        self.auto_apply = auto_apply
        self.timeout_minutes = timeout_minutes
        
        self.limit_manager = LimitManager()
        self.auth_checker = KimiAuthChecker()
        
        self._expect_driver: Optional[KimiExpectDriver] = None
    
    def run_batch_loop(
        self,
        project_name: Optional[str] = None,
        max_tasks: Optional[int] = None,
        continuous: bool = False,
    ) -> List[BatchResult]:
        """Run batch execution loop.
        
        Args:
            project_name: Filter by project name
            max_tasks: Maximum number of tasks to execute
            continuous: Keep running until queue is empty
            
        Returns:
            List of batch results
        """
        results = []
        task_count = 0
        
        logger.info(
            "Starting batch loop",
            project=project_name,
            max_tasks=max_tasks,
            continuous=continuous
        )
        
        while True:
            # Check limits before each task
            should_pause, message = self.limit_manager.should_pause_queue()
            if should_pause:
                logger.error(f"Queue paused: {message}")
                break
            
            # Fetch next task
            task = self._fetch_next_task(project_name)
            
            if not task:
                if continuous:
                    logger.info("No pending tasks, waiting...")
                    import time
                    time.sleep(5)
                    continue
                else:
                    logger.info("No pending tasks, exiting")
                    break
            
            # Execute task
            result = self.execute_task(task.id)
            results.append(result)
            task_count += 1
            
            if max_tasks and task_count >= max_tasks:
                logger.info(f"Reached max tasks ({max_tasks})")
                break
            
            # Small delay between tasks
            if not result.success:
                logger.warning("Task failed, pausing briefly...")
                import time
                time.sleep(2)
        
        return results
    
    def _fetch_next_task(self, project_name: Optional[str] = None) -> Optional[Task]:
        """Fetch the next pending task."""
        session = self.db.get_session()
        
        try:
            query = session.query(Task).filter_by(status=TaskStatus.PENDING)
            
            if project_name:
                from vps_dev_agent.core.para_models import Project
                project = session.query(Project).filter_by(name=project_name).first()
                if project:
                    query = query.filter_by(project_id=project.id)
            
            # Order by priority (ascending - lower is higher priority)
            task = query.order_by(
                Task.priority.asc(),
                Task.created_at.asc()
            ).first()
            
            return task
            
        finally:
            session.close()
    
    def execute_task(self, task_id: str) -> BatchResult:
        """Execute a single task."""
        session = self.db.get_session()
        
        try:
            task = session.query(Task).filter_by(id=task_id).first()
            if not task:
                return BatchResult(
                    task_id=task_id,
                    success=False,
                    exit_code=1,
                    error_message="Task not found"
                )
            
            project = session.query(Project).filter_by(id=task.project_id).first()
            if not project:
                return BatchResult(
                    task_id=task_id,
                    success=False,
                    exit_code=1,
                    error_message="Project not found"
                )
            
            # Update task status
            task.status = TaskStatus.RUNNING
            task.started_at = datetime.utcnow()
            task.attempt_count += 1
            session.commit()
            
            logger.info(f"Executing task {task_id}", project=project.name)
            
            # Pre-flight checks
            if not self._preflight_check(project):
                task.status = TaskStatus.FAILED
                task.error_log = "Preflight check failed"
                session.commit()
                return BatchResult(
                    task_id=task_id,
                    success=False,
                    exit_code=1,
                    error_message="Preflight check failed"
                )
            
            # Prepare workspace and context
            spec_path = Path(task.spec_path)
            if not spec_path.is_absolute():
                spec_path = Path(project.repo_path) / spec_path
            
            prompt = self._prepare_prompt(task, project, spec_path)
            
            # Create git backup
            git_guardian = GitGuardian(project.repo_path)
            backup = git_guardian.create_backup(str(task_id))
            
            # Execute based on mode
            if self.mode == ExecutionMode.NATIVE_BATCH:
                result = self._execute_native(task, project, prompt)
            else:
                result = self._execute_interactive(task, project, prompt)
            
            # Update task with results
            task.kimi_exit_code = result.exit_code
            task.kimi_tokens_used = result.tokens_used
            
            if result.success:
                task.status = TaskStatus.COMPLETED
                task.completed_at = datetime.utcnow()
                task.result_summary = result.summary
                
                # Git commit
                if result.summary:
                    git_guardian.commit_changes(
                        message=result.summary,
                        files=result.files_modified,
                        task_id=str(task_id),
                    )
                
                # Cleanup backup
                git_guardian.cleanup_backup(str(task_id))
                
            else:
                task.status = TaskStatus.FAILED
                task.error_log = result.error_message
                
                # Rollback on failure
                if backup:
                    git_guardian.restore_backup(str(task_id))
            
            session.commit()
            
            return result
            
        except Exception as e:
            session.rollback()
            logger.error(f"Task execution failed: {e}")
            
            # Try to mark task as failed
            try:
                task.status = TaskStatus.FAILED
                task.error_log = str(e)
                session.commit()
            except:
                pass
            
            return BatchResult(
                task_id=task_id,
                success=False,
                exit_code=1,
                error_message=str(e)
            )
            
        finally:
            session.close()
    
    def _preflight_check(self, project: Project) -> bool:
        """Run pre-flight checks."""
        # Check auth
        if not self.auth_checker.is_session_valid():
            logger.error("Not authenticated with Kimi CLI")
            return False
        
        # Check limits
        can_proceed, message = self.limit_manager.should_pause_queue()
        if not can_proceed:
            logger.error(f"Limit check failed: {message}")
            return False
        
        # Check project path exists
        if not Path(project.repo_path).exists():
            logger.error(f"Project path does not exist: {project.repo_path}")
            return False
        
        return True
    
    def _prepare_prompt(
        self,
        task: Task,
        project: Project,
        spec_path: Path,
    ) -> str:
        """Prepare prompt from spec and context."""
        from vps_dev_agent.core.spec_parser import SpecParser
        from vps_dev_agent.prompts.formatter import PromptFormatter
        
        # Load spec
        parser = SpecParser(spec_path)
        spec = parser.load()
        
        # Build PARA context
        context = self._build_para_context(project, spec)
        
        # Format prompt
        formatter = PromptFormatter()
        prompt = formatter.format_kimi_prompt(
            task=task,
            project=project,
            spec=spec,
            context=context,
            auto_apply=self.auto_apply or task.yolo_mode,
        )
        
        return prompt
    
    def _build_para_context(self, project: Project, spec) -> Dict[str, Any]:
        """Build context from PARA structure."""
        session = self.db.get_session()
        context = {
            'project_name': project.name,
            'project_description': project.description,
            'areas': [],
            'resources': [],
            'archives': [],
        }
        
        try:
            from vps_dev_agent.core.para_models import Area, Resource, Archive
            
            # Get areas
            areas = session.query(Area).filter_by(project_id=project.id).all()
            context['areas'] = [
                {'name': a.name, 'description': a.description}
                for a in areas
            ]
            
            # Get relevant resources
            if spec.context.area_ids:
                resources = session.query(Resource).filter(
                    Resource.area_id.in_(spec.context.area_ids)
                ).all()
                context['resources'] = [
                    {
                        'type': r.type,
                        'title': r.title,
                        'content': r.content[:1000] if r.content else None,
                        'file_path': r.file_path,
                    }
                    for r in resources
                ]
            
            # Get recent archives (lessons learned)
            if spec.context.include_archives:
                archives = session.query(Archive).filter_by(
                    project_id=project.id,
                    success=True,
                ).order_by(Archive.created_at.desc()).limit(
                    spec.context.archive_limit
                ).all()
                
                context['archives'] = [
                    {
                        'lessons': a.lessons_learned,
                        'task_description': a.task_description,
                    }
                    for a in archives if a.lessons_learned
                ]
            
        finally:
            session.close()
        
        return context
    
    def _execute_native(
        self,
        task: Task,
        project: Project,
        prompt: str,
    ) -> BatchResult:
        """Execute using native batch mode."""
        task_id = str(task.id)
        
        # Write prompt to temp file
        with tempfile.NamedTemporaryFile(
            mode='w',
            suffix='.txt',
            delete=False,
            encoding='utf-8'
        ) as f:
            f.write(prompt)
            prompt_file = f.name
        
        try:
            # Build command
            cmd = self._build_native_command(
                task_id=task_id,
                prompt_file=prompt_file,
                working_dir=project.repo_path,
                auto_apply=self.auto_apply or task.yolo_mode,
                timeout=self.timeout_minutes,
            )
            
            logger.debug(f"Executing: {cmd}")
            
            # Run command
            result = subprocess.run(
                cmd,
                shell=True,
                capture_output=True,
                text=True,
                timeout=self.timeout_minutes * 60,
            )
            
            # Parse output
            return self._parse_native_output(task_id, result)
            
        except subprocess.TimeoutExpired:
            return BatchResult(
                task_id=task_id,
                success=False,
                exit_code=1,
                error_message=f"Timeout after {self.timeout_minutes} minutes"
            )
        except Exception as e:
            return BatchResult(
                task_id=task_id,
                success=False,
                exit_code=1,
                error_message=str(e)
            )
        finally:
            # Cleanup temp file
            try:
                os.unlink(prompt_file)
            except:
                pass
    
    def _build_native_command(
        self,
        task_id: str,
        prompt_file: str,
        working_dir: str,
        auto_apply: bool,
        timeout: int,
    ) -> str:
        """Build native batch command."""
        # Note: This is a template - actual command structure depends on Kimi CLI
        # Adjust according to actual Kimi CLI interface
        cmd_parts = [
            "kimi",
            "execute",
            f"--task-id {task_id}",
            f"--prompt-file {prompt_file}",
            f"--working-dir {working_dir}",
            "--output-format json",
            f"--timeout {timeout}m",
        ]
        
        if auto_apply:
            cmd_parts.append("--auto-apply")
        
        return " ".join(cmd_parts)
    
    def _parse_native_output(
        self,
        task_id: str,
        result: subprocess.CompletedProcess,
    ) -> BatchResult:
        """Parse native execution output."""
        output = result.stdout + result.stderr
        
        # Try to parse JSON
        try:
            # Look for JSON in output
            json_match = re.search(r'\{.*\}', output, re.DOTALL)
            if json_match:
                data = json.loads(json_match.group())
                
                return BatchResult(
                    task_id=task_id,
                    success=data.get('exit_code', 1) == 0,
                    exit_code=data.get('exit_code', 1),
                    files_modified=[f.get('path') for f in data.get('files_modified', [])],
                    summary=data.get('summary'),
                    tokens_used=data.get('tokens_used'),
                    error_message=data.get('error') if data.get('exit_code', 0) != 0 else None,
                )
        except json.JSONDecodeError:
            pass
        
        # Fallback: parse from text
        return BatchResult(
            task_id=task_id,
            success=result.returncode == 0,
            exit_code=result.returncode,
            summary=output[:200] if output else None,
            error_message=output if result.returncode != 0 else None,
        )
    
    def _execute_interactive(
        self,
        task: Task,
        project: Project,
        prompt: str,
    ) -> BatchResult:
        """Execute using interactive mode (fallback)."""
        task_id = str(task.id)
        
        try:
            driver = KimiExpectDriver(timeout=self.timeout_minutes * 60)
            
            result = driver.execute_task(
                prompt_text=prompt,
                auto_apply=self.auto_apply or task.yolo_mode,
                working_dir=project.repo_path,
            )
            
            return BatchResult(
                task_id=task_id,
                success=result.exit_code == 0,
                exit_code=result.exit_code,
                files_modified=[f.get('path') for f in result.files_modified],
                summary=result.summary,
                tokens_used=result.tokens_used,
                error_message=result.stderr if result.exit_code != 0 else None,
            )
            
        except Exception as e:
            return BatchResult(
                task_id=task_id,
                success=False,
                exit_code=1,
                error_message=str(e)
            )
