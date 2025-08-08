from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
import json

from app.auth.dependencies import get_current_active_user
from app.schema import (
    UserResponse, ChatRequest, ChatResponse, ConversationResponse, 
    ConversationCreate, DocumentChunk
)
from app.generation.chat_service import ChatService
from app.dependencies import get_chat_service
from app.db.database import get_database_session
from app.db.models import Conversation
from app.exceptions import LLMServiceError
from app.logger import logger

router = APIRouter()


@router.post("/", response_model=ChatResponse)
async def chat_with_documents(
    request: ChatRequest,
    current_user: UserResponse = Depends(get_current_active_user),
    chat_service: ChatService = Depends(get_chat_service),
    db: AsyncSession = Depends(get_database_session)
):
    """Send a chat message and get response"""
    try:
        response = await chat_service.process_chat_request(
            request=request,
            user_id=current_user.id,
            db=db
        )
        return response
        
    except LLMServiceError as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Error processing chat request: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to process chat request"
        )


@router.post("/stream")
async def chat_with_documents_stream(
    request: ChatRequest,
    current_user: UserResponse = Depends(get_current_active_user),
    chat_service: ChatService = Depends(get_chat_service),
    db: AsyncSession = Depends(get_database_session)
):
    """Send a chat message and get streaming response"""
    
    async def generate_stream():
        try:
            async for chunk in chat_service.process_streaming_chat_request(
                request=request,
                user_id=current_user.id,
                db=db
            ):
                yield f"data: {json.dumps(chunk)}\n\n"
        except Exception as e:
            error_chunk = {
                "type": "error",
                "error": str(e)
            }
            yield f"data: {json.dumps(error_chunk)}\n\n"
    
    return StreamingResponse(
        generate_stream(),
        media_type="text/plain",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "Content-Type": "text/event-stream"
        }
    )


@router.get("/conversations", response_model=List[ConversationResponse])
async def get_user_conversations(
    limit: int = 20,
    offset: int = 0,
    current_user: UserResponse = Depends(get_current_active_user),
    chat_service: ChatService = Depends(get_chat_service),
    db: AsyncSession = Depends(get_database_session)
):
    """Get list of user's conversations"""
    try:
        conversations = await chat_service.get_conversation_list(
            user_id=current_user.id,
            db=db,
            limit=limit,
            offset=offset
        )
        
        return [
            ConversationResponse(
                id=conv["id"],
                title=conv["title"],
                user_id=current_user.id,
                message_count=conv["message_count"],
                created_at=conv["created_at"],
                updated_at=conv["updated_at"],
                metadata=conv["metadata"]
            )
            for conv in conversations
        ]
        
    except Exception as e:
        logger.error(f"Error getting conversations for user {current_user.id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve conversations"
        )


@router.get("/conversations/{conversation_id}")
async def get_conversation(
    conversation_id: str,
    current_user: UserResponse = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_database_session)
):
    """Get specific conversation with messages"""
    try:
        stmt = select(Conversation).where(
            and_(
                Conversation.id == conversation_id,
                Conversation.user_id == current_user.id
            )
        )
        result = await db.execute(stmt)
        conversation = result.scalar_one_or_none()
        
        if not conversation:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Conversation not found"
            )
        
        # Get conversation with messages
        from sqlalchemy.orm import selectinload
        stmt = select(Conversation).where(
            Conversation.id == conversation_id
        ).options(selectinload(Conversation.messages))
        
        result = await db.execute(stmt)
        conversation = result.scalar_one()
        
        # Format response
        messages = []
        for msg in sorted(conversation.messages, key=lambda x: x.created_at):
            messages.append({
                "role": msg.role,
                "content": msg.content,
                "timestamp": msg.created_at.isoformat(),
                "metadata": msg.metadata
            })
        
        return {
            "id": conversation.id,
            "title": conversation.title,
            "user_id": conversation.user_id,
            "message_count": conversation.message_count,
            "created_at": conversation.created_at.isoformat(),
            "updated_at": conversation.updated_at.isoformat(),
            "metadata": conversation.metadata,
            "messages": messages
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting conversation {conversation_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve conversation"
        )


@router.delete("/conversations/{conversation_id}")
async def delete_conversation(
    conversation_id: str,
    current_user: UserResponse = Depends(get_current_active_user),
    chat_service: ChatService = Depends(get_chat_service),
    db: AsyncSession = Depends(get_database_session)
):
    """Delete a conversation"""
    try:
        deleted = await chat_service.delete_conversation(
            conversation_id=conversation_id,
            user_id=current_user.id,
            db=db
        )
        
        if not deleted:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Conversation not found"
            )
        
        return {"message": "Conversation deleted successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting conversation {conversation_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete conversation"
        )


@router.post("/search", response_model=List[DocumentChunk])
async def search_documents(
    query: str,
    max_results: int = 5,
    similarity_threshold: float = 0.7,
    document_ids: Optional[List[str]] = None,
    current_user: UserResponse = Depends(get_current_active_user),
    chat_service: ChatService = Depends(get_chat_service)
):
    """Search user's documents for relevant content"""
    try:
        # Use the document retriever from chat service
        chunks = await chat_service.document_retriever.retrieve_relevant_chunks(
            query=query,
            user_id=current_user.id,
            document_ids=document_ids,
            max_chunks=max_results,
            similarity_threshold=similarity_threshold
        )
        
        return chunks
        
    except Exception as e:
        logger.error(f"Error searching documents: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to search documents"
        )


@router.get("/stats")
async def get_chat_stats(
    current_user: UserResponse = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_database_session)
):
    """Get chat statistics for the user"""
    try:
        from sqlalchemy import func
        from app.db.models import ChatMessage
        
        # Get conversation count
        conversation_count_stmt = select(func.count(Conversation.id)).where(
            Conversation.user_id == current_user.id
        )
        conversation_count_result = await db.execute(conversation_count_stmt)
        conversation_count = conversation_count_result.scalar()
        
        # Get message count
        message_count_stmt = select(func.count(ChatMessage.id)).where(
            ChatMessage.conversation_id.in_(
                select(Conversation.id).where(Conversation.user_id == current_user.id)
            )
        )
        message_count_result = await db.execute(message_count_stmt)
        message_count = message_count_result.scalar()
        
        # Get recent conversation
        recent_conversation_stmt = select(Conversation).where(
            Conversation.user_id == current_user.id
        ).order_by(Conversation.updated_at.desc()).limit(1)
        recent_conversation_result = await db.execute(recent_conversation_stmt)
        recent_conversation = recent_conversation_result.scalar_one_or_none()
        
        return {
            "conversation_count": conversation_count or 0,
            "message_count": message_count or 0,
            "last_conversation_date": (
                recent_conversation.updated_at.isoformat() 
                if recent_conversation else None
            ),
            "user_id": current_user.id
        }
        
    except Exception as e:
        logger.error(f"Error getting chat stats: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get chat statistics"
        )


@router.post("/conversations", response_model=ConversationResponse)
async def create_conversation(
    conversation_data: ConversationCreate,
    current_user: UserResponse = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_database_session)
):
    """Create a new conversation"""
    try:
        import uuid
        
        conversation = Conversation(
            id=str(uuid.uuid4()),
            title=conversation_data.title,
            user_id=current_user.id,
            metadata=conversation_data.metadata or {}
        )
        
        db.add(conversation)
        await db.commit()
        await db.refresh(conversation)
        
        return ConversationResponse.from_orm(conversation)
        
    except Exception as e:
        logger.error(f"Error creating conversation: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create conversation"
        )
