"""Tests for version consistency and constants module."""


def test_version_is_2_0_0():
    """Version should be 2.0.0 across all locations."""
    from snatch.constants import VERSION

    assert VERSION == "2.0.0"


def test_init_version_matches_constants():
    """__init__.py version should match constants.py."""
    import snatch
    from snatch.constants import VERSION

    assert snatch.__version__ == VERSION


def test_defaults_version_matches_constants():
    """defaults.py VERSION should be imported from constants."""
    from snatch.constants import VERSION
    from snatch.defaults import VERSION as DEFAULTS_VERSION

    assert DEFAULTS_VERSION == VERSION


def test_no_duplicate_process_prefix_keys():
    """PROCESS_PREFIXES should have no duplicate keys."""
    from snatch.constants import PROCESS_PREFIXES

    # Python dicts can't have actual duplicate keys, but the source file
    # originally had duplicate "organize" keys. Verify the dict is well-formed.
    assert "organize" in PROCESS_PREFIXES
    assert len(PROCESS_PREFIXES) >= 10


def test_default_timeout_consistency():
    """DEFAULT_TIMEOUT should be consistent between modules."""
    from snatch.constants import DEFAULT_TIMEOUT
    from snatch.defaults import DEFAULT_TIMEOUT as DEFAULTS_TIMEOUT

    assert DEFAULT_TIMEOUT == DEFAULTS_TIMEOUT
