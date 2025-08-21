"""
ValidationMixin provides standardized validation functionality for handlers.
"""

from typing import Any, List, Dict, Optional, Union
from fastapi import HTTPException

from .logging_mixin import LoggingMixin


class ValidationMixin(LoggingMixin):
    """Provides standardized validation utilities with logging."""
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
    
    def validate_required_fields(self, data: Dict[str, Any], required_fields: List[str], operation: str = "operation") -> None:
        """
        Validate that required fields are present and not empty.
        
        Args:
            data: Dictionary to validate
            required_fields: List of required field names
            operation: Operation name for logging context
            
        Raises:
            HTTPException: 400 if validation fails
        """
        missing_fields = []
        empty_fields = []
        
        for field in required_fields:
            if field not in data:
                missing_fields.append(field)
            elif data[field] is None or (isinstance(data[field], str) and not data[field].strip()):
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
    
    def validate_positive_integer(self, value: Any, field_name: str, min_value: int = 1) -> int:
        """
        Validate that a value is a positive integer.
        
        Args:
            value: Value to validate
            field_name: Field name for error messages
            min_value: Minimum allowed value (default: 1)
            
        Returns:
            Validated integer value
            
        Raises:
            HTTPException: 400 if validation fails
        """
        try:
            int_value = int(value)
            if int_value < min_value:
                self.log_validation_error(field_name, value, f"Value must be >= {min_value}")
                raise HTTPException(
                    status_code=400,
                    detail=f"{field_name} must be >= {min_value}"
                )
            return int_value
        except (TypeError, ValueError):
            self.log_validation_error(field_name, value, "Value must be an integer")
            raise HTTPException(
                status_code=400,
                detail=f"{field_name} must be a valid integer"
            )
    
    def validate_string_length(self, value: str, field_name: str, min_length: int = 0, max_length: Optional[int] = None) -> str:
        """
        Validate string length constraints.
        
        Args:
            value: String value to validate
            field_name: Field name for error messages
            min_length: Minimum length (default: 0)
            max_length: Maximum length (optional)
            
        Returns:
            Validated string value
            
        Raises:
            HTTPException: 400 if validation fails
        """
        if not isinstance(value, str):
            self.log_validation_error(field_name, value, "Value must be a string")
            raise HTTPException(
                status_code=400,
                detail=f"{field_name} must be a string"
            )
        
        if len(value) < min_length:
            self.log_validation_error(field_name, len(value), f"String too short, minimum {min_length}")
            raise HTTPException(
                status_code=400,
                detail=f"{field_name} must be at least {min_length} characters"
            )
        
        if max_length and len(value) > max_length:
            self.log_validation_error(field_name, len(value), f"String too long, maximum {max_length}")
            raise HTTPException(
                status_code=400,
                detail=f"{field_name} must be at most {max_length} characters"
            )
        
        return value
    
    def validate_allowed_values(self, value: Any, allowed_values: List[Any], field_name: str) -> Any:
        """
        Validate that value is in allowed list.
        
        Args:
            value: Value to validate
            allowed_values: List of allowed values
            field_name: Field name for error messages
            
        Returns:
            Validated value
            
        Raises:
            HTTPException: 400 if validation fails
        """
        if value not in allowed_values:
            self.log_validation_error(field_name, value, f"Value not in allowed list: {allowed_values}")
            raise HTTPException(
                status_code=400,
                detail=f"{field_name} must be one of: {', '.join(map(str, allowed_values))}"
            )
        
        return value
    
    def validate_list_not_empty(self, value: List[Any], field_name: str) -> List[Any]:
        """
        Validate that list is not empty.
        
        Args:
            value: List to validate
            field_name: Field name for error messages
            
        Returns:
            Validated list
            
        Raises:
            HTTPException: 400 if validation fails
        """
        if not isinstance(value, list):
            self.log_validation_error(field_name, type(value).__name__, "Value must be a list")
            raise HTTPException(
                status_code=400,
                detail=f"{field_name} must be a list"
            )
        
        if not value:
            self.log_validation_error(field_name, "empty_list", "List cannot be empty")
            raise HTTPException(
                status_code=400,
                detail=f"{field_name} cannot be empty"
            )
        
        return value
    
    def validate_file_paths(self, file_paths: Optional[List[str]]) -> Optional[List[str]]:
        """
        Validate file paths if provided.
        
        Args:
            file_paths: List of file paths to validate
            
        Returns:
            Validated file paths or None
            
        Raises:
            HTTPException: 400 if validation fails
        """
        if file_paths is None:
            return None
        
        if not isinstance(file_paths, list):
            self.log_validation_error("file_paths", type(file_paths).__name__, "Must be a list")
            raise HTTPException(
                status_code=400,
                detail="file_paths must be a list"
            )
        
        for i, path in enumerate(file_paths):
            if not isinstance(path, str):
                self.log_validation_error(f"file_paths[{i}]", type(path).__name__, "Must be a string")
                raise HTTPException(
                    status_code=400,
                    detail=f"file_paths[{i}] must be a string"
                )
            
            if not path.strip():
                self.log_validation_error(f"file_paths[{i}]", "empty_string", "Cannot be empty")
                raise HTTPException(
                    status_code=400,
                    detail=f"file_paths[{i}] cannot be empty"
                )
        
        return file_paths
    
    def validate_language_code(self, language: str) -> str:
        """
        Validate language code format.
        
        Args:
            language: Language code to validate
            
        Returns:
            Validated language code
            
        Raises:
            HTTPException: 400 if validation fails
        """
        # Basic language code validation - could be enhanced
        language = self.validate_string_length(language, "language", min_length=2, max_length=10)
        
        # Additional validation could go here (ISO codes, etc.)
        
        return language