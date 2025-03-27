import os
import sys
import json
import zipfile
import platform
import subprocess
import tempfile
from pathlib import Path
import shutil
import time
from io import BytesIO

# Try importing required packages, install if needed
try:
    from tqdm import tqdm
    from colorama import init, Fore, Style
    import requests
except ImportError:
    print("Installing required packages...")
    subprocess.check_call([sys.executable, "-m", "pip", "install", "tqdm", "colorama", "requests"])
    from tqdm import tqdm
    from colorama import init, Fore, Style
    import requests

# Initialize colorama with auto-reset
init(autoreset=True)

CONFIG_FILE = 'config.json'
DEFAULT_CONFIG = {
    'ffmpeg_location': '',  # Will be auto-detected
    'video_output': str(Path.home() / 'Videos'),
    'audio_output': str(Path.home() / 'Music'),
    'max_concurrent': 3
}

def print_banner():
    """Display a banner for the setup script"""
    print(f"\n{Fore.CYAN}╔{'═' * 50}╗")
    print(f"{Fore.CYAN}║{Fore.GREEN}          FFmpeg Setup for Snatch          {Fore.CYAN}║")
    print(f"{Fore.CYAN}╚{'═' * 50}╝{Style.RESET_ALL}\n")

def is_windows():
    """Check if running on Windows"""
    return platform.system() == "Windows"

def is_ffmpeg_working(ffmpeg_path):
    """Test if FFmpeg works properly"""
    try:
        cmd = [ffmpeg_path, "-version"] if os.path.isfile(ffmpeg_path) else ["ffmpeg", "-version"]
        result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=5)
        return result.returncode == 0 and b"ffmpeg version" in result.stdout
    except (subprocess.SubprocessError, FileNotFoundError, PermissionError):
        return False

def find_existing_ffmpeg():
    """Find FFmpeg in PATH or common locations"""
    # First check if ffmpeg is in PATH
    try:
        if is_windows():
            # Windows: Use where command
            result = subprocess.run(["where", "ffmpeg"], capture_output=True, text=True)
            if result.returncode == 0:
                path = result.stdout.strip().split('\n')[0]
                if os.path.exists(path):
                    return path
        else:
            # Unix-like: Use which command
            result = subprocess.run(["which", "ffmpeg"], capture_output=True, text=True)
            if result.returncode == 0:
                path = result.stdout.strip()
                if os.path.exists(path):
                    return path
    except (subprocess.SubprocessError, FileNotFoundError):
        pass
        
    # Check common locations
    common_locations = []
    
    if is_windows():
        # Windows common locations
        common_locations = [
            r'C:\ffmpeg\bin\ffmpeg.exe',
            r'C:\Program Files\ffmpeg\bin\ffmpeg.exe',
            r'C:\ffmpeg\ffmpeg-master-latest-win64-gpl\bin\ffmpeg.exe',
            os.path.join(os.path.dirname(os.path.abspath(__file__)), 'ffmpeg', 'bin', 'ffmpeg.exe')
        ]
    else:
        # Unix-like common locations
        common_locations = [
            '/usr/bin/ffmpeg',
            '/usr/local/bin/ffmpeg',
            '/opt/local/bin/ffmpeg',
            '/opt/homebrew/bin/ffmpeg'
        ]
    
    for location in common_locations:
        if os.path.exists(location) and is_ffmpeg_working(location):
            return location
            
    return None

def download_with_progress(url):
    """Download file with progress bar and return content"""
    try:
        print(f"{Fore.CYAN}Downloading from: {url}{Style.RESET_ALL}")
        response = requests.get(url, stream=True, timeout=60)
        response.raise_for_status()
        
        total_size = int(response.headers.get('content-length', 0))
        content = BytesIO()
        
        with tqdm(
            total=total_size,
            unit='B',
            unit_scale=True,
            unit_divisor=1024,
            desc=f"{Fore.CYAN}Downloading FFmpeg{Style.RESET_ALL}",
            bar_format="{desc}: {percentage:3.0f}%|{bar}| {n_fmt}/{total_fmt} [{elapsed}<{remaining}]"
        ) as pbar:
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    content.write(chunk)
                    pbar.update(len(chunk))
        
        content.seek(0)
        return content
    except requests.RequestException as e:
        print(f"{Fore.RED}Download error: {str(e)}{Style.RESET_ALL}")
        return None

