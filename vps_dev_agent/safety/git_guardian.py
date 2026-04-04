"""Git backup and revert system."""

import os
import uuid
from pathlib import Path
from typing import Optional, List
from dataclasses import dataclass
from datetime import datetime

import git
from git import Repo, GitCommandError

from vps_dev_agent.utils.logger import get_logger

logger = get_logger()


@dataclass
class BackupInfo:
    """Backup branch information."""
    task_id: str
    branch_name: str
    original_branch: str
    commit_hash: str
    created_at: datetime


class GitGuardian:
    """Manages git backups and rollbacks."""
    
    BACKUP_PREFIX = "auto/backup"
    
    def __init__(self, repo_path: str):
        self.repo_path = Path(repo_path)
        self.repo: Optional[Repo] = None
        self._init_repo()
    
    def _init_repo(self):
        """Initialize git repository connection."""
        try:
            self.repo = Repo(self.repo_path)
            logger.debug(f"Initialized git repo: {self.repo_path}")
        except git.InvalidGitRepositoryError:
            logger.warning(f"Not a git repository: {self.repo_path}")
            self.repo = None
    
    def is_git_repo(self) -> bool:
        """Check if path is a valid git repository."""
        return self.repo is not None
    
    def has_uncommitted_changes(self) -> bool:
        """Check if there are uncommitted changes."""
        if not self.repo:
            return False
        return self.repo.is_dirty() or len(self.repo.untracked_files) > 0
    
    def create_backup(self, task_id: str) -> Optional[BackupInfo]:
        """Create a backup branch for the task."""
        if not self.repo:
            logger.warning("Not a git repository, cannot create backup")
            return None
        
        try:
            # Check for uncommitted changes
            if self.has_uncommitted_changes():
                logger.warning("Uncommitted changes detected, stashing...")
                self.repo.git.stash('push', '-m', f'auto-stash-before-task-{task_id}')
            
            # Get current branch
            original_branch = self.repo.active_branch.name
            commit_hash = self.repo.head.commit.hexsha
            
            # Create backup branch
            backup_branch = f"{self.BACKUP_PREFIX}/{task_id}"
            
            # Delete existing backup branch if exists
            if backup_branch in [b.name for b in self.repo.branches]:
                self.repo.delete_head(backup_branch, force=True)
            
            # Create new backup branch
            self.repo.create_head(backup_branch)
            
            backup_info = BackupInfo(
                task_id=task_id,
                branch_name=backup_branch,
                original_branch=original_branch,
                commit_hash=commit_hash,
                created_at=datetime.utcnow(),
            )
            
            logger.info(
                f"Created backup branch: {backup_branch}",
                task_id=task_id,
                commit=commit_hash[:8]
            )
            
            return backup_info
            
        except GitCommandError as e:
            logger.error(f"Failed to create backup: {e}")
            return None
    
    def restore_backup(self, task_id: str) -> bool:
        """Restore from backup branch."""
        if not self.repo:
            logger.warning("Not a git repository, cannot restore")
            return False
        
        try:
            backup_branch = f"{self.BACKUP_PREFIX}/{task_id}"
            
            # Check if backup branch exists
            if backup_branch not in [b.name for b in self.repo.branches]:
                logger.error(f"Backup branch not found: {backup_branch}")
                return False
            
            # Stash any current changes
            if self.has_uncommitted_changes():
                self.repo.git.stash('push', '-m', f'auto-stash-restore-{task_id}')
            
            # Get backup commit
            backup_commit = self.repo.heads[backup_branch].commit.hexsha
            
            # Hard reset to backup
            self.repo.head.reset(backup_commit, index=True, working_tree=True)
            
            logger.info(
                f"Restored from backup: {backup_branch}",
                task_id=task_id,
                commit=backup_commit[:8]
            )
            
            return True
            
        except GitCommandError as e:
            logger.error(f"Failed to restore backup: {e}")
            return False
    
    def commit_changes(
        self,
        message: str,
        files: Optional[List[str]] = None,
        task_id: Optional[str] = None,
    ) -> Optional[str]:
        """Commit changes with task metadata."""
        if not self.repo:
            logger.warning("Not a git repository, cannot commit")
            return None
        
        try:
            # Add files
            if files:
                for file_path in files:
                    full_path = self.repo_path / file_path
                    if full_path.exists():
                        self.repo.git.add(file_path)
            else:
                self.repo.git.add('-A')
            
            # Check if there's anything to commit
            if not self.repo.index.diff('HEAD'):
                logger.info("No changes to commit")
                return None
            
            # Prepare commit message
            full_message = message
            if task_id:
                full_message = f"[Task {task_id}] {message}"
            
            # Commit
            commit = self.repo.index.commit(full_message)
            
            logger.info(
                f"Created commit: {commit.hexsha[:8]}",
                message=message[:50]
            )
            
            return commit.hexsha
            
        except GitCommandError as e:
            logger.error(f"Failed to commit changes: {e}")
            return None
    
    def cleanup_backup(self, task_id: str) -> bool:
        """Remove backup branch after successful task."""
        if not self.repo:
            return False
        
        try:
            backup_branch = f"{self.BACKUP_PREFIX}/{task_id}"
            
            if backup_branch in [b.name for b in self.repo.branches]:
                self.repo.delete_head(backup_branch)
                logger.info(f"Cleaned up backup branch: {backup_branch}")
                return True
            
            return True
            
        except GitCommandError as e:
            logger.error(f"Failed to cleanup backup: {e}")
            return False
    
    def get_diff_since_backup(self, task_id: str) -> str:
        """Get diff between backup and current state."""
        if not self.repo:
            return ""
        
        try:
            backup_branch = f"{self.BACKUP_PREFIX}/{task_id}"
            
            if backup_branch not in [b.name for b in self.repo.branches]:
                return ""
            
            backup_commit = self.repo.heads[backup_branch].commit
            current_commit = self.repo.head.commit
            
            diff = self.repo.git.diff(backup_commit.hexsha, current_commit.hexsha)
            return diff
            
        except GitCommandError as e:
            logger.error(f"Failed to get diff: {e}")
            return ""
    
    def list_backups(self) -> List[str]:
        """List all backup branches."""
        if not self.repo:
            return []
        
        backups = [
            b.name for b in self.repo.branches
            if b.name.startswith(self.BACKUP_PREFIX)
        ]
        return backups
