import os
import sys
import subprocess

def install_dependencies():
    """Install all dependencies required for testing."""
    dependencies = [
        "pytest",
        "pytest-cov",
        "pytest-mock",
        "pytest-timeout",
        "requests"
    ]
    
    print("Installing test dependencies...")
    for dep in dependencies:
        print(f"Installing {dep}...")
        subprocess.call([sys.executable, "-m", "pip", "install", dep])
    
    print("All dependencies installed successfully!")

def setup_test_directory():
    """Create necessary directories for testing."""
    test_dir = os.path.dirname(os.path.abspath(__file__))
    
    # Ensure helpers directory exists
    helpers_dir = os.path.join(test_dir, "helpers")
    os.makedirs(helpers_dir, exist_ok=True)
    
    # Create __init__.py files
    open(os.path.join(test_dir, "__init__.py"), "w").close()
    open(os.path.join(helpers_dir, "__init__.py"), "w").close()
    
    print("Test directory structure set up successfully!")

if __name__ == "__main__":
    install_dependencies()
    setup_test_directory()
    print("Test environment setup complete!")