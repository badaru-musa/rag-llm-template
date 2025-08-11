from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from fastapi.responses import StreamingResponse, Response
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_, func
import json
import io
import csv
from datetime import datetime

from app.auth.dependencies import get_current_active_user
from app.schema import (
    UserResponse, ChatRequest, ChatResponse, ConversationResponse, 
    ConversationCreate, DocumentChunk, MessageSearchRequest, MessageUpdateRequest,
    MessageLikeRequest, RegenerateRequest, ConversationExportRequest,
    MessageResponse, ConversationMessagesResponse
)
from app.generation.chat_service import ChatService
from app.dependencies import get_chat_service
from app.db.database import get_database_session
from app.db.models import Conversation, ChatMessage
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
        logger.info(f"User {current_user.id} sending chat message (conversation_id: {request.conversation_id})")
        
        # Validate request
        if not request.message or len(request.message.strip()) == 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Message cannot be empty"
            )
        
        if request.conversation_id and len(request.conversation_id.strip()) == 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Conversation ID cannot be empty string"
            )
        
        response = await chat_service.process_chat_request(
            request=request,
            user_id=current_user.id,
            db=db
        )
        
        logger.info(f"Successfully processed chat request for user {current_user.id}")
        return response
        
    except HTTPException:
        raise
    except LLMServiceError as e:
        logger.error(f"LLM service error for user {current_user.id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"LLM service error: {str(e)}"
        )
    except Exception as e:
        logger.error(f"Unexpected error processing chat request for user {current_user.id}: {type(e).__name__}: {str(e)}")
        import traceback
        logger.error(f"Full traceback: {traceback.format_exc()}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to process chat request: {str(e)}"
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
                meta=conv["meta"]  # Fixed: changed from metadata to meta
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
                "metadata": msg.meta  # Fixed: changed from metadata to meta
            })
        
        return {
            "id": conversation.id,
            "title": conversation.title,
            "user_id": conversation.user_id,
            "message_count": conversation.message_count,
            "created_at": conversation.created_at.isoformat(),
            "updated_at": conversation.updated_at.isoformat(),
            "metadata": conversation.meta,  # Fixed: changed from metadata to meta
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


from pydantic import BaseModel, Field

class SearchRequest(BaseModel):
    """Search request schema"""
    query: str = Field(..., description="Search query")
    max_results: int = Field(default=5, ge=1, le=20, description="Maximum results to return")
    similarity_threshold: float = Field(default=0.7, ge=0.0, le=1.0, description="Similarity threshold")
    document_ids: Optional[List[str]] = Field(default=None, description="Filter by document IDs")

@router.post("/search", response_model=List[DocumentChunk])
async def search_documents(
    search_request: SearchRequest,
    current_user: UserResponse = Depends(get_current_active_user),
    chat_service: ChatService = Depends(get_chat_service)
):
    """Search user's documents for relevant content"""
    try:
        # Use the document retriever from chat service
        chunks = await chat_service.document_retriever.retrieve_relevant_chunks(
            query=search_request.query,
            user_id=current_user.id,
            document_ids=search_request.document_ids,
            max_chunks=search_request.max_results,
            similarity_threshold=search_request.similarity_threshold
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
            meta=conversation_data.meta or {}  # Fixed: changed from metadata to meta
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


@router.get("/conversations/{conversation_id}/messages", response_model=ConversationMessagesResponse)
async def get_conversation_messages(
    conversation_id: str,
    limit: int = Query(default=50, ge=1, le=200, description="Maximum number of messages to return", example=50),
    offset: int = Query(default=0, ge=0, description="Number of messages to skip for pagination", example=0),
    include_meta: bool = Query(default=True, description="Include message metadata", example=True),
    current_user: UserResponse = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_database_session)
):
    """
    Retrieve all messages from a conversation with pagination.
    
    This endpoint allows users to fetch all messages from a specific conversation
    they own, with support for pagination to handle large conversations.
    
    **Example usage:**
    ```
    GET /chat/conversations/abc-123/messages?limit=20&offset=0&include_meta=true
    ```
    
    **Parameters:**
    - conversation_id: Conversation ID (path parameter)
    - limit: Maximum number of messages to return (default: 50, max: 200)
    - offset: Number of messages to skip for pagination (default: 0)
    - include_meta: Include message metadata in response (default: true)
    """
    try:
        logger.info(f"User {current_user.id} requesting messages for conversation {conversation_id} (limit={limit}, offset={offset})")
        
        # Verify the conversation exists and belongs to the user
        conversation_stmt = select(Conversation).where(
            and_(
                Conversation.id == conversation_id,
                Conversation.user_id == current_user.id
            )
        )
        conversation_result = await db.execute(conversation_stmt)
        conversation = conversation_result.scalar_one_or_none()
        
        if not conversation:
            logger.warning(f"Conversation {conversation_id} not found for user {current_user.id}")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Conversation {conversation_id} not found or access denied"
            )
        
        # Get total message count
        total_count_stmt = select(func.count(ChatMessage.id)).where(
            ChatMessage.conversation_id == conversation_id
        )
        total_count_result = await db.execute(total_count_stmt)
        total_messages = total_count_result.scalar() or 0
        
        logger.info(f"Found {total_messages} total messages in conversation {conversation_id}")
        
        # Get messages with pagination
        messages_stmt = select(ChatMessage).where(
            ChatMessage.conversation_id == conversation_id
        ).order_by(ChatMessage.created_at.asc()).offset(offset).limit(limit)
        
        messages_result = await db.execute(messages_stmt)
        messages = messages_result.scalars().all()
        
        logger.info(f"Retrieved {len(messages)} messages for conversation {conversation_id}")
        
        # Format messages
        formatted_messages = []
        for msg in messages:
            try:
                message_data = {
                    "id": msg.id,
                    "role": msg.role,
                    "content": msg.content,
                    "original_content": msg.original_content,
                    "is_edited": msg.is_edited,
                    "edit_count": msg.edit_count,
                    "like_status": msg.like_status,
                    "conversation_id": msg.conversation_id,
                    "created_at": msg.created_at,
                    "updated_at": msg.updated_at,
                    "meta": msg.meta if include_meta else {}
                }
                formatted_messages.append(MessageResponse(**message_data))
            except Exception as msg_error:
                logger.error(f"Error formatting message {msg.id}: {str(msg_error)}")
                # Continue processing other messages rather than failing completely
                continue
        
        response = ConversationMessagesResponse(
            conversation_id=conversation_id,
            title=conversation.title,
            total_messages=total_messages,
            messages=formatted_messages
        )
        
        logger.info(f"Successfully retrieved {len(formatted_messages)} messages for conversation {conversation_id}")
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error getting messages for conversation {conversation_id}: {type(e).__name__}: {str(e)}")
        import traceback
        logger.error(f"Full traceback: {traceback.format_exc()}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve conversation messages: {str(e)}"
        )


