"""LLM adapter using LiteLLM."""

import os
import json
from typing import List, Dict, Any, Optional, AsyncGenerator
from dataclasses import dataclass
from enum import Enum

from tenacity import retry, stop_after_attempt, wait_exponential
import litellm
from litellm import completion, acompletion

from vps_dev_agent.utils.logger import get_logger

logger = get_logger()


class LLMProvider(str, Enum):
    """Supported LLM providers."""
    MOONSHOT = "moonshot"
    DEEPSEEK = "deepseek"
    OPENAI = "openai"
    ANTHROPIC = "anthropic"


@dataclass
class LLMResponse:
    """Structured LLM response."""
    content: str
    model: str
    usage: Dict[str, int]
    finish_reason: Optional[str] = None
    raw_response: Optional[Any] = None


@dataclass
class FileChange:
    """Represents a file change from LLM."""
    path: str
    operation: str  # create, modify, delete
    content: Optional[str] = None
    diff: Optional[str] = None


class LLMAdapter:
    """Adapter for LLM interactions using LiteLLM."""
    
    # Provider priority fallback order
    FALLBACK_ORDER = [
        LLMProvider.MOONSHOT,
        LLMProvider.DEEPSEEK,
        LLMProvider.OPENAI,
    ]
    
    # Model mappings
    DEFAULT_MODELS = {
        LLMProvider.MOONSHOT: "moonshot-v1-32k",
        LLMProvider.DEEPSEEK: "deepseek-chat",
        LLMProvider.OPENAI: "gpt-4o",
        LLMProvider.ANTHROPIC: "claude-3-5-sonnet-20240620",
    }
    
    def __init__(
        self,
        provider: Optional[LLMProvider] = None,
        model: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
        api_key: Optional[str] = None,
    ):
        self.provider = provider or self._get_first_available_provider()
        self.model = model or self.DEFAULT_MODELS[self.provider]
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.api_key = api_key or self._get_api_key(self.provider)
        
        # Set API key in environment for LiteLLM
        if self.api_key:
            env_var = f"{self.provider.value.upper()}_API_KEY"
            os.environ[env_var] = self.api_key
    
    def _get_api_key(self, provider: LLMProvider) -> Optional[str]:
        """Get API key from environment."""
        env_vars = {
            LLMProvider.MOONSHOT: ["MOONSHOT_API_KEY", "KIMI_API_KEY"],
            LLMProvider.DEEPSEEK: ["DEEPSEEK_API_KEY"],
            LLMProvider.OPENAI: ["OPENAI_API_KEY"],
            LLMProvider.ANTHROPIC: ["ANTHROPIC_API_KEY"],
        }
        
        for env_var in env_vars.get(provider, []):
            key = os.getenv(env_var)
            if key:
                return key
        return None
    
    def _get_first_available_provider(self) -> LLMProvider:
        """Find first provider with API key available."""
        for provider in self.FALLBACK_ORDER:
            if self._get_api_key(provider):
                return provider
        # Default to Moonshot even if no key (will fail gracefully)
        return LLMProvider.MOONSHOT
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        reraise=True
    )
    def complete(
        self,
        messages: List[Dict[str, str]],
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        tools: Optional[List[Dict]] = None,
    ) -> LLMResponse:
        """Send completion request to LLM."""
        temp = temperature if temperature is not None else self.temperature
        tokens = max_tokens if max_tokens is not None else self.max_tokens
        
        try:
            response = completion(
                model=f"{self.provider.value}/{self.model}",
                messages=messages,
                temperature=temp,
                max_tokens=tokens,
                tools=tools,
            )
            
            return LLMResponse(
                content=response.choices[0].message.content or "",
                model=response.model,
                usage={
                    "prompt_tokens": response.usage.prompt_tokens,
                    "completion_tokens": response.usage.completion_tokens,
                    "total_tokens": response.usage.total_tokens,
                },
                finish_reason=response.choices[0].finish_reason,
                raw_response=response,
            )
            
        except Exception as e:
            logger.error(f"LLM completion failed: {e}", provider=self.provider.value)
            raise
    
    async def complete_async(
        self,
        messages: List[Dict[str, str]],
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> LLMResponse:
        """Async completion request."""
        temp = temperature if temperature is not None else self.temperature
        tokens = max_tokens if max_tokens is not None else self.max_tokens
        
        try:
            response = await acompletion(
                model=f"{self.provider.value}/{self.model}",
                messages=messages,
                temperature=temp,
                max_tokens=tokens,
            )
            
            return LLMResponse(
                content=response.choices[0].message.content or "",
                model=response.model,
                usage={
                    "prompt_tokens": response.usage.prompt_tokens,
                    "completion_tokens": response.usage.completion_tokens,
                    "total_tokens": response.usage.total_tokens,
                },
                finish_reason=response.choices[0].finish_reason,
                raw_response=response,
            )
            
        except Exception as e:
            logger.error(f"Async LLM completion failed: {e}", provider=self.provider.value)
            raise
    
    def generate_code_changes(
        self,
        context: str,
        spec: str,
        project_files: Optional[List[str]] = None,
    ) -> List[FileChange]:
        """Generate code changes based on context and spec."""
        
        system_prompt = """You are an expert software developer. Your task is to generate code changes based on the provided specification.

Respond with a JSON object containing a "changes" array. Each change should have:
- "path": file path relative to project root
- "operation": "create", "modify", or "delete"
- "content": full file content (for create/modify)
- "diff": unified diff format (optional, for modify)

Example response:
```json
{
  "changes": [
    {
      "path": "src/main.py",
      "operation": "modify",
      "content": "# new content here",
      "diff": "@@ -1,5 +1,5 @@..."
    }
  ]
}
```

Important:
1. Provide complete file content for new files
2. For modifications, provide the full updated file content
3. Ensure all code is syntactically correct
4. Follow existing code style and conventions
"""

        user_prompt = f"""Context:
{context}

Specification:
{spec}

"""
        if project_files:
            user_prompt += f"""Existing project files:
{chr(10).join(f"- {f}" for f in project_files)}

"""
        
        user_prompt += "Generate the necessary code changes as JSON."
        
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]
        
        response = self.complete(messages, temperature=0.3)
        
        # Parse JSON response
        try:
            content = response.content
            # Extract JSON from markdown code blocks if present
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0]
            elif "```" in content:
                content = content.split("```")[1].split("```")[0]
            
            data = json.loads(content.strip())
            changes = []
            for change_data in data.get("changes", []):
                changes.append(FileChange(
                    path=change_data["path"],
                    operation=change_data["operation"],
                    content=change_data.get("content"),
                    diff=change_data.get("diff"),
                ))
            return changes
            
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse LLM response as JSON: {e}")
            logger.debug(f"Response content: {response.content[:500]}")
            raise ValueError(f"Invalid JSON response from LLM: {e}")
    
    def switch_provider(self, provider: LLMProvider) -> bool:
        """Switch to a different provider."""
        api_key = self._get_api_key(provider)
        if not api_key:
            return False
        
        self.provider = provider
        self.model = self.DEFAULT_MODELS[provider]
        self.api_key = api_key
        
        env_var = f"{provider.value.upper()}_API_KEY"
        os.environ[env_var] = api_key
        
        logger.info(f"Switched to provider: {provider.value}")
        return True


def get_default_adapter() -> LLMAdapter:
    """Get default LLM adapter instance."""
    return LLMAdapter()
