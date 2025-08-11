"""
Admin user management endpoints
These endpoints are restricted to users with admin role
Provides functionality to:
- Create new users
- Delete users
- Update user roles
- List all users
- Get user statistics
"""

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, or_
from datetime import datetime

from app.auth.dependencies import get_current_active_user
from app.dependencies import get_auth_service, get_database_session
from app.auth.auth_service import AuthService
from app.schema import UserResponse, UserCreate, UserUpdate
from app.db.database import get_database_session
from app.db.models import User, Document, Conversation
from app.enums import UserRole
from app.exceptions import DatabaseError, ValidationError, AuthenticationError
from app.logger import logger
from app.ingestion.file_uploader import FileUploader

router = APIRouter()


def require_admin_role(current_user: UserResponse = Depends(get_current_active_user)) -> UserResponse:
    """
    Dependency to ensure the current user has admin role.
    This is used to protect admin-only endpoints.
    """
    if current_user.role != UserRole.ADMIN.value:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied. Admin role required."
        )
    return current_user


@router.post("/users", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def create_user(
    user_data: UserCreate,
    current_admin: UserResponse = Depends(require_admin_role),
    db: AsyncSession = Depends(get_database_session),
    auth_service: AuthService = Depends(get_auth_service)
):
    """
    Create a new user account (Admin only).
    
    This endpoint allows administrators to create new user accounts directly,
    bypassing the normal registration process. This is useful for:
    - Creating accounts for users who can't self-register
    - Setting up service accounts
    - Pre-provisioning accounts for an organization
    """
    try:
        user = await auth_service.admin_create_user(user_data, current_admin, db)
        logger.info(f"New user registered: {user.username}")
        return UserResponse(
            id=user.id,
            email=user.email,
            username=user.username,
            full_name=user.full_name,
            role=user.role,
            is_active=user.is_active,
            created_at=user.created_at,
            updated_at=user.updated_at
        )
    except (ValidationError, AuthenticationError, DatabaseError) as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.delete("/users/{user_id}")
async def delete_user(
    user_id: int,
    cascade: bool = False,
    current_admin: UserResponse = Depends(require_admin_role),
    db: AsyncSession = Depends(get_database_session)
):
    """
    Delete a user account (Admin only).
    
    Parameters:
    - user_id: ID of the user to delete
    - cascade: If true, also delete all user's documents and conversations.
               If false, only delete if user has no associated data.
    
    This endpoint allows administrators to remove user accounts.
    It includes safety checks to prevent accidental data loss.
    """
    try:
        # Prevent admin from deleting themselves
        if user_id == current_admin.id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot delete your own admin account"
            )
        
        # Get the user to delete
        stmt = select(User).where(User.id == user_id)
        result = await db.execute(stmt)
        user_to_delete = result.scalar_one_or_none()
        
        if not user_to_delete:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        
        # Check if user has associated data
        doc_count_stmt = select(func.count(Document.id)).where(Document.user_id == user_id)
        doc_count_result = await db.execute(doc_count_stmt)
        document_count = doc_count_result.scalar()
        
        conv_count_stmt = select(func.count(Conversation.id)).where(Conversation.user_id == user_id)
        conv_count_result = await db.execute(conv_count_stmt)
        conversation_count = conv_count_result.scalar()
        
        if (document_count > 0 or conversation_count > 0) and not cascade:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"User has {document_count} documents and {conversation_count} conversations. "
                       f"Use cascade=true to delete all associated data."
            )
        
        # If cascade, clean up user's files from disk
        if cascade and document_count > 0:
            try:
                file_uploader = FileUploader()
                deleted_files = file_uploader.cleanup_user_files(user_id)
                logger.info(f"Cleaned up {deleted_files} files for user {user_id}")
            except Exception as e:
                logger.warning(f"Error cleaning up files for user {user_id}: {str(e)}")
        
        # Delete the user (cascading deletes will handle related data due to SQLAlchemy relationships)
        await db.delete(user_to_delete)
        await db.commit()
        
        logger.info(f"Admin {current_admin.username} deleted user {user_to_delete.username} (cascade={cascade})")
        
        return {
            "message": "User deleted successfully",
            "deleted_user": user_to_delete.username,
            "documents_deleted": document_count if cascade else 0,
            "conversations_deleted": conversation_count if cascade else 0
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting user {user_id}: {str(e)}")
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete user"
        )


