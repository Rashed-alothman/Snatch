"""Tests for config loading, caching, and error handling."""
import json
import os
from unittest.mock import patch

import pytest


class TestConfigLoading:
    """Test _load_existing_config function."""

    def test_returns_dict_when_no_file(self, temp_dir):
        fake_path = os.path.join(temp_dir, "nonexistent.json")
        with patch("snatch.config.CONFIG_FILE", fake_path):
            from snatch.config import _load_existing_config
            # Reset cache
            import snatch.config as cfg
            cfg._cached_config = None
            cfg._config_mtime = 0.0

            config = _load_existing_config()
            assert isinstance(config, dict)

    def test_loads_values_from_file(self, temp_dir):
        config_path = os.path.join(temp_dir, "config.json")
        with open(config_path, "w") as f:
            json.dump({"max_concurrent": 5, "organize": True}, f)

        with patch("snatch.config.CONFIG_FILE", config_path):
            import snatch.config as cfg
            cfg._cached_config = None
            cfg._config_mtime = 0.0

            config = cfg._load_existing_config()
            assert config["max_concurrent"] == 5
            assert config["organize"] is True

    def test_corrupt_json_returns_defaults(self, temp_dir):
        config_path = os.path.join(temp_dir, "config.json")
        with open(config_path, "w") as f:
            f.write("NOT VALID JSON {{{{")

        with patch("snatch.config.CONFIG_FILE", config_path):
            import snatch.config as cfg
            cfg._cached_config = None
            cfg._config_mtime = 0.0

            config = cfg._load_existing_config()
            assert isinstance(config, dict)

    def test_caching_returns_same_result(self, temp_dir):
        config_path = os.path.join(temp_dir, "config.json")
        with open(config_path, "w") as f:
            json.dump({"max_concurrent": 7}, f)

        with patch("snatch.config.CONFIG_FILE", config_path):
            import snatch.config as cfg
            cfg._cached_config = None
            cfg._config_mtime = 0.0

            first = cfg._load_existing_config()
            second = cfg._load_existing_config()
            assert first == second
            assert first["max_concurrent"] == 7

    def test_cache_invalidated_on_file_change(self, temp_dir):
        config_path = os.path.join(temp_dir, "config.json")
        with open(config_path, "w") as f:
            json.dump({"max_concurrent": 3}, f)

        with patch("snatch.config.CONFIG_FILE", config_path):
            import snatch.config as cfg
            cfg._cached_config = None
            cfg._config_mtime = 0.0

            first = cfg._load_existing_config()
            assert first["max_concurrent"] == 3

            # Modify file (force different mtime)
            import time
            time.sleep(0.05)
            with open(config_path, "w") as f:
                json.dump({"max_concurrent": 10}, f)

            reloaded = cfg._load_existing_config()
            assert reloaded["max_concurrent"] == 10
