"""Tests for network module."""
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


class TestConnectionCheck:
    """Test parallel connection checking."""

    @pytest.mark.asyncio
    async def test_returns_true_when_one_endpoint_up(self):
        from snatch.network import NetworkManager
        nm = NetworkManager.__new__(NetworkManager)
        nm.last_connection_check = 0
        nm.connection_check_interval = 0
        nm.connection_status = False

        # Mock: first endpoint succeeds, rest fail
        async def mock_check(endpoint):
            return endpoint == "https://www.google.com"

        with patch.object(nm, "_perform_connection_check") as mock_perform:
            mock_perform.return_value = True
            result = await nm.check_connection()
            assert result is True

    @pytest.mark.asyncio
    async def test_cached_result_returned(self):
        """Recent check result should be returned without re-checking."""
        import time
        from snatch.network import NetworkManager
        nm = NetworkManager.__new__(NetworkManager)
        nm.last_connection_check = time.time()  # Just checked
        nm.connection_check_interval = 60
        nm.connection_status = True

        # Should return cached True without calling _perform_connection_check
        result = await nm.check_connection()
        assert result is True