def verify_zip_archive(content):
    """Verify if content is a valid zip archive with FFmpeg"""
    try:
        with zipfile.ZipFile(content) as zip_file:
            file_list = zip_file.namelist()
            # Check if archive contains ffmpeg.exe or similar files
            has_ffmpeg = any('ffmpeg' in f.lower() and f.endswith(('.exe', '')) for f in file_list)
            return has_ffmpeg
    except zipfile.BadZipFile:
        return False

def extract_with_progress(zip_content, extract_path):
    """Extract zip with progress indication"""
    with zipfile.ZipFile(zip_content) as zip_ref:
        members = zip_ref.namelist()
        total = len(members)
        
        with tqdm(
            total=total,
            desc=f"{Fore.CYAN}Extracting FFmpeg{Style.RESET_ALL}",
            bar_format="{desc}: {percentage:3.0f}%|{bar}| {n_fmt}/{total_fmt} [{elapsed}<{remaining}]"
        ) as pbar:
            for i, member in enumerate(members):
                zip_ref.extract(member, extract_path)
                pbar.update(1)
                # Throttle updates to avoid console flicker
                if i % 50 == 0:
                    time.sleep(0.01)

def find_ffmpeg_exe(base_path):
    """Find FFmpeg executable in the extracted files"""
    spinner_chars = ['⠋', '⠙', '⠹', '⠸', '⠼', '⠴', '⠦', '⠧', '⠇', '⠏']
    i = 0
    print(f"{Fore.CYAN}Locating FFmpeg executable...{Style.RESET_ALL}", end='', flush=True)
    
    # Define the file pattern based on OS
    file_pattern = 'ffmpeg.exe' if is_windows() else 'ffmpeg'
    
    # Search all subdirectories for ffmpeg executable
    for i, (root, dirs, files) in enumerate(os.walk(base_path)):
        print(f"\r{Fore.CYAN}Locating FFmpeg executable... {spinner_chars[i % len(spinner_chars)]}{Style.RESET_ALL}", end='', flush=True)
        
        if file_pattern in files:
            ffmpeg_path = os.path.join(root, file_pattern)
            print(f"\r{Fore.GREEN}Found FFmpeg executable!{' ' * 20}{Style.RESET_ALL}")
            return ffmpeg_path
            
        if i % 10 == 0:
            time.sleep(0.01)  # Prevent UI freeze
    
    print(f"\r{Fore.RED}FFmpeg executable not found in extracted files.{' ' * 20}{Style.RESET_ALL}")
    return None

def save_config(config):
    """Save configuration to file"""
    try:
        with open(CONFIG_FILE, 'w') as f:
            json.dump(config, f, indent=4)
        print(f"{Fore.GREEN}Configuration saved successfully.{Style.RESET_ALL}")
        return True
    except (IOError, PermissionError) as e:
        print(f"{Fore.RED}Error saving configuration: {str(e)}{Style.RESET_ALL}")
        return False

def load_config():
    """Load existing configuration or create default"""
    try:
        if os.path.exists(CONFIG_FILE):
            with open(CONFIG_FILE, 'r') as f:
                config = json.load(f)
                # Ensure all default keys exist
                for key, value in DEFAULT_CONFIG.items():
                    if key not in config:
                        config[key] = value
                return config
        else:
            return DEFAULT_CONFIG.copy()
    except (IOError, json.JSONDecodeError):
        print(f"{Fore.YELLOW}Warning: Couldn't read config file, using defaults.{Style.RESET_ALL}")
        return DEFAULT_CONFIG.copy()

