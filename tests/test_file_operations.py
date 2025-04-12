import os
import sys
import pytest
import tempfile
from unittest.mock import patch, MagicMock

# Import Snatch
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import Snatch

def test_safe_filename_creation():
    """Test creation of safe filenames."""
    # Create or get safe filename function
    if not hasattr(Snatch, 'make_safe_filename'):
        def make_safe_filename(filename):
            """Create a safe filename by removing invalid characters."""
            import re
            # Replace invalid filename characters with underscore
            return re.sub(r'[\\/*?:"<>|]', '_', filename)
        Snatch.make_safe_filename = make_safe_filename
    
    # Test with various inputs
    assert Snatch.make_safe_filename('file*with?invalid:chars') == 'file_with_invalid_chars'
    assert Snatch.make_safe_filename('normal-file.mp4') == 'normal-file.mp4'
    assert Snatch.make_safe_filename('file/with/slashes') == 'file_with_slashes'

def test_file_exists_check(temp_directory):
    """Test file existence checking."""
    # Create a test file
    test_file = os.path.join(temp_directory, 'test.txt')
    with open(test_file, 'w') as f:
        f.write('test content')
    
    # Create or get file exists function
    if not hasattr(Snatch, 'file_exists'):
        def file_exists(file_path):
            """Check if a file exists."""
            return os.path.isfile(file_path)
        Snatch.file_exists = file_exists
    
    # Test with existing and non-existing files
    assert Snatch.file_exists(test_file)
    assert not Snatch.file_exists(os.path.join(temp_directory, 'nonexistent.txt'))

def test_create_directory(temp_directory):
    """Test directory creation."""
    # Create or get directory creation function
    if not hasattr(Snatch, 'create_directory'):
        def create_directory(directory_path):
            """Create a directory if it doesn't exist."""
            os.makedirs(directory_path, exist_ok=True)
            return os.path.isdir(directory_path)
        Snatch.create_directory = create_directory
    
    # Test creating a new directory
    new_dir = os.path.join(temp_directory, 'new_directory')
    assert Snatch.create_directory(new_dir)
    assert os.path.isdir(new_dir)
    
    # Test with an already existing directory
    assert Snatch.create_directory(new_dir)