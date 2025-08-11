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

from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status, Query
from pydantic import Field
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, or_
from datetime import datetime
import json

from app.auth.dependencies import get_current_active_user
from app.dependencies import get_auth_service, get_database_session
from app.auth.auth_service import AuthService
from app.schema import UserResponse, UserCreate, UserUpdate, RoleCreate, RoleResponse, DocumentPermissionCreate, DocumentPermissionResponse
from app.db.database import get_database_session
from app.db.models import User, Document, Conversation, Role, DocumentPermission
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


@router.post("/roles", response_model=RoleResponse, status_code=status.HTTP_201_CREATED)
async def create_role(
    name: str = Query(..., min_length=3, max_length=100, description="Role name", example="content_editor"),
    description: Optional[str] = Query(None, description="Role description", example="Users who can edit content"),
    permissions: Optional[str] = Query(None, description="Role permissions as JSON string", example='{"documents": {"create": true, "edit": true}}'),
    current_admin: UserResponse = Depends(require_admin_role),
    db: AsyncSession = Depends(get_database_session)
):
    """
    Create a new role (Admin only).
    
    This endpoint allows administrators to create custom roles with specific permissions.
    Roles can be assigned to users and used to control access to documents and features.
    
    **Example usage:**
    ```
    POST /admin/roles?name=content_editor&description=Users who can edit content&permissions={"documents":{"create":true,"edit":true}}
    ```
    
    **Parameters:**
    - name: Role name (required, 3-100 characters)
    - description: Role description (optional)  
    - permissions: Role permissions as JSON string (optional)
    """
    try:
        # Parse permissions JSON string if provided
        permissions_dict = {}
        if permissions:
            try:
                permissions_dict = json.loads(permissions)
            except json.JSONDecodeError:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Invalid JSON format for permissions parameter"
                )
        
        # Check if role with same name already exists
        existing_role_stmt = select(Role).where(Role.name == name)
        existing_role_result = await db.execute(existing_role_stmt)
        existing_role = existing_role_result.scalar_one_or_none()
        
        if existing_role:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Role with name '{name}' already exists"
            )
        
        # Create new role
        new_role = Role(
            name=name,
            description=description,
            permissions=permissions_dict,
            created_by=current_admin.id
        )
        
        db.add(new_role)
        await db.commit()
        await db.refresh(new_role)
        
        logger.info(f"Admin {current_admin.username} created new role: {name}")
        
        return RoleResponse(
            id=new_role.id,
            name=new_role.name,
            description=new_role.description,
            permissions=new_role.permissions,
            created_by=new_role.created_by,
            created_at=new_role.created_at,
            updated_at=new_role.updated_at
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating role: {str(e)}")
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create role"
        )


@router.get("/roles", response_model=List[RoleResponse])
async def list_roles(
    skip: int = Query(default=0, ge=0, description="Number of roles to skip for pagination", example=0),
    limit: int = Query(default=50, ge=1, le=100, description="Maximum number of roles to return", example=10),
    name_filter: Optional[str] = Query(None, description="Filter roles by name (partial match)", example="editor"),
    current_admin: UserResponse = Depends(require_admin_role),
    db: AsyncSession = Depends(get_database_session)
):
    """
    List all custom roles (Admin only).
    
    This endpoint allows administrators to view all custom roles in the system.
    
    **Example usage:**
    ```
    GET /admin/roles?skip=0&limit=10&name_filter=editor
    ```
    
    **Parameters:**
    - skip: Number of roles to skip for pagination (default: 0)
    - limit: Maximum number of roles to return (default: 50, max: 100)  
    - name_filter: Filter roles by name (partial match, optional)
    """
    try:
        query = select(Role)
        
        # Apply name filter if provided
        if name_filter:
            query = query.where(Role.name.ilike(f"%{name_filter}%"))
        
        # Apply ordering and pagination
        query = query.order_by(Role.created_at.desc()).offset(skip).limit(limit)
        result = await db.execute(query)
        roles = result.scalars().all()
        
        return [RoleResponse(
            id=role.id,
            name=role.name,
            description=role.description,
            permissions=role.permissions,
            created_by=role.created_by,
            created_at=role.created_at,
            updated_at=role.updated_at
        ) for role in roles]
        
    except Exception as e:
        logger.error(f"Error listing roles: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve roles"
        )


