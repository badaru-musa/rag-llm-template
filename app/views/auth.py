from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.auth.auth_service import AuthService
from app.auth.dependencies import get_current_user, get_current_active_user, security
from app.schema import UserCreate, UserResponse, Token, UserUpdate
from app.dependencies import get_auth_service, get_database_session
from app.exceptions import AuthenticationError, ValidationError, DatabaseError
from app.db.models import User
from app.logger import logger

router = APIRouter()


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register_user(
    user_data: UserCreate,
    auth_service: AuthService = Depends(get_auth_service),
    db: AsyncSession = Depends(get_database_session)
):
    """Register a new user"""
    try:
        user = await auth_service.create_user(user_data, db)
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


@router.post("/login", response_model=Token)
async def login_user(
    form_data: OAuth2PasswordRequestForm = Depends(),
    auth_service: AuthService = Depends(get_auth_service),
    db: AsyncSession = Depends(get_database_session)
):
    """Login user and return access token"""
    try:
        token = await auth_service.login_user(form_data.username, form_data.password, db)
        return token
    except AuthenticationError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e),
            headers={"WWW-Authenticate": "Bearer"},
        )


@router.post("/logout")
async def logout_user(
    current_user: UserResponse = Depends(get_current_active_user),
    auth_service: AuthService = Depends(get_auth_service),
    db: AsyncSession = Depends(get_database_session),
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """Logout current user"""
    token = credentials.credentials
    await auth_service.logout(token, db)
    return {"message": "Successfully logged out"}


@router.get("/me", response_model=UserResponse)
async def get_current_user_info(
    current_user: UserResponse = Depends(get_current_active_user)
):
    """Get current user information"""
    return current_user


@router.put("/me", response_model=UserResponse)
async def update_current_user(
    user_update: UserUpdate,
    current_user: UserResponse = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_database_session)
):
    """Update current user information"""
    try:
        stmt = select(User).where(User.id == current_user.id)
        result = await db.execute(stmt)
        user = result.scalar_one_or_none()
        
        if user:
            if user_update.full_name is not None:
                user.full_name = user_update.full_name
            if user_update.role is not None:
                user.role = user_update.role.value if hasattr(user_update.role, 'value') else user_update.role
            if user_update.is_active is not None:
                user.is_active = user_update.is_active
            
            await db.commit()
            await db.refresh(user)
            
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
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update user: {str(e)}"
        )


@router.post("/change-password")
async def change_password(
    current_password: str,
    new_password: str,
    current_user: UserResponse = Depends(get_current_active_user),
    auth_service: AuthService = Depends(get_auth_service),
    db: AsyncSession = Depends(get_database_session)
):
    """Change user password"""
    try:
        success = await auth_service.change_password(
            user_id=current_user.id,
            current_password=current_password,
            new_password=new_password,
            db=db
        )
        
        if success:
            return {"message": "Password changed successfully"}
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Failed to change password"
            )
    except AuthenticationError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.post("/verify-token")
async def verify_token(
    current_user: UserResponse = Depends(get_current_user)
):
    """Verify if the provided token is valid"""
    return {
        "valid": True,
        "user_id": current_user.id,
        "username": current_user.username
    }


@router.get("/users/{user_id}", response_model=UserResponse)
async def get_user_by_id(
    user_id: int,
    current_user: UserResponse = Depends(get_current_active_user),
    auth_service: AuthService = Depends(get_auth_service),
    db: AsyncSession = Depends(get_database_session)
):
    """Get user by ID (admin only or own profile)"""
    try:
        await auth_service.require_permission(
            current_user,
            required_role=current_user.role,
            resource_owner_id=user_id
        )
        
        user = await auth_service.get_user(user_id, db)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        
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
    except Exception as e:
        if "Access denied" in str(e):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=str(e)
            )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error retrieving user"
        )
