from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_

from app.auth.dependencies import get_current_active_user
from app.schema import (
    UserResponse, DocumentResponse, DocumentCreate, DocumentUpdate, 
    FileUploadResponse, DocumentChunk
)
from app.db.models import Document, DocumentChunk as DocumentChunkModel
from app.db.database import get_database_session
from app.ingestion.document_processor import DocumentProcessor
from app.ingestion.file_uploader import FileUploader
from app.retrieval.retriever import DocumentRetriever
from app.dependencies import get_document_processor, get_document_retriever
from app.enums import DocumentStatus
from app.exceptions import DocumentProcessingError, FileUploadError, ValidationError
from app.logger import logger

router = APIRouter()


@router.post("/upload", response_model=FileUploadResponse, status_code=status.HTTP_201_CREATED)
async def upload_document(
    file: UploadFile = File(...),
    title: Optional[str] = Form(None),
    current_user: UserResponse = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_database_session),
    document_processor: DocumentProcessor = Depends(get_document_processor)
):
    """Upload and process a document"""
    try:
        # Initialize file uploader
        file_uploader = FileUploader()
        
        # Save uploaded file
        file_path = await file_uploader.save_uploaded_file(
            file=file,
            user_id=current_user.id,
            custom_filename=None
        )
        
        # Extract file type
        file_type = file.filename.split('.')[-1].lower() if file.filename else 'txt'
        
        # Create document record
        document_title = title or file.filename or "Untitled Document"
        document = Document(
            title=document_title,
            file_path=file_path,
            file_type=file_type,
            status=DocumentStatus.PROCESSING.value,
            user_id=current_user.id,
            meta={"original_filename": file.filename}
        )
        
        db.add(document)
        await db.commit()
        await db.refresh(document)
        
        # Process document asynchronously (simplified - in production you'd use a task queue)
        try:
            content, chunks = await document_processor.process_document(
                file_path=file_path,
                file_type=file_type,
                meta={
                    "document_id": document.id,
                    "user_id": current_user.id,
                    "document_title": document_title
                }
            )
            
            # Generate embeddings for chunks in batches
            logger.info(f"Processing {len(chunks)} chunks for embeddings...")
            chunks_with_embeddings = await document_processor.process_chunks_with_embeddings(chunks)
            
            # Store chunks in vector store with embeddings
            from app.dependencies import get_vector_store
            vector_store = get_vector_store()
            
            # Ensure vector store is initialized
            if not vector_store.collection:
                await vector_store.initialize()
            
            # Store chunks in vector store - process in batches to avoid issues
            stored_count = 0
            failed_chunks = []
            batch_size = 5000  # Process in batches for vector store
            
            for i in range(0, len(chunks_with_embeddings), batch_size):
                batch_end = min(i + batch_size, len(chunks_with_embeddings))
                batch_chunks = chunks_with_embeddings[i:batch_end]
                
                # Filter out chunks without embeddings
                valid_chunks = [chunk for chunk in batch_chunks if chunk.get("embedding") is not None]
                
                if valid_chunks:
                    try:
                        chunk_texts = [chunk["content"] for chunk in valid_chunks]
                        chunk_metadatas = [chunk["meta"] for chunk in valid_chunks]
                        chunk_ids = [chunk["id"] for chunk in valid_chunks]
                        embeddings = [chunk["embedding"] for chunk in valid_chunks]
                        
                        # Store batch in vector store
                        vector_store.collection.add(
                            embeddings=embeddings,
                            documents=chunk_texts,
                            metadatas=chunk_metadatas,
                            ids=chunk_ids
                        )
                        stored_count += len(valid_chunks)
                        logger.info(f"Stored batch {i//batch_size + 1} ({len(valid_chunks)} chunks) in vector store")
                        
                    except Exception as batch_error:
                        logger.error(f"Failed to store batch {i//batch_size + 1} in vector store: {str(batch_error)}")
                        failed_chunks.extend([chunk["id"] for chunk in valid_chunks])
            
            logger.info(f"Successfully stored {stored_count}/{len(chunks_with_embeddings)} chunks in vector store for document {document.id}")
            if failed_chunks:
                logger.warning(f"Failed to store {len(failed_chunks)} chunks: {failed_chunks[:5]}...")
            
            # Save document content
            document.content = content
            document.chunk_count = len(chunks_with_embeddings)
            document.status = DocumentStatus.COMPLETED.value
            
            # Save chunks to database
            for chunk_data in chunks_with_embeddings:
                chunk = DocumentChunkModel(
                    id=chunk_data["id"],
                    content=chunk_data["content"],
                    chunk_index=chunk_data["meta"]["chunk_index"],
                    meta=chunk_data["meta"],
                    document_id=document.id
                )
                db.add(chunk)
            
            await db.commit()
            await db.refresh(document)
            
            logger.info(f"Successfully processed document {document.id} for user {current_user.id}")
            
        except Exception as e:
            logger.error(f"Error processing document {document.id}: {str(e)}")
            document.status = DocumentStatus.FAILED.value
            document.meta = {**document.meta, "error": str(e)}
            await db.commit()
        
        return FileUploadResponse(
            filename=file.filename or "unknown",
            file_size=file_uploader.get_file_info(file_path).get("file_size", 0),
            file_type=file_type,
            document_id=document.id
        )
        
    except FileUploadError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Error uploading document: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to upload document"
        )


