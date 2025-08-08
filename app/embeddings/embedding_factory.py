from abc import ABC, abstractmethod
from typing import List, Optional
import numpy as np
from app.enums import EmbeddingProvider
from app.exceptions import EmbeddingServiceError, ConfigurationError
from config import Settings


class BaseEmbeddingService(ABC):
    """Abstract base class for embedding services"""
    
    @abstractmethod
    async def embed_text(self, text: str) -> List[float]:
        """Generate embedding for a single text"""
        pass
    
    @abstractmethod
    async def embed_texts(self, texts: List[str]) -> List[List[float]]:
        """Generate embeddings for multiple texts"""
        pass
    
    @abstractmethod
    def get_dimension(self) -> int:
        """Get the dimension of the embeddings"""
        pass


class LocalEmbeddingService(BaseEmbeddingService):
    pass
#     """Local embedding service using sentence-transformers"""
    
#     def __init__(self, config: Settings):
#         self.config = config
#         self.model = None
#         self._initialize_model()
    
#     def _initialize_model(self):
#         """Initialize the local embedding model"""
#         try:
#             from sentence_transformers import SentenceTransformer
#             self.model = SentenceTransformer(self.config.local_embedding_model)
#         except ImportError:
#             raise ConfigurationError("sentence-transformers library not installed")
#         except Exception as e:
#             raise EmbeddingServiceError(f"Failed to load local embedding model: {str(e)}")
    
#     async def embed_text(self, text: str) -> List[float]:
#         """Generate embedding for a single text"""
#         try:
#             if not self.model:
#                 raise EmbeddingServiceError("Embedding model not initialized")
            
#             embedding = self.model.encode(text, convert_to_numpy=True)
#             return embedding.tolist()
#         except Exception as e:
#             raise EmbeddingServiceError(f"Failed to generate embedding: {str(e)}")
    
#     async def embed_texts(self, texts: List[str]) -> List[List[float]]:
#         """Generate embeddings for multiple texts"""
#         try:
#             if not self.model:
#                 raise EmbeddingServiceError("Embedding model not initialized")
            
#             embeddings = self.model.encode(texts, convert_to_numpy=True)
#             return embeddings.tolist()
#         except Exception as e:
#             raise EmbeddingServiceError(f"Failed to generate embeddings: {str(e)}")
    
#     def get_dimension(self) -> int:
#         """Get the dimension of the embeddings"""
#         return self.config.embedding_dimension


class OpenAIEmbeddingService(BaseEmbeddingService):
    """OpenAI embedding service"""
    
    def __init__(self, config: Settings):
        self.config = config
        self._validate_config()
        self._initialize_client()
    
    def _validate_config(self):
        """Validate OpenAI configuration"""
        if not self.config.openai_api_key:
            raise ConfigurationError("OpenAI API key is required")
    
    def _initialize_client(self):
        """Initialize OpenAI client"""
        try:
            from openai import OpenAI
            self.client = OpenAI(api_key=self.config.openai_api_key)
        except ImportError:
            raise ConfigurationError("OpenAI library not installed")
    
    async def embed_text(self, text: str) -> List[float]:
        """Generate embedding for a single text"""
        try:
            response = self.client.embeddings.create(
                model=self.config.openai_embedding_model,
                input=text
            )
            return response.data[0].embedding
        except Exception as e:
            raise EmbeddingServiceError(f"OpenAI embedding API error: {str(e)}")
    
    async def embed_texts(self, texts: List[str]) -> List[List[float]]:
        """Generate embeddings for multiple texts"""
        try:
            response = self.client.embeddings.create(
                model=self.config.openai_embedding_model,
                input=texts
            )
            return [item.embedding for item in response.data]
        except Exception as e:
            raise EmbeddingServiceError(f"OpenAI embedding API error: {str(e)}")
    
    def get_dimension(self) -> int:
        """Get the dimension of the embeddings"""
        return self.config.openai_embedding_dimension


class AzureOpenAIEmbeddingService(BaseEmbeddingService):
    """Azure OpenAI embedding service"""
    
    def __init__(self, config: Settings):
        self.config = config
        self._validate_config()
        self._initialize_client()
    
    def _validate_config(self):
        """Validate Azure OpenAI configuration"""
        if not self.config.azure_openai_api_key:
            raise ConfigurationError("Azure OpenAI API key is required")
        if not self.config.azure_openai_endpoint:
            raise ConfigurationError("Azure OpenAI endpoint is required")
        if not self.config.azure_embedding_deployment_name:
            raise ConfigurationError("Azure OpenAI embedding deployment name is required")
    
    def _initialize_client(self):
        """Initialize Azure OpenAI client"""
        try:
            from openai import AzureOpenAI
            self.client = AzureOpenAI(
                api_key=self.config.azure_openai_api_key,
                api_version=self.config.azure_openai_api_version,
                azure_endpoint=self.config.azure_openai_endpoint,
            )
        except ImportError:
            raise ConfigurationError("OpenAI library not installed")
    
    async def embed_text(self, text: str) -> List[float]:
        """Generate embedding for a single text"""
        try:
            response = self.client.embeddings.create(
                model=self.config.azure_embedding_deployment_name,
                input=text
            )
            return response.data[0].embedding
        except Exception as e:
            raise EmbeddingServiceError(f"Azure OpenAI embedding API error: {str(e)}")
    
    async def embed_texts(self, texts: List[str]) -> List[List[float]]:
        """Generate embeddings for multiple texts"""
        try:
            response = self.client.embeddings.create(
                model=self.config.azure_embedding_deployment_name,
                input=texts
            )
            return [item.embedding for item in response.data]
        except Exception as e:
            raise EmbeddingServiceError(f"Azure OpenAI embedding API error: {str(e)}")
    
    def get_dimension(self) -> int:
        """Get the dimension of the embeddings"""
        return self.config.openai_embedding_dimension


class EmbeddingFactory:
    """Factory for creating embedding services"""
    
    def __init__(self, config: Settings):
        self.config = config
        self._services = {
            # EmbeddingProvider.LOCAL: LocalEmbeddingService,
            EmbeddingProvider.OPENAI: OpenAIEmbeddingService,
            EmbeddingProvider.AZURE_OPENAI: AzureOpenAIEmbeddingService,
        }
    
    def create_embedding_service(self, provider: str) -> BaseEmbeddingService:
        """Create embedding service based on provider"""
        try:
            provider_enum = EmbeddingProvider(provider)
        except ValueError:
            raise ConfigurationError(f"Unsupported embedding provider: {provider}")
        
        service_class = self._services.get(provider_enum)
        if not service_class:
            raise ConfigurationError(f"Embedding service not found for provider: {provider}")
        
        return service_class(self.config)