@router.put("/users/{user_id}/role", response_model=UserResponse)
async def update_user_role(
    user_id: int,
    new_role: UserRole,
    current_admin: UserResponse = Depends(require_admin_role),
    db: AsyncSession = Depends(get_database_session)
):
    """
    Update a user's role (Admin only).
    
    This endpoint allows administrators to change user roles, such as:
    - Promoting a user to admin
    - Demoting an admin to regular user
    - Changing between different role types
    
    Safety checks prevent the last admin from being demoted.
    """
    try:
        # Get the user to update
        stmt = select(User).where(User.id == user_id)
        result = await db.execute(stmt)
        user_to_update = result.scalar_one_or_none()
        
        if not user_to_update:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        
        # Check if this would remove the last admin
        if user_to_update.role == UserRole.ADMIN.value and new_role != UserRole.ADMIN:
            admin_count_stmt = select(func.count(User.id)).where(
                and_(
                    User.role == UserRole.ADMIN.value,
                    User.is_active == True
                )
            )
            admin_count_result = await db.execute(admin_count_stmt)
            admin_count = admin_count_result.scalar()
            
            if admin_count <= 1:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Cannot demote the last active admin"
                )
        
        # Update the role
        old_role = user_to_update.role
        user_to_update.role = new_role.value
        user_to_update.updated_at = datetime.utcnow()
        
        await db.commit()
        await db.refresh(user_to_update)
        
        logger.info(f"Admin {current_admin.username} changed role for user {user_to_update.username} from {old_role} to {new_role.value}")
        
        return UserResponse.from_orm(user_to_update)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating user role: {str(e)}")
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update user role"
        )


@router.get("/users", response_model=List[UserResponse])
async def list_all_users(
    skip: int = 0,
    limit: int = 50,
    role_filter: Optional[UserRole] = None,
    active_only: bool = True,
    current_admin: UserResponse = Depends(require_admin_role),
    db: AsyncSession = Depends(get_database_session)
):
    """
    List all users in the system (Admin only).
    
    Parameters:
    - skip: Number of users to skip (for pagination)
    - limit: Maximum number of users to return
    - role_filter: Filter by specific role
    - active_only: If true, only return active users
    
    This endpoint provides administrators with a complete view of all user accounts.
    """
    try:
        query = select(User)
        
        # Apply filters
        if role_filter:
            query = query.where(User.role == role_filter.value)
        
        if active_only:
            query = query.where(User.is_active == True)
        
        # Apply pagination
        query = query.order_by(User.created_at.desc()).offset(skip).limit(limit)
        
        result = await db.execute(query)
        users = result.scalars().all()
        
        return [UserResponse.from_orm(user) for user in users]
        
    except Exception as e:
        logger.error(f"Error listing users: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve users"
        )


@router.get("/users/{user_id}", response_model=UserResponse)
async def get_user_details(
    user_id: int,
    current_admin: UserResponse = Depends(require_admin_role),
    db: AsyncSession = Depends(get_database_session)
):
    """
    Get detailed information about a specific user (Admin only).
    
    This endpoint allows administrators to view complete user information,
    including metadata that regular users cannot access.
    """
    try:
        stmt = select(User).where(User.id == user_id)
        result = await db.execute(stmt)
        user = result.scalar_one_or_none()
        
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        
        return UserResponse.from_orm(user)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting user details: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve user details"
        )


