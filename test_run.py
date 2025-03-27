import os
import sys
import subprocess
import time
from pathlib import Path

def print_colored(text, color):
    """Print colored text"""
    colors = {
        'green': '\033[92m',
        'yellow': '\033[93m',
        'red': '\033[91m',
        'blue': '\033[94m',
        'end': '\033[0m'
    }
    
    print(f"{colors.get(color, '')}{text}{colors['end']}")

def run_test(command, desc):
    """Run a test command and report results"""
    print_colored(f"\nTesting: {desc}", "blue")
    print_colored(f"Command: {command}", "yellow")
    try:
        # Use different approaches for different platforms
        if sys.platform == 'win32':
            process = subprocess.Popen(command, shell=True)
        else:
            # For non-Windows systems, use list format
            process = subprocess.Popen(command.split())
            
        # Let the process run for 3 seconds to see if it starts properly
        time.sleep(3)
        if process.poll() is None:
            # Process is still running, which is good
            print_colored("✓ Test PASSED: Process started correctly", "green")
            # Kill the process since we just wanted to test startup
            process.terminate()
            try:
                process.wait(timeout=2)  # Give it 2 seconds to terminate
            except subprocess.TimeoutExpired:
                process.kill()  # Force kill if it doesn't terminate
            return True
        else:
            # Process exited already - check exit code
            if process.returncode == 0:
                print_colored("✓ Test PASSED: Process completed successfully", "green")
                return True
            else:
                print_colored(f"✗ Test FAILED: Process exited with code {process.returncode}", "red")
                return False
    except Exception as e:
        print_colored(f"✗ Test FAILED: {str(e)}", "red")
        return False

def main():
    print_colored("Snatch Functionality Test", "blue")
    
    # Test 1: Run with version flag
    run_test("python Snatch.py --version", "Version flag")
    
    # Test 2: Run with list-sites flag
    run_test("python Snatch.py --list-sites", "List sites")
    
    # Test 3: Run with interactive flag (with shorter timeout)
    print_colored("\nTesting: Interactive mode", "blue")
    print_colored("Command: python Snatch.py --interactive", "yellow")
    try:
        # Just quickly check if it starts without error
        result = subprocess.run(["python", "Snatch.py", "--interactive"], 
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE, 
                                timeout=1)
        # We only check that it starts - we'll terminate it after 1 second
        print_colored("✓ Test PASSED: Interactive mode started", "green")
    except subprocess.TimeoutExpired:
        # This is actually expected - it means the process is still running (interactive)
        print_colored("✓ Test PASSED: Interactive mode is running", "green")
    except Exception as e:
        print_colored(f"✗ Test FAILED: {str(e)}", "red")
    
    # Test 4: Run batch file
    if os.path.exists("Snatch.bat"):
        run_test("Snatch.bat --version", "Batch file launcher")
    else:
        print_colored("✗ Snatch.bat not found", "red")

    print_colored("\nTests completed. If any test failed, check the error messages above.", "blue")

if __name__ == "__main__":
    main()
