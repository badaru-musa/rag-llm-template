import os
import hashlib
import uuid
import json
from typing import Any, Dict, List, Optional, Union
from datetime import datetime, timezone
from pathlib import Path
import re


def generate_uuid() -> str:
    """Generate a new UUID4 string"""
    return str(uuid.uuid4())


def generate_short_id(length: int = 8) -> str:
    """Generate a short random ID"""
    return str(uuid.uuid4()).replace('-', '')[:length]


def calculate_file_hash(file_path: Union[str, Path], algorithm: str = 'md5') -> str:
    """Calculate hash of a file"""
    hash_func = getattr(hashlib, algorithm)()
    
    try:
        with open(file_path, 'rb') as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_func.update(chunk)
        return hash_func.hexdigest()
    except Exception:
        return ""


def safe_filename(filename: str) -> str:
    """Make a filename safe for file system"""
    # Remove or replace unsafe characters
    filename = re.sub(r'[<>:"/\\|?*]', '_', filename)
    # Remove leading/trailing whitespace and dots
    filename = filename.strip('. ')
    # Limit length
    if len(filename) > 255:
        name, ext = os.path.splitext(filename)
        filename = name[:255-len(ext)] + ext
    
    return filename or "unnamed_file"


def format_file_size(size_bytes: int) -> str:
    """Format file size in human readable format"""
    if size_bytes == 0:
        return "0 B"
    
    size_names = ["B", "KB", "MB", "GB", "TB"]
    i = 0
    while size_bytes >= 1024 and i < len(size_names) - 1:
        size_bytes /= 1024.0
        i += 1
    
    return f"{size_bytes:.1f} {size_names[i]}"


def chunk_text(
    text: str,
    chunk_size: int = 15000,
    chunk_overlap: int = 1000,
    separators: List[str] = None
) -> List[str]:
    """Split text into chunks with optional overlap"""
    if separators is None:
        separators = ["\n\n", "\n", ". ", "! ", "? ", " "]
    
    chunks = []
    start = 0
    
    while start < len(text):
        end = start + chunk_size
        
        if end >= len(text):
            # Last chunk
            chunk = text[start:].strip()
            if chunk:
                chunks.append(chunk)
            break
        
        # Try to break at a good separator
        best_break = end
        for separator in separators:
            break_point = text.rfind(separator, start, end)
            if break_point > start:
                best_break = break_point + len(separator)
                break
        
        chunk = text[start:best_break].strip()
        if chunk:
            chunks.append(chunk)
        
        start = max(start + 1, best_break - chunk_overlap)
    
    return chunks


def clean_text(text: str) -> str:
    """Clean and normalize text"""
    text = re.sub(r'\s+', ' ', text)
    text = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x84\x86-\x9f]', '', text)
    text = text.strip()
    
    return text


def extract_keywords(text: str, max_keywords: int = 10) -> List[str]:
    """Extract keywords from text (simple implementation)"""
    import re
    from collections import Counter
    
    stop_words = {
        'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 
        'with', 'by', 'is', 'are', 'was', 'were', 'be', 'been', 'have', 'has', 'had',
        'do', 'does', 'did', 'will', 'would', 'could', 'should', 'may', 'might',
        'this', 'that', 'these', 'those', 'i', 'you', 'he', 'she', 'it', 'we', 'they'
    }

    words = re.findall(r'\b[a-zA-Z]{3,}\b', text.lower())
    
    filtered_words = [word for word in words if word not in stop_words]
    

    word_freq = Counter(filtered_words)
    keywords = [word for word, _ in word_freq.most_common(max_keywords)]
    
    return keywords


def merge_dictionaries(*dicts: Dict[str, Any]) -> Dict[str, Any]:
    """Merge multiple dictionaries, with later ones taking precedence"""
    result = {}
    for d in dicts:
        if d:
            result.update(d)
    return result


def flatten_dict(d: Dict[str, Any], parent_key: str = '', sep: str = '_') -> Dict[str, Any]:
    """Flatten a nested dictionary"""
    items = []
    for k, v in d.items():
        new_key = f"{parent_key}{sep}{k}" if parent_key else k
        if isinstance(v, dict):
            items.extend(flatten_dict(v, new_key, sep=sep).items())
        else:
            items.append((new_key, v))
    return dict(items)