@router.get("/users/{user_id}/stats")
async def get_user_statistics(
    user_id: int,
    current_admin: UserResponse = Depends(require_admin_role),
    db: AsyncSession = Depends(get_database_session)
):
    """
    Get usage statistics for a specific user (Admin only).
    
    This endpoint provides detailed statistics about a user's resource usage,
    including document count, conversation count, storage usage, and activity metrics.
    """
    try:
        # Verify user exists
        user_stmt = select(User).where(User.id == user_id)
        user_result = await db.execute(user_stmt)
        user = user_result.scalar_one_or_none()
        
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        
        # Get document statistics
        doc_count_stmt = select(func.count(Document.id)).where(Document.user_id == user_id)
        doc_count_result = await db.execute(doc_count_stmt)
        document_count = doc_count_result.scalar() or 0
        
        # Get conversation statistics
        conv_count_stmt = select(func.count(Conversation.id)).where(Conversation.user_id == user_id)
        conv_count_result = await db.execute(conv_count_stmt)
        conversation_count = conv_count_result.scalar() or 0
        
        # Get total chunks count
        from app.db.models import DocumentChunk
        chunk_count_stmt = select(func.count(DocumentChunk.id)).join(
            Document, DocumentChunk.document_id == Document.id
        ).where(Document.user_id == user_id)
        chunk_count_result = await db.execute(chunk_count_stmt)
        total_chunks = chunk_count_result.scalar() or 0
        
        # Get message count
        from app.db.models import ChatMessage
        message_count_stmt = select(func.count(ChatMessage.id)).join(
            Conversation, ChatMessage.conversation_id == Conversation.id
        ).where(Conversation.user_id == user_id)
        message_count_result = await db.execute(message_count_stmt)
        message_count = message_count_result.scalar() or 0
        
        # Get storage usage
        file_uploader = FileUploader()
        storage_info = file_uploader.get_user_storage_usage(user_id)
        
        # Get last activity dates
        last_doc_stmt = select(Document.created_at).where(
            Document.user_id == user_id
        ).order_by(Document.created_at.desc()).limit(1)
        last_doc_result = await db.execute(last_doc_stmt)
        last_document_date = last_doc_result.scalar_one_or_none()
        
        last_conv_stmt = select(Conversation.updated_at).where(
            Conversation.user_id == user_id
        ).order_by(Conversation.updated_at.desc()).limit(1)
        last_conv_result = await db.execute(last_conv_stmt)
        last_conversation_date = last_conv_result.scalar_one_or_none()
        
        return {
            "user_id": user_id,
            "username": user.username,
            "email": user.email,
            "role": user.role,
            "is_active": user.is_active,
            "account_created": user.created_at.isoformat(),
            "statistics": {
                "documents": {
                    "total_count": document_count,
                    "total_chunks": total_chunks,
                    "last_upload": last_document_date.isoformat() if last_document_date else None
                },
                "conversations": {
                    "total_count": conversation_count,
                    "total_messages": message_count,
                    "last_activity": last_conversation_date.isoformat() if last_conversation_date else None
                },
                "storage": {
                    "total_size_bytes": storage_info.get("total_size", 0),
                    "total_size_mb": round(storage_info.get("total_size", 0) / (1024 * 1024), 2),
                    "file_count": storage_info.get("file_count", 0)
                }
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting user statistics: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve user statistics"
        )


@router.put("/users/{user_id}/status", response_model=UserResponse)
async def update_user_status(
    user_id: int,
    is_active: bool,
    current_admin: UserResponse = Depends(require_admin_role),
    db: AsyncSession = Depends(get_database_session)
):
    """
    Enable or disable a user account (Admin only).
    
    This endpoint allows administrators to:
    - Disable accounts for users who violate terms of service
    - Temporarily suspend accounts
    - Re-enable previously disabled accounts
    
    Disabled users cannot log in but their data is preserved.
    """
    try:
        # Prevent admin from disabling themselves
        if user_id == current_admin.id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot disable your own admin account"
            )
        
        # Get the user to update
        stmt = select(User).where(User.id == user_id)
        result = await db.execute(stmt)
        user_to_update = result.scalar_one_or_none()
        
        if not user_to_update:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        
        # Check if this would disable the last admin
        if user_to_update.role == UserRole.ADMIN.value and not is_active:
            admin_count_stmt = select(func.count(User.id)).where(
                and_(
                    User.role == UserRole.ADMIN.value,
                    User.is_active == True,
                    User.id != user_id
                )
            )
            admin_count_result = await db.execute(admin_count_stmt)
            other_admin_count = admin_count_result.scalar()
            
            if other_admin_count == 0:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Cannot disable the last active admin"
                )
        
        # Update the status
        user_to_update.is_active = is_active
        user_to_update.updated_at = datetime.utcnow()
        
        await db.commit()
        await db.refresh(user_to_update)
        
        action = "enabled" if is_active else "disabled"
        logger.info(f"Admin {current_admin.username} {action} user {user_to_update.username}")
        
        return UserResponse.from_orm(user_to_update)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating user status: {str(e)}")
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update user status"
        )


@router.get("/stats/overview")
async def get_system_overview(
    current_admin: UserResponse = Depends(require_admin_role),
    db: AsyncSession = Depends(get_database_session)
):
    """
    Get system-wide statistics overview (Admin only).
    
    This endpoint provides administrators with a high-level view of system usage,
    including total users, documents, conversations, and storage usage.
    """
    try:
        # User statistics
        total_users_stmt = select(func.count(User.id))
        total_users_result = await db.execute(total_users_stmt)
        total_users = total_users_result.scalar() or 0
        
        active_users_stmt = select(func.count(User.id)).where(User.is_active == True)
        active_users_result = await db.execute(active_users_stmt)
        active_users = active_users_result.scalar() or 0
        
        admin_count_stmt = select(func.count(User.id)).where(User.role == UserRole.ADMIN.value)
        admin_count_result = await db.execute(admin_count_stmt)
        admin_count = admin_count_result.scalar() or 0
        
        # Document statistics
        total_docs_stmt = select(func.count(Document.id))
        total_docs_result = await db.execute(total_docs_stmt)
        total_documents = total_docs_result.scalar() or 0
        
        from app.db.models import DocumentChunk
        total_chunks_stmt = select(func.count(DocumentChunk.id))
        total_chunks_result = await db.execute(total_chunks_stmt)
        total_chunks = total_chunks_result.scalar() or 0
        
        # Conversation statistics
        total_convs_stmt = select(func.count(Conversation.id))
        total_convs_result = await db.execute(total_convs_stmt)
        total_conversations = total_convs_result.scalar() or 0
        
        from app.db.models import ChatMessage
        total_msgs_stmt = select(func.count(ChatMessage.id))
        total_msgs_result = await db.execute(total_msgs_stmt)
        total_messages = total_msgs_result.scalar() or 0
        
        return {
            "users": {
                "total": total_users,
                "active": active_users,
                "inactive": total_users - active_users,
                "admins": admin_count,
            },
            "documents": {
                "total": total_documents,
                "total_chunks": total_chunks,
                "average_chunks_per_doc": round(total_chunks / total_documents, 2) if total_documents > 0 else 0
            },
            "conversations": {
                "total": total_conversations,
                "total_messages": total_messages,
                "average_messages_per_conversation": round(total_messages / total_conversations, 2) if total_conversations > 0 else 0
            },
            "system_info": {
                "timestamp": datetime.utcnow().isoformat(),
                "admin_user": current_admin.username
            }
        }
        
    except Exception as e:
        logger.error(f"Error getting system overview: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve system statistics"
        )
