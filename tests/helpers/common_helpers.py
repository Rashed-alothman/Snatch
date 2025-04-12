import os
import tempfile
from unittest.mock import MagicMock

def ensure_directory_exists(directory_path):
    """Ensure a directory exists, creating it if necessary."""
    os.makedirs(directory_path, exist_ok=True)
    return directory_path

def create_test_file(directory, filename, content="test content"):
    """Create a test file with specified content."""
    file_path = os.path.join(directory, filename)
    ensure_directory_exists(os.path.dirname(file_path))
    
    with open(file_path, "w") as f:
        f.write(content)
    
    return file_path

def create_binary_file(directory, filename, size_kb=10):
    """Create a binary file of specified size."""
    file_path = os.path.join(directory, filename)
    ensure_directory_exists(os.path.dirname(file_path))
    
    with open(file_path, "wb") as f:
        f.write(os.urandom(size_kb * 1024))  # Random bytes
    
    return file_path

def create_mock_response(status_code=200, content="", headers=None):
    """Create a mock HTTP response."""
    mock_response = MagicMock()
    mock_response.status_code = status_code
    mock_response.content = content
    mock_response.headers = headers or {}
    
    def raise_for_status():
        if status_code >= 400:
            raise Exception(f"HTTP Error: {status_code}")
    
    mock_response.raise_for_status = raise_for_status
    return mock_response