def sanitize_json(obj: Any) -> Any:
    """Sanitize object for JSON serialization"""
    if isinstance(obj, dict):
        return {k: sanitize_json(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [sanitize_json(item) for item in obj]
    elif isinstance(obj, datetime):
        return obj.isoformat()
    elif isinstance(obj, (set, tuple)):
        return list(obj)
    elif hasattr(obj, '__dict__'):
        return sanitize_json(obj.__dict__)
    else:
        return obj


def validate_url(url: str) -> bool:
    """Validate if string is a valid URL"""
    import re
    url_pattern = re.compile(
        r'^https?://'  # http:// or https://
        r'(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+[A-Z]{2,6}\.?|'  # domain...
        r'localhost|'  # localhost...
        r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})'
        r'(?::\d+)?'
        r'(?:/?|[/?]\S+)$', re.IGNORECASE)
    
    return url_pattern.match(url) is not None


def validate_email(email: str) -> bool:
    """Validate email address"""
    import re
    email_pattern = re.compile(
        r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    )
    return email_pattern.match(email) is not None


def truncate_text(text: str, max_length: int = 100, suffix: str = "...") -> str:
    """Truncate text to specified length"""
    if len(text) <= max_length:
        return text
    
    return text[:max_length - len(suffix)] + suffix


def get_file_extension(filename: str) -> str:
    """Get file extension from filename"""
    return Path(filename).suffix.lower().lstrip('.')


def is_supported_file_type(filename: str, supported_types: List[str]) -> bool:
    """Check if file type is supported"""
    extension = get_file_extension(filename)
    return extension in [ext.lower().lstrip('.') for ext in supported_types]


def create_directory_if_not_exists(directory: Union[str, Path]) -> Path:
    """Create directory if it doesn't exist"""
    path = Path(directory)
    path.mkdir(parents=True, exist_ok=True)
    return path


def get_timestamp(timezone_aware: bool = True) -> datetime:
    """Get current timestamp"""
    if timezone_aware:
        return datetime.now(timezone.utc)
    else:
        return datetime.now()


def format_timestamp(dt: datetime, format_str: str = "%Y-%m-%d %H:%M:%S") -> str:
    """Format datetime as string"""
    return dt.strftime(format_str)


def parse_timestamp(timestamp_str: str, format_str: str = "%Y-%m-%d %H:%M:%S") -> datetime:
    """Parse timestamp string to datetime"""
    return datetime.strptime(timestamp_str, format_str)


def retry_operation(func, max_retries: int = 3, delay: float = 1.0):
    """Retry an operation with exponential backoff"""
    import time
    
    for attempt in range(max_retries):
        try:
            return func()
        except Exception as e:
            if attempt == max_retries - 1:
                raise e
            time.sleep(delay * (2 ** attempt))


def load_json_file(file_path: Union[str, Path]) -> Dict[str, Any]:
    """Load JSON file safely"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return {}


def save_json_file(data: Dict[str, Any], file_path: Union[str, Path]) -> bool:
    """Save data to JSON file safely"""
    try:
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False, default=str)
        return True
    except Exception:
        return False


def normalize_whitespace(text: str) -> str:
    """Normalize whitespace in text"""
    text = re.sub(r'\s+', ' ', text)
    text = re.sub(r'\n\s*\n\s*\n+', '\n\n', text)
    return text.strip()


def estimate_reading_time(text: str, words_per_minute: int = 200) -> int:
    """Estimate reading time in minutes"""
    word_count = len(text.split())
    reading_time = max(1, round(word_count / words_per_minute))
    return reading_time


def anonymize_email(email: str) -> str:
    """Anonymize email address for logging"""
    if '@' not in email:
        return "invalid_email"
    
    local, domain = email.split('@', 1)
    if len(local) <= 2:
        anonymized_local = local
    else:
        anonymized_local = local[0] + '*' * (len(local) - 2) + local[-1]
    
    return f"{anonymized_local}@{domain}"
