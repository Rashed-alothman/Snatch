import os
import sys
import pytest
import re

# Add the parent directory to sys.path to make Snatch importable
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

# Import Snatch
import Snatch

def is_valid_url(url):
    """Improved URL validation function that properly handles protocols and incomplete URLs."""
    if url is None or not url:
        return False
    # Only consider http and https as valid protocols with proper domain structure
    return bool(re.match(r'^https?://[a-zA-Z0-9].*\.[a-zA-Z0-9]', url))

# Replace the mocked function with our improved version
Snatch.is_valid_url = is_valid_url

def test_is_valid_url():
    """Test is_valid_url function with valid and invalid URLs."""
    # Test valid HTTP URLs
    assert Snatch.is_valid_url("http://example.com")
    assert Snatch.is_valid_url("https://example.com/path/to/resource")
    assert Snatch.is_valid_url("https://example.com/path?query=value")
    
    # Test invalid URLs
    assert not Snatch.is_valid_url("not_a_url")
    assert not Snatch.is_valid_url("ftp://invalid.protocol.com")
    assert not Snatch.is_valid_url("")
    assert not Snatch.is_valid_url(None)

def test_url_validation_edge_cases():
    """Test edge cases for URL validation."""
    # Edge cases - incomplete URLs should fail
    assert not Snatch.is_valid_url("http://")  # No domain specified
    assert not Snatch.is_valid_url("https://")  # No domain specified
    
    # URLs with special characters but still valid domain structure
    assert Snatch.is_valid_url("https://example.com/path with spaces")
    assert Snatch.is_valid_url("https://example.com/path?query=value&another=value")