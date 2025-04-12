# Snatch Test Suite Documentation

This directory contains tests for the Snatch application, a tool for downloading and processing media files.

## Test Structure

- `conftest.py`: Common test fixtures and setup
- `functional/`: Tests for functional behaviors
- `unit/`: Unit tests for individual functions
- `helpers/`: Helper functions and utilities for testing

## Running Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=Snatch

# Generate HTML coverage report
pytest --cov=Snatch --cov-report=html

# Run integration tests only
pytest -m integration
```
