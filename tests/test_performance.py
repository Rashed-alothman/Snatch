import pytest
import sys
import time
from unittest.mock import patch

sys.path.insert(0, '..')
import Snatch

def test_performance_of_critical_function():
    """Test performance of URL validation function."""
    # Define a performant URL validation function if not exists
    if not hasattr(Snatch, 'is_valid_url'):
        return pytest.skip("No suitable functions for performance testing found")
    
    # Test URLs
    urls = [
        "https://example.com/video.mp4",
        "http://test.org/path/to/resource?query=value&param=123",
        "https://subdomain.domain.com/very/long/path/to/resource/with/many/segments",
        "http://example.com/" + "a" * 1000,  # Long URL
        "not_a_url",
        "ftp://invalid.protocol.com",
        None,
        ""
    ]
    
    # Test function performance
    start_time = time.time()
    for _ in range(1000):  # Run 1000 validations
        for url in urls:
            try:
                Snatch.is_valid_url(url)
            except Exception:
                pass
    end_time = time.time()
    
    execution_time = end_time - start_time
    
    # Performance assertion - ensure validation is reasonably fast
    # (8000 validations should complete in under 1 second on modern hardware)
    assert execution_time < 1.0, f"URL validation performance is too slow: {execution_time:.4f} seconds"
    
    # Log performance metrics
    print(f"\nURL validation performance: {execution_time:.4f} seconds for 8000 validations")
    print(f"Average per validation: {(execution_time / 8000) * 1000:.4f} ms")