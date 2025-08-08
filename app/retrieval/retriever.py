from typing import List, Dict, Any, Optional
from app.retrieval.vector_store import ChromaVectorStore
from app.schema import DocumentChunk
from app.exceptions import VectorStoreError
from app.logger import logger


class DocumentRetriever:
    """Service for retrieving relevant documents for RAG"""
    
    def __init__(
        self,
        vector_store: ChromaVectorStore,
        max_chunks: int = 5,
        similarity_threshold: float = 0.7
    ):
        self.vector_store = vector_store
        self.max_chunks = max_chunks
        self.similarity_threshold = similarity_threshold
    
    async def retrieve_relevant_chunks(
        self,
        query: str,
        user_id: Optional[int] = None,
        document_ids: Optional[List[str]] = None,
        max_chunks: Optional[int] = None,
        similarity_threshold: Optional[float] = None
    ) -> List[DocumentChunk]:
        """Retrieve relevant document chunks for a query"""
        
        try:
            # Use provided parameters or defaults
            max_chunks = max_chunks or self.max_chunks
            similarity_threshold = similarity_threshold or self.similarity_threshold
            
            # Build where clause for filtering
            where_clause = None
            if user_id and document_ids:
                where_clause = {"$and": [
                    {"user_id": {"$eq": user_id}},
                    {"document_id": {"$in": document_ids}}
                ]}
            elif user_id:
                where_clause = {"user_id": {"$eq": user_id}}
            elif document_ids:
                where_clause = {"document_id": {"$in": document_ids}}
            
            results = await self.vector_store.search(
                query=query,
                n_results=max_chunks,
                where=where_clause if where_clause else None,
                score_threshold=similarity_threshold
            )
            
            # Convert to DocumentChunk objects
            chunks = []
            for result in results:
                chunk = DocumentChunk(
                    id=result["id"],
                    content=result["content"],
                    meta=result.get("metadata", {}),
                    score=result["score"]
                )
                chunks.append(chunk)
            
            logger.info(f"Retrieved {len(chunks)} relevant chunks for query")
            return chunks
            
        except Exception as e:
            logger.error(f"Error retrieving relevant chunks: {str(e)}")
            raise VectorStoreError(f"Failed to retrieve relevant chunks: {str(e)}")
    
    async def retrieve_chunks_by_document(
        self,
        document_id: str,
        user_id: Optional[int] = None
    ) -> List[DocumentChunk]:
        """Retrieve all chunks for a specific document"""
        
        try:
            where_clause = {"$and": [
                {"document_id": {"$eq": str(document_id)}},
                {"user_id": {"$eq": user_id}}
            ]} if user_id else {"document_id": {"$eq": str(document_id)}}
            
            results = await self.vector_store.search(
                query="",  # Empty query to get all matching documents
                n_results=1000,  # Large number to get all chunks
                where=where_clause
            )
            
            # Convert to DocumentChunk objects
            chunks = []
            for result in results:
                chunk = DocumentChunk(
                    id=result["id"],
                    content=result["content"],
                    meta=result.get("metadata", {}),
                    score=result.get("score", 1.0)
                )
                chunks.append(chunk)
            
            # Sort by chunk index if available
            chunks.sort(key=lambda x: x.meta.get("chunk_index", 0))
            
            logger.info(f"Retrieved {len(chunks)} chunks for document {document_id}")
            return chunks
            
        except Exception as e:
            logger.error(f"Error retrieving chunks for document {document_id}: {str(e)}")
            raise VectorStoreError(f"Failed to retrieve chunks for document: {str(e)}")
    
    async def get_chunk_by_id(
        self,
        chunk_id: str,
        user_id: Optional[int] = None
    ) -> Optional[DocumentChunk]:
        """Get a specific chunk by ID"""
        
        try:
            result = await self.vector_store.get_document(chunk_id)
            
            if result:
                # Check user access if user_id is provided
                if user_id and result.get("metadata", {}).get("user_id") != user_id:
                    return None
                
                chunk = DocumentChunk(
                    id=result["id"],
                    content=result["content"],
                    meta=result.get("metadata", {})
                )
                return chunk
            
            return None
            
        except Exception as e:
            logger.error(f"Error retrieving chunk {chunk_id}: {str(e)}")
            raise VectorStoreError(f"Failed to retrieve chunk: {str(e)}")
    
    async def delete_chunks(
        self,
        chunk_ids: List[str],
        user_id: Optional[int] = None
    ) -> int:
        """Delete chunks by IDs"""
        
        try:
            # If user_id is provided, verify ownership first
            if user_id:
                verified_ids = []
                for chunk_id in chunk_ids:
                    chunk = await self.get_chunk_by_id(chunk_id, user_id)
                    if chunk:
                        verified_ids.append(chunk_id)
                chunk_ids = verified_ids
            
            if chunk_ids:
                deleted_count = await self.vector_store.delete_documents(chunk_ids)
                logger.info(f"Deleted {deleted_count} chunks")
                return deleted_count
            
            return 0
            
        except Exception as e:
            logger.error(f"Error deleting chunks: {str(e)}")
            raise VectorStoreError(f"Failed to delete chunks: {str(e)}")
    
    async def get_user_document_count(self, user_id: int) -> int:
        """Get the number of documents for a user"""
        
        try:
            stats = await self.vector_store.get_collection_stats()
            # This is a simplified implementation
            return stats.get("document_count", 0)
            
        except Exception as e:
            logger.error(f"Error getting user document count: {str(e)}")
            return 0
    
    def format_chunks_for_context(self, chunks: List[DocumentChunk]) -> str:
        """Format retrieved chunks into context string for LLM"""
        
        if not chunks:
            return ""
        
        context_parts = []
        for i, chunk in enumerate(chunks, 1):
            # Include source information
            source_info = ""
            if chunk.meta.get("document_title"):
                source_info = f" (Source: {chunk.meta['document_title']})"
            
            context_parts.append(f"[Document {i}]{source_info}:\n{chunk.content}")
        
        return "\n\n".join(context_parts)
    
    async def get_retrieval_stats(self) -> Dict[str, Any]:
        """Get retrieval statistics"""
        
        try:
            vector_stats = await self.vector_store.get_collection_stats()
            return {
                "vector_store_stats": vector_stats,
                "max_chunks": self.max_chunks,
                "similarity_threshold": self.similarity_threshold
            }
            
        except Exception as e:
            logger.error(f"Error getting retrieval stats: {str(e)}")
            return {}
