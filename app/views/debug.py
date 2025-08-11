from fastapi import APIRouter, Depends, HTTPException
from app.auth.dependencies import get_current_active_user
from app.schema import UserResponse
from app.dependencies import get_vector_store, get_document_retriever
from app.logger import logger

router = APIRouter()


@router.get("/vector-store/stats")
async def get_vector_store_stats(
    current_user: UserResponse = Depends(get_current_active_user),
    vector_store = Depends(get_vector_store)
):
    """Get vector store statistics and debug info"""
    try:
        # Ensure vector store is initialized
        if not vector_store.collection:
            await vector_store.initialize()
        
        stats = await vector_store.get_collection_stats()
        
        # Get sample documents
        sample_docs = []
        try:
            results = vector_store.collection.get(
                limit=5,
                include=["documents", "metadatas"]
            )
            
            for i in range(min(3, len(results['ids']))):
                sample_docs.append({
                    "id": results['ids'][i],
                    "content_preview": results['documents'][i][:100] if results['documents'] else "",
                    "metadata": results['metadatas'][i] if results['metadatas'] else {}
                })
        except Exception as e:
            logger.error(f"Error getting sample docs: {e}")
        
        return {
            "stats": stats,
            "sample_documents": sample_docs,
            "user_id": current_user.id
        }
        
    except Exception as e:
        logger.error(f"Error getting vector store stats: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/vector-store/test-search")
async def test_vector_search(
    query: str,
    current_user: UserResponse = Depends(get_current_active_user),
    retriever = Depends(get_document_retriever)
):
    """Test vector search with different configurations"""
    try:
        # Ensure vector store is initialized
        if not retriever.vector_store.collection:
            await retriever.vector_store.initialize()
        
        results = {}
        
        # Test 1: Search without any filters
        try:
            chunks_no_filter = await retriever.retrieve_relevant_chunks(
                query=query,
                user_id=None,  # No user filter
                max_chunks=5,
                similarity_threshold=0.1  # Very low threshold
            )
            results["no_filter"] = {
                "count": len(chunks_no_filter),
                "chunks": [{"content": c.content[:100], "score": c.score} for c in chunks_no_filter[:2]]
            }
        except Exception as e:
            results["no_filter"] = {"error": str(e)}
        
        # Test 2: Search with user filter
        try:
            chunks_with_user = await retriever.retrieve_relevant_chunks(
                query=query,
                user_id=current_user.id,
                max_chunks=5,
                similarity_threshold=0.1
            )
            results["with_user_filter"] = {
                "count": len(chunks_with_user),
                "chunks": [{"content": c.content[:100], "score": c.score} for c in chunks_with_user[:2]]
            }
        except Exception as e:
            results["with_user_filter"] = {"error": str(e)}
        
        # Test 3: Get raw ChromaDB search
        try:
            import chromadb
            client = chromadb.PersistentClient(path="./data/vector_store")
            collection = client.get_collection(name="documents")
            
            # Get embedding for query
            from app.dependencies import get_embedding_service
            embedding_service = get_embedding_service()
            query_embedding = await embedding_service.embed_text(query)
            
            # Raw search
            raw_results = collection.query(
                query_embeddings=[query_embedding],
                n_results=5,
                include=["documents", "metadatas", "distances"]
            )
            
            results["raw_chromadb"] = {
                "count": len(raw_results['documents'][0]) if raw_results['documents'] else 0,
                "sample": raw_results['documents'][0][:2] if raw_results['documents'] and raw_results['documents'][0] else []
            }
        except Exception as e:
            results["raw_chromadb"] = {"error": str(e)}
        
        return {
            "query": query,
            "user_id": current_user.id,
            "results": results
        }
        
    except Exception as e:
        logger.error(f"Error testing vector search: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/vector-store/user-documents")
async def get_user_documents_in_vector_store(
    current_user: UserResponse = Depends(get_current_active_user),
    vector_store = Depends(get_vector_store)
):
    """Check what documents are in vector store for current user"""
    try:
        if not vector_store.collection:
            await vector_store.initialize()
        
        # Get all documents with user_id metadata
        all_docs = vector_store.collection.get(
            where={"user_id": {"$eq": current_user.id}},
            limit=100,
            include=["documents", "metadatas"]
        )
        
        # Group by document
        documents = {}
        for i, metadata in enumerate(all_docs['metadatas'] if all_docs['metadatas'] else []):
            if metadata:
                doc_id = metadata.get('document_id', 'unknown')
                if doc_id not in documents:
                    documents[doc_id] = {
                        "document_id": doc_id,
                        "document_title": metadata.get('document_title', 'Unknown'),
                        "chunk_count": 0,
                        "sample_chunks": []
                    }
                
                documents[doc_id]["chunk_count"] += 1
                if len(documents[doc_id]["sample_chunks"]) < 2:
                    documents[doc_id]["sample_chunks"].append({
                        "chunk_index": metadata.get('chunk_index', -1),
                        "content_preview": all_docs['documents'][i][:100] if all_docs['documents'] else ""
                    })
        
        return {
            "user_id": current_user.id,
            "total_chunks": len(all_docs['ids']) if all_docs['ids'] else 0,
            "documents": list(documents.values())
        }
        
    except Exception as e:
        logger.error(f"Error getting user documents from vector store: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
