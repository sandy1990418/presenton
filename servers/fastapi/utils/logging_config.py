"""
Unified logging configuration for Presenton FastAPI server.
Provides structured logging with environment-specific settings.
"""

import logging
import os
import sys
from typing import Optional, Dict, Any
import json
from datetime import datetime


class JSONFormatter(logging.Formatter):
    """Custom JSON formatter for structured logging in production."""
    
    def format(self, record: logging.LogRecord) -> str:
        log_data = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }
        
        # Add exception info if present
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)
        
        # Add extra fields if present
        if hasattr(record, "extra_data"):
            log_data.update(record.extra_data)
            
        # Add request_id if available (for tracing)
        if hasattr(record, "request_id"):
            log_data["request_id"] = record.request_id
            
        return json.dumps(log_data)


class ColoredFormatter(logging.Formatter):
    """Colored formatter for development environment."""
    
    COLORS = {
        'DEBUG': '\033[36m',      # Cyan
        'INFO': '\033[32m',       # Green  
        'WARNING': '\033[33m',    # Yellow
        'ERROR': '\033[31m',      # Red
        'CRITICAL': '\033[35m',   # Magenta
    }
    RESET = '\033[0m'
    
    def format(self, record: logging.LogRecord) -> str:
        color = self.COLORS.get(record.levelname, self.RESET)
        record.levelname = f"{color}{record.levelname}{self.RESET}"
        
        # Format timestamp  
        timestamp = datetime.fromtimestamp(record.created).strftime('%H:%M:%S')
        
        # Create formatted message
        message = f"{color}[{timestamp}]{self.RESET} {record.levelname} {color}{record.name}{self.RESET}: {record.getMessage()}"
        
        # Add exception info if present
        if record.exc_info:
            message += "\n" + self.formatException(record.exc_info)
            
        return message


class PresentonLogger:
    """Central logger factory for Presenton application."""
    
    _loggers: Dict[str, logging.Logger] = {}
    _configured = False
    
    @classmethod
    def configure(
        cls, 
        level: str = "INFO", 
        environment: str = "development",
        log_file: Optional[str] = None
    ):
        """Configure global logging settings."""
        if cls._configured:
            return
            
        # Set root logger level
        root_logger = logging.getLogger()
        root_logger.setLevel(getattr(logging, level.upper()))
        
        # Clear any existing handlers
        root_logger.handlers.clear()
        
        # Console handler
        console_handler = logging.StreamHandler(sys.stdout)
        
        if environment.lower() == "production":
            # Production: JSON structured logging
            formatter = JSONFormatter()
            console_handler.setLevel(logging.INFO)
        else:
            # Development: Colored console output
            formatter = ColoredFormatter()
            console_handler.setLevel(logging.DEBUG)
            
        console_handler.setFormatter(formatter)
        root_logger.addHandler(console_handler)
        
        # Optional file handler
        if log_file:
            file_handler = logging.FileHandler(log_file)
            file_handler.setLevel(logging.DEBUG)
            file_handler.setFormatter(JSONFormatter())
            root_logger.addHandler(file_handler)
            
        # Suppress some noisy third-party loggers
        logging.getLogger("httpx").setLevel(logging.WARNING)
        logging.getLogger("httpcore").setLevel(logging.WARNING)
        logging.getLogger("urllib3").setLevel(logging.WARNING)
        
        cls._configured = True
    
    @classmethod
    def get_logger(cls, name: str) -> logging.Logger:
        """Get a configured logger instance."""
        if not cls._configured:
            # Auto-configure with defaults if not already configured
            environment = os.getenv("ENVIRONMENT", "development")
            log_level = os.getenv("LOG_LEVEL", "INFO")
            cls.configure(level=log_level, environment=environment)
        
        if name not in cls._loggers:
            logger = logging.getLogger(f"presenton.{name}")
            cls._loggers[name] = logger
            
        return cls._loggers[name]


class LoggerAdapter(logging.LoggerAdapter):
    """Enhanced logger adapter with structured data support."""
    
    def process(self, msg, kwargs):
        # Extract extra data for structured logging
        extra = kwargs.get('extra', {})
        if 'extra_data' not in extra and any(key not in ['exc_info', 'stack_info', 'stacklevel'] for key in kwargs if key != 'extra'):
            # Move custom kwargs to extra_data for JSON formatter
            extra_data = {k: v for k, v in kwargs.items() if k not in ['exc_info', 'stack_info', 'stacklevel', 'extra']}
            extra['extra_data'] = extra_data
            # Clean up the original kwargs
            for key in extra_data:
                kwargs.pop(key, None)
            kwargs['extra'] = extra
        return msg, kwargs


def get_logger(name: str, **context) -> LoggerAdapter:
    """
    Get a configured logger with optional context.
    
    Args:
        name: Logger name (usually class or module name)
        **context: Additional context to include in all log messages
        
    Returns:
        LoggerAdapter instance with context
    """
    base_logger = PresentonLogger.get_logger(name)
    return LoggerAdapter(base_logger, context)


# Auto-configure on import if environment variables are set
if os.getenv("AUTO_CONFIGURE_LOGGING", "true").lower() == "true":
    environment = os.getenv("ENVIRONMENT", "development") 
    log_level = os.getenv("LOG_LEVEL", "INFO")
    log_file = os.getenv("LOG_FILE")
    PresentonLogger.configure(level=log_level, environment=environment, log_file=log_file)