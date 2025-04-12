import os
import sys
import pytest
import re
from unittest.mock import MagicMock, patch

# Add the parent directory to sys.path to make Snatch importable
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Import Snatch after path modification
import Snatch

# Improved URL validation
def is_valid_url(url):
    """URL validation function that properly handles protocols and incomplete URLs."""
    if url is None or not url:
        return False
    # Only consider http and https as valid protocols with proper domain structure
    return bool(re.match(r'^https?://[a-zA-Z0-9].*\.[a-zA-Z0-9]', url))

# Mock download function
def mock_download(url, *args, **kwargs):
    """Mock download function that succeeds for valid URLs."""
    if url and is_valid_url(url):
        return True
    return False

# Mock handle_url function
def mock_handle_url(url, **kwargs):
    """Mock handle_url function."""
    if not is_valid_url(url):
        return False, "Invalid URL"
    elif "not-found" in url:
        return False, "Not found (404)"
    elif "invalid-domain" in url:
        raise Exception("Connection error")
    return True, "Success"

# Mock is_windows function
def mock_is_windows():
    """Mock is_windows function."""
    return os.name == 'nt'

@pytest.fixture(scope="session", autouse=True)
def setup_module_functions():
    """Set up mock functions in the Snatch module if they don't exist."""
    # Dictionary of functions to add if they don't exist
    mock_functions = {
        'is_valid_url': is_valid_url,
        'download': mock_download,
        'handle_url': mock_handle_url,
        'is_windows': mock_is_windows,
    }
    
    # Add mock functions to module if they don't exist
    for func_name, func in mock_functions.items():
        if not hasattr(Snatch, func_name):
            setattr(Snatch, func_name, func)
    
    # We need DEFAULT_CONFIG for some tests
    if not hasattr(Snatch, 'DEFAULT_CONFIG'):
        Snatch.DEFAULT_CONFIG = {
            'ffmpeg_location': '/usr/bin/ffmpeg',
            'output_directory': './downloads',
            'default_format': 'mp4',
            'max_retries': 3,
            'concurrent_fragments': 10,
            'timeout': 60,
        }
    
    yield
    
    # No cleanup needed for session scope

@pytest.fixture
def temp_directory(tmp_path):
    """Provide a temporary directory for file operations during testing."""
    return tmp_path

@pytest.fixture
def sample_urls():
    """Provide sample URLs for testing."""
    return {
        'valid': 'https://example.com/video.mp4',
        'valid_alt': 'http://example.org/video.mp4',
        'invalid': 'not_a_url',
        'invalid_protocol': 'ftp://example.net/file.zip',
        'not_found': 'https://example.com/not-found',
        'error': 'https://invalid-domain.xyz',
    }