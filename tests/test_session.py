"""Tests for session management."""
import os
from unittest.mock import patch, MagicMock

import pytest


class TestSessionManager:
    """Test SessionManager initialization and basic operations."""

    def test_session_creation(self, temp_dir):
        session_file = os.path.join(temp_dir, "sessions.json")
        from snatch.session import SessionManager
        sm = SessionManager(session_file)
        assert sm is not None
        assert sm._async_manager is not None

    def test_nonexistent_session_returns_none(self, temp_dir):
        session_file = os.path.join(temp_dir, "sessions.json")
        from snatch.session import SessionManager
        sm = SessionManager(session_file)

        data = sm.get_session("https://no-such-url.example.com/video.mp4")
        assert data is None

    def test_update_session_creates_entry(self, temp_dir):
        session_file = os.path.join(temp_dir, "sessions.json")
        from snatch.session import SessionManager
        sm = SessionManager(session_file)

        url = "https://example.com/video.mp4"
        sm.update_session(url, 50.0, total_size=10000, file_path="/tmp/video.mp4")

        data = sm.get_session(url)
        assert data is not None


class TestAsyncSessionManager:
    """Test AsyncSessionManager."""

    def test_init(self, temp_dir):
        session_file = os.path.join(temp_dir, "sessions.json")
        from snatch.session import AsyncSessionManager
        asm = AsyncSessionManager(session_file)
        assert asm is not None
