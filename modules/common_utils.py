import re
import platform

def sanitize_filename(filename: str) -> str:
    """Sanitize filename by removing invalid characters"""
    # Remove invalid characters
    invalid_chars = r'[<>:"/\\|?*]'
    filename = re.sub(invalid_chars, '', filename)
    
    # Remove control characters
    filename = "".join(char for char in filename if ord(char) >= 32)
    
    # Ensure filename is not empty
    if not filename:
        filename = "download"
        
    return filename.strip()

def is_windows() -> bool:
    """Check if running on Windows"""
    return platform.system().lower() == "windows"