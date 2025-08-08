from typing import Any, Dict, Optional
from fastapi import HTTPException, status


class BaseRAGException(Exception):
    """Base exception for RAG application"""
    
    def __init__(
        self,
        message: str,
        details: Optional[Dict[str, Any]] = None,
        status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR
    ):
        self.message = message
        self.details = details or {}
        self.status_code = status_code
        super().__init__(self.message)


class DocumentProcessingError(BaseRAGException):
    """Raised when document processing fails"""
    
    def __init__(self, message: str = "Document processing failed", **kwargs):
        super().__init__(message, status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, **kwargs)


class VectorStoreError(BaseRAGException):
    """Raised when vector store operations fail"""
    
    def __init__(self, message: str = "Vector store operation failed", **kwargs):
        super().__init__(message, status_code=status.HTTP_503_SERVICE_UNAVAILABLE, **kwargs)


class LLMServiceError(BaseRAGException):
    """Raised when LLM service fails"""
    
    def __init__(self, message: str = "LLM service error", **kwargs):
        super().__init__(message, status_code=status.HTTP_503_SERVICE_UNAVAILABLE, **kwargs)


class EmbeddingServiceError(BaseRAGException):
    """Raised when embedding service fails"""
    
    def __init__(self, message: str = "Embedding service error", **kwargs):
        super().__init__(message, status_code=status.HTTP_503_SERVICE_UNAVAILABLE, **kwargs)


class AuthenticationError(BaseRAGException):
    """Raised when authentication fails"""
    
    def __init__(self, message: str = "Authentication failed", **kwargs):
        super().__init__(message, status_code=status.HTTP_401_UNAUTHORIZED, **kwargs)


class AuthorizationError(BaseRAGException):
    """Raised when authorization fails"""
    
    def __init__(self, message: str = "Authorization failed", **kwargs):
        super().__init__(message, status_code=status.HTTP_403_FORBIDDEN, **kwargs)


class ValidationError(BaseRAGException):
    """Raised when validation fails"""
    
    def __init__(self, message: str = "Validation error", **kwargs):
        super().__init__(message, status_code=status.HTTP_400_BAD_REQUEST, **kwargs)


class NotFoundError(BaseRAGException):
    """Raised when resource is not found"""
    
    def __init__(self, message: str = "Resource not found", **kwargs):
        super().__init__(message, status_code=status.HTTP_404_NOT_FOUND, **kwargs)


class ConfigurationError(BaseRAGException):
    """Raised when configuration is invalid"""
    
    def __init__(self, message: str = "Configuration error", **kwargs):
        super().__init__(message, status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, **kwargs)


class FileUploadError(BaseRAGException):
    """Raised when file upload fails"""
    
    def __init__(self, message: str = "File upload error", **kwargs):
        super().__init__(message, status_code=status.HTTP_400_BAD_REQUEST, **kwargs)


class DatabaseError(BaseRAGException):
    """Raised when database operations fail"""
    
    def __init__(self, message: str = "Database error", **kwargs):
        super().__init__(message, status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, **kwargs)


def create_http_exception(exc: BaseRAGException) -> HTTPException:
    """Convert BaseRAGException to HTTPException"""
    return HTTPException(
        status_code=exc.status_code,
        detail={
            "message": exc.message,
            "details": exc.details,
        }
    )