@router.get("/conversations/{conversation_id}/messages/search", response_model=List[MessageResponse])
async def search_conversation_messages(
    conversation_id: str,
    query: str = Query(..., min_length=1, description="Search query", example="hello"),
    limit: int = Query(default=10, ge=1, le=50, description="Maximum results to return", example=10),
    offset: int = Query(default=0, ge=0, description="Results offset for pagination", example=0),
    role_filter: Optional[str] = Query(None, description="Filter by message role (user or assistant)", example="user"),
    current_user: UserResponse = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_database_session)
):
    """
    Search for messages within a specific conversation.
    
    This endpoint allows users to search through messages in a conversation
    using text matching on message content.
    
    **Example usage:**
    ```
    GET /chat/conversations/abc-123/messages/search?query=hello&limit=10&role_filter=user
    ```
    
    **Parameters:**
    - conversation_id: Conversation ID (path parameter)
    - query: Search query (required, min 1 character)
    - limit: Maximum results to return (default: 10, max: 50)
    - offset: Results offset for pagination (default: 0)
    - role_filter: Filter by message role - 'user' or 'assistant' (optional)
    """
    try:
        logger.info(f"User {current_user.id} searching for '{query}' in conversation {conversation_id}")
        
        # Verify the conversation exists and belongs to the user
        conversation_stmt = select(Conversation).where(
            and_(
                Conversation.id == conversation_id,
                Conversation.user_id == current_user.id
            )
        )
        conversation_result = await db.execute(conversation_stmt)
        conversation = conversation_result.scalar_one_or_none()
        
        if not conversation:
            logger.warning(f"Conversation {conversation_id} not found for user {current_user.id}")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Conversation {conversation_id} not found or access denied"
            )
        
        # Build search query with filters
        search_conditions = [
            ChatMessage.conversation_id == conversation_id,
            or_(
                ChatMessage.content.ilike(f"%{query}%"),
                ChatMessage.original_content.ilike(f"%{query}%")
            )
        ]
        
        # Add role filter if specified
        if role_filter and role_filter in ["user", "assistant"]:
            search_conditions.append(ChatMessage.role == role_filter)
        
        # Search messages using ILIKE for case-insensitive partial matching
        search_stmt = select(ChatMessage).where(
            and_(*search_conditions)
        ).order_by(ChatMessage.created_at.desc()).offset(offset).limit(limit)
        
        search_result = await db.execute(search_stmt)
        messages = search_result.scalars().all()
        
        logger.info(f"Found {len(messages)} messages matching '{query}' in conversation {conversation_id}")
        
        # Format messages
        formatted_messages = []
        for msg in messages:
            try:
                formatted_messages.append(MessageResponse(
                    id=msg.id,
                    role=msg.role,
                    content=msg.content,
                    original_content=msg.original_content,
                    is_edited=msg.is_edited,
                    edit_count=msg.edit_count,
                    like_status=msg.like_status,
                    conversation_id=msg.conversation_id,
                    created_at=msg.created_at,
                    updated_at=msg.updated_at,
                    meta=msg.meta
                ))
            except Exception as msg_error:
                logger.error(f"Error formatting search result message {msg.id}: {str(msg_error)}")
                continue
        
        logger.info(f"User {current_user.id} searched '{query}' in conversation {conversation_id}, returned {len(formatted_messages)} messages")
        
        return formatted_messages
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error searching messages in conversation {conversation_id}: {type(e).__name__}: {str(e)}")
        import traceback
        logger.error(f"Full traceback: {traceback.format_exc()}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to search conversation messages: {str(e)}"
        )


