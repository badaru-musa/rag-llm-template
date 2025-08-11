from typing import List, Dict, Any, Optional, AsyncGenerator
import uuid
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_

from app.generation.llm_factory import BaseLLMService
from app.retrieval.retriever import DocumentRetriever
from app.schema import ChatRequest, ChatResponse, ChatMessage, DocumentChunk
from app.db.models import Conversation, ChatMessage as ChatMessageModel
from app.enums import ChatRole
from app.exceptions import LLMServiceError, DatabaseError
from app.prompts.system_prompts import get_rag_system_prompt, get_no_context_system_prompt
from app.logger import logger

 
class ChatService:
    """Service for handling chat interactions with RAG capabilities"""
    
    def __init__(
        self,
        llm_service: BaseLLMService,
        document_retriever: DocumentRetriever,
        use_vector_search: bool = True
    ):
        self.llm_service = llm_service
        self.document_retriever = document_retriever
        self.use_vector_search = use_vector_search
    
    async def process_chat_request(
        self,
        request: ChatRequest,
        user_id: int,
        db: AsyncSession
    ) -> ChatResponse:
        """Process a chat request and return response"""
        
        try:
            # Get or create conversation
            conversation_id = request.conversation_id or str(uuid.uuid4())
            conversation = await self._get_or_create_conversation(conversation_id, user_id, db)
            
            # Get conversation history
            chat_history = await self._get_conversation_history(conversation_id, db)
            
            # Determine if vector search should be used
            use_vector_search = request.use_vector_search
            if use_vector_search is None:
                use_vector_search = self.use_vector_search
            
            # Retrieve relevant context if enabled
            relevant_chunks = []
            if use_vector_search:
                # Ensure vector store is initialized
                if not self.document_retriever.vector_store.collection:
                    await self.document_retriever.vector_store.initialize()
                    logger.info("Initialized vector store for search")
                
                relevant_chunks = await self.document_retriever.retrieve_relevant_chunks(
                    query=request.message,
                    user_id=user_id,
                    max_chunks=request.max_chunks,
                    similarity_threshold=0.3  # Lower threshold for better recall
                )
                logger.info(f"Retrieved {len(relevant_chunks)} chunks for query: {request.message[:50]}...")
            
            # Build messages for LLM
            messages = await self._build_llm_messages(
                user_message=request.message,
                chat_history=chat_history,
                relevant_chunks=relevant_chunks,
                use_vector_search=use_vector_search
            )
            
            # Generate response from LLM
            response_content = await self.llm_service.generate_response(messages)
            
            # Save user message and assistant response
            await self._save_chat_messages(
                conversation_id=conversation_id,
                user_message=request.message,
                assistant_response=response_content,
                db=db
            )
            
            # Create response
            response = ChatResponse(
                message=response_content,
                conversation_id=conversation_id,
                sources=relevant_chunks,
                meta={
                    "use_vector_search": use_vector_search,
                    "chunks_retrieved": len(relevant_chunks),
                    "model_used": self.llm_service.__class__.__name__
                }
            )
            
            logger.info(f"Processed chat request for user {user_id}, conversation {conversation_id}")
            return response
            
        except Exception as e:
            logger.error(f"Error processing chat request: {str(e)}")
            raise LLMServiceError(f"Failed to process chat request: {str(e)}")
    
    async def process_streaming_chat_request(
        self,
        request: ChatRequest,
        user_id: int,
        db: AsyncSession
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """Process a chat request with streaming response"""
        
        try:
            # Get or create conversation
            conversation_id = request.conversation_id or str(uuid.uuid4())
            conversation = await self._get_or_create_conversation(conversation_id, user_id, db)
            
            # Get conversation history
            chat_history = await self._get_conversation_history(conversation_id, db)
            
            # Determine if vector search should be used
            use_vector_search = request.use_vector_search
            if use_vector_search is None:
                use_vector_search = self.use_vector_search
            
            # Retrieve relevant context if enabled
            relevant_chunks = []
            if use_vector_search:
                # Ensure vector store is initialized
                if not self.document_retriever.vector_store.collection:
                    await self.document_retriever.vector_store.initialize()
                    logger.info("Initialized vector store for streaming search")
                
                relevant_chunks = await self.document_retriever.retrieve_relevant_chunks(
                    query=request.message,
                    user_id=user_id,
                    max_chunks=request.max_chunks,
                    similarity_threshold=0.3  # Lower threshold for better recall
                )
                logger.info(f"Retrieved {len(relevant_chunks)} chunks for streaming query")
            
            # Build messages for LLM
            messages = await self._build_llm_messages(
                user_message=request.message,
                chat_history=chat_history,
                relevant_chunks=relevant_chunks,
                use_vector_search=use_vector_search
            )
            
            # Yield initial metadata
            yield {
                "type": "metadata",
                "conversation_id": conversation_id,
                "sources": [chunk.dict() for chunk in relevant_chunks],
                "metadata": {
                    "use_vector_search": use_vector_search,
                    "chunks_retrieved": len(relevant_chunks),
                    "model_used": self.llm_service.__class__.__name__
                }
            }
            
            # Stream response from LLM
            response_parts = []
            async for chunk in self.llm_service.generate_streaming_response(messages):
                response_parts.append(chunk)
                yield {
                    "type": "content",
                    "content": chunk
                }
            
            # Combine full response
            full_response = "".join(response_parts)
            
            # Save messages
            await self._save_chat_messages(
                conversation_id=conversation_id,
                user_message=request.message,
                assistant_response=full_response,
                db=db
            )
            
            # Yield completion
            yield {
                "type": "complete",
                "conversation_id": conversation_id
            }
            
        except Exception as e:
            logger.error(f"Error processing streaming chat request: {str(e)}")
            yield {
                "type": "error",
                "error": str(e)
            }
    
    async def _get_or_create_conversation(
        self,
        conversation_id: str,
        user_id: int,
        db: AsyncSession
    ) -> Conversation:
        """Get existing conversation or create new one"""
        
        if not db:
            return None
        
        try:
            # Try to get existing conversation
            stmt = select(Conversation).where(
                and_(
                    Conversation.id == conversation_id,
                    Conversation.user_id == user_id
                )
            )
            result = await db.execute(stmt)
            conversation = result.scalar_one_or_none()
            
            if not conversation:
                # Create new conversation
                conversation = Conversation(
                    id=conversation_id,
                    user_id=user_id,
                    title=None,  # Will be set later if needed
                    meta={}
                )
                db.add(conversation)
                await db.commit()
                await db.refresh(conversation)
                
                logger.info(f"Created new conversation {conversation_id} for user {user_id}")
            
            return conversation
            
        except Exception as e:
            logger.error(f"Error getting/creating conversation: {str(e)}")
            raise DatabaseError(f"Failed to manage conversation: {str(e)}")
    
    async def _get_conversation_history(
        self,
        conversation_id: str,
        db: AsyncSession,
        limit: int = 10
    ) -> List[ChatMessage]:
        """Get recent conversation history"""
        
        if not db:
            return []
        
        try:
            stmt = (
                select(ChatMessageModel)
                .where(ChatMessageModel.conversation_id == conversation_id)
                .order_by(ChatMessageModel.created_at.desc())
                .limit(limit)
            )
            result = await db.execute(stmt)
            messages = result.scalars().all()
            
            # Convert to ChatMessage objects and reverse order (oldest first)
            chat_history = []
            for msg in reversed(messages):
                chat_history.append(
                    ChatMessage(
                        role=ChatRole(msg.role),
                        content=msg.content,
                        timestamp=msg.created_at
                    )
                )
            
            return chat_history
            
        except Exception as e:
            logger.error(f"Error getting conversation history: {str(e)}")
            return []
    
    async def _build_llm_messages(
        self,
        user_message: str,
        chat_history: List[ChatMessage],
        relevant_chunks: List[DocumentChunk],
        use_vector_search: bool
    ) -> List[Dict[str, str]]:
        """Build messages array for LLM"""
        
        messages = []
        
        # Add system prompt
        if use_vector_search and relevant_chunks:
            context = self.document_retriever.format_chunks_for_context(relevant_chunks)
            system_prompt = get_rag_system_prompt(context)
        else:
            system_prompt = get_no_context_system_prompt()
        
        messages.append({
            "role": "system",
            "content": system_prompt
        })
        
        # Add conversation history
        for msg in chat_history:
            # Handle both enum and string types
            role_value = msg.role.value if hasattr(msg.role, 'value') else str(msg.role)
            messages.append({
                "role": role_value,
                "content": msg.content
            })
        
        # Add current user message
        messages.append({
            "role": "user",
            "content": user_message
        })
        
        return messages
    
    async def _save_chat_messages(
        self,
        conversation_id: str,
        user_message: str,
        assistant_response: str,
        db: AsyncSession
    ):
        """Save chat messages to database"""
        
        if not db:
            return
        
        try:
            # Save user message
            user_msg = ChatMessageModel(
                conversation_id=conversation_id,
                role=ChatRole.USER.value,
                content=user_message,
                meta={}
            )
            db.add(user_msg)
            
            # Save assistant response
            assistant_msg = ChatMessageModel(
                conversation_id=conversation_id,
                role=ChatRole.ASSISTANT.value,
                content=assistant_response,
                meta={}
            )
            db.add(assistant_msg)
            
            # Update conversation message count
            stmt = select(Conversation).where(Conversation.id == conversation_id)
            result = await db.execute(stmt)
            conversation = result.scalar_one_or_none()
            
            if conversation:
                conversation.message_count += 2
                conversation.updated_at = datetime.utcnow()
            
            await db.commit()
            
        except Exception as e:
            logger.error(f"Error saving chat messages: {str(e)}")
            await db.rollback()
            raise DatabaseError(f"Failed to save chat messages: {str(e)}")
    
    async def get_conversation_list(
        self,
        user_id: int,
        db: AsyncSession,
        limit: int = 20,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        """Get list of conversations for a user"""
        
        if not db:
            return []
        
        try:
            stmt = (
                select(Conversation)
                .where(Conversation.user_id == user_id)
                .order_by(Conversation.updated_at.desc())
                .limit(limit)
                .offset(offset)
            )
            result = await db.execute(stmt)
            conversations = result.scalars().all()
            
            conversation_list = []
            for conv in conversations:
                conversation_list.append({
                    "id": conv.id,
                    "title": conv.title or "New Conversation",
                    "message_count": conv.message_count,
                    "created_at": conv.created_at.isoformat(),
                    "updated_at": conv.updated_at.isoformat(),
                    "meta": conv.meta
                })
            
            return conversation_list
            
        except Exception as e:
            logger.error(f"Error getting conversation list: {str(e)}")
            return []
    
    async def delete_conversation(
        self,
        conversation_id: str,
        user_id: int,
        db: AsyncSession
    ) -> bool:
        """Delete a conversation and all its messages"""
        
        if not db:
            return False
        
        try:
            # Get conversation
            stmt = select(Conversation).where(
                and_(
                    Conversation.id == conversation_id,
                    Conversation.user_id == user_id
                )
            )
            result = await db.execute(stmt)
            conversation = result.scalar_one_or_none()
            
            if conversation:
                await db.delete(conversation)
                await db.commit()
                logger.info(f"Deleted conversation {conversation_id}")
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"Error deleting conversation: {str(e)}")
            await db.rollback()
            return False
