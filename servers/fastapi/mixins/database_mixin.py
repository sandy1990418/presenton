"""
DatabaseMixin provides standardized database operations for handlers.
"""

from typing import TypeVar, Type, Optional
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import SQLModel

from .logging_mixin import LoggingMixin

T = TypeVar('T', bound=SQLModel)


class DatabaseMixin(LoggingMixin):
    """Provides standardized database operations with logging."""
    
    def __init__(self, sql_session: AsyncSession, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.sql_session = sql_session
    
    async def get_or_404(self, model_class: Type[T], id: str, error_detail: Optional[str] = None) -> T:
        """
        Get a model instance by ID or raise HTTP 404 if not found.
        
        Args:
            model_class: The SQLModel class to query
            id: The ID to search for
            error_detail: Custom error message (optional)
            
        Returns:
            The model instance
            
        Raises:
            HTTPException: 404 if not found
        """
        model_name = model_class.__name__
        self.log_database_operation("get", model_name, id=id)
        
        try:
            instance = await self.sql_session.get(model_class, id)
            if not instance:
                error_msg = error_detail or f"{model_name} not found"
                self.logger.warning(
                    f"{model_name} not found",
                    model=model_name,
                    id=id,
                    error="not_found"
                )
                raise HTTPException(status_code=404, detail=error_msg)
            
            self.log_database_operation("get_success", model_name, id=id)
            return instance
            
        except HTTPException:
            raise
        except Exception as e:
            self.log_request_error("database_get", e, model=model_name, id=id)
            raise HTTPException(status_code=500, detail="Database error")
    
    async def safe_commit(self) -> None:
        """
        Commit database transaction with error handling.
        
        Raises:
            HTTPException: 500 if commit fails
        """
        try:
            self.log_database_operation("commit", "transaction")
            await self.sql_session.commit()
            self.log_database_operation("commit_success", "transaction")
            
        except Exception as e:
            self.log_request_error("database_commit", e)
            await self.sql_session.rollback()
            raise HTTPException(status_code=500, detail="Failed to save changes")
    
    async def safe_add(self, instance: SQLModel) -> None:
        """
        Add instance to session with logging.
        
        Args:
            instance: The model instance to add
        """
        model_name = instance.__class__.__name__
        self.log_database_operation("add", model_name)
        self.sql_session.add(instance)
    
    async def safe_add_all(self, instances: list[SQLModel]) -> None:
        """
        Add multiple instances to session with logging.
        
        Args:
            instances: List of model instances to add
        """
        if not instances:
            return
            
        model_counts = {}
        for instance in instances:
            model_name = instance.__class__.__name__
            model_counts[model_name] = model_counts.get(model_name, 0) + 1
        
        self.logger.debug("Adding multiple instances", models=model_counts, total_count=len(instances))
        self.sql_session.add_all(instances)
    
    async def delete_by_id(self, model_class: Type[T], id: str) -> None:
        """
        Delete a model instance by ID.
        
        Args:
            model_class: The SQLModel class 
            id: The ID to delete
            
        Raises:
            HTTPException: 404 if not found
        """
        instance = await self.get_or_404(model_class, id)
        model_name = model_class.__name__
        
        self.log_database_operation("delete", model_name, id=id)
        await self.sql_session.delete(instance)
        
    def validate_required_fields(self, data: dict, required_fields: list[str], operation: str = "operation") -> None:
        """
        Validate that required fields are present and not empty.
        
        Args:
            data: Dictionary to validate
            required_fields: List of required field names
            operation: Operation name for logging
            
        Raises:
            HTTPException: 400 if validation fails
        """
        missing_fields = []
        empty_fields = []
        
        for field in required_fields:
            if field not in data:
                missing_fields.append(field)
            elif not data[field]:
                empty_fields.append(field)
        
        if missing_fields:
            self.log_validation_error("missing_fields", missing_fields, f"Required fields missing for {operation}")
            raise HTTPException(
                status_code=400, 
                detail=f"Missing required fields: {', '.join(missing_fields)}"
            )
        
        if empty_fields:
            self.log_validation_error("empty_fields", empty_fields, f"Required fields empty for {operation}")
            raise HTTPException(
                status_code=400,
                detail=f"Required fields cannot be empty: {', '.join(empty_fields)}"
            )