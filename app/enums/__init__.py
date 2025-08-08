from enum import Enum


class LLMProvider(str, Enum):
    """LLM Provider enumeration"""
    AZURE_OPENAI = "azure_openai"
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    GEMINI = "gemini"
    MISTRAL = "mistral"
    LOCAL = "local"


class EmbeddingProvider(str, Enum):
    """Embedding Provider enumeration"""
    LOCAL = "local"
    OPENAI = "openai"
    AZURE_OPENAI = "azure_openai"
    CLAUDE = "claude"


class DocumentStatus(str, Enum):
    """Document processing status"""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class ChatRole(str, Enum):
    """Chat message roles"""
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"


class FileType(str, Enum):
    """Supported file types"""
    PDF = "pdf"
    TXT = "txt"
    DOCX = "docx"
    MD = "md"


class UserRole(str, Enum):
    """User roles"""
    ADMIN = "admin"
    USER = "user"
    VIEWER = "viewer"