@router.put("/conversations/{conversation_id}/messages/{message_id}", response_model=MessageResponse)
async def update_message(
    conversation_id: str,
    message_id: int,
    content: str = Query(..., min_length=1, description="New message content", example="Updated message content"),
    current_user: UserResponse = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_database_session)
):
    """
    Update or edit a previously sent message.
    
    This endpoint allows users to edit their own messages within a conversation.
    The original content is preserved for audit purposes.
    
    **Example usage:**
    ```
    PUT /chat/conversations/abc-123/messages/456?content=Updated message content
    ```
    
    **Parameters:**
    - conversation_id: Conversation ID (path parameter)
    - message_id: Message ID (path parameter)
    - content: New message content (required, min 1 character)
    """
    try:
        # Verify the conversation exists and belongs to the user
        conversation_stmt = select(Conversation).where(
            and_(
                Conversation.id == conversation_id,
                Conversation.user_id == current_user.id
            )
        )
        conversation_result = await db.execute(conversation_stmt)
        conversation = conversation_result.scalar_one_or_none()
        
        if not conversation:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Conversation not found"
            )
        
        # Get the message to update
        message_stmt = select(ChatMessage).where(
            and_(
                ChatMessage.id == message_id,
                ChatMessage.conversation_id == conversation_id
            )
        )
        message_result = await db.execute(message_stmt)
        message = message_result.scalar_one_or_none()
        
        if not message:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Message not found"
            )
        
        # Only allow editing user messages (not assistant responses)
        if message.role != "user":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Only user messages can be edited"
            )
        
        # Store original content if this is the first edit
        if not message.is_edited:
            message.original_content = message.content
        
        # Update the message
        old_content = message.content
        message.content = content
        message.is_edited = True
        message.edit_count += 1
        message.updated_at = datetime.utcnow()
        
        await db.commit()
        await db.refresh(message)
        
        logger.info(f"User {current_user.id} edited message {message_id} in conversation {conversation_id} (length: {len(old_content)} -> {len(content)})")
        
        return MessageResponse(
            id=message.id,
            role=message.role,
            content=message.content,
            original_content=message.original_content,
            is_edited=message.is_edited,
            edit_count=message.edit_count,
            like_status=message.like_status,
            conversation_id=message.conversation_id,
            created_at=message.created_at,
            updated_at=message.updated_at,
            meta=message.meta
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating message {message_id}: {str(e)}")
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update message"
        )