def setup_ffmpeg():
    """Main function to set up FFmpeg"""
    print_banner()
    
    # Step 1: Check if FFmpeg is already available
    print(f"{Fore.CYAN}Step 1: Checking for existing FFmpeg installation...{Style.RESET_ALL}")
    ffmpeg_path = find_existing_ffmpeg()
    
    if ffmpeg_path:
        print(f"{Fore.GREEN}✓ FFmpeg already installed at: {ffmpeg_path}{Style.RESET_ALL}")
        config = load_config()
        config['ffmpeg_location'] = os.path.dirname(ffmpeg_path) if os.path.isfile(ffmpeg_path) else ffmpeg_path
        save_config(config)
        return True
        
    # Step 2: Download FFmpeg
    print(f"\n{Fore.CYAN}Step 2: Downloading FFmpeg...{Style.RESET_ALL}")
    
    # Try multiple sources
    ffmpeg_sources = [
        "https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-win64-gpl.zip",
        "https://github.com/GyanD/codexffmpeg/releases/download/5.1.2/ffmpeg-5.1.2-essentials_build.zip"
    ]
    
    zip_content = None
    for source in ffmpeg_sources:
        print(f"Trying source: {source}")
        zip_content = download_with_progress(source)
        if zip_content and verify_zip_archive(zip_content):
            print(f"{Fore.GREEN}✓ Valid FFmpeg archive downloaded{Style.RESET_ALL}")
            break
        elif zip_content:
            print(f"{Fore.YELLOW}⚠ Downloaded file is not a valid FFmpeg archive. Trying next source...{Style.RESET_ALL}")
    
    if not zip_content:
        print(f"{Fore.RED}✗ Failed to download FFmpeg from any source.{Style.RESET_ALL}")
        print(f"{Fore.YELLOW}Please download and install FFmpeg manually from: https://ffmpeg.org/download.html{Style.RESET_ALL}")
        return False
        
    # Step 3: Extract FFmpeg
    print(f"\n{Fore.CYAN}Step 3: Extracting FFmpeg...{Style.RESET_ALL}")
    
    # Create a permanent directory for FFmpeg
    ffmpeg_dir = Path('C:/ffmpeg') if is_windows() else Path.home() / '.ffmpeg'
    try:
        ffmpeg_dir.mkdir(exist_ok=True)
        print(f"Extracting to {ffmpeg_dir}")
        extract_with_progress(zip_content, ffmpeg_dir)
    except (IOError, zipfile.BadZipFile, PermissionError) as e:
        print(f"{Fore.RED}✗ Extraction failed: {str(e)}{Style.RESET_ALL}")
        
        # Try extracting to a temporary directory as fallback
        print(f"{Fore.YELLOW}Trying to extract to temporary directory...{Style.RESET_ALL}")
        temp_dir = Path(tempfile.gettempdir()) / 'ffmpeg'
        temp_dir.mkdir(exist_ok=True)
        
        try:
            extract_with_progress(zip_content, temp_dir)
            ffmpeg_dir = temp_dir
        except Exception as e2:
            print(f"{Fore.RED}✗ Extraction to temporary directory also failed: {str(e2)}{Style.RESET_ALL}")
            return False
    
    # Step 4: Find FFmpeg executable in extracted files
    print(f"\n{Fore.CYAN}Step 4: Locating FFmpeg in extracted files...{Style.RESET_ALL}")
    ffmpeg_path = find_ffmpeg_exe(ffmpeg_dir)
    
    if not ffmpeg_path:
        print(f"{Fore.RED}✗ Could not locate FFmpeg executable in extracted files.{Style.RESET_ALL}")
        return False
    
    # Step 5: Verify FFmpeg works
    print(f"\n{Fore.CYAN}Step 5: Verifying FFmpeg installation...{Style.RESET_ALL}")
    if not is_ffmpeg_working(ffmpeg_path):
        print(f"{Fore.RED}✗ FFmpeg installation verification failed.{Style.RESET_ALL}")
        return False
    
    # Step 6: Update configuration
    print(f"\n{Fore.CYAN}Step 6: Updating configuration...{Style.RESET_ALL}")
    config = load_config()
    # Store either the directory containing ffmpeg.exe or the executable path based on what works
    ffmpeg_location = os.path.dirname(ffmpeg_path)
    config['ffmpeg_location'] = ffmpeg_location
    
    if save_config(config):
        print(f"\n{Fore.GREEN}✓ FFmpeg setup completed successfully!{Style.RESET_ALL}")
        print(f"{Fore.GREEN}FFmpeg location: {ffmpeg_location}{Style.RESET_ALL}")
        return True
    else:
        print(f"\n{Fore.YELLOW}⚠ FFmpeg was installed but configuration could not be saved.{Style.RESET_ALL}")
        print(f"{Fore.YELLOW}Please manually update config.json with:{Style.RESET_ALL}")
        print(f"{Fore.YELLOW}\"ffmpeg_location\": \"{ffmpeg_location}\"{Style.RESET_ALL}")
        return False

