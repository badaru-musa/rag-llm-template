"""Authentication service for JWT token management and user authentication"""

from typing import Optional, Dict, Any
from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from passlib.context import CryptContext
from jose import JWTError, jwt
from fastapi import HTTPException, status

from app.db.models import User, UserSession
from app.schema import UserCreate, UserResponse, Token
from app.exceptions import AuthenticationError, AuthorizationError
from app.logger import logger


class AuthService:
    """Authentication service for managing users and JWT tokens"""
    
    def __init__(
        self,
        secret_key: str,
        algorithm: str = "HS256",
        access_token_expire_minutes: int = 30
    ):
        self.secret_key = secret_key
        self.algorithm = algorithm
        self.access_token_expire_minutes = access_token_expire_minutes
        self.pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
    
    def verify_password(self, plain_password: str, hashed_password: str) -> bool:
        """Verify a plain password against its hash"""
        return self.pwd_context.verify(plain_password, hashed_password)
    
    def get_password_hash(self, password: str) -> str:
        """Generate password hash"""
        return self.pwd_context.hash(password)
    
    def create_access_token(self, data: Dict[str, Any]) -> str:
        """Create JWT access token"""
        to_encode = data.copy()
        expire = datetime.utcnow() + timedelta(minutes=self.access_token_expire_minutes)
        to_encode.update({"exp": expire})
        
        encoded_jwt = jwt.encode(to_encode, self.secret_key, algorithm=self.algorithm)
        return encoded_jwt
    
    def verify_token(self, token: str) -> Optional[Dict[str, Any]]:
        """Verify and decode JWT token"""
        try:
            payload = jwt.decode(token, self.secret_key, algorithms=[self.algorithm])
            return payload
        except JWTError:
            return None
    
    async def authenticate_user(self, username: str, password: str, db: AsyncSession) -> Optional[User]:
        """Authenticate user with username/email and password"""
        try:
            # Find user by username or email
            stmt = select(User).where(
                (User.username == username) | (User.email == username)
            )
            result = await db.execute(stmt)
            user = result.scalar_one_or_none()
            
            if not user:
                return None
            
            if not self.verify_password(password, user.hashed_password):
                return None
            
            if not user.is_active:
                raise AuthenticationError("User account is disabled")
            
            return user
            
        except Exception as e:
            logger.error(f"Error authenticating user: {str(e)}")
            raise AuthenticationError("Authentication failed")
    
    async def create_user(self, user_data: UserCreate, db: AsyncSession) -> User:
        """Create new user account"""
        try:
            # Check if user already exists
            stmt = select(User).where(
                (User.username == user_data.username) | (User.email == user_data.email)
            )
            result = await db.execute(stmt)
            existing_user = result.scalar_one_or_none()
            
            if existing_user:
                raise AuthenticationError("User with this username or email already exists")
            
            # Create new user
            hashed_password = self.get_password_hash(user_data.password)
            new_user = User(
                email=user_data.email,
                username=user_data.username,
                full_name=user_data.full_name,
                hashed_password=hashed_password,
                role=user_data.role.value if hasattr(user_data.role, 'value') else user_data.role,
                is_active=True
            )
            
            db.add(new_user)
            await db.commit()
            await db.refresh(new_user)
            
            logger.info(f"Created new user: {new_user.username}")
            return new_user
            
        except AuthenticationError:
            raise
        except Exception as e:
            await db.rollback()
            logger.error(f"Error creating user: {str(e)}")
            raise AuthenticationError("Failed to create user")
        
    async def admin_create_user(self, user_data: UserCreate, current_admin: UserResponse, db: AsyncSession) -> User:
        """Admin user create new user account"""
        try:
            # Check if user already exists
            stmt = select(User).where(
                (User.username == user_data.username) | (User.email == user_data.email)
            )
            result = await db.execute(stmt)
            existing_user = result.scalar_one_or_none()
            
            if existing_user:
                raise AuthenticationError("User with this username or email already exists")
            
            # Create new user
            hashed_password = self.get_password_hash(user_data.password)
            new_user = User(
                email=user_data.email,
                username=user_data.username,
                full_name=user_data.full_name,
                hashed_password=hashed_password,
                role=user_data.role.value if hasattr(user_data.role, 'value') else user_data.role,
                is_active=True
            )
            
            db.add(new_user)
            await db.commit()
            await db.refresh(new_user)
            
            logger.info(f"Admin {current_admin.username} created new user: {new_user.username}")
            return new_user
            
        except AuthenticationError:
            raise
        except Exception as e:
            await db.rollback()
            logger.error(f"Error creating user: {str(e)}")
            raise AuthenticationError("Failed to create user")
    
    async def get_user_by_id(self, user_id: int, db: AsyncSession) -> Optional[User]:
        """Get user by ID"""
        try:
            stmt = select(User).where(User.id == user_id)
            result = await db.execute(stmt)
            return result.scalar_one_or_none()
            
        except Exception as e:
            logger.error(f"Error getting user by ID: {str(e)}")
            return None
    
    async def get_user_by_username(self, username: str, db: AsyncSession) -> Optional[User]:
        """Get user by username"""
        try:
            stmt = select(User).where(User.username == username)
            result = await db.execute(stmt)
            return result.scalar_one_or_none()
            
        except Exception as e:
            logger.error(f"Error getting user by username: {str(e)}")
            return None
    
    async def login(self, username: str, password: str, db: AsyncSession) -> Token:
        """Login user and return access token"""
        user = await self.authenticate_user(username, password, db)
        if not user:
            raise AuthenticationError("Invalid username or password")
        
        # Create access token
        access_token = self.create_access_token(
            data={"sub": str(user.id), "username": user.username}
        )
        
        # Create user session record
        try:
            import uuid
            session = UserSession(
                id=str(uuid.uuid4()),
                user_id=user.id,
                expires_at=datetime.utcnow() + timedelta(minutes=self.access_token_expire_minutes),
                metadata={"login_time": datetime.utcnow().isoformat()}
            )
            db.add(session)
            await db.commit()
        except Exception as e:
            logger.error(f"Error creating user session: {str(e)}")
        
        return Token(
            access_token=access_token,
            token_type="bearer",
            expires_in=self.access_token_expire_minutes * 60
        )
    
    async def login_user(self, username: str, password: str, db: AsyncSession):
        """Alias for login method"""
        return await self.login(username, password, db)
    
    async def get_current_user_from_token(self, token: str, db: AsyncSession) -> Optional[User]:
        """Get current user from JWT token"""
        payload = self.verify_token(token)
        if not payload:
            return None
        
        user_id = payload.get("sub")
        if not user_id:
            return None
        
        try:
            return await self.get_user_by_id(int(user_id), db)
        except (ValueError, TypeError):
            return None
    
    async def change_password(
        self,
        user_id: int,
        current_password: str,
        new_password: str,
        db: AsyncSession
    ) -> bool:
        """Change user password"""
        try:
            user = await self.get_user_by_id(user_id, db)
            if not user:
                raise AuthenticationError("User not found")
            
            if not self.verify_password(current_password, user.hashed_password):
                raise AuthenticationError("Current password is incorrect")
            
            user.hashed_password = self.get_password_hash(new_password)
            await db.commit()
            
            logger.info(f"Password changed for user {user_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error changing password: {str(e)}")
            await db.rollback()
            raise AuthenticationError("Failed to change password")
    
    async def require_permission(
        self,
        current_user,
        required_role: str,
        resource_owner_id: Optional[int] = None
    ):
        """Check if user has required permission"""
        # Allow if user is accessing their own resource
        if resource_owner_id and current_user.id == resource_owner_id:
            return True
        
        # Check role-based access
        if current_user.role == "admin":
            return True
        
        if current_user.role != required_role:
            raise AuthorizationError("Access denied: insufficient permissions")
        
        return True
    
    async def get_user(self, user_id: int, db: AsyncSession):
        """Alias for get_user_by_id"""
        return await self.get_user_by_id(user_id, db)
    
    async def update_user(
        self,
        user_id: int,
        user_update,
        db: AsyncSession
    ) -> User:
        """Update user information"""
        try:
            user = await self.get_user_by_id(user_id, db)
            if not user:
                raise AuthenticationError("User not found")
            
            if hasattr(user_update, 'full_name') and user_update.full_name is not None:
                user.full_name = user_update.full_name
            
            if hasattr(user_update, 'role') and user_update.role is not None:
                user.role = user_update.role.value if hasattr(user_update.role, 'value') else user_update.role
            
            if hasattr(user_update, 'is_active') and user_update.is_active is not None:
                user.is_active = user_update.is_active
            
            await db.commit()
            await db.refresh(user)
            
            logger.info(f"Updated user {user_id}")
            return user
            
        except Exception as e:
            logger.error(f"Error updating user: {str(e)}")
            await db.rollback()
            raise AuthenticationError("Failed to update user")
    
    async def logout(self, token: str, db: AsyncSession) -> bool:
        """Logout user (invalidate session)"""
        payload = self.verify_token(token)
        if not payload:
            return False
        
        try:
            user_id = int(payload.get("sub", 0))
            # Mark all user sessions as expired
            stmt = select(UserSession).where(UserSession.user_id == user_id)
            result = await db.execute(stmt)
            sessions = result.scalars().all()
            
            for session in sessions:
                session.expires_at = datetime.utcnow()
            
            await db.commit()
            return True
            
        except Exception as e:
            logger.error(f"Error during logout: {str(e)}")
            return False
