import os
import datetime
import contextlib
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Optional, Generator, Any
from rich.console import Console

from msh.constants import DEFAULT_LOGS_DIR, LOG_MAX_BYTES, LOG_BACKUP_COUNT


class StructuredLogger:
    """
    Structured logger that outputs to both console (Rich) and log files.
    
    Log files are written to .msh/logs/ directory with rotation.
    """
    
    def __init__(self, log_dir: Optional[str] = None, enable_file_logging: bool = True) -> None:
        """
        Initialize the logger.
        
        Args:
            log_dir: Optional directory for log files. Defaults to .msh/logs/
            enable_file_logging: Whether to write to log files. Defaults to True.
        """
        # Check if running in CI
        self.is_ci: bool = os.environ.get("CI", "false").lower() == "true" or \
                     os.environ.get("GITHUB_ACTIONS", "false").lower() == "true"
        self.console: Console = Console(force_terminal=not self.is_ci)
        
        # Setup file logging
        self.enable_file_logging: bool = enable_file_logging
        self.log_dir: Optional[str] = log_dir
        self.file_logger: Optional[logging.Logger] = None
        
        if self.enable_file_logging:
            self._setup_file_logging()
    
    def _setup_file_logging(self) -> None:
        """Setup file logging with rotation."""
        if self.log_dir is None:
            # Use project root to find .msh/logs/
            cwd = os.getcwd()
            self.log_dir = os.path.join(cwd, DEFAULT_LOGS_DIR)
        
        # Create logs directory if it doesn't exist
        Path(self.log_dir).mkdir(parents=True, exist_ok=True)
        
        # Setup Python logging
        self.file_logger = logging.getLogger("msh")
        self.file_logger.setLevel(logging.DEBUG)
        
        # Prevent duplicate logs if logger is initialized multiple times
        if self.file_logger.handlers:
            return
        
        # Main log file (rotates at configured size, keeps configured backups)
        main_log_path = os.path.join(self.log_dir, "msh.log")
        main_handler = RotatingFileHandler(
            main_log_path,
            maxBytes=LOG_MAX_BYTES,
            backupCount=LOG_BACKUP_COUNT,
            encoding='utf-8'
        )
        main_handler.setLevel(logging.DEBUG)
        main_formatter = logging.Formatter(
            '%(asctime)s [%(levelname)s] %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        main_handler.setFormatter(main_formatter)
        self.file_logger.addHandler(main_handler)
        
        # Error log file (only ERROR and CRITICAL)
        error_log_path = os.path.join(self.log_dir, "msh.error.log")
        error_handler = RotatingFileHandler(
            error_log_path,
            maxBytes=LOG_MAX_BYTES,
            backupCount=LOG_BACKUP_COUNT,
            encoding='utf-8'
        )
        error_handler.setLevel(logging.ERROR)
        error_formatter = logging.Formatter(
            '%(asctime)s [%(levelname)s] %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        error_handler.setFormatter(error_formatter)
        self.file_logger.addHandler(error_handler)
    
    def _strip_rich_markup(self, msg: str) -> str:
        """Remove Rich markup tags from message."""
        # Common Rich tags
        tags = [
            "[bold green]", "[/bold green]",
            "[bold blue]", "[/bold blue]",
            "[bold red]", "[/bold red]",
            "[bold yellow]", "[/bold yellow]",
            "[yellow]", "[/yellow]",
            "[green]", "[/green]",
            "[red]", "[/red]",
            "[blue]", "[/blue]",
            "[cyan]", "[/cyan]",
            "[magenta]", "[/magenta]",
            "[dim]", "[/dim]",
        ]
        clean_msg = msg
        for tag in tags:
            clean_msg = clean_msg.replace(tag, "")
        return clean_msg
    
    def _determine_log_level(self, msg: str) -> int:
        """Determine log level from message content."""
        msg_lower = msg.lower()
        if "[error]" in msg_lower or "[bold red]" in msg_lower:
            return logging.ERROR
        elif "[warn]" in msg_lower or "[yellow]" in msg_lower:
            return logging.WARNING
        elif "[debug]" in msg_lower:
            return logging.DEBUG
        else:
            return logging.INFO
    
    def print(self, msg: str, style: Optional[str] = None) -> None:
        """
        Print message to console and optionally to log file.
        
        Args:
            msg: Message to print
            style: Optional Rich style (not used for file logging)
        """
        # Console output
        if self.is_ci:
            # Strip rich markup for CI logs
            ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            clean_msg = self._strip_rich_markup(msg)
            log_level = self._determine_log_level(msg)
            level_name = logging.getLevelName(log_level)
            print(f"[{ts}] [{level_name}] {clean_msg}")
        else:
            self.console.print(msg, style=style)
        
        # File logging
        if self.file_logger:
            clean_msg = self._strip_rich_markup(msg)
            log_level = self._determine_log_level(msg)
            self.file_logger.log(log_level, clean_msg)
    
    def debug(self, msg: str) -> None:
        """Log debug message."""
        self.print(f"[dim][DEBUG] {msg}[/dim]")
    
    def info(self, msg: str) -> None:
        """Log info message."""
        self.print(msg)
    
    def warning(self, msg: str) -> None:
        """Log warning message."""
        self.print(f"[yellow][WARN] {msg}[/yellow]")
    
    def error(self, msg: str) -> None:
        """Log error message."""
        self.print(f"[bold red][ERROR] {msg}[/bold red]")
    
    @contextlib.contextmanager
    def status(self, msg: str, spinner: str = "line") -> Generator[None, None, None]:
        """
        Context manager for status messages.
        
        Args:
            msg: Status message
            spinner: Spinner style (ignored in CI mode)
        """
        if self.is_ci:
            self.print(f"Starting: {msg}")
            yield
            self.print(f"Finished: {msg}")
        else:
            with self.console.status(msg, spinner=spinner):
                yield

logger = StructuredLogger()