@router.get("/", response_model=List[DocumentResponse])
async def list_user_documents(
    skip: int = 0,
    limit: int = 20,
    status_filter: Optional[DocumentStatus] = None,
    current_user: UserResponse = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_database_session)
):
    """Get list of user's documents"""
    try:
        query = select(Document).where(Document.user_id == current_user.id)
        
        if status_filter:
            query = query.where(Document.status == status_filter.value)
        
        query = query.order_by(Document.created_at.desc()).offset(skip).limit(limit)
        
        result = await db.execute(query)
        documents = result.scalars().all()
        
        return [DocumentResponse.from_orm(doc) for doc in documents]
        
    except Exception as e:
        logger.error(f"Error listing documents for user {current_user.id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve documents"
        )


@router.get("/{document_id}", response_model=DocumentResponse)
async def get_document(
    document_id: int,
    current_user: UserResponse = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_database_session)
):
    """Get specific document by ID"""
    try:
        stmt = select(Document).where(
            and_(
                Document.id == document_id,
                Document.user_id == current_user.id
            )
        )
        result = await db.execute(stmt)
        document = result.scalar_one_or_none()
        
        if not document:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Document not found"
            )
        
        return DocumentResponse.from_orm(document)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting document {document_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve document"
        )


@router.put("/{document_id}", response_model=DocumentResponse)
async def update_document(
    document_id: int,
    document_update: DocumentUpdate,
    current_user: UserResponse = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_database_session)
):
    """Update document meta"""
    try:
        stmt = select(Document).where(
            and_(
                Document.id == document_id,
                Document.user_id == current_user.id
            )
        )
        result = await db.execute(stmt)
        document = result.scalar_one_or_none()
        
        if not document:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Document not found"
            )
        
        # Update fields
        if document_update.title is not None:
            document.title = document_update.title
        
        if document_update.meta is not None:
            document.meta = {**document.meta, **document_update.meta}
        
        await db.commit()
        await db.refresh(document)
        
        return DocumentResponse.from_orm(document)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating document {document_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update document"
        )


@router.delete("/{document_id}")
async def delete_document(
    document_id: int,
    current_user: UserResponse = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_database_session),
    document_retriever: DocumentRetriever = Depends(get_document_retriever)
):
    """Delete a document and its chunks"""
    try:
        stmt = select(Document).where(
            and_(
                Document.id == document_id,
                Document.user_id == current_user.id
            )
        )
        result = await db.execute(stmt)
        document = result.scalar_one_or_none()
        
        if not document:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Document not found"
            )
        
        # Delete from vector store first
        try:
            chunks = await document_retriever.retrieve_chunks_by_document(
                document_id=str(document_id),
                user_id=current_user.id
            )
            chunk_ids = [chunk.id for chunk in chunks]
            if chunk_ids:
                await document_retriever.delete_chunks(chunk_ids, current_user.id)
        except Exception as e:
            logger.warning(f"Error deleting chunks from vector store: {str(e)}")
        
        # Delete file
        if document.file_path:
            try:
                file_uploader = FileUploader()
                await file_uploader.delete_file(document.file_path, current_user.id)
            except Exception as e:
                logger.warning(f"Error deleting file {document.file_path}: {str(e)}")
        
        # Delete from database
        await db.delete(document)
        await db.commit()
        
        logger.info(f"Deleted document {document_id} for user {current_user.id}")
        
        return {"message": "Document deleted successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting document {document_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete document"
        )


@router.get("/{document_id}/chunks", response_model=List[DocumentChunk])
async def get_document_chunks(
    document_id: int,
    current_user: UserResponse = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_database_session),
    document_retriever: DocumentRetriever = Depends(get_document_retriever)
):
    """Get all chunks for a document"""
    try:
        # Verify document exists and belongs to user
        stmt = select(Document).where(
            and_(
                Document.id == document_id,
                Document.user_id == current_user.id
            )
        )
        result = await db.execute(stmt)
        document = result.scalar_one_or_none()
        
        if not document:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Document not found"
            )
        
        # First try to get chunks from database
        chunks_stmt = select(DocumentChunkModel).where(
            DocumentChunkModel.document_id == document_id
        ).order_by(DocumentChunkModel.chunk_index)
        
        chunks_result = await db.execute(chunks_stmt)
        db_chunks = chunks_result.scalars().all()
        
        if db_chunks:
            # Convert database chunks to response model
            chunks = [
                DocumentChunk(
                    id=chunk.id,
                    content=chunk.content,
                    meta=chunk.meta or {},
                    score=None
                )
                for chunk in db_chunks
            ]
            logger.info(f"Retrieved {len(chunks)} chunks from database for document {document_id}")
            return chunks
        
        # Fallback to vector store if no chunks in database
        logger.info(f"No chunks in database for document {document_id}, trying vector store")
        chunks = await document_retriever.retrieve_chunks_by_document(
            document_id=str(document_id),
            user_id=current_user.id
        )
        
        return chunks
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting chunks for document {document_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve document chunks"
        )


