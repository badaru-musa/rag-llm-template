import os
import shutil
from typing import Optional
from pathlib import Path
from fastapi import UploadFile
from app.exceptions import FileUploadError
from app.logger import logger
from config import settings


class FileUploader:
    """Service for handling file uploads"""
    
    def __init__(self, upload_directory: str = "./data/documents"):
        self.upload_directory = Path(upload_directory)
        self.upload_directory.mkdir(parents=True, exist_ok=True)
    
    async def save_uploaded_file(
        self,
        file: UploadFile,
        user_id: int,
        custom_filename: Optional[str] = None
    ) -> str:
        """Save uploaded file to disk"""
        
        try:
            # Validate file
            await self._validate_upload_file(file)
            
            # Create user directory
            user_dir = self.upload_directory / str(user_id)
            user_dir.mkdir(exist_ok=True)
            
            # Generate filename
            filename = custom_filename or file.filename
            if not filename:
                raise FileUploadError("No filename provided")
            
            # Ensure unique filename
            file_path = self._get_unique_filepath(user_dir, filename)
            
            # Save file
            with open(file_path, "wb") as buffer:
                shutil.copyfileobj(file.file, buffer)
            
            logger.info(f"Saved uploaded file: {file_path}")
            return str(file_path)
            
        except FileUploadError:
            raise
        except Exception as e:
            logger.error(f"Error saving uploaded file: {str(e)}")
            raise FileUploadError(f"Failed to save file: {str(e)}")
        finally:
            file.file.close()
    
    async def _validate_upload_file(self, file: UploadFile):
        """Validate uploaded file"""
        
        # Check file size
        if hasattr(file.file, 'seek') and hasattr(file.file, 'tell'):
            file.file.seek(0, 2)  # Seek to end
            file_size = file.file.tell()
            file.file.seek(0)  # Reset to beginning
            
            if file_size > settings.max_file_size:
                raise FileUploadError(
                    f"File size ({file_size}) exceeds maximum allowed size ({settings.max_file_size})"
                )
        
        # Check file extension
        if file.filename:
            file_extension = Path(file.filename).suffix.lower()
            if file_extension not in settings.allowed_extensions:
                raise FileUploadError(
                    f"File type {file_extension} not allowed. Allowed types: {settings.allowed_extensions}"
                )
        else:
            raise FileUploadError("No filename provided")
    
    def _get_unique_filepath(self, directory: Path, filename: str) -> Path:
        """Generate unique filepath to avoid overwrites"""
        
        base_path = directory / filename
        
        if not base_path.exists():
            return base_path
        
        # Add counter to make unique
        stem = base_path.stem
        suffix = base_path.suffix
        counter = 1
        
        while True:
            new_path = directory / f"{stem}_{counter}{suffix}"
            if not new_path.exists():
                return new_path
            counter += 1
    
    async def delete_file(self, file_path: str, user_id: int) -> bool:
        """Delete a file"""
        
        try:
            path = Path(file_path)
            
            # Security check: ensure file is in user's directory
            user_dir = self.upload_directory / str(user_id)
            if not str(path).startswith(str(user_dir)):
                raise FileUploadError("Access denied: file not in user directory")
            
            if path.exists():
                path.unlink()
                logger.info(f"Deleted file: {file_path}")
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"Error deleting file {file_path}: {str(e)}")
            raise FileUploadError(f"Failed to delete file: {str(e)}")
    
    def get_file_info(self, file_path: str) -> dict:
        """Get file information"""
        
        try:
            path = Path(file_path)
            
            if not path.exists():
                raise FileUploadError("File not found")
            
            stat = path.stat()
            
            return {
                "filename": path.name,
                "file_path": str(path),
                "file_size": stat.st_size,
                "file_type": path.suffix.lower().lstrip('.'),
                "created_at": stat.st_ctime,
                "modified_at": stat.st_mtime,
                "exists": True
            }
            
        except Exception as e:
            logger.error(f"Error getting file info for {file_path}: {str(e)}")
            return {"exists": False, "error": str(e)}
    
    def cleanup_user_files(self, user_id: int) -> int:
        """Clean up all files for a user"""
        
        try:
            user_dir = self.upload_directory / str(user_id)
            
            if not user_dir.exists():
                return 0
            
            file_count = 0
            for file_path in user_dir.rglob("*"):
                if file_path.is_file():
                    file_path.unlink()
                    file_count += 1
            
            # Remove empty directories
            try:
                user_dir.rmdir()
            except OSError:
                pass  # Directory not empty or other issue
            
            logger.info(f"Cleaned up {file_count} files for user {user_id}")
            return file_count
            
        except Exception as e:
            logger.error(f"Error cleaning up files for user {user_id}: {str(e)}")
            return 0
    
    def get_user_storage_usage(self, user_id: int) -> dict:
        """Get storage usage statistics for a user"""
        
        try:
            user_dir = self.upload_directory / str(user_id)
            
            if not user_dir.exists():
                return {"total_size": 0, "file_count": 0}
            
            total_size = 0
            file_count = 0
            
            for file_path in user_dir.rglob("*"):
                if file_path.is_file():
                    total_size += file_path.stat().st_size
                    file_count += 1
            
            return {
                "total_size": total_size,
                "file_count": file_count,
                "user_id": user_id
            }
            
        except Exception as e:
            logger.error(f"Error getting storage usage for user {user_id}: {str(e)}")
            return {"total_size": 0, "file_count": 0, "error": str(e)}
