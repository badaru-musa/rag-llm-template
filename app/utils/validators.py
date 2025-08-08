from typing import Any, Dict, List, Optional, Union
import re
from datetime import datetime
from app.exceptions import ValidationError


class Validator:
    """Collection of validation utilities"""
    
    @staticmethod
    def validate_required_fields(data: Dict[str, Any], required_fields: List[str]):
        """Validate that all required fields are present and not empty"""
        missing_fields = []
        empty_fields = []
        
        for field in required_fields:
            if field not in data:
                missing_fields.append(field)
            elif data[field] is None or (isinstance(data[field], str) and not data[field].strip()):
                empty_fields.append(field)
        
        if missing_fields:
            raise ValidationError(f"Missing required fields: {', '.join(missing_fields)}")
        
        if empty_fields:
            raise ValidationError(f"Empty required fields: {', '.join(empty_fields)}")
    
    @staticmethod
    def validate_email(email: str) -> bool:
        """Validate email format"""
        pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        return bool(re.match(pattern, email))
    
    @staticmethod
    def validate_password_strength(password: str, min_length: int = 8) -> List[str]:
        """Validate password strength and return list of issues"""
        issues = []
        
        if len(password) < min_length:
            issues.append(f"Password must be at least {min_length} characters long")
        
        if not re.search(r'[A-Z]', password):
            issues.append("Password must contain at least one uppercase letter")
        
        if not re.search(r'[a-z]', password):
            issues.append("Password must contain at least one lowercase letter")
        
        if not re.search(r'\d', password):
            issues.append("Password must contain at least one digit")
        
        if not re.search(r'[!@#$%^&*(),.?":{}|<>]', password):
            issues.append("Password must contain at least one special character")
        
        return issues
    
    @staticmethod
    def validate_username(username: str) -> List[str]:
        """Validate username format"""
        issues = []
        
        if len(username) < 3:
            issues.append("Username must be at least 3 characters long")
        
        if len(username) > 30:
            issues.append("Username must be no more than 30 characters long")
        
        if not re.match(r'^[a-zA-Z0-9_-]+$', username):
            issues.append("Username can only contain letters, numbers, underscores, and hyphens")
        
        if username.startswith('_') or username.startswith('-'):
            issues.append("Username cannot start with underscore or hyphen")
        
        if username.endswith('_') or username.endswith('-'):
            issues.append("Username cannot end with underscore or hyphen")
        
        return issues
    
    @staticmethod
    def validate_file_size(file_size: int, max_size: int) -> bool:
        """Validate file size"""
        return file_size <= max_size
    
    @staticmethod
    def validate_file_extension(filename: str, allowed_extensions: List[str]) -> bool:
        """Validate file extension"""
        if not filename:
            return False
        
        extension = filename.split('.')[-1].lower()
        return extension in [ext.lower().lstrip('.') for ext in allowed_extensions]
    
    @staticmethod
    def validate_url(url: str) -> bool:
        """Validate URL format"""
        pattern = re.compile(
            r'^https?://'
            r'(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+[A-Z]{2,6}\.?|'  # domain
            r'localhost|'
            r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})'
            r'(?::\d+)?'
            r'(?:/?|[/?]\S+)$', re.IGNORECASE)
        
        return bool(pattern.match(url))
    
    @staticmethod
    def validate_json_structure(data: Dict[str, Any], schema: Dict[str, Any]) -> List[str]:
        """Validate JSON data against a simple schema"""
        issues = []
        
        def check_field(field_name: str, field_value: Any, field_schema: Dict[str, Any]):
            expected_type = field_schema.get('type')
            if expected_type:
                if expected_type == 'string' and not isinstance(field_value, str):
                    issues.append(f"Field '{field_name}' must be a string")
                elif expected_type == 'integer' and not isinstance(field_value, int):
                    issues.append(f"Field '{field_name}' must be an integer")
                elif expected_type == 'float' and not isinstance(field_value, (int, float)):
                    issues.append(f"Field '{field_name}' must be a number")
                elif expected_type == 'boolean' and not isinstance(field_value, bool):
                    issues.append(f"Field '{field_name}' must be a boolean")
                elif expected_type == 'list' and not isinstance(field_value, list):
                    issues.append(f"Field '{field_name}' must be a list")
                elif expected_type == 'dict' and not isinstance(field_value, dict):
                    issues.append(f"Field '{field_name}' must be a dictionary")
            
            if isinstance(field_value, str):
                min_length = field_schema.get('min_length')
                max_length = field_schema.get('max_length')
                
                if min_length and len(field_value) < min_length:
                    issues.append(f"Field '{field_name}' must be at least {min_length} characters")
                
                if max_length and len(field_value) > max_length:
                    issues.append(f"Field '{field_name}' must be no more than {max_length} characters")
                
                pattern = field_schema.get('pattern')
                if pattern and not re.match(pattern, field_value):
                    issues.append(f"Field '{field_name}' does not match required pattern")
            
            elif isinstance(field_value, (int, float)):
                min_value = field_schema.get('min_value')
                max_value = field_schema.get('max_value')
                
                if min_value is not None and field_value < min_value:
                    issues.append(f"Field '{field_name}' must be at least {min_value}")
                
                if max_value is not None and field_value > max_value:
                    issues.append(f"Field '{field_name}' must be no more than {max_value}")
        
        required_fields = schema.get('required', [])
        for field in required_fields:
            if field not in data:
                issues.append(f"Required field '{field}' is missing")
        
        for field_name, field_value in data.items():
            if field_name in schema.get('properties', {}):
                field_schema = schema['properties'][field_name]
                check_field(field_name, field_value, field_schema)
        
        return issues
    
    @staticmethod
    def validate_date_range(start_date: datetime, end_date: datetime) -> bool:
        """Validate that start date is before end date"""
        return start_date < end_date
    
    @staticmethod
    def validate_positive_integer(value: Any) -> bool:
        """Validate that value is a positive integer"""
        try:
            int_value = int(value)
            return int_value > 0
        except (ValueError, TypeError):
            return False
    
    @staticmethod
    def validate_non_negative_number(value: Any) -> bool:
        """Validate that value is a non-negative number"""
        try:
            num_value = float(value)
            return num_value >= 0
        except (ValueError, TypeError):
            return False
    
    @staticmethod
    def sanitize_input(text: str, max_length: int = 1000) -> str:
        """Sanitize user input"""
        if not isinstance(text, str):
            text = str(text)
        
        text = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', '', text)
        
        text = text.strip()
        
        # Limit length
        if len(text) > max_length:
            text = text[:max_length]
        
        return text
    
    @staticmethod
    def validate_query_parameters(
        params: Dict[str, Any],
        allowed_params: List[str],
        param_types: Dict[str, type] = None
    ) -> Dict[str, Any]:
        """Validate query parameters"""
        validated = {}
        param_types = param_types or {}
        
        for key, value in params.items():
            if key not in allowed_params:
                continue
            
            expected_type = param_types.get(key, str)
            
            try:
                if expected_type == bool:
                    if isinstance(value, str):
                        validated[key] = value.lower() in ('true', '1', 'yes', 'on')
                    else:
                        validated[key] = bool(value)
                elif expected_type == int:
                    validated[key] = int(value)
                elif expected_type == float:
                    validated[key] = float(value)
                else:
                    validated[key] = str(value)
            except (ValueError, TypeError):
                raise ValidationError(f"Invalid type for parameter '{key}'")
        
        return validated


