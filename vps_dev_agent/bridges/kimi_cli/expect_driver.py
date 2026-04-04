"""Pexpect driver for interactive Kimi CLI mode (fallback)."""

import re
import time
import select
from typing import Optional, List, Dict, Any, Callable
from dataclasses import dataclass
from enum import Enum

from vps_dev_agent.utils.logger import get_logger

logger = get_logger()

# Try to import pexpect, but make it optional
try:
    import pexpect
    PEXPECT_AVAILABLE = True
except ImportError:
    PEXPECT_AVAILABLE = False
    logger.warning("pexpect not installed, interactive mode unavailable")


class PromptType(str, Enum):
    """Types of prompts from Kimi CLI."""
    READY = "ready"
    CONFIRM = "confirm"
    ERROR = "error"
    LIMIT_WARNING = "limit_warning"
    INPUT_REQUEST = "input_request"
    UNKNOWN = "unknown"


@dataclass
class Prompt:
    """Detected prompt from CLI."""
    type: PromptType
    text: str
    raw_output: str


@dataclass
class ExecutionResult:
    """Result of interactive execution."""
    exit_code: int
    stdout: str
    stderr: str
    files_modified: List[Dict[str, Any]]
    summary: Optional[str] = None
    tokens_used: Optional[int] = None


class KimiExpectDriver:
    """Pexpect-based driver for interactive Kimi CLI."""
    
    # Default prompt patterns
    DEFAULT_PROMPTS = {
        PromptType.READY: r"moonshot@kimi-cli",
        PromptType.CONFIRM: r"Apply these changes\?",
        PromptType.ERROR: r"Error:",
        PromptType.LIMIT_WARNING: r"limit exceeded|quota exceeded",
        PromptType.INPUT_REQUEST: r">\s*$",
    }
    
    def __init__(
        self,
        timeout: int = 300,
        prompt_patterns: Optional[Dict[PromptType, str]] = None,
    ):
        self.timeout = timeout
        self.prompt_patterns = prompt_patterns or self.DEFAULT_PROMPTS.copy()
        self.child: Optional[Any] = None
        self._output_buffer: List[str] = []
        
        if not PEXPECT_AVAILABLE:
            raise RuntimeError(
                "pexpect is required for interactive mode. "
                "Install: pip install pexpect"
            )
    
    def start_session(self, working_dir: Optional[str] = None) -> bool:
        """Start Kimi CLI session."""
        try:
            cmd = "kimi"
            if working_dir:
                cmd = f"cd {working_dir} && {cmd}"
            
            self.child = pexpect.spawn(cmd, timeout=self.timeout, encoding='utf-8')
            
            # Wait for ready prompt
            index = self.child.expect([
                self.prompt_patterns[PromptType.READY],
                pexpect.TIMEOUT,
                pexpect.EOF,
            ])
            
            if index == 0:
                logger.info("Kimi CLI session started")
                return True
            else:
                logger.error("Failed to start Kimi CLI session")
                return False
                
        except Exception as e:
            logger.error(f"Failed to start session: {e}")
            return False
    
    def send_command(self, command: str) -> bool:
        """Send a command to Kimi CLI."""
        if not self.child:
            logger.error("No active session")
            return False
        
        try:
            self.child.sendline(command)
            logger.debug(f"Sent command: {command[:100]}...")
            return True
        except Exception as e:
            logger.error(f"Failed to send command: {e}")
            return False
    
    def wait_for_prompt(self, timeout: Optional[int] = None) -> Prompt:
        """Wait for and identify a prompt."""
        if not self.child:
            return Prompt(PromptType.UNKNOWN, "", "No active session")
        
        timeout = timeout or self.timeout
        patterns = list(self.prompt_patterns.values())
        
        try:
            index = self.child.expect(patterns + [pexpect.TIMEOUT, pexpect.EOF], timeout=timeout)
            
            output = self.child.before or ""
            self._output_buffer.append(output)
            
            if index < len(patterns):
                prompt_type = list(self.prompt_patterns.keys())[index]
                matched_text = self.child.after or ""
                
                return Prompt(
                    type=prompt_type,
                    text=matched_text,
                    raw_output=output,
                )
            elif index == len(patterns):
                return Prompt(PromptType.UNKNOWN, "", "Timeout waiting for prompt")
            else:
                return Prompt(PromptType.UNKNOWN, "", "EOF reached")
                
        except Exception as e:
            logger.error(f"Error waiting for prompt: {e}")
            return Prompt(PromptType.UNKNOWN, "", str(e))
    
    def execute_task(
        self,
        prompt_text: str,
        auto_apply: bool = False,
        working_dir: Optional[str] = None,
    ) -> ExecutionResult:
        """Execute a task in interactive mode.
        
        Args:
            prompt_text: The task prompt to send
            auto_apply: Whether to auto-confirm changes
            working_dir: Working directory for execution
            
        Returns:
            ExecutionResult with parsed output
        """
        if not self.start_session(working_dir):
            return ExecutionResult(
                exit_code=1,
                stdout="",
                stderr="Failed to start Kimi CLI session",
                files_modified=[],
            )
        
        try:
            # Send the prompt
            self.send_command(f"/code {prompt_text}")
            
            files_modified = []
            summary = None
            tokens_used = None
            
            # Interaction loop
            while True:
                prompt = self.wait_for_prompt()
                
                if prompt.type == PromptType.READY:
                    # Task completed
                    break
                    
                elif prompt.type == PromptType.CONFIRM:
                    # Need to confirm changes
                    if auto_apply:
                        self.child.sendline("y")
                        logger.info("Auto-approved changes")
                    else:
                        # In conservative mode, we'd need to ask user
                        # For now, reject to be safe
                        self.child.sendline("n")
                        logger.warning("Changes rejected (conservative mode)")
                        
                elif prompt.type == PromptType.ERROR:
                    # Error occurred
                    return ExecutionResult(
                        exit_code=1,
                        stdout="\n".join(self._output_buffer),
                        stderr=prompt.raw_output,
                        files_modified=files_modified,
                    )
                    
                elif prompt.type == PromptType.LIMIT_WARNING:
                    # Limit reached
                    return ExecutionResult(
                        exit_code=2,
                        stdout="\n".join(self._output_buffer),
                        stderr="Limit exceeded",
                        files_modified=files_modified,
                    )
                    
                elif prompt.type == PromptType.INPUT_REQUEST:
                    # Kimi is waiting for input
                    # Try to parse any intermediate results
                    self._parse_intermediate_output(prompt.raw_output, files_modified)
                    
                elif prompt.type == PromptType.UNKNOWN:
                    # Unknown state
                    logger.warning(f"Unknown prompt: {prompt.text}")
                    break
            
            # Parse final output
            full_output = "\n".join(self._output_buffer)
            files_modified = self._parse_files_modified(full_output)
            summary = self._parse_summary(full_output)
            tokens_used = self._parse_tokens(full_output)
            
            return ExecutionResult(
                exit_code=0,
                stdout=full_output,
                stderr="",
                files_modified=files_modified,
                summary=summary,
                tokens_used=tokens_used,
            )
            
        except Exception as e:
            logger.error(f"Execution failed: {e}")
            return ExecutionResult(
                exit_code=1,
                stdout="\n".join(self._output_buffer),
                stderr=str(e),
                files_modified=[],
            )
        
        finally:
            self.close()
    
    def _parse_intermediate_output(self, output: str, files_modified: List[Dict]):
        """Parse intermediate output for file changes."""
        # This would extract file modifications from ongoing output
        # Implementation depends on Kimi CLI output format
        pass
    
    def _parse_files_modified(self, output: str) -> List[Dict[str, Any]]:
        """Parse list of modified files from output."""
        files = []
        
        # Look for JSON-like file listings
        # Pattern: ```json { "files": [...] } ```
        json_pattern = r'```json\s*(.*?)```'
        matches = re.findall(json_pattern, output, re.DOTALL)
        
        for match in matches:
            try:
                import json
                data = json.loads(match)
                if 'files' in data:
                    files.extend(data['files'])
                elif 'changes' in data:
                    files.extend(data['changes'])
            except json.JSONDecodeError:
                continue
        
        return files
    
    def _parse_summary(self, output: str) -> Optional[str]:
        """Parse summary from output."""
        # Look for summary section
        patterns = [
            r'Summary:\s*(.+?)(?=\n\n|\Z)',
            r'## Summary\s*(.+?)(?=\n##|\Z)',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, output, re.DOTALL | re.IGNORECASE)
            if match:
                return match.group(1).strip()
        
        return None
    
    def _parse_tokens(self, output: str) -> Optional[int]:
        """Parse token usage from output."""
        pattern = r'(\d+)\s*tokens?\s*used'
        match = re.search(pattern, output, re.IGNORECASE)
        
        if match:
            return int(match.group(1))
        
        return None
    
    def close(self):
        """Close the session."""
        if self.child:
            try:
                self.child.sendline("/exit")
                self.child.close()
            except:
                pass
            finally:
                self.child = None
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