@router.post("/documents/{document_id}/permissions", response_model=DocumentPermissionResponse, status_code=status.HTTP_201_CREATED)
async def create_document_permission(
    document_id: int,
    user_id: Optional[int] = Query(None, description="User ID (either user_id or role_id required)", example=123),
    role_id: Optional[int] = Query(None, description="Role ID (either user_id or role_id required)", example=456),
    can_read: bool = Query(default=True, description="Read permission", example=True),
    can_write: bool = Query(default=False, description="Write permission", example=False),
    can_delete: bool = Query(default=False, description="Delete permission", example=False),
    can_share: bool = Query(default=False, description="Share permission", example=True),
    expires_at: Optional[str] = Query(None, description="Permission expiration (ISO format)", example="2024-12-31T23:59:59"),
    current_admin: UserResponse = Depends(require_admin_role),
    db: AsyncSession = Depends(get_database_session)
):
    """
    Grant document access permissions to users or roles (Admin only).
    
    This endpoint allows administrators to control who has access to specific documents.
    Permissions can be granted to individual users or to roles.
    
    **Example usage:**
    ```
    POST /admin/documents/123/permissions?user_id=456&can_read=true&can_write=true&expires_at=2024-12-31T23:59:59
    ```
    
    **Parameters:**
    - document_id: Document ID (path parameter)
    - user_id: User ID (optional, either user_id or role_id required)
    - role_id: Role ID (optional, either user_id or role_id required)  
    - can_read: Read permission (default: true)
    - can_write: Write permission (default: false)
    - can_delete: Delete permission (default: false)
    - can_share: Share permission (default: false)
    - expires_at: Permission expiration in ISO format (optional)
    """
    try:
        # Parse expires_at if provided
        expires_at_dt = None
        if expires_at:
            try:
                from datetime import datetime
                expires_at_dt = datetime.fromisoformat(expires_at.replace('Z', '+00:00'))
            except ValueError:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Invalid date format for expires_at. Use ISO format: YYYY-MM-DDTHH:MM:SS"
                )
        
        # Verify the document exists and belongs to the admin
        document_stmt = select(Document).where(Document.id == document_id)
        document_result = await db.execute(document_stmt)
        document = document_result.scalar_one_or_none()
        
        if not document:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Document not found"
            )
        
        # Check that admin owns the document (only document owners can grant permissions)
        if document.user_id != current_admin.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You can only grant permissions for documents you own"
            )
        
        # Validate that either user_id or role_id is provided, but not both
        if not user_id and not role_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Either user_id or role_id must be provided"
            )
        
        if user_id and role_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot specify both user_id and role_id"
            )
        
        # If user_id provided, verify the user exists
        if user_id:
            user_stmt = select(User).where(User.id == user_id)
            user_result = await db.execute(user_stmt)
            user = user_result.scalar_one_or_none()
            if not user:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="User not found"
                )
        
        # If role_id provided, verify the role exists
        if role_id:
            role_stmt = select(Role).where(Role.id == role_id)
            role_result = await db.execute(role_stmt)
            role = role_result.scalar_one_or_none()
            if not role:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Role not found"
                )
        
        # Check if permission already exists
        existing_permission_stmt = select(DocumentPermission).where(
            and_(
                DocumentPermission.document_id == document_id,
                or_(
                    DocumentPermission.user_id == user_id,
                    DocumentPermission.role_id == role_id
                )
            )
        )
        existing_permission_result = await db.execute(existing_permission_stmt)
        existing_permission = existing_permission_result.scalar_one_or_none()
        
        if existing_permission:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Permission already exists for this user/role and document"
            )
        
        # Create new permission
        new_permission = DocumentPermission(
            document_id=document_id,
            user_id=user_id,
            role_id=role_id,
            can_read=can_read,
            can_write=can_write,
            can_delete=can_delete,
            can_share=can_share,
            granted_by=current_admin.id,
            expires_at=expires_at_dt
        )
        
        db.add(new_permission)
        await db.commit()
        await db.refresh(new_permission)
        
        target = f"user {user_id}" if user_id else f"role {role_id}"
        logger.info(f"Admin {current_admin.username} granted document permissions to {target} for document {document_id}")
        
        return DocumentPermissionResponse(
            id=new_permission.id,
            document_id=new_permission.document_id,
            user_id=new_permission.user_id,
            role_id=new_permission.role_id,
            can_read=new_permission.can_read,
            can_write=new_permission.can_write,
            can_delete=new_permission.can_delete,
            can_share=new_permission.can_share,
            granted_by=new_permission.granted_by,
            expires_at=new_permission.expires_at,
            created_at=new_permission.created_at,
            updated_at=new_permission.updated_at
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating document permission: {str(e)}")
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create document permission"
        )


