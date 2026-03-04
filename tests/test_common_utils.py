"""Tests for common utility functions."""
import os
import platform

from snatch.common_utils import sanitize_filename, format_size, is_windows


class TestSanitizeFilename:
    def test_removes_invalid_chars(self):
        assert sanitize_filename('file<>:"/\\|?*name') == "filename"

    def test_strips_leading_trailing_dots(self):
        assert sanitize_filename("...test...") == "test"

    def test_strips_leading_trailing_spaces(self):
        assert sanitize_filename("  test  ") == "test"

    def test_replaces_tabs_and_newlines(self):
        result = sanitize_filename("hello\tworld\ntest")
        assert "\t" not in result
        assert "\n" not in result

    def test_empty_string_returns_download(self):
        assert sanitize_filename("") == "download"

    def test_reserved_windows_names(self):
        assert sanitize_filename("CON") == "download"
        assert sanitize_filename("PRN") == "download"
        assert sanitize_filename("NUL") == "download"
        assert sanitize_filename("COM1") == "download"
        assert sanitize_filename("LPT1") == "download"

    def test_truncates_long_filenames(self):
        long_name = "a" * 300
        result = sanitize_filename(long_name)
        assert len(result) <= 240

    def test_normal_filename_unchanged(self):
        assert sanitize_filename("my_video.mp4") == "my_video.mp4"


class TestFormatSize:
    def test_zero_bytes(self):
        assert format_size(0) == "0 B"

    def test_negative_bytes(self):
        assert format_size(-1) == "0 B"

    def test_bytes(self):
        assert format_size(500) == "500.00 B"

    def test_kilobytes(self):
        assert format_size(1024) == "1.00 KB"

    def test_megabytes(self):
        assert format_size(1024 * 1024) == "1.00 MB"

    def test_gigabytes(self):
        assert format_size(1024**3) == "1.00 GB"

    def test_custom_precision(self):
        assert format_size(1500, precision=1) == "1.5 KB"


class TestIsWindows:
    def test_returns_bool(self):
        result = is_windows()
        assert isinstance(result, bool)

    def test_matches_platform(self):
        expected = platform.system().lower() == "windows"
        assert is_windows() == expected
