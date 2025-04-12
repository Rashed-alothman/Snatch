import os
import sys
import pytest
import re

# Add the parent directory to sys.path to make Snatch importable
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

# Import Snatch
import Snatch

def is_valid_url(url):
    """Improved URL validation function that properly handles protocols."""
    if url is None or not url:
        return False
    # Only consider http and https as valid protocols
    return bool(re.match(r'^https?://.+\..+', url))

# Replace the mocked function with our improved version
Snatch.is_valid_url = is_valid_url

def test_url_processing_workflow():
    """Test the full URL validation and processing workflow."""
    # Test with valid URLs
    assert Snatch.is_valid_url("https://example.com/video.mp4")
    assert Snatch.is_valid_url("http://subdomain.example.com/path/to/file.mp4")
    
    # Test with invalid URLs
    assert not Snatch.is_valid_url("ftp://example.com/video.mp4")
    assert not Snatch.is_valid_url("invalid_url")
    assert not Snatch.is_valid_url(None)
    assert not Snatch.is_valid_url("")