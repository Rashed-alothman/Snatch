"""Tests for the download manager module."""
import asyncio
from unittest.mock import MagicMock, patch

import pytest


class TestDownloadChunk:
    """Test DownloadChunk dataclass."""

    def test_chunk_creation(self):
        from snatch.manager import DownloadChunk
        chunk = DownloadChunk(start=0, end=1023)
        assert chunk.start == 0
        assert chunk.end == 1023
        assert chunk.data == b""
        assert chunk.retries == 0
        assert chunk.sha256 == ""

    def test_chunk_size(self):
        from snatch.manager import DownloadChunk
        chunk = DownloadChunk(start=100, end=199)
        assert chunk.end - chunk.start + 1 == 100


def _make_manager(config):
    """Helper to create an AsyncDownloadManager with mocked deps."""
    from snatch.manager import AsyncDownloadManager
    mock_session = MagicMock()
    mock_cache = MagicMock()
    with patch("snatch.manager.EnhancedErrorHandler"):
        return AsyncDownloadManager(
            config=config,
            session_manager=mock_session,
            download_cache=mock_cache,
        )


class TestManagerInit:
    """Test AsyncDownloadManager initialization."""

    def test_default_chunk_size(self, mock_config):
        mgr = _make_manager(mock_config)
        assert mgr.chunk_size == 1024 * 1024  # 1MB default

    def test_config_stored(self, mock_config):
        mgr = _make_manager(mock_config)
        assert mgr.config is mock_config


class TestConnectionPooling:
    """Test that HTTP client is created with connection pooling."""

    @pytest.mark.asyncio
    async def test_http_client_has_connector_limits(self, mock_config):
        mgr = _make_manager(mock_config)
        client = mgr._create_http_client()
        assert client.connector is not None
        assert client.connector._limit == 30
        assert client.connector._limit_per_host == 10
        await client.close()
