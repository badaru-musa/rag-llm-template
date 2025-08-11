from typing import Optional, List, Any, Dict
from pydantic import BaseModel, Field
from datetime import datetime
from app.enums import ChatRole, DocumentStatus, UserRole


class BaseSchema(BaseModel):
    """Base schema with common fields"""
    
    class Config:
        from_attributes = True
        use_enum_values = True
        populate_by_name = True


class UserBase(BaseSchema):
    """Base user schema"""
    email: str = Field(..., description="User email address")
    username: str = Field(..., description="Username")
    full_name: Optional[str] = Field(None, description="Full name")
    role: UserRole = Field(default=UserRole.USER, description="User role")
    is_active: bool = Field(default=True, description="User active status")


class UserCreate(UserBase):
    """User creation schema"""
    password: str = Field(..., min_length=6, description="User password")


class UserUpdate(BaseSchema):
    """User update schema"""
    full_name: Optional[str] = None
    role: Optional[UserRole] = None
    is_active: Optional[bool] = None


class UserResponse(UserBase):
    """User response schema"""
    id: int = Field(..., description="User ID")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")
    
    class Config:
        from_attributes = True


class Token(BaseSchema):
    """Token schema"""
    access_token: str = Field(..., description="Access token")
    token_type: str = Field(default="bearer", description="Token type")
    expires_in: int = Field(..., description="Token expiration time in seconds")


class TokenData(BaseSchema):
    """Token data schema"""
    user_id: Optional[int] = None
    username: Optional[str] = None


class DocumentBase(BaseSchema):
    """Base document schema"""
    title: str = Field(..., description="Document title")
    content: Optional[str] = Field(None, description="Document content")
    file_path: Optional[str] = Field(None, description="File path")
    file_type: str = Field(..., description="File type")
    meta: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Document metadata")


class DocumentCreate(DocumentBase):
    """Document creation schema"""
    pass


class DocumentUpdate(BaseSchema):
    """Document update schema"""
    title: Optional[str] = None
    meta: Optional[Dict[str, Any]] = None


class DocumentResponse(DocumentBase):
    """Document response schema"""
    id: int = Field(..., description="Document ID")
    status: DocumentStatus = Field(..., description="Processing status")
    user_id: int = Field(..., description="Owner user ID")
    chunk_count: int = Field(default=0, description="Number of chunks")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")
    
    class Config:
        from_attributes = True


class DocumentChunk(BaseSchema):
    """Document chunk schema"""
    id: str = Field(..., description="Chunk ID")
    content: str = Field(..., description="Chunk content")
    meta: Dict[str, Any] = Field(default_factory=dict, description="Chunk metadata")
    score: Optional[float] = Field(None, description="Similarity score")


class ChatMessage(BaseSchema):
    """Chat message schema"""
    role: ChatRole = Field(..., description="Message role")
    content: str = Field(..., description="Message content")
    timestamp: Optional[datetime] = Field(default_factory=datetime.utcnow, description="Message timestamp")


class ChatRequest(BaseSchema):
    """Chat request schema"""
    message: str = Field(..., min_length=1, description="User message")
    conversation_id: Optional[str] = Field(None, description="Conversation ID")
    use_vector_search: Optional[bool] = Field(None, description="Whether to use vector search")
    max_chunks: Optional[int] = Field(None, ge=1, le=20, description="Maximum chunks to retrieve")


class ChatResponse(BaseSchema):
    """Chat response schema"""
    message: str = Field(..., description="Assistant response")
    conversation_id: str = Field(..., description="Conversation ID")
    sources: List[DocumentChunk] = Field(default_factory=list, description="Source chunks used")
    meta: Dict[str, Any] = Field(default_factory=dict, description="Response metadata")


class ConversationBase(BaseSchema):
    """Base conversation schema"""
    title: Optional[str] = Field(None, description="Conversation title")
    meta: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Conversation metadata")


class ConversationCreate(ConversationBase):
    """Conversation creation schema"""
    pass


class ConversationResponse(ConversationBase):
    """Conversation response schema"""
    id: str = Field(..., description="Conversation ID")
    user_id: int = Field(..., description="User ID")
    message_count: int = Field(default=0, description="Number of messages")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")
    
    class Config:
        from_attributes = True


class HealthResponse(BaseSchema):
    """Health check response schema"""
    status: str = Field(..., description="Service status")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Check timestamp")
    version: str = Field(..., description="Application version")
    dependencies: Dict[str, Any] = Field(default_factory=dict, description="Dependency status")


class ErrorResponse(BaseSchema):
    """Error response schema"""
    message: str = Field(..., description="Error message")
    details: Optional[Dict[str, Any]] = Field(None, description="Error details")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Error timestamp")


class FileUploadResponse(BaseSchema):
    """File upload response schema"""
    filename: str = Field(..., description="Uploaded filename")
    file_size: int = Field(..., description="File size in bytes")
    file_type: str = Field(..., description="File type")
    document_id: int = Field(..., description="Created document ID")
