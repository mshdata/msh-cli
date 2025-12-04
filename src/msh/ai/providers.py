"""
AI Provider Abstractions for msh.

Supports multiple AI providers: OpenAI, Anthropic, Ollama, etc.
"""
import os
from typing import Dict, Any, Optional, List
from msh.ai.config import AIConfig
from msh.logger import logger


class AIProvider:
    """Base class for AI providers."""
    
    def __init__(self, config: Dict[str, Any]):
        """
        Initialize AI provider.
        
        Args:
            config: AI configuration dictionary
        """
        self.config = config
        self.provider = config.get("provider")
        self.model = config.get("model")
        self.api_key = self._get_api_key(config.get("api_key"))
        self.endpoint = config.get("endpoint")
        self.timeout = config.get("timeout_seconds", 60)
    
    def _get_api_key(self, api_key: Optional[str]) -> Optional[str]:
        """Resolve API key from config."""
        if not api_key:
            return None
        
        if isinstance(api_key, str) and api_key.startswith("env:"):
            var_name = api_key[4:]
            return os.environ.get(var_name)
        
        return api_key
    
    def call(self, prompt: str, context: Optional[Dict[str, Any]] = None) -> str:
        """
        Call the AI provider with a prompt.
        
        Args:
            prompt: Prompt text
            context: Optional context dictionary
            
        Returns:
            Response text
            
        Raises:
            NotImplementedError: Must be implemented by subclasses
        """
        raise NotImplementedError("Subclasses must implement call()")


class OpenAIProvider(AIProvider):
    """OpenAI provider implementation."""
    
    def call(self, prompt: str, context: Optional[Dict[str, Any]] = None) -> str:
        """Call OpenAI API."""
        try:
            import openai
            
            if not self.api_key:
                raise ValueError("OpenAI API key not configured")
            
            client = openai.OpenAI(api_key=self.api_key)
            
            messages = [{"role": "user", "content": prompt}]
            
            response = client.chat.completions.create(
                model=self.model,
                messages=messages,
                timeout=self.timeout
            )
            
            return response.choices[0].message.content or ""
        
        except ImportError:
            raise ImportError("openai package not installed. Install with: pip install openai")
        except Exception as e:
            logger.error(f"OpenAI API call failed: {e}")
            raise


class AnthropicProvider(AIProvider):
    """Anthropic provider implementation."""
    
    def call(self, prompt: str, context: Optional[Dict[str, Any]] = None) -> str:
        """Call Anthropic API."""
        try:
            import anthropic
            
            if not self.api_key:
                raise ValueError("Anthropic API key not configured")
            
            client = anthropic.Anthropic(api_key=self.api_key)
            
            message = client.messages.create(
                model=self.model,
                max_tokens=4096,
                messages=[{"role": "user", "content": prompt}]
            )
            
            return message.content[0].text if message.content else ""
        
        except ImportError:
            raise ImportError("anthropic package not installed. Install with: pip install anthropic")
        except Exception as e:
            logger.error(f"Anthropic API call failed: {e}")
            raise


class OllamaProvider(AIProvider):
    """Ollama provider implementation (local)."""
    
    def call(self, prompt: str, context: Optional[Dict[str, Any]] = None) -> str:
        """Call Ollama API (local)."""
        try:
            import requests
            
            endpoint = self.endpoint or "http://localhost:11434/api/generate"
            
            response = requests.post(
                endpoint,
                json={
                    "model": self.model,
                    "prompt": prompt,
                    "stream": False
                },
                timeout=self.timeout
            )
            
            response.raise_for_status()
            return response.json().get("response", "")
        
        except ImportError:
            raise ImportError("requests package not installed. Install with: pip install requests")
        except Exception as e:
            logger.error(f"Ollama API call failed: {e}")
            raise


def get_provider(config: Optional[Dict[str, Any]] = None, project_root: Optional[str] = None) -> AIProvider:
    """
    Get AI provider instance based on configuration.
    
    Args:
        config: Optional AI configuration dictionary. If None, loads from config files.
        project_root: Optional project root directory.
        
    Returns:
        AIProvider instance
        
    Raises:
        ValueError: If provider not supported or not configured
    """
    if config is None:
        ai_config = AIConfig(project_root=project_root)
        config = ai_config.load()
    
    provider_name = config.get("provider")
    if not provider_name:
        raise ValueError("AI provider not configured. Run 'msh config ai --provider <provider>'")
    
    provider_name_lower = provider_name.lower()
    
    if provider_name_lower == "openai":
        return OpenAIProvider(config)
    elif provider_name_lower == "anthropic":
        return AnthropicProvider(config)
    elif provider_name_lower == "ollama":
        return OllamaProvider(config)
    else:
        raise ValueError(f"Unsupported AI provider: {provider_name}")

