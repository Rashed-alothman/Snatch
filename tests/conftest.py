"""Shared test fixtures for Snatch test suite."""
import os
import tempfile

import pytest


@pytest.fixture
def temp_dir():
    """Provide a temporary directory that's cleaned up after the test."""
    with tempfile.TemporaryDirectory() as d:
        yield d


@pytest.fixture
def mock_config(temp_dir):
    """Provide a mock configuration dictionary with temp directories."""
    return {
        "video_output": os.path.join(temp_dir, "video"),
        "audio_output": os.path.join(temp_dir, "audio"),
        "sessions_dir": os.path.join(temp_dir, "sessions"),
        "cache_dir": os.path.join(temp_dir, "cache"),
        "ffmpeg_location": "",
        "max_concurrent": 3,
        "organize": False,
        "organization_templates": {
            "audio": "{uploader}/{album}/{title}",
            "video": "{uploader}/{year}/{title}",
        },
        "upscaling": {"enabled": False},
        "audio_enhancement": {"enabled": False},
    }
