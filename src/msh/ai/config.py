"""
AI Configuration Management for msh.

Manages AI provider and model configuration.
"""
import os
import yaml
from typing import Dict, Any, Optional
from pathlib import Path
from msh.logger import logger


class AIConfig:
    """Manages AI configuration."""
    
    GLOBAL_CONFIG_PATH = os.path.expanduser("~/.msh/config")
    PROJECT_CONFIG_KEY = "ai"
    
    def __init__(self, project_root: Optional[str] = None):
        """
        Initialize AI config.
        
        Args:
            project_root: Project root directory. Defaults to current working directory.
        """
        if project_root is None:
            project_root = os.getcwd()
        
        self.project_root = project_root
        self.project_config_path = os.path.join(project_root, "msh.yaml")
    
    def load(self) -> Dict[str, Any]:
        """
        Load AI configuration from global and project configs.
        
        Project config overrides global config.
        
        Returns:
            AI configuration dictionary
        """
        config = {}
        
        # Load global config
        if os.path.exists(self.GLOBAL_CONFIG_PATH):
            try:
                with open(self.GLOBAL_CONFIG_PATH, "r") as f:
                    global_config = yaml.safe_load(f) or {}
                    config = global_config.get("ai", {}).copy()
            except (yaml.YAMLError, IOError) as e:
                logger.warning(f"Failed to load global AI config: {e}")
        
        # Load project config (overrides global)
        if os.path.exists(self.project_config_path):
            try:
                with open(self.project_config_path, "r") as f:
                    project_config = yaml.safe_load(f) or {}
                    project_ai_config = project_config.get("ai", {})
                    if project_ai_config:
                        config.update(project_ai_config)
            except (yaml.YAMLError, IOError) as e:
                logger.warning(f"Failed to load project AI config: {e}")
        
        return config
    
    def save_global(
        self,
        provider: Optional[str] = None,
        model: Optional[str] = None,
        api_key: Optional[str] = None,
        endpoint: Optional[str] = None,
        timeout_seconds: Optional[int] = None
    ) -> None:
        """
        Save AI configuration to global config file.
        
        Args:
            provider: AI provider ID (openai, anthropic, ollama, etc.)
            model: Model name or version
            api_key: API key or env:VAR_NAME reference
            endpoint: Optional override for API endpoint
            timeout_seconds: Optional timeout in seconds (default: 60)
        """
        # Load existing config
        config = {}
        if os.path.exists(self.GLOBAL_CONFIG_PATH):
            try:
                with open(self.GLOBAL_CONFIG_PATH, "r") as f:
                    config = yaml.safe_load(f) or {}
            except (yaml.YAMLError, IOError):
                pass
        
        # Update AI section
        if "ai" not in config:
            config["ai"] = {}
        
        ai_config = config["ai"]
        
        if provider is not None:
            ai_config["provider"] = provider
        if model is not None:
            ai_config["model"] = model
        if api_key is not None:
            ai_config["api_key"] = api_key
        if endpoint is not None:
            ai_config["endpoint"] = endpoint
        if timeout_seconds is not None:
            ai_config["timeout_seconds"] = timeout_seconds
        elif "timeout_seconds" not in ai_config:
            ai_config["timeout_seconds"] = 60
        
        # Save
        os.makedirs(os.path.dirname(self.GLOBAL_CONFIG_PATH), exist_ok=True)
        with open(self.GLOBAL_CONFIG_PATH, "w") as f:
            yaml.dump(config, f, default_flow_style=False)
    
    def get_api_key(self) -> Optional[str]:
        """
        Get API key, resolving env:VAR_NAME references.
        
        Returns:
            API key string or None
        """
        config = self.load()
        api_key = config.get("api_key")
        
        if not api_key:
            return None
        
        # Check if it's an env reference
        if isinstance(api_key, str) and api_key.startswith("env:"):
            var_name = api_key[4:]
            return os.environ.get(var_name)
        
        return api_key
    
    def validate(self) -> bool:
        """
        Validate AI configuration.
        
        Returns:
            True if configuration is valid
        """
        config = self.load()
        
        # Check required fields
        if not config.get("provider"):
            logger.error("AI provider not configured. Run 'msh config ai --provider <provider>'")
            return False
        
        if not config.get("model"):
            logger.error("AI model not configured. Run 'msh config ai --model <model>'")
            return False
        
        # Check API key
        api_key = self.get_api_key()
        if not api_key:
            logger.warning("AI API key not configured. Some AI features may not work.")
        
        return True

