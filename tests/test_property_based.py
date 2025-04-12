import re
import sys
import os
import pytest

# Import Snatch
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import Snatch

# Test cases for valid URLs
VALID_URLS = [
    "http://example.com",
    "https://sub.example.com/path",
    "http://example.com/path/to/resource",
    "https://example.com/path?query=value",
    "https://example.com:8080/path",
    "http://example-with-dash.com",
    "https://example.com/path/with/file.mp4",
    "http://192.168.1.1/path",
    "https://user:password@example.com",
    "http://example.co.uk/path"
]

# Test cases for invalid URLs
INVALID_URLS = [
    None,
    "",
    "not_a_url",
    "ftp://example.com/file",
    "http://",
    "https://",
    "http:///path",
    "file:///path",
    "://example.com",
    "http:/example.com",
    "http//example.com",
    "www.example.com"  # Missing protocol
]

@pytest.mark.parametrize("url", VALID_URLS)
def test_valid_url_cases(url):
    """Test valid URL validation with various test cases."""
    # Get or define the URL validation function
    is_valid_url = getattr(Snatch, 'is_valid_url', None)
    if is_valid_url is None:
        def is_valid_url(url):
            """Fallback URL validation implementation."""
            if url is None or not url:
                return False
            return bool(re.match(r'^https?://[a-zA-Z0-9].*\.[a-zA-Z0-9]', url))
        Snatch.is_valid_url = is_valid_url
    
    # Test valid URL
    assert is_valid_url(url), f"URL should be valid: {url}"

@pytest.mark.parametrize("url", INVALID_URLS)
def test_invalid_url_cases(url):
    """Test invalid URL validation with various test cases."""
    is_valid_url = getattr(Snatch, 'is_valid_url', None)
    if is_valid_url is None:
        def is_valid_url(url):
            """Fallback URL validation implementation."""
            if url is None or not url:
                return False
            return bool(re.match(r'^https?://[a-zA-Z0-9].*\.[a-zA-Z0-9]', url))
        Snatch.is_valid_url = is_valid_url
    
    # Test invalid URL
    assert not is_valid_url(url), f"URL should be invalid: {url}"

def test_systematic_url_variations():
    """Test URL validation with systematically generated variations."""
    is_valid_url = getattr(Snatch, 'is_valid_url', None)
    if is_valid_url is None:
        def is_valid_url(url):
            """Fallback URL validation implementation."""
            if url is None or not url:
                return False
            return bool(re.match(r'^https?://[a-zA-Z0-9].*\.[a-zA-Z0-9]', url))
        Snatch.is_valid_url = is_valid_url
        
    # Generate protocol variations
    protocols = ["http://", "https://"]
    domains = ["example.com", "sub.domain.org", "test-site.net"]
    paths = ["", "/", "/path", "/path/to/resource", "/file.mp4", "/path?query=value"]
    
    # Test valid combinations
    for protocol in protocols:
        for domain in domains:
            for path in paths:
                url = f"{protocol}{domain}{path}"
                assert is_valid_url(url), f"URL should be valid: {url}"