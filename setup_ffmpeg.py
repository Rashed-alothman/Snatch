import os
import sys
import json
import zipfile
import requests
from pathlib import Path
from tqdm import tqdm
import shutil
from colorama import init, Fore, Style

# Initialize colorama
init()

def download_file(url, filename):
    """Download a file with progress bar"""
    response = requests.get(url, stream=True)
    total_size = int(response.headers.get('content-length', 0))
    
    with open(filename, 'wb') as file, tqdm(
        desc=f"{Fore.CYAN}Downloading FFmpeg{Style.RESET_ALL}",
        total=total_size,
        unit='iB',
        unit_scale=True,
        unit_divisor=1024,
    ) as pbar:
        for data in response.iter_content(chunk_size=1024):
            size = file.write(data)
            pbar.update(size)

def setup_ffmpeg():
    """Download and setup FFmpeg"""
    ffmpeg_dir = Path('C:/ffmpeg')
    zip_path = Path('ffmpeg.zip')
    
    try:
        print(f"{Fore.CYAN}Setting up FFmpeg...{Style.RESET_ALL}")
        
        # Create ffmpeg directory
        ffmpeg_dir.mkdir(exist_ok=True)
        
        # Download FFmpeg
        ffmpeg_url = "https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-win64-gpl.zip"
        download_file(ffmpeg_url, zip_path)
        
        print(f"{Fore.CYAN}Extracting FFmpeg...{Style.RESET_ALL}")
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            zip_ref.extractall(ffmpeg_dir)
        
        # Update config.json
        config_path = Path('config.json')
        if config_path.exists():
            with open(config_path, 'r') as f:
                config = json.load(f)
        else:
            config = {}
        
        config['ffmpeg_location'] = str(ffmpeg_dir / 'ffmpeg-master-latest-win64-gpl' / 'bin')
        
        with open(config_path, 'w') as f:
            json.dump(config, f, indent=4)
        
        # Cleanup
        zip_path.unlink()
        
        print(f"{Fore.GREEN}✓ FFmpeg setup complete!{Style.RESET_ALL}")
        print(f"FFmpeg location: {config['ffmpeg_location']}")
        
    except Exception as e:
        print(f"{Fore.RED}Error setting up FFmpeg: {str(e)}{Style.RESET_ALL}")
        if zip_path.exists():
            zip_path.unlink()
        sys.exit(1)

if __name__ == "__main__":
    setup_ffmpeg()