@router.post("/conversations/{conversation_id}/regenerate", response_model=ChatResponse)
async def regenerate_last_response(
    conversation_id: str,
    use_vector_search: Optional[bool] = Query(None, description="Whether to use vector search", example=True),
    max_chunks: Optional[int] = Query(None, ge=1, le=20, description="Maximum chunks to retrieve", example=5),
    current_user: UserResponse = Depends(get_current_active_user),
    chat_service: ChatService = Depends(get_chat_service),
    db: AsyncSession = Depends(get_database_session)
):
    """
    Regenerate the response to the most recent message in a conversation.
    
    This endpoint regenerates the last assistant response using the most recent user message,
    allowing users to get alternative responses to their queries.
    
    **Example usage:**
    ```
    POST /chat/conversations/abc-123/regenerate?use_vector_search=true&max_chunks=5
    ```
    
    **Parameters:**
    - conversation_id: Conversation ID (path parameter)
    - use_vector_search: Whether to use vector search (optional)
    - max_chunks: Maximum chunks to retrieve (optional, 1-20)
    """
    try:
        # Verify the conversation exists and belongs to the user
        conversation_stmt = select(Conversation).where(
            and_(
                Conversation.id == conversation_id,
                Conversation.user_id == current_user.id
            )
        )
        conversation_result = await db.execute(conversation_stmt)
        conversation = conversation_result.scalar_one_or_none()
        
        if not conversation:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Conversation not found"
            )
        
        # Get the last user message and last assistant message
        last_user_msg_stmt = select(ChatMessage).where(
            and_(
                ChatMessage.conversation_id == conversation_id,
                ChatMessage.role == "user"
            )
        ).order_by(ChatMessage.created_at.desc()).limit(1)
        
        last_user_result = await db.execute(last_user_msg_stmt)
        last_user_message = last_user_result.scalar_one_or_none()
        
        if not last_user_message:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No user message found to regenerate response for"
            )
        
        # Delete the last assistant message if it exists
        last_assistant_stmt = select(ChatMessage).where(
            and_(
                ChatMessage.conversation_id == conversation_id,
                ChatMessage.role == "assistant",
                ChatMessage.created_at > last_user_message.created_at
            )
        ).order_by(ChatMessage.created_at.desc()).limit(1)
        
        last_assistant_result = await db.execute(last_assistant_stmt)
        last_assistant_message = last_assistant_result.scalar_one_or_none()
        
        if last_assistant_message:
            await db.delete(last_assistant_message)
            conversation.message_count -= 1
        
        # Create a new chat request with the last user message
        chat_request = ChatRequest(
            message=last_user_message.content,
            conversation_id=conversation_id,
            use_vector_search=use_vector_search,
            max_chunks=max_chunks
        )
        
        # Process the chat request to generate a new response
        logger.info(f"Processing regenerate request for conversation {conversation_id}")
        response = await chat_service.process_chat_request(
            request=chat_request,
            user_id=current_user.id,
            db=db
        )
        
        logger.info(f"User {current_user.id} successfully regenerated response in conversation {conversation_id}")
        
        return response
        
    except HTTPException:
        raise
    except LLMServiceError as e:
        logger.error(f"LLM service error during regeneration: {str(e)}")
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"LLM service error: {str(e)}"
        )
    except Exception as e:
        logger.error(f"Unexpected error regenerating response in conversation {conversation_id}: {type(e).__name__}: {str(e)}")
        import traceback
        logger.error(f"Full traceback: {traceback.format_exc()}")
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to regenerate response: {str(e)}"
        )


