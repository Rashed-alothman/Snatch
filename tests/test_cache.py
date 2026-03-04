"""Tests for the DownloadCache module."""
import os
import tempfile
from unittest.mock import patch

import pytest


@pytest.fixture
def cache_dir():
    """Provide a temporary cache directory."""
    with tempfile.TemporaryDirectory() as d:
        yield d


@pytest.fixture
def cache(cache_dir):
    """Provide a DownloadCache instance with a temp directory."""
    with patch("snatch.cache.CACHE_DIR", cache_dir):
        from snatch.cache import DownloadCache

        return DownloadCache(max_memory_entries=10, cache_ttl=3600)


class TestDownloadCache:
    def test_set_and_get(self, cache):
        cache.set("key1", {"url": "http://example.com", "title": "Test"})
        result = cache.get("key1")
        assert result is not None
        assert result["url"] == "http://example.com"
        assert result["title"] == "Test"

    def test_get_nonexistent_key(self, cache):
        assert cache.get("nonexistent") is None

    def test_get_empty_key(self, cache):
        assert cache.get("") is None

    def test_set_empty_key(self, cache):
        assert cache.set("", {"data": "test"}) is False

    def test_set_empty_value(self, cache):
        assert cache.set("key", {}) is False

    def test_invalidate(self, cache):
        cache.set("key1", {"data": "test"})
        cache.invalidate("key1")
        assert cache.get("key1") is None

    def test_clear(self, cache):
        cache.set("key1", {"data": "test1"})
        cache.set("key2", {"data": "test2"})
        cache.clear()
        assert cache.get("key1") is None
        assert cache.get("key2") is None

    def test_get_returns_copy(self, cache):
        original = {"data": "test"}
        cache.set("key1", original)
        result = cache.get("key1")
        result["data"] = "modified"
        # Original cached value should be unchanged
        assert cache.get("key1")["data"] == "test"

    def test_get_stats(self, cache):
        cache.set("key1", {"data": "test"})
        stats = cache.get_stats()
        assert stats["memory_entries"] == 1
        assert stats["max_memory_entries"] == 10
        assert stats["cache_ttl"] == 3600
