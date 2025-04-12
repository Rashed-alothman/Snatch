import os
import sys
import pytest
from unittest.mock import patch, MagicMock

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import Snatch module
import Snatch

@pytest.mark.parametrize("url,expected_status", [
    ("https://example.com/video", 200),
    ("https://example.com/not-found", 404),
    ("https://invalid-domain.xyz", "Exception"),
])
def test_url_handling(url, expected_status):
    """Test URL handling with different scenarios."""
    # The mock handle_url function is provided by conftest.py
    if expected_status == "Exception":
        # Test exception case
        with pytest.raises(Exception):
            Snatch.handle_url(url)
    else:
        # Test normal cases
        success, message = Snatch.handle_url(url)
        
        if expected_status == 200:
            assert success, f"Should succeed for status {expected_status}"
        elif expected_status == 404:
            assert not success, f"Should fail for status {expected_status}"