@router.get("/documents/{document_id}/permissions", response_model=List[DocumentPermissionResponse])
async def list_document_permissions(
    document_id: int,
    user_id_filter: Optional[int] = Query(None, description="Filter permissions by user ID", example=123),
    role_id_filter: Optional[int] = Query(None, description="Filter permissions by role ID", example=456),
    active_only: bool = Query(default=True, description="Show only non-expired permissions", example=True),
    current_admin: UserResponse = Depends(require_admin_role),
    db: AsyncSession = Depends(get_database_session)
):
    """
    List all permissions for a specific document (Admin only).
    
    This endpoint allows administrators to view who has access to a specific document.
    
    **Example usage:**
    ```
    GET /admin/documents/123/permissions?user_id_filter=456&active_only=true
    ```
    
    **Parameters:**
    - document_id: Document ID (path parameter)
    - user_id_filter: Filter permissions by user ID (optional)
    - role_id_filter: Filter permissions by role ID (optional)
    - active_only: Show only non-expired permissions (default: true)
    """
    try:
        # Verify the document exists
        document_stmt = select(Document).where(Document.id == document_id)
        document_result = await db.execute(document_stmt)
        document = document_result.scalar_one_or_none()
        
        if not document:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Document not found"
            )
        
        # Get permissions for this document with filters
        permissions_stmt = select(DocumentPermission).where(DocumentPermission.document_id == document_id)
        
        # Apply filters
        if user_id_filter:
            permissions_stmt = permissions_stmt.where(DocumentPermission.user_id == user_id_filter)
        
        if role_id_filter:
            permissions_stmt = permissions_stmt.where(DocumentPermission.role_id == role_id_filter)
        
        if active_only:
            from datetime import datetime
            permissions_stmt = permissions_stmt.where(
                or_(
                    DocumentPermission.expires_at.is_(None),
                    DocumentPermission.expires_at > datetime.utcnow()
                )
            )
        
        permissions_result = await db.execute(permissions_stmt)
        permissions = permissions_result.scalars().all()
        
        return [DocumentPermissionResponse(
            id=permission.id,
            document_id=permission.document_id,
            user_id=permission.user_id,
            role_id=permission.role_id,
            can_read=permission.can_read,
            can_write=permission.can_write,
            can_delete=permission.can_delete,
            can_share=permission.can_share,
            granted_by=permission.granted_by,
            expires_at=permission.expires_at,
            created_at=permission.created_at,
            updated_at=permission.updated_at
        ) for permission in permissions]
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error listing document permissions: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve document permissions"
        )


@router.delete("/documents/{document_id}/permissions/{permission_id}")
async def revoke_document_permission(
    document_id: int,
    permission_id: int,
    reason: Optional[str] = Query(None, description="Reason for revoking permission", example="User no longer needs access"),
    current_admin: UserResponse = Depends(require_admin_role),
    db: AsyncSession = Depends(get_database_session)
):
    """
    Revoke document permission (Admin only).
    
    This endpoint allows administrators to revoke previously granted document permissions.
    
    **Example usage:**
    ```
    DELETE /admin/documents/123/permissions/456?reason=User no longer needs access
    ```
    
    **Parameters:**
    - document_id: Document ID (path parameter)
    - permission_id: Permission ID to revoke (path parameter)
    - reason: Optional reason for revoking permission (query parameter)
    """
    try:
        # Get the permission to revoke
        permission_stmt = select(DocumentPermission).where(
            and_(
                DocumentPermission.id == permission_id,
                DocumentPermission.document_id == document_id
            )
        )
        permission_result = await db.execute(permission_stmt)
        permission = permission_result.scalar_one_or_none()
        
        if not permission:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Permission not found"
            )
        
        # Verify the document belongs to the admin
        document_stmt = select(Document).where(Document.id == document_id)
        document_result = await db.execute(document_stmt)
        document = document_result.scalar_one_or_none()
        
        if not document or document.user_id != current_admin.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You can only revoke permissions for documents you own"
            )
        
        # Delete the permission
        await db.delete(permission)
        await db.commit()
        
        target = f"user {permission.user_id}" if permission.user_id else f"role {permission.role_id}"
        reason_msg = f" Reason: {reason}" if reason else ""
        logger.info(f"Admin {current_admin.username} revoked document permission from {target} for document {document_id}.{reason_msg}")
        
        return {
            "message": "Document permission revoked successfully",
            "permission_id": permission_id,
            "target": target,
            "reason": reason
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error revoking document permission: {str(e)}")
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to revoke document permission"
        )
