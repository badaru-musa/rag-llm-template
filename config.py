from typing import Optional, List
from pydantic_settings import BaseSettings
from pydantic import Field
import os


class Settings(BaseSettings):
    # Application Settings
    app_name: str = Field(default="RAG-LLM-Template", env="APP_NAME")
    app_version: str = Field(default="1.0.0", env="APP_VERSION")
    debug: bool = Field(default=True, env="DEBUG")
    host: str = Field(default="0.0.0.0", env="HOST")
    port: int = Field(default=8000, env="PORT")

    # Database Configuration
    database_url: str = Field(default="sqlite+aiosqlite:///./data/db/app.db", env="DATABASE_URL")
    redis_url: Optional[str] = Field(default=None, env="REDIS_URL")

    # Email settings (optional)
    MAIL_USERNAME: Optional[str] = Field(default=None, env="MAIL_USERNAME")
    MAIL_PASSWORD: Optional[str] = Field(default=None, env="MAIL_PASSWORD")
    MAIL_FROM: Optional[str] = Field(default="noreply@example.com", env="MAIL_FROM")
    MAIL_PORT: int = Field(default=587, env="MAIL_PORT")
    MAIL_SERVER: Optional[str] = Field(default="smtp.gmail.com", env="MAIL_SERVER")
    MAIL_FROM_NAME: Optional[str] = Field(default="RAG LLM App", env="MAIL_FROM_NAME")

    # ChromaDB Configuration
    chroma_host: str = Field(default="localhost", env="CHROMA_HOST")
    chroma_port: int = Field(default=8000, env="CHROMA_PORT")
    chroma_collection_name: str = Field(default="documents", env="CHROMA_COLLECTION_NAME")
    chroma_persist_directory: str = Field(default="./data/vector_store", env="CHROMA_PERSIST_DIRECTORY")

    # LLM Provider Configuration
    llm_provider: str = Field(default="openai", env="LLM_PROVIDER")

    # Azure OpenAI Configuration
    azure_openai_api_key: Optional[str] = Field(default=None, env="AZURE_OPENAI_API_KEY")
    azure_openai_endpoint: Optional[str] = Field(default=None, env="AZURE_OPENAI_ENDPOINT")
    azure_openai_api_version: str = Field(default="2023-12-01-preview", env="AZURE_OPENAI_API_VERSION")
    azure_openai_deployment_name: Optional[str] = Field(default=None, env="AZURE_OPENAI_DEPLOYMENT_NAME")
    azure_openai_model_name: str = Field(default="gpt-4", env="AZURE_OPENAI_MODEL_NAME")

    # OpenAI Configuration
    openai_api_key: Optional[str] = Field(default=None, env="OPENAI_API_KEY")
    openai_model: str = Field(default="gpt-4.1 nano", env="OPENAI_MODEL")

    # Anthropic Configuration
    anthropic_api_key: Optional[str] = Field(default=None, env="ANTHROPIC_API_KEY")
    anthropic_model: str = Field(default="claude-3-sonnet-20240229", env="ANTHROPIC_MODEL")

    # Google Gemini Configuration
    google_api_key: Optional[str] = Field(default=None, env="GOOGLE_API_KEY")
    gemini_model: str = Field(default="gemini-pro", env="GEMINI_MODEL")

    # Local Model Configuration
    local_model_path: str = Field(default="./models/local_model", env="LOCAL_MODEL_PATH")
    local_model_type: str = Field(default="huggingface", env="LOCAL_MODEL_TYPE")

    # Embedding Configuration
    embedding_provider: str = Field(default="openai", env="EMBEDDING_PROVIDER")
    local_embedding_model: str = Field(default="sentence-transformers/all-MiniLM-L6-v2", env="LOCAL_EMBEDDING_MODEL")
    embedding_dimension: int = Field(default=384, env="EMBEDDING_DIMENSION")
    openai_embedding_model: str = Field(default="text-embedding-3-small", env="OPENAI_EMBEDDING_MODEL")
    openai_embedding_dimension: int = Field(default=1536, env="OPENAI_EMBEDDING_DIMENSION")
    azure_embedding_deployment_name: Optional[str] = Field(default=None, env="AZURE_EMBEDDING_DEPLOYMENT_NAME")
    azure_embedding_model_name: str = Field(default="text-embedding-ada-002", env="AZURE_EMBEDDING_MODEL_NAME")

    # RAG Configuration
    use_vector_search: bool = Field(default=True, env="USE_VECTOR_SEARCH")
    max_chunks_returned: int = Field(default=5, env="MAX_CHUNKS_RETURNED")
    chunk_size: int = Field(default=15000, env="CHUNK_SIZE")
    chunk_overlap: int = Field(default=1000, env="CHUNK_OVERLAP")
    similarity_threshold: float = Field(default=0.7, env="SIMILARITY_THRESHOLD")

    # Authentication
    secret_key: str = Field(default="CHANGE_THIS_SECRET_KEY_IN_PRODUCTION", env="SECRET_KEY")
    algorithm: str = Field(default="HS256", env="ALGORITHM")
    access_token_expire_minutes: int = Field(default=30, env="ACCESS_TOKEN_EXPIRE_MINUTES")

    # File Upload
    max_file_size: int = Field(default=10485760, env="MAX_FILE_SIZE")  # 10MB
    allowed_extensions: List[str] = Field(default=[".pdf", ".txt", ".docx", ".md"], env="ALLOWED_EXTENSIONS")

    # Logging
    log_level: str = Field(default="INFO", env="LOG_LEVEL")
    log_format: str = Field(
        default="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        env="LOG_FORMAT"
    )

    model_config = {
        "env_file": ".env",
        "case_sensitive": False,
        "extra": "ignore"
    }


# Global settings instance
settings = Settings()