def validate_chat_message(message: str) -> str:
    """Validate and sanitize chat message"""
    if not message or not message.strip():
        raise ValidationError("Message cannot be empty")
    
    message = message.strip()
    
    if len(message) > 10000:  # 10KB limit
        raise ValidationError("Message is too long (maximum 10,000 characters)")
    
    # Check for potential injection attempts (basic)
    dangerous_patterns = [
        r'<script\b[^<]*(?:(?!<\/script>)<[^<]*)*<\/script>',
        r'javascript:',
        r'on\w+\s*=',
    ]
    
    for pattern in dangerous_patterns:
        if re.search(pattern, message, re.IGNORECASE):
            raise ValidationError("Message contains potentially dangerous content")
    
    return message


def validate_document_metadata(metadata: Dict[str, Any]) -> Dict[str, Any]:
    """Validate document metadata"""
    if not isinstance(metadata, dict):
        raise ValidationError("Metadata must be a dictionary")
    
    # Limit metadata size
    metadata_str = str(metadata)
    if len(metadata_str) > 50000:  # 50KB limit
        raise ValidationError("Metadata is too large")
    
    # Sanitize string values
    sanitized = {}
    for key, value in metadata.items():
        if isinstance(key, str) and len(key) <= 100:  # Limit key length
            if isinstance(value, str):
                sanitized[key] = Validator.sanitize_input(value, max_length=1000)
            elif isinstance(value, (int, float, bool, type(None))):
                sanitized[key] = value
            elif isinstance(value, (list, dict)):
                # Allow simple nested structures but limit depth
                sanitized[key] = value
    
    return sanitized


def validate_search_query(query: str) -> str:
    """Validate search query"""
    if not query or not query.strip():
        raise ValidationError("Search query cannot be empty")
    
    query = query.strip()
    
    if len(query) < 2:
        raise ValidationError("Search query must be at least 2 characters")
    
    if len(query) > 500:
        raise ValidationError("Search query is too long (maximum 500 characters)")
    
    return query