@router.post("/conversations/{conversation_id}/messages/{message_id}/like", response_model=MessageResponse)
async def like_dislike_message(
    conversation_id: str,
    message_id: int,
    like_status: str = Query(..., pattern="^(liked|disliked|none)$", description="Like status: liked, disliked, or none", example="liked"),
    current_user: UserResponse = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_database_session)
):
    """
    Like, dislike, or remove like/dislike from a message.
    
    This endpoint allows users to express their preference for assistant responses
    by liking or disliking them.
    
    **Example usage:**
    ```
    POST /chat/conversations/abc-123/messages/456/like?like_status=liked
    ```
    
    **Parameters:**
    - conversation_id: Conversation ID (path parameter)
    - message_id: Message ID (path parameter)
    - like_status: Like status - 'liked', 'disliked', or 'none' (required)
    """
    try:
        # Verify the conversation exists and belongs to the user
        conversation_stmt = select(Conversation).where(
            and_(
                Conversation.id == conversation_id,
                Conversation.user_id == current_user.id
            )
        )
        conversation_result = await db.execute(conversation_stmt)
        conversation = conversation_result.scalar_one_or_none()
        
        if not conversation:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Conversation not found"
            )
        
        # Get the message to like/dislike
        message_stmt = select(ChatMessage).where(
            and_(
                ChatMessage.id == message_id,
                ChatMessage.conversation_id == conversation_id
            )
        )
        message_result = await db.execute(message_stmt)
        message = message_result.scalar_one_or_none()
        
        if not message:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Message not found"
            )
        
        # Only allow liking/disliking assistant messages
        if message.role != "assistant":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Only assistant messages can be liked or disliked"
            )
        
        # Update the like status
        if like_status == "none":
            message.like_status = None
        else:
            message.like_status = like_status
        
        message.updated_at = datetime.utcnow()
        
        await db.commit()
        await db.refresh(message)
        
        logger.info(f"User {current_user.id} {like_status} message {message_id} in conversation {conversation_id}")
        
        return MessageResponse(
            id=message.id,
            role=message.role,
            content=message.content,
            original_content=message.original_content,
            is_edited=message.is_edited,
            edit_count=message.edit_count,
            like_status=message.like_status,
            conversation_id=message.conversation_id,
            created_at=message.created_at,
            updated_at=message.updated_at,
            meta=message.meta
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating like status for message {message_id}: {str(e)}")
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update message like status"
        )


@router.get("/conversations/{conversation_id}/export")
async def export_conversation(
    conversation_id: str,
    format: str = Query(..., pattern="^(pdf|csv|txt)$", description="Export format: pdf, csv, or txt", example="csv"),
    include_metadata: bool = Query(default=True, description="Include message metadata", example=True),
    include_timestamps: bool = Query(default=True, description="Include timestamps", example=True),
    current_user: UserResponse = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_database_session)
):
    """
    Export conversation messages in PDF, CSV, or text format.
    
    This endpoint allows users to download their conversations in various formats
    for backup, analysis, or sharing purposes.
    
    **Example usage:**
    ```
    GET /chat/conversations/abc-123/export?format=csv&include_metadata=true&include_timestamps=true
    ```
    
    **Parameters:**
    - conversation_id: Conversation ID (path parameter)
    - format: Export format - 'pdf', 'csv', or 'txt' (required)
    - include_metadata: Include message metadata in export (default: true)
    - include_timestamps: Include timestamps in export (default: true)
    """
    try:
        # Verify the conversation exists and belongs to the user
        conversation_stmt = select(Conversation).where(
            and_(
                Conversation.id == conversation_id,
                Conversation.user_id == current_user.id
            )
        )
        conversation_result = await db.execute(conversation_stmt)
        conversation = conversation_result.scalar_one_or_none()
        
        if not conversation:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Conversation not found"
            )
        
        # Get all messages from the conversation
        messages_stmt = select(ChatMessage).where(
            ChatMessage.conversation_id == conversation_id
        ).order_by(ChatMessage.created_at.asc())
        
        messages_result = await db.execute(messages_stmt)
        messages = messages_result.scalars().all()
        
        if not messages:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No messages found in conversation"
            )
        
        # Create export request object for helper functions
        from types import SimpleNamespace
        export_params = SimpleNamespace(
            format=format,
            include_metadata=include_metadata,
            include_timestamps=include_timestamps
        )
        
        logger.info(f"Exporting conversation {conversation_id} as {format} for user {current_user.id}")
        
        # Generate the appropriate format
        if format == "csv":
            return await _export_as_csv(conversation, messages, export_params)
        elif format == "txt":
            return await _export_as_text(conversation, messages, export_params)
        elif format == "pdf":
            return await _export_as_pdf(conversation, messages, export_params)
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Unsupported export format"
            )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error exporting conversation {conversation_id}: {type(e).__name__}: {str(e)}")
        import traceback
        logger.error(f"Full traceback: {traceback.format_exc()}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to export conversation: {str(e)}"
        )