def copy_relevant_files_to_script_directory():
    """Copy just the necessary FFmpeg executables to script directory for portability"""
    try:
        config = load_config()
        ffmpeg_source_dir = config.get('ffmpeg_location', '')
        
        if not ffmpeg_source_dir or not os.path.exists(ffmpeg_source_dir):
            print(f"{Fore.YELLOW}No valid FFmpeg location found in config.{Style.RESET_ALL}")
            return False
        
        # Create local ffmpeg folder
        local_dir = Path(os.path.dirname(os.path.abspath(__file__))) / 'ffmpeg' / 'bin'
        local_dir.mkdir(parents=True, exist_ok=True)
        
        # Copy the exe files
        essential_files = ['ffmpeg.exe', 'ffprobe.exe'] if is_windows() else ['ffmpeg', 'ffprobe']
        files_copied = 0
        
        for file in essential_files:
            source = os.path.join(ffmpeg_source_dir, file)
            target = local_dir / file
            
            if os.path.exists(source):
                print(f"Copying {file} to local directory...")
                shutil.copy2(source, target)
                files_copied += 1
        
        if files_copied > 0:
            print(f"{Fore.GREEN}✓ Copied {files_copied} FFmpeg file(s) to local directory.{Style.RESET_ALL}")
            
            # Update config to use local copy
            config['ffmpeg_location'] = str(local_dir)
            save_config(config)
            return True
        else:
            print(f"{Fore.YELLOW}No FFmpeg files were found to copy.{Style.RESET_ALL}")
            return False
            
    except Exception as e:
        print(f"{Fore.RED}Error creating local FFmpeg copy: {str(e)}{Style.RESET_ALL}")
        return False

if __name__ == "__main__":
    try:
        success = setup_ffmpeg()
        
        if success:
            # Ask user if they want a local copy
            response = input(f"\n{Fore.CYAN}Would you like to create a portable copy of FFmpeg in the script directory? (y/n): {Style.RESET_ALL}")
            if response.lower().startswith('y'):
                copy_relevant_files_to_script_directory()
                
            print(f"\n{Fore.GREEN}Setup complete! You can now use Snatch to download videos.{Style.RESET_ALL}")
            print(f"{Fore.CYAN}Try running: python Snatch.py --test{Style.RESET_ALL}")
        else:
            print(f"\n{Fore.RED}Setup failed. Please try manual installation.{Style.RESET_ALL}")
            sys.exit(1)
    except KeyboardInterrupt:
        print(f"\n{Fore.YELLOW}Setup cancelled by user.{Style.RESET_ALL}")
        sys.exit(1)
    except Exception as e:
        print(f"\n{Fore.RED}Unexpected error: {str(e)}{Style.RESET_ALL}")
        sys.exit(1)