@router.post("/{document_id}/reprocess")
async def reprocess_document(
    document_id: int,
    current_user: UserResponse = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_database_session),
    document_processor: DocumentProcessor = Depends(get_document_processor)
):
    """Reprocess a document (re-chunk and re-embed)"""
    try:
        stmt = select(Document).where(
            and_(
                Document.id == document_id,
                Document.user_id == current_user.id
            )
        )
        result = await db.execute(stmt)
        document = result.scalar_one_or_none()
        
        if not document:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Document not found"
            )
        
        if not document.file_path:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Document has no file to reprocess"
            )
        
        # Update status to processing
        document.status = DocumentStatus.PROCESSING.value
        await db.commit()
        
        # Reprocess document (simplified - in production use task queue)
        try:
            content, chunks = await document_processor.process_document(
                file_path=document.file_path,
                file_type=document.file_type,
                meta={
                    "document_id": document.id,
                    "user_id": current_user.id,
                    "document_title": document.title
                }
            )
            
            # Generate embeddings for chunks in batches
            logger.info(f"Reprocessing {len(chunks)} chunks for embeddings...")
            chunks_with_embeddings = await document_processor.process_chunks_with_embeddings(chunks)
            
            # Delete old chunks from database
            stmt = select(DocumentChunkModel).where(DocumentChunkModel.document_id == document.id)
            result = await db.execute(stmt)
            old_chunks = result.scalars().all()
            old_chunk_ids = [chunk.id for chunk in old_chunks]
            
            # Delete old chunks from vector store
            if old_chunk_ids:
                from app.dependencies import get_vector_store
                vector_store = get_vector_store()
                if not vector_store.collection:
                    await vector_store.initialize()
                try:
                    # Delete in batches to avoid issues
                    for i in range(0, len(old_chunk_ids), 5000):
                        batch_ids = old_chunk_ids[i:i+5000]
                        await vector_store.delete_documents(batch_ids)
                except Exception as e:
                    logger.warning(f"Error deleting old chunks from vector store: {str(e)}")
            
            # Delete old chunks from database
            for chunk in old_chunks:
                await db.delete(chunk)
            
            # Store new chunks in vector store with embeddings - batch processing
            from app.dependencies import get_vector_store
            vector_store = get_vector_store()
            if not vector_store.collection:
                await vector_store.initialize()
            
            stored_count = 0
            failed_chunks = []
            batch_size = 5000
            
            for i in range(0, len(chunks_with_embeddings), batch_size):
                batch_end = min(i + batch_size, len(chunks_with_embeddings))
                batch_chunks = chunks_with_embeddings[i:batch_end]
                
                # Filter out chunks without embeddings
                valid_chunks = [chunk for chunk in batch_chunks if chunk.get("embedding") is not None]
                
                if valid_chunks:
                    try:
                        chunk_texts = [chunk["content"] for chunk in valid_chunks]
                        chunk_metadatas = [chunk["meta"] for chunk in valid_chunks]
                        chunk_ids = [chunk["id"] for chunk in valid_chunks]
                        embeddings = [chunk["embedding"] for chunk in valid_chunks]
                        
                        vector_store.collection.add(
                            embeddings=embeddings,
                            documents=chunk_texts,
                            metadatas=chunk_metadatas,
                            ids=chunk_ids
                        )
                        stored_count += len(valid_chunks)
                        
                    except Exception as batch_error:
                        logger.error(f"Failed to store batch in vector store: {str(batch_error)}")
                        failed_chunks.extend([chunk["id"] for chunk in valid_chunks])
            
            logger.info(f"Stored {stored_count}/{len(chunks_with_embeddings)} reprocessed chunks in vector store for document {document.id}")
            
            # Save new chunks to database
            for chunk_data in chunks_with_embeddings:
                chunk = DocumentChunkModel(
                    id=chunk_data["id"],
                    content=chunk_data["content"],
                    chunk_index=chunk_data["meta"]["chunk_index"],
                    meta=chunk_data["meta"],
                    document_id=document.id
                )
                db.add(chunk)
            
            document.content = content
            document.chunk_count = len(chunks_with_embeddings)
            document.status = DocumentStatus.COMPLETED.value
            
            await db.commit()
            
            return {"message": "Document reprocessed successfully"}
            
        except Exception as e:
            document.status = DocumentStatus.FAILED.value
            document.meta = {**document.meta, "reprocess_error": str(e)}
            await db.commit()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to reprocess document: {str(e)}"
            )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error reprocessing document {document_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to reprocess document"
        )
