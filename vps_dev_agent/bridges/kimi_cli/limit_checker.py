"""Kimi CLI subscription limit checker."""

import re
import json
import subprocess
from typing import Optional
from dataclasses import dataclass
from datetime import datetime
from enum import Enum

from vps_dev_agent.utils.logger import get_logger

logger = get_logger()


class SubscriptionTier(str, Enum):
    """Subscription tiers."""
    FREE = "Free"
    BASIC = "Basic"
    PRO = "Pro"
    ENTERPRISE = "Enterprise"


@dataclass
class QuotaInfo:
    """Quota information from Kimi CLI."""
    requests_remaining: int
    tokens_remaining: int
    tier: SubscriptionTier
    checked_at: datetime
    raw_output: Optional[str] = None
    
    @property
    def is_near_limit(self) -> bool:
        """Check if near limit (threshold: 10 requests)."""
        return self.requests_remaining <= 10
    
    @property
    def is_critical(self) -> bool:
        """Check if critically low (threshold: 3 requests)."""
        return self.requests_remaining <= 3
    
    @property
    def can_execute(self) -> bool:
        """Check if can execute at least one more task."""
        return self.requests_remaining > 0


class LimitChecker:
    """Checks Kimi CLI subscription limits."""
    
    # Regex patterns for parsing quota info
    PATTERNS = {
        'requests_remaining': re.compile(r'Remaining:\s*(\d+)\s*requests?', re.IGNORECASE),
        'tokens_remaining': re.compile(r'(\d+)\s*tokens?', re.IGNORECASE),
        'tier': re.compile(r'Tier:\s*(Pro|Basic|Free|Enterprise)', re.IGNORECASE),
    }
    
    def __init__(self, check_command: str = "kimi --version --show-limits"):
        self.check_command = check_command
        self._last_quota: Optional[QuotaInfo] = None
    
    def get_remaining_quota(self, force_refresh: bool = False) -> Optional[QuotaInfo]:
        """Get remaining quota from Kimi CLI."""
        if not force_refresh and self._last_quota:
            # Cache for 5 minutes
            age = datetime.utcnow() - self._last_quota.checked_at
            if age.seconds < 300:
                return self._last_quota
        
        try:
            result = subprocess.run(
                self.check_command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=30,
            )
            
            output = result.stdout + result.stderr
            quota = self._parse_quota(output)
            
            if quota:
                self._last_quota = quota
                logger.info(
                    f"Quota check: {quota.requests_remaining} requests remaining",
                    tier=quota.tier.value,
                    tokens=quota.tokens_remaining
                )
            else:
                logger.warning("Could not parse quota from Kimi CLI output")
                
            return quota
            
        except subprocess.TimeoutExpired:
            logger.error("Quota check timed out")
            return None
        except Exception as e:
            logger.error(f"Failed to check quota: {e}")
            return None
    
    def _parse_quota(self, output: str) -> Optional[QuotaInfo]:
        """Parse quota information from CLI output."""
        requests_match = self.PATTERNS['requests_remaining'].search(output)
        tokens_match = self.PATTERNS['tokens_remaining'].search(output)
        tier_match = self.PATTERNS['tier'].search(output)
        
        if not requests_match:
            logger.debug(f"Could not find requests remaining in output: {output[:500]}")
            return None
        
        requests_remaining = int(requests_match.group(1))
        tokens_remaining = int(tokens_match.group(1)) if tokens_match else 0
        
        tier = SubscriptionTier.FREE
        if tier_match:
            tier_str = tier_match.group(1).capitalize()
            try:
                tier = SubscriptionTier(tier_str)
            except ValueError:
                logger.warning(f"Unknown tier: {tier_str}")
        
        return QuotaInfo(
            requests_remaining=requests_remaining,
            tokens_remaining=tokens_remaining,
            tier=tier,
            checked_at=datetime.utcnow(),
            raw_output=output,
        )
    
    def is_near_limit(self, threshold: int = 10) -> bool:
        """Check if near limit."""
        quota = self.get_remaining_quota()
        if not quota:
            # If we can't check, assume we're fine but warn
            logger.warning("Could not verify quota, proceeding with caution")
            return False
        return quota.requests_remaining <= threshold
    
    def check_before_task(self) -> tuple[bool, Optional[str]]:
        """Check quota before executing a task.
        
        Returns:
            (can_proceed, warning_message)
        """
        quota = self.get_remaining_quota(force_refresh=True)
        
        if not quota:
            return True, "Could not verify quota, proceeding with caution"
        
        if quota.requests_remaining <= 0:
            return False, f"Quota exceeded. Tier: {quota.tier.value}"
        
        if quota.is_critical:
            return False, f"Critical: only {quota.requests_remaining} requests remaining"
        
        if quota.is_near_limit:
            return True, f"Warning: only {quota.requests_remaining} requests remaining"
        
        return True, None
    
    def wait_for_reset(self, poll_interval: int = 3600) -> bool:
        """Poll until quota resets or is upgraded.
        
        Args:
            poll_interval: Seconds between checks (default: 1 hour)
            
        Returns:
            True if quota available, False if interrupted
        """
        import time
        
        logger.info(f"Waiting for quota reset (polling every {poll_interval}s)")
        
        while True:
            quota = self.get_remaining_quota(force_refresh=True)
            
            if quota and quota.can_execute:
                logger.info(f"Quota available: {quota.requests_remaining} requests")
                return True
            
            logger.info(f"Quota still exceeded, waiting {poll_interval}s...")
            time.sleep(poll_interval)


class LimitManager:
    """Manages limit-related actions for the queue."""
    
    def __init__(self, checker: Optional[LimitChecker] = None):
        self.checker = checker or LimitChecker()
        self._paused_for_limit = False
    
    def should_pause_queue(self) -> tuple[bool, str]:
        """Check if queue should be paused due to limits."""
        can_proceed, message = self.checker.check_before_task()
        
        if not can_proceed:
            self._paused_for_limit = True
            return True, message
        
        return False, message or ""
    
    def resume_if_available(self) -> bool:
        """Check if queue can be resumed."""
        if not self._paused_for_limit:
            return True
        
        quota = self.checker.get_remaining_quota(force_refresh=True)
        
        if quota and quota.can_execute:
            self._paused_for_limit = False
            logger.info("Quota available, queue can resume")
            return True
        
        return False
