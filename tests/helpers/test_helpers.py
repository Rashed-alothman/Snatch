import os
import tempfile
import pytest
from unittest.mock import patch, MagicMock
import requests

class MockResponse:
    """Mock HTTP response for testing."""
    
    def __init__(self, content=b"", status_code=200, headers=None, url=None):
        self.content = content
        self.status_code = status_code
        self.headers = headers or {}
        self.url = url or "https://example.com"
        
    def raise_for_status(self):
        """Raise an exception if status code is 4xx or 5xx."""
        if 400 <= self.status_code < 600:
            raise requests.exceptions.HTTPError(f"HTTP Error: {self.status_code}")
        
    def json(self):
        """Return JSON content if applicable."""
        import json
        try:
            return json.loads(self.content)
        except:
            raise ValueError("Response content is not valid JSON")

def create_test_file(directory, filename, content="test content"):
    """Create a test file for file operations testing."""
    file_path = os.path.join(directory, filename)
    with open(file_path, "w") as f:
        f.write(content)
    return file_path

def create_mock_video_file(directory, filename="test_video.mp4", size_kb=100):
    """Create a mock video file of specified size."""
    file_path = os.path.join(directory, filename)
    # Create a binary file with random data to simulate a video
    with open(file_path, "wb") as f:
        f.write(os.urandom(size_kb * 1024))  # Random bytes of specified size
    return file_path

def patch_requests_get(status_code=200, content=b"test content", headers=None):
    """Create a patch for requests.get that returns a mock response."""
    mock_response = MockResponse(content=content, status_code=status_code, headers=headers)
    return patch('requests.get', return_value=mock_response)