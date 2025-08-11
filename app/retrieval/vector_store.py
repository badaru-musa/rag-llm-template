from typing import List, Dict, Any, Optional, Tuple
import uuid
from app.embeddings.embedding_factory import BaseEmbeddingService
from app.exceptions import VectorStoreError
from app.logger import logger


class ChromaVectorStore:
    """ChromaDB vector store implementation"""
    
    def __init__(
        self,
        host: str,
        port: int,
        collection_name: str,
        persist_directory: str,
        embedding_service: BaseEmbeddingService
    ):
        self.host = host
        self.port = port
        self.collection_name = collection_name
        self.persist_directory = persist_directory
        self.embedding_service = embedding_service
        self.client = None
        self.collection = None
    
    async def initialize(self):
        """Initialize ChromaDB client and collection"""
        try:
            import chromadb
            
            # Use PersistentClient for local storage
            self.client = chromadb.PersistentClient(
                path=self.persist_directory
            )
            
            # Get or create collection
            try:
                self.collection = self.client.get_collection(name=self.collection_name)
                logger.info(f"Connected to existing ChromaDB collection: {self.collection_name}")
            except Exception:
                # Create new collection if it doesn't exist
                self.collection = self.client.create_collection(
                    name=self.collection_name,
                    metadata={"description": "RAG document embeddings"}
                )
                logger.info(f"Created new ChromaDB collection: {self.collection_name}")
            
        except ImportError:
            raise VectorStoreError("ChromaDB library not installed")
        except Exception as e:
            raise VectorStoreError(f"Failed to initialize ChromaDB: {str(e)}")
    
    async def add_documents(
        self,
        documents: List[str],
        metadatas: List[Dict[str, Any]],
        ids: Optional[List[str]] = None
    ) -> List[str]:
        """Add documents to the vector store"""
        try:
            if not self.collection:
                raise VectorStoreError("ChromaDB collection not initialized")
            
            if not ids:
                ids = [str(uuid.uuid4()) for _ in documents]
            
            # Generate embeddings
            embeddings = await self.embedding_service.embed_texts(documents)
            
            # Add to ChromaDB
            self.collection.add(
                embeddings=embeddings,
                documents=documents,
                metadatas=metadatas,
                ids=ids
            )
            
            logger.info(f"Added {len(documents)} documents to ChromaDB")
            return ids
            
        except Exception as e:
            raise VectorStoreError(f"Failed to add documents to ChromaDB: {str(e)}")
    
    async def search(
        self,
        query: str,
        n_results: int = 5,
        where: Optional[Dict[str, Any]] = None,
        score_threshold: Optional[float] = None
    ) -> List[Dict[str, Any]]:
        """Search for similar documents"""
        try:
            if not self.collection:
                logger.warning("ChromaDB collection not initialized, attempting to initialize...")
                await self.initialize()
            
            # Log collection stats before search
            try:
                count = self.collection.count()
                logger.info(f"Collection has {count} documents before search")
            except:
                pass
            
            # Generate query embedding
            query_embedding = await self.embedding_service.embed_text(query)
            logger.info(f"Generated query embedding for: '{query[:50]}...'")
            
            # Perform search
            logger.info(f"Searching with n_results={n_results}, where={where}")
            results = self.collection.query(
                query_embeddings=[query_embedding],
                n_results=n_results,
                where=where,
                include=["documents", "metadatas", "distances"]
            )
            
            # Log raw results
            logger.info(f"Raw search results - documents found: {len(results.get('documents', [[]])[0])}")
            
            # Format results
            formatted_results = []
            if results["documents"] and results["documents"][0]:
                for i in range(len(results["documents"][0])):
                    distance = results["distances"][0][i]
                    # Convert distance to similarity score (1 - distance)
                    similarity_score = 1 - distance
                    
                    # Apply score threshold if specified
                    if score_threshold and similarity_score < score_threshold:
                        logger.debug(f"Skipping result with score {similarity_score} below threshold {score_threshold}")
                        continue
                    
                    formatted_results.append({
                        "id": results["ids"][0][i],
                        "content": results["documents"][0][i],
                        "metadata": results["metadatas"][0][i] or {},
                        "score": similarity_score
                    })
            
            logger.info(f"Found {len(formatted_results)} similar documents for query after filtering")
            return formatted_results
            
        except Exception as e:
            raise VectorStoreError(f"Failed to search ChromaDB: {str(e)}")
    
    async def get_document(self, document_id: str) -> Optional[Dict[str, Any]]:
        """Get a specific document by ID"""
        try:
            if not self.collection:
                raise VectorStoreError("ChromaDB collection not initialized")
            
            results = self.collection.get(
                ids=[document_id],
                include=["documents", "metadatas"]
            )
            
            if results["documents"] and results["documents"][0]:
                return {
                    "id": document_id,
                    "content": results["documents"][0],
                    "metadata": results["metadatas"][0] or {}
                }
            
            return None
            
        except Exception as e:
            raise VectorStoreError(f"Failed to get document from ChromaDB: {str(e)}")
    
    async def delete_documents(self, document_ids: List[str]) -> int:
        """Delete documents by IDs"""
        try:
            if not self.collection:
                raise VectorStoreError("ChromaDB collection not initialized")
            
            self.collection.delete(ids=document_ids)
            logger.info(f"Deleted {len(document_ids)} documents from ChromaDB")
            return len(document_ids)
            
        except Exception as e:
            raise VectorStoreError(f"Failed to delete documents from ChromaDB: {str(e)}")
    
    async def update_document(
        self,
        document_id: str,
        document: str,
        metadata: Dict[str, Any]
    ):
        """Update a document"""
        try:
            if not self.collection:
                raise VectorStoreError("ChromaDB collection not initialized")

            embedding = await self.embedding_service.embed_text(document)
            
            # Update in ChromaDB
            self.collection.update(
                ids=[document_id],
                embeddings=[embedding],
                documents=[document],
                metadatas=[metadata]
            )
            
            logger.info(f"Updated document {document_id} in ChromaDB")
            
        except Exception as e:
            raise VectorStoreError(f"Failed to update document in ChromaDB: {str(e)}")
    
    async def get_collection_stats(self) -> Dict[str, Any]:
        """Get collection statistics"""
        try:
            if not self.collection:
                raise VectorStoreError("ChromaDB collection not initialized")
            
            count = self.collection.count()
            return {
                "collection_name": self.collection_name,
                "document_count": count,
                "embedding_dimension": self.embedding_service.get_dimension()
            }
            
        except Exception as e:
            raise VectorStoreError(f"Failed to get collection stats: {str(e)}")
    
    async def close(self):
        """Close the vector store connection"""
        try:
            if self.client:
                # ChromaDB doesn't have an explicit close method for HTTP client
                self.client = None
                self.collection = None
                logger.info("Closed ChromaDB connection")
        except Exception as e:
            logger.error(f"Error closing ChromaDB connection: {str(e)}")
