#!/usr/bin/env python
import os
import sys
import subprocess
import platform
import shutil
from pathlib import Path

def print_colored(text, color):
    """Print colored text if colorama is available"""
    colors = {
        'green': '\033[92m',
        'yellow': '\033[93m',
        'red': '\033[91m',
        'blue': '\033[94m',
        'end': '\033[0m'
    }
    
    try:
        print(f"{colors.get(color, '')}{text}{colors['end']}")
    except:
        print(text)

def is_admin():
    """Check if running with admin privileges"""
    try:
        if platform.system() == "Windows":
            import ctypes
            return ctypes.windll.shell32.IsUserAnAdmin() != 0
        else:
            return os.geteuid() == 0
    except:
        return False

def install_dependencies():
    """Install Python dependencies"""
    print_colored("\n[Step 1/4] Installing dependencies...", "blue")
    
    # Check if pip is available
    try:
        subprocess.run([sys.executable, '-m', 'pip', '--version'], check=True, stdout=subprocess.PIPE)
    except:
        print_colored("Error: pip not found. Please install pip first.", "red")
        return False
    
    # Create requirements list
    requirements = [
        "yt-dlp>=2023.12.30",
        "mutagen>=1.47.0",
        "colorama>=0.4.6",
        "tqdm>=4.66.1",
        "requests>=2.31.0",
        "psutil>=5.9.0",
        "requests>=2.31.0"
    ]
    
    # Write to requirements.txt
    req_path = Path("requirements.txt")
    try:
        with open(req_path, 'w') as f:
            f.write("\n".join(requirements))
    except:
        print_colored("Warning: Could not write requirements.txt. Continuing anyway...", "yellow")
    
    # Install dependencies
    try:
        subprocess.run([sys.executable, '-m', 'pip', 'install', '--upgrade'] + requirements, check=True)
        print_colored("✓ Dependencies installed successfully!", "green")
        return True
    except Exception as e:
        print_colored(f"Error installing dependencies: {str(e)}", "red")
        print_colored("Try running as administrator or with --user flag", "yellow")
        return False

def setup_ffmpeg():
    """Install FFmpeg using the setup script"""
    print_colored("\n[Step 2/4] Setting up FFmpeg...", "blue")
    
    # Check if setup_ffmpeg.py exists
    if not os.path.exists("setup_ffmpeg.py"):
        print_colored("Error: setup_ffmpeg.py not found.", "red")
        return False
    
    # Run the FFmpeg setup script
    try:
        subprocess.run([sys.executable, 'setup_ffmpeg.py'], check=True)
        print_colored("✓ FFmpeg setup completed!", "green")
        return True
    except Exception as e:
        print_colored(f"Error setting up FFmpeg: {str(e)}", "red")
        return False

def create_launcher():
    """Create launcher files for easier startup"""
    print_colored("\n[Step 3/4] Creating launcher files...", "blue")
    
    try:
        # Create batch file for Windows
        if platform.system() == "Windows":
            with open("Snatch.bat", "w") as f:
                f.write('@echo off\n')
                f.write('echo Starting Snatch...\n')
                f.write(f'"{sys.executable}" "{os.path.abspath("Snatch.py")}"\n')
                f.write('if %ERRORLEVEL% NEQ 0 pause\n')
            print_colored("✓ Created Snatch.bat - Double-click to run the app!", "green")
            
        # Create shell script for Unix-like systems
        else:
            with open("snatch.sh", "w") as f:
                f.write('#!/bin/bash\n')
                f.write('echo "Starting Snatch..."\n')
                f.write(f'"{sys.executable}" "{os.path.abspath("Snatch.py")}"\n')
            
            # Make the script executable
            os.chmod("snatch.sh", 0o755)
            print_colored("✓ Created snatch.sh - Run with ./snatch.sh", "green")
            
        return True
    except Exception as e:
        print_colored(f"Error creating launcher: {str(e)}", "red")
        print_colored("You can still run the app with: python Snatch.py", "yellow")
        return False

def check_installation():
    """Verify that everything is working"""
    print_colored("\n[Step 4/4] Verifying installation...", "blue")
    
    # Check for main script
    if not os.path.exists("Snatch.py"):
        print_colored("Error: Snatch.py not found.", "red")
        return False
    
    # Try to run a basic test
    try:
        subprocess.run([sys.executable, 'Snatch.py', '--version'], check=True, stdout=subprocess.PIPE)
        print_colored("✓ Installation verified successfully!", "green")
        return True
    except Exception as e:
        print_colored(f"Error: {str(e)}", "red")
        return False

def main():
    print_colored("\n=== Snatch Setup Wizard ===", "blue")
    
    # Check for admin rights
    if not is_admin() and platform.system() == "Windows":
        print_colored("Warning: Running without administrator privileges. Some features might not work.", "yellow")
    
    # Install dependencies
    if not install_dependencies():
        if input("Continue anyway? (y/n): ").lower() != 'y':
            return False
    
    # Setup FFmpeg
    if not setup_ffmpeg():
        if input("Continue anyway? (y/n): ").lower() != 'y':
            return False
    
    # Create launcher
    create_launcher()
    
    # Check installation
    if check_installation():
        print_colored("\n=== Setup Complete! ===", "green")
        print_colored("\nHow to run Snatch:", "blue")
        
        if platform.system() == "Windows":
            print_colored("1. Double-click Snatch.bat file", "yellow")
            print_colored("   OR", "blue")
            print_colored("2. Run: python Snatch.py", "yellow")
        else:
            print_colored("1. Run: ./snatch.sh", "yellow")
            print_colored("   OR", "blue")
            print_colored("2. Run: python Snatch.py", "yellow")
            
        print_colored("\nFor interactive mode:", "blue")
        print_colored("  python Snatch.py --interactive", "yellow")
        
        return True
    else:
        print_colored("\n=== Setup Failed ===", "red")
        print_colored("Please check the errors above and try again.", "yellow")
        return False

if __name__ == "__main__":
    try:
        success = main()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print_colored("\nSetup cancelled by user.", "yellow")
        sys.exit(1)
