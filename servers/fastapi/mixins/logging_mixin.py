"""
LoggingMixin provides standardized logging functionality for handlers.
"""

from typing import Any, Optional
from utils.logging_config import get_logger, LoggerAdapter


class LoggingMixin:
    """Provides structured logging capabilities to handler classes."""
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.logger: LoggerAdapter = get_logger(self.__class__.__name__)
    
    def log_request_start(self, operation: str, **context) -> None:
        """Log the start of a request operation."""
        self.logger.info(f"Starting {operation}", operation=operation, **context)
    
    def log_request_success(self, operation: str, **context) -> None:
        """Log successful completion of a request operation."""
        self.logger.info(f"Completed {operation}", operation=operation, status="success", **context)
    
    def log_request_error(self, operation: str, error: Exception, **context) -> None:
        """Log request operation failure with exception details."""
        self.logger.exception(
            f"Failed {operation}",
            operation=operation,
            status="error", 
            error_type=type(error).__name__,
            **context
        )
    
    def log_validation_error(self, field: str, value: Any, reason: str) -> None:
        """Log validation errors."""
        self.logger.warning(
            f"Validation failed for {field}",
            validation_error=True,
            field=field,
            value=str(value)[:100],  # Truncate long values
            reason=reason
        )
    
    def log_database_operation(self, operation: str, model: str, **context) -> None:
        """Log database operations."""
        self.logger.debug(
            f"Database {operation}",
            database_operation=operation,
            model=model,
            **context
        )
    
    def log_external_service_call(self, service: str, operation: str, **context) -> None:
        """Log external service calls."""
        self.logger.debug(
            f"Calling {service} for {operation}",
            external_service=service,
            service_operation=operation,
            **context
        )
    
    def log_streaming_progress(self, step: str, current: Optional[int] = None, total: Optional[int] = None, **context) -> None:
        """Log streaming operation progress."""
        progress_data = {"streaming_step": step, **context}
        if current is not None and total is not None:
            progress_data.update({"current": current, "total": total, "progress_pct": round((current / total) * 100, 1)})
        
        self.logger.info(f"Streaming: {step}", **progress_data)
    
    def log_asset_generation(self, asset_type: str, count: int, **context) -> None:
        """Log asset generation activities."""
        self.logger.info(
            f"Generated {count} {asset_type} assets",
            asset_generation=True,
            asset_type=asset_type,
            asset_count=count,
            **context
        )
    
    def log_performance_metric(self, operation: str, duration_ms: float, **context) -> None:
        """Log performance metrics."""
        self.logger.info(
            f"Performance: {operation} took {duration_ms:.2f}ms",
            performance_metric=True,
            operation=operation,
            duration_ms=duration_ms,
            **context
        )