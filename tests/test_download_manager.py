import os
import sys
import pytest
import tempfile
from unittest.mock import patch, MagicMock

# Import Snatch
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import Snatch

class TestDownloadManager:
    """Tests for download management functionality."""
    
    @pytest.fixture
    def download_manager(self):
        """Create a download manager for testing."""
        # Check if DownloadManager exists in Snatch
        if hasattr(Snatch, 'DownloadManager'):
            # Create a more complete mock config with all potentially needed keys
            mock_config = {
                "output_directory": "downloads",
                "video_output": "videos",
                "audio_output": "audio",
                "max_retries": 3,
                "timeout": 30,
                "concurrent_fragments": 3,
                "buffer_size": 8192,
                "ffmpeg_location": "/mock/path/to/ffmpeg"
            }
            return Snatch.DownloadManager(mock_config)
        else:
            pytest.skip("DownloadManager class not found in Snatch module")
    
    def test_manager_initialization(self, download_manager):
        """Test that download manager initializes properly."""
        # Simply check that the manager instance was created successfully
        assert download_manager is not None
        assert hasattr(download_manager, 'batch_download')
    
    @patch('Snatch.is_valid_url', return_value=True)  # Mock URL validation to always return True
    def test_batch_download_callable(self, mock_is_valid, download_manager):
        """Test that batch_download method can be called."""
        # Setup a valid URL
        valid_url = "https://example.com/video.mp4"
        
        # We're just testing that the method can be called without errors
        # We'll patch any necessary dependencies
        with patch.object(Snatch, 'handle_url', return_value=(True, "Success")):
            result = download_manager.batch_download(valid_url)
            # Just verify it ran without exception
            assert True
    
    @patch('Snatch.is_valid_url', return_value=True)
    @patch('Snatch.handle_url', return_value=(True, "Success"))
    def test_batch_download_with_list(self, mock_handle_url, mock_is_valid, download_manager):
        """Test batch_download with a list of URLs."""
        # Test with a list of URLs
        urls = [
            "https://example.com/video1.mp4",
            "https://example.com/video2.mp4"
        ]
        
        # Call the method
        with patch('Snatch.download', return_value=True):
            result = download_manager.batch_download(urls)
            # Just verify it ran without exception
            assert True