async def _export_as_csv(conversation, messages, export_request):
    """Export conversation as CSV file"""
    output = io.StringIO()
    writer = csv.writer(output)
    
    # Write header
    headers = ["Message ID", "Role", "Content"]
    if export_request.include_timestamps:
        headers.extend(["Created At", "Updated At"])
    if export_request.include_metadata:
        headers.extend(["Is Edited", "Edit Count", "Like Status", "Original Content"])
    
    writer.writerow(headers)
    
    # Write messages
    for message in messages:
        row = [message.id, message.role, message.content]
        
        if export_request.include_timestamps:
            row.extend([
                message.created_at.isoformat(),
                message.updated_at.isoformat() if message.updated_at else ""
            ])
        
        if export_request.include_metadata:
            row.extend([
                message.is_edited,
                message.edit_count,
                message.like_status or "",
                message.original_content or ""
            ])
        
        writer.writerow(row)
    
    output.seek(0)
    
    # Create filename
    filename = f"conversation_{conversation.id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    
    return Response(
        content=output.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )


async def _export_as_text(conversation, messages, export_request):
    """Export conversation as text file"""
    output = []
    
    # Add conversation header
    output.append(f"Conversation: {conversation.title or 'Untitled'}")
    output.append(f"Created: {conversation.created_at.isoformat()}")
    output.append(f"Last Updated: {conversation.updated_at.isoformat()}")
    output.append(f"Total Messages: {len(messages)}")
    output.append("=" * 50)
    output.append("")
    
    # Add messages
    for i, message in enumerate(messages, 1):
        output.append(f"Message {i}")
        output.append(f"Role: {message.role.upper()}")
        
        if export_request.include_timestamps:
            output.append(f"Time: {message.created_at.isoformat()}")
        
        if export_request.include_metadata and message.is_edited:
            output.append(f"Edited: Yes (edited {message.edit_count} times)")
            if message.original_content:
                output.append(f"Original: {message.original_content[:100]}...")
        
        if export_request.include_metadata and message.like_status:
            output.append(f"Rating: {message.like_status}")
        
        output.append(f"Content: {message.content}")
        output.append("-" * 30)
        output.append("")
    
    content = "\n".join(output)
    
    # Create filename
    filename = f"conversation_{conversation.id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
    
    return Response(
        content=content,
        media_type="text/plain",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )


async def _export_as_pdf(conversation, messages, export_request):
    """Export conversation as PDF file - simplified version"""
    try:
        from reportlab.lib.pagesizes import letter
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.units import inch
        from io import BytesIO
    except ImportError:
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail="PDF export requires reportlab package. Please install: pip install reportlab"
        )
    
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter)
    
    # Get styles
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=16,
        spaceAfter=20,
    )
    
    message_style = ParagraphStyle(
        'MessageStyle',
        parent=styles['Normal'],
        fontSize=10,
        leftIndent=20,
        spaceAfter=10,
    )
    
    role_style = ParagraphStyle(
        'RoleStyle',
        parent=styles['Normal'],
        fontSize=12,
        textColor='blue',
        spaceBefore=10,
        spaceAfter=5,
    )
    
    # Build story
    story = []
    
    # Add title
    story.append(Paragraph(f"Conversation: {conversation.title or 'Untitled'}", title_style))
    
    # Add conversation info
    story.append(Paragraph(f"Created: {conversation.created_at.isoformat()}", styles['Normal']))
    story.append(Paragraph(f"Total Messages: {len(messages)}", styles['Normal']))
    story.append(Spacer(1, 0.2*inch))
    
    # Add messages
    for i, message in enumerate(messages, 1):
        # Role header
        story.append(Paragraph(f"Message {i} - {message.role.upper()}", role_style))
        
        # Timestamp if requested
        if export_request.include_timestamps:
            story.append(Paragraph(f"Time: {message.created_at.isoformat()}", styles['Normal']))
        
        # Metadata if requested
        if export_request.include_metadata:
            if message.is_edited:
                story.append(Paragraph(f"Edited {message.edit_count} times", styles['Normal']))
            if message.like_status:
                story.append(Paragraph(f"Rating: {message.like_status}", styles['Normal']))
        
        # Message content
        # Escape HTML characters in content
        content = message.content.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
        story.append(Paragraph(content, message_style))
        story.append(Spacer(1, 0.1*inch))
    
    # Build PDF
    doc.build(story)
    
    # Create filename
    filename = f"conversation_{conversation.id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
    
    buffer.seek(0)
    
    return Response(
        content=buffer.getvalue(),
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )
