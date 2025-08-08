from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_database_session as get_db
from app.generation.llm_factory import LLMFactory
from app.embeddings.embedding_factory import EmbeddingFactory
from app.retrieval.vector_store import ChromaVectorStore
from app.ingestion.document_processor import DocumentProcessor
from app.retrieval.retriever import DocumentRetriever
from app.generation.chat_service import ChatService
from app.auth.auth_service import AuthService
from config import settings

# Singleton instances
_llm_factory = None
_embedding_factory = None
_embedding_service = None
_vector_store = None
_document_processor = None
_document_retriever = None
_auth_service = None
_chat_service = None


def get_llm_factory():
    global _llm_factory
    if _llm_factory is None:
        _llm_factory = LLMFactory(settings)
    return _llm_factory


def get_llm_service():
    factory = get_llm_factory()
    return factory.create_llm(settings.llm_provider)


def get_embedding_factory():
    global _embedding_factory
    if _embedding_factory is None:
        _embedding_factory = EmbeddingFactory(settings)
    return _embedding_factory


def get_embedding_service():
    global _embedding_service
    if _embedding_service is None:
        factory = get_embedding_factory()
        _embedding_service = factory.create_embedding_service(settings.embedding_provider)
    return _embedding_service


def get_vector_store():
    global _vector_store
    if _vector_store is None:
        _vector_store = ChromaVectorStore(
            host=settings.chroma_host,
            port=settings.chroma_port,
            collection_name=settings.chroma_collection_name,
            persist_directory=settings.chroma_persist_directory,
            embedding_service=get_embedding_service()
        )
    return _vector_store


def get_document_processor():
    global _document_processor
    if _document_processor is None:
        _document_processor = DocumentProcessor(
            chunk_size=settings.chunk_size,
            chunk_overlap=settings.chunk_overlap,
            embedding_service=get_embedding_service()
        )
    return _document_processor


def get_document_retriever():
    global _document_retriever
    if _document_retriever is None:
        _document_retriever = DocumentRetriever(
            vector_store=get_vector_store(),
            max_chunks=settings.max_chunks_returned,
            similarity_threshold=settings.similarity_threshold
        )
    return _document_retriever


async def get_database_session() -> AsyncGenerator[AsyncSession, None]:
    async for session in get_db():
        yield session


def get_auth_service():
    global _auth_service
    if _auth_service is None:
        _auth_service = AuthService(
            secret_key=settings.secret_key,
            algorithm=settings.algorithm,
            access_token_expire_minutes=settings.access_token_expire_minutes
        )
    return _auth_service


def get_chat_service():
    global _chat_service
    if _chat_service is None:
        _chat_service = ChatService(
            llm_service=get_llm_service(),
            document_retriever=get_document_retriever(),
            use_vector_search=settings.use_vector_search
        )
    return _chat_service


class Container:
    """Simple container for initialization"""
    
    @staticmethod
    async def init_resources():
        """Initialize async resources"""
        vector_store = get_vector_store()
        await vector_store.initialize()
    
    @staticmethod
    async def shutdown_resources():
        """Cleanup resources"""
        if _vector_store is not None:
            await _vector_store.close()


def get_container():
    """Get container for app initialization"""
    return Container
