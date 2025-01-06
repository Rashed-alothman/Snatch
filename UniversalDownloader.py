import sys
import os
import yt_dlp
import argparse
import logging
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Optional, List, Dict
import json
import textwrap
import mutagen
from mutagen.mp3 import MP3
from mutagen.flac import FLAC
import subprocess
from tqdm import tqdm
import threading
import time
from colorama import init, Fore, Style
from difflib import get_close_matches
import shutil
import re

# Initialize colorama for Windows support
init()

class CustomHelpFormatter(argparse.HelpFormatter):
    def _split_lines(self, text, width):
        return [line for line in textwrap.wrap(text, width)]

EXAMPLES = """
Examples:
---------
1. Download a video from various platforms:
   python UniversalDownloader.py "https://youtube.com/watch?v=example"
   python UniversalDownloader.py "https://vimeo.com/123456789"
   python UniversalDownloader.py "https://dailymotion.com/video/x7tgd2g"
   python UniversalDownloader.py "https://twitch.tv/videos/1234567890"

2. Download audio only (MP3):
   python UniversalDownloader.py "https://soundcloud.com/artist/track" --audio-only

3. Download video in specific resolution:
   python UniversalDownloader.py "https://youtube.com/watch?v=example" --resolution 1080

4. Download multiple videos:
   python UniversalDownloader.py "URL1" "URL2" "URL3"

5. Download with custom filename:
   python UniversalDownloader.py "URL" --filename "my_video"

6. Download audio in FLAC format:
   python UniversalDownloader.py "URL" --audio-only --audio-format flac

Advanced Usage:
--------------
- Custom output directory:
  python UniversalDownloader.py "URL" --output-dir "path/to/directory"

- Specify format ID (for advanced users):
  python UniversalDownloader.py "URL" --format-id 137+140

- List all supported sites:
  python UniversalDownloader.py --list-sites

Common Issues:
--------------
1. FFMPEG not found: Install FFMPEG and update config.json
2. SSL Error: Update Python and yt-dlp
3. Permission Error: Run with admin privileges
"""

CONFIG_FILE = 'config.json'
DEFAULT_CONFIG = {
    'ffmpeg_location': '',  # Will be auto-detected
    'video_output': str(Path.home() / 'Videos'),
    'audio_output': str(Path.home() / 'Music'),
    'max_concurrent': 3
}

def find_ffmpeg():
    """Find FFmpeg in common locations or PATH"""
    common_locations = [
        r'C:\ffmpeg\bin',
        r'C:\Program Files\ffmpeg\bin',
        r'C:\ffmpeg\ffmpeg-master-latest-win64-gpl\bin',
        r'.\ffmpeg\bin',  # Relative to script location
    ]
    
    # Check if ffmpeg is in PATH
    if os.system('ffmpeg -version > nul 2>&1') == 0:
        return 'ffmpeg'
    
    # Check common locations
    for location in common_locations:
        ffmpeg_path = os.path.join(location, 'ffmpeg.exe')
        if os.path.exists(ffmpeg_path):
            return location
    
    return None

def print_ffmpeg_instructions():
    """Print instructions for installing FFmpeg"""
    print(f"{Fore.YELLOW}FFmpeg not found! Please follow these steps to install FFmpeg:{Style.RESET_ALL}")
    print("\n1. Download FFmpeg:")
    print("   - Visit: https://github.com/BtbN/FFmpeg-Builds/releases")
    print("   - Download: ffmpeg-master-latest-win64-gpl.zip")
    print("\n2. Install FFmpeg:")
    print("   - Extract the downloaded zip file")
    print("   - Copy the extracted folder to C:\\ffmpeg")
    print("   - Ensure ffmpeg.exe is in C:\\ffmpeg\\bin")
    print("\nAlternatively:")
    print("- Use chocolatey: choco install ffmpeg")
    print("- Use winget: winget install ffmpeg")
    print("\nAfter installation, either:")
    print("1. Add FFmpeg to your system PATH, or")
    print("2. Update config.json with the correct ffmpeg_location")
    print("\nFor detailed instructions, visit: https://www.wikihow.com/Install-FFmpeg-on-Windows")

class ColorProgressBar:
    def __init__(self, total, desc="Processing"):
        self.progress = tqdm(
            total=total,
            desc=f"{Fore.CYAN}{desc}{Style.RESET_ALL}",
            bar_format="{desc}: {percentage:3.0f}%|{bar}| {n_fmt}/{total_fmt}",
            ncols=80,
            unit="%"
        )
        self.colors = [Fore.BLUE, Fore.CYAN, Fore.GREEN, Fore.YELLOW]
        self.current_color_idx = 0
        self.last_update = 0

    def update(self, n=1):
        current_time = time.time()
        if current_time - self.last_update > 0.1:  # Limit color updates
            self.current_color_idx = (self.current_color_idx + 1) % len(self.colors)
            self.progress.bar_format = (
                "{desc}: {percentage:3.0f}%|"
                f"{self.colors[self.current_color_idx]}"
                "{bar}"
                f"{Style.RESET_ALL}"
                "| {n_fmt}/{total_fmt}"
            )
            self.last_update = current_time
        self.progress.update(n)

    def close(self):
        self.progress.close()
        print(f"\n{Fore.GREEN}✓ Complete!{Style.RESET_ALL}")

def print_banner():
    """Display an enhanced colorful welcome banner"""
    terminal_width = shutil.get_terminal_size().columns
    banner = f"""
{Fore.CYAN}╔{'═' * 68}╗
║  {Fore.YELLOW}██╗   ██╗{Fore.GREEN}███╗   ██╗{Fore.RED}██╗{Fore.BLUE}██╗   ██╗{Fore.MAGENTA}███████╗{Fore.WHITE}██████╗   {Fore.CYAN}║
║  {Fore.YELLOW}██║   ██║{Fore.GREEN}████╗  ██║{Fore.RED}██║{Fore.BLUE}██║   ██║{Fore.MAGENTA}██╔════╝{Fore.WHITE}██╔══██╗  {Fore.CYAN}║
║  {Fore.YELLOW}██║   ██║{Fore.GREEN}██╔██╗ ██║{Fore.RED}██║{Fore.BLUE}██║   ██║{Fore.MAGENTA}█████╗  {Fore.WHITE}██████╔╝  {Fore.CYAN}║
║  {Fore.YELLOW}██║   ██║{Fore.GREEN}██║╚██╗██║{Fore.RED}██║{Fore.BLUE}╚██╗ ██╔╝{Fore.MAGENTA}██╔══╝  {Fore.WHITE}██╔══██╗  {Fore.CYAN}║
║  {Fore.YELLOW}╚██████╔╝{Fore.GREEN}██║ ╚████║{Fore.RED}██║{Fore.BLUE} ╚████╔╝ {Fore.MAGENTA}███████╗{Fore.WHITE}██║  ██║  {Fore.CYAN}║
║   {Fore.YELLOW}╚═════╝ {Fore.GREEN}╚═╝  ╚═══╝{Fore.RED}╚═╝{Fore.BLUE}  ╚═══╝  {Fore.MAGENTA}╚══════╝{Fore.WHITE}╚═╝  ╚═╝  {Fore.CYAN}║
╠{'═' * 68}╣
║     {Fore.GREEN}■ {Fore.WHITE}Version: {Fore.YELLOW}1.1.0{Fore.WHITE}                                               {Fore.CYAN}║
║     {Fore.GREEN}■ {Fore.WHITE}Author : {Fore.YELLOW}Rashed Alothman{Fore.WHITE}                                       {Fore.CYAN}║
║     {Fore.GREEN}■ {Fore.WHITE}GitHub : {Fore.YELLOW}github.com/Rashed-alothman/Universal-downloader{Fore.WHITE}      {Fore.CYAN}║
╠{'═' * 68}╣
║  {Fore.YELLOW}Type {Fore.GREEN}help{Fore.YELLOW} or {Fore.GREEN}?{Fore.YELLOW} for commands  {Fore.WHITE}|  {Fore.YELLOW}Press {Fore.GREEN}Ctrl+C{Fore.YELLOW} to cancel{Fore.CYAN}  ║
╚{'═' * 68}╝{Style.RESET_ALL}"""

    # Calculate padding for centering
    lines = banner.split('\n')
    max_content_width = max(len(re.sub(r'\033\[[0-9;]+m', '', line)) for line in lines if line)
    padding = max(0, (terminal_width - max_content_width) // 2)
    
    # Print banner with padding
    print('\n' * 2)  # Add some space above banner
    for line in banner.split('\n'):
        if line:
            print(' ' * padding + line)
    print('\n')  # Add space below banner

class SpinnerAnimation:
    """Animated spinner for loading states"""
    def __init__(self, message="Processing"):
        self.spinner = ['⠋', '⠙', '⠹', '⠸', '⠼', '⠴', '⠦', '⠧', '⠇', '⠏']
        self.message = message
        self.running = False
        self.thread = None

    def spin(self):
        while self.running:
            for char in self.spinner:
                if not self.running:
                    break
                print(f"\r{Fore.CYAN}{char} {self.message}...{Style.RESET_ALL}", end='')
                time.sleep(0.1)

    def start(self):
        self.running = True
        self.thread = threading.Thread(target=self.spin)
        self.thread.start()

    def stop(self):
        self.running = False
        if self.thread:
            self.thread.join()
        print('\r' + ' ' * (len(self.message) + 20) + '\r', end='')

def fuzzy_match_command(input_cmd: str, valid_commands: list) -> str:
    """Find the closest matching command"""
    matches = get_close_matches(input_cmd.lower(), valid_commands, n=1, cutoff=0.6)
    return matches[0] if matches else None

class DownloadManager:
    def __init__(self, config: Dict):
        self.config = config
        if not self.config['ffmpeg_location']:
            ffmpeg_path = find_ffmpeg()
            if ffmpeg_path:
                self.config['ffmpeg_location'] = ffmpeg_path
            else:
                print_ffmpeg_instructions()
                raise FileNotFoundError("FFmpeg is required but not found. Please install FFmpeg and try again.")
        
        self.setup_logging()
        self.verify_paths()
        self.last_percentage = 0  # Initialize last_percentage
        self.valid_commands = [
            'download', 'dl', 'audio', 'video', 'help', '?', 'exit', 'quit', 'q',
            'flac', 'mp3', 'wav', 'm4a', 'list', 'sites', 'clear', 'cls'
        ]

    def setup_logging(self):
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler('download_log.txt'),
                logging.StreamHandler()
            ]
        )

    def verify_paths(self):
        if not os.path.exists(self.config['ffmpeg_location']):
            raise FileNotFoundError(f"FFMPEG not found at {self.config['ffmpeg_location']}")
        os.makedirs(self.config['video_output'], exist_ok=True)
        os.makedirs(self.config['audio_output'], exist_ok=True)

    def progress_hook(self, d):
        if d['status'] == 'downloading':
            total = d.get('total_bytes') or d.get('total_bytes_estimate', 0)
            downloaded = d.get('downloaded_bytes', 0)
            
            # Initialize progress bar if not exists
            if not hasattr(self, 'pbar'):
                self.pbar = ColorProgressBar(100, desc="Downloading")
            
            if total > 0:
                percentage = min(int((downloaded / total) * 100), 100)
                if percentage > self.last_percentage:
                    self.pbar.update(percentage - self.last_percentage)
                    self.last_percentage = percentage
                
        elif d['status'] == 'finished':
            if hasattr(self, 'pbar'):
                self.pbar.close()
                delattr(self, 'pbar')
            self.last_percentage = 0  # Reset last_percentage
            print(f"{Fore.GREEN}✓ Download Complete!{Style.RESET_ALL}")

    def verify_audio_file(self, filepath: str) -> bool:
        """Enhanced audio file verification with comprehensive FLAC checks"""
        try:
            if filepath.lower().endswith('.flac'):
                audio = FLAC(filepath)
                
                # Strict FLAC verification
                if not audio.verify():
                    logging.error("FLAC integrity check failed")
                    return False

                # Verify format-specific properties
                bit_depth = getattr(audio.info, 'bits_per_sample', 0)
                if bit_depth not in [16, 24, 32]:
                    logging.error(f"Invalid bit depth: {bit_depth}")
                    return False
                
                if audio.info.channels not in [1, 2]:
                    logging.error(f"Invalid channel count: {audio.info.channels}")
                    return False
                
                if audio.info.sample_rate not in [44100, 48000, 88200, 96000, 192000]:
                    logging.error(f"Invalid sample rate: {audio.info.sample_rate}")
                    return False

                # Additional quality checks
                minimum_bitrate = 400000  # 400kbps minimum for FLAC
                if audio.info.bits_per_sample * audio.info.sample_rate * audio.info.channels < minimum_bitrate:
                    logging.error("FLAC quality too low")
                    return False

                # Check STREAMINFO block
                if not audio.info.total_samples or not audio.info.length:
                    logging.error("Invalid FLAC stream info")
                    return False

                # Verify FLAC stream markers
                with open(filepath, 'rb') as f:
                    header = f.read(4)
                    if header != b'fLaC':
                        logging.error("Invalid FLAC signature")
                        return False

                return True
            return True  # Non-FLAC files pass

        except Exception as e:
            logging.error(f"FLAC verification error: {str(e)}")
            return False

    def convert_to_flac(self, input_file: str, output_file: str) -> bool:
        """Convert audio to FLAC with high quality settings and metadata preservation."""
        try:
            # First verify the input file
            if not self.verify_audio_file(input_file):
                raise ValueError("Input file verification failed")

            # Get original metadata and file size
            original_audio = mutagen.File(input_file)
            input_size = os.path.getsize(input_file)
            
            # Prepare FFmpeg command with progress pipe
            cmd = [
                os.path.join(self.config['ffmpeg_location'], 'ffmpeg'),
                '-i', input_file,
                '-c:a', 'flac',
                '-compression_level', '12',
                '-sample_fmt', 's32',
                '-ar', '48000',
                '-progress', 'pipe:1',
                output_file
            ]
            
            # Create progress bar
            pbar = ColorProgressBar(100, desc="Converting to FLAC")
            
            # Execute conversion with progress monitoring
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                universal_newlines=True
            )

            # Monitor conversion progress
            last_progress = 0
            while True:
                line = process.stdout.readline()
                if not line and process.poll() is not None:
                    break
                
                if 'out_time_ms=' in line:
                    try:
                        time_ms = int(line.split('=')[1])
                        progress = min(int((time_ms / 1000) / original_audio.info.length * 100), 100)
                        if progress > last_progress:
                            pbar.update(progress - last_progress)
                            last_progress = progress
                    except (ValueError, AttributeError):
                        continue

            # Close progress bar
            pbar.close()

            # Check conversion result
            if process.returncode != 0:
                raise RuntimeError(f"FFmpeg conversion failed: {process.stderr.read()}")

            # Verify and handle metadata
            if not self.verify_audio_file(output_file):
                raise ValueError("Output file verification failed")

            if original_audio and original_audio.tags:
                flac_audio = FLAC(output_file)
                for key, value in original_audio.tags.items():
                    flac_audio[key] = value
                flac_audio.save()

            # Compare files
            orig_info = mutagen.File(input_file).info
            conv_info = mutagen.File(output_file).info
            
            if abs(orig_info.length - conv_info.length) > 0.1:  # Allow 100ms difference
                raise ValueError("Duration mismatch between input and output files")

            return True

        except Exception as e:
            print(f"\n{Fore.RED}✗ Conversion Failed: {str(e)}{Style.RESET_ALL}")
            if os.path.exists(output_file):
                os.remove(output_file)
            return False

    def get_download_options(self, url: str, audio_only: bool, resolution: Optional[str] = None,
                           format_id: Optional[str] = None, filename: Optional[str] = None,
                           audio_format: str = 'mp3') -> Dict:
        output_path = self.config['audio_output'] if audio_only else self.config['video_output']
        
        options = {
            'outtmpl': os.path.join(output_path, f"{filename or '%(title)s'}.%(ext)s"),
            'ffmpeg_location': self.config['ffmpeg_location'],
            'progress_hooks': [self.progress_hook],
            'ignoreerrors': True,
            'continue': True,
            'postprocessor_hooks': [self.post_process_hook],
            'concurrent_fragment_downloads': 3,
            'no_url_cleanup': True,     # Prevent URL normalization
            'clean_infojson': False,    # Keep original URL in info JSON
            'prefer_insecure': True,    # Keep original URL scheme
        }

        if audio_only:
            options['format'] = 'bestaudio/best'
            options['extract_audio'] = True
            
            if audio_format == 'flac':
                # Two-stage conversion for highest quality FLAC
                temp_format = '%(title)s.temp.wav'
                options['postprocessors'] = [
                    {
                        'key': 'FFmpegExtractAudio',
                        'preferredcodec': 'wav',  # First convert to WAV
                        'preferredquality': '0',
                    },
                    {
                        'key': 'FFmpegMetadata',
                        'add_metadata': True,
                    },
                    # Convert WAV to high-quality FLAC
                    {
                        'key': 'ExecAfterDownload',
                        'exec_cmd': (
                            f'"{os.path.join(self.config["ffmpeg_location"], "ffmpeg")}" -i "{{}}" '
                            '-c:a flac -compression_level 12 -sample_fmt s32p '
                            '-ar 96000 -bits_per_raw_sample 24 -vn '
                            '-af "aresample=resampler=soxr:precision=28:dither_method=triangular" '
                            '-metadata encoded_by="UniversalDownloader" '
                            '"{{}}".flac && del "{{}}"'
                        )
                    }
                ]
                options['postprocessor_args'] = [
                    '-acodec', 'pcm_s32le',  # 32-bit WAV
                    '-ar', '96000',          # 96kHz sampling
                    '-bits_per_raw_sample', '32'
                ]
            else:
                # ...existing non-FLAC options...
                pass

        # ...rest of existing options...
        return options

    def post_process_hook(self, d):
        """Enhanced post-processing handler with detailed FLAC verification"""
        if d['status'] == 'started':
            print(f"\n{Fore.CYAN}Post-processing: {d.get('info_dict', {}).get('title', 'Unknown')}{Style.RESET_ALL}")
        elif d['status'] == 'finished':
            filename = d.get('filename', '')
            if filename.endswith('.flac'):
                print(f"\n{Fore.CYAN}Verifying FLAC conversion...{Style.RESET_ALL}")
                try:
                    if self.verify_audio_file(filename):
                        audio = FLAC(filename)
                        filesize = os.path.getsize(filename)
                        bitrate = (filesize * 8) / (audio.info.length * 1000)  # kbps
                        
                        print(f"\n{Fore.GREEN}✓ FLAC conversion successful:{Style.RESET_ALL}")
                        print(f"   - Sample Rate: {audio.info.sample_rate} Hz")
                        print(f"   - Bit Depth: {audio.info.bits_per_sample} bit")
                        print(f"   - Channels: {audio.info.channels}")
                        print(f"   - Duration: {int(audio.info.length // 60)}:{int(audio.info.length % 60):02d}")
                        print(f"   - Average Bitrate: {int(bitrate)} kbps")
                        print(f"   - File Size: {filesize // 1024 // 1024} MB")
                        print(f"   - Compression Level: Maximum (12)")
                        print(f"   - Format: {audio.info.pprint()}")
                    else:
                        print(f"{Fore.RED}✗ FLAC verification failed - attempting recovery...{Style.RESET_ALL}")
                        # Try to recover by reconverting
                        temp_wav = filename.replace('.flac', '.temp.wav')
                        if os.path.exists(temp_wav):
                            self.convert_to_flac(temp_wav, filename)
                except Exception as e:
                    print(f"{Fore.RED}✗ Error during FLAC verification: {str(e)}{Style.RESET_ALL}")

    def download(self, url: str, **kwargs):
        try:
            print(f"\n{Fore.CYAN}Fetching video information...{Style.RESET_ALL}")
            
            ydl_opts = {
                'outtmpl': os.path.join(
                    self.config['audio_output'] if kwargs.get('audio_only') else self.config['video_output'],
                    f"{kwargs.get('filename') or '%(title)s'}.%(ext)s"
                ),
                'ffmpeg_location': self.config['ffmpeg_location'],
                'progress_hooks': [self.progress_hook],
                'ignoreerrors': True,
                'continue': True,
                'postprocessor_hooks': [self.post_process_hook],
                'concurrent_fragment_downloads': 3,
                'no_url_cleanup': True,     # Prevent URL modification
                'clean_infojson': False,    # Keep original URL in info JSON
                'no_clean_urls': True,      # Prevent URL cleaning
                'no_check_certificate': True,
                'prefer_insecure': True,    # Keep original URL scheme
                'retries': 5,
                'fragment_retries': 5,
                'no_sanitize_url': True,    # Prevent URL sanitization
                'extract_flat': False,      # Prevent URL flattening
                'match_filter': lambda info: None if not info.get('original_url', '').lower() == url.lower() else None,  # Force exact URL matching
                'keepvideo': False,  # Remove the original webm after conversion
            }

            if kwargs.get('audio_only'):
                ydl_opts.update({
                    'format': 'bestaudio/best',
                    'extract_audio': True,
                    'audio_format': kwargs.get('audio_format', 'mp3')
                })

            # Show mode
            if kwargs.get('audio_only'):
                format_name = kwargs.get('audio_format', 'mp3').upper()
                print(f"{Fore.YELLOW}Mode: Audio Only ({format_name}){Style.RESET_ALL}")
            else:
                resolution = kwargs.get('resolution', 'best')
                print(f"{Fore.YELLOW}Mode: Video (Quality: {resolution}){Style.RESET_ALL}")

            # Reset progress bar state
            if hasattr(self, 'pbar'):
                delattr(self, 'pbar')
            self.last_percentage = 0

            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                try:
                    # Store original URL
                    original_url = url
                    
                    # Create custom info extractor to preserve URL
                    class PreserveURLIE(yt_dlp.extractor.common.InfoExtractor):
                        def _extract_webpage_url(self, *args, **kwargs):
                            return original_url

                    ydl.add_info_extractor(PreserveURLIE())
                    
                    # Extract info using exact URL
                    info = ydl.extract_info(original_url, download=False)
                    if not info:
                        raise ValueError("Could not fetch video information")
                    
                    # Show video information
                    print(f"{Fore.CYAN}Title: {info.get('title', 'Unknown')}{Style.RESET_ALL}")
                    print(f"Channel: {info.get('channel', 'Unknown')}")
                    print(f"Duration: {int(info.get('duration', 0) // 60)}:{int(info.get('duration', 0) % 60):02d}")
                    
                    # Download using exact URL
                    ydl._download_retcode = 0
                    ydl.download([original_url])
                    return True
                    
                except yt_dlp.utils.DownloadError as e:
                    print(f"{Fore.RED}Download Error: {str(e)}{Style.RESET_ALL}")
                    return False

        except Exception as e:
            logging.error(f"Error downloading {url}: {str(e)}")
            return False

    def batch_download(self, urls: List[str], **kwargs):
        with ThreadPoolExecutor(max_workers=self.config['max_concurrent']) as executor:
            futures = [executor.submit(self.download, url, **kwargs) for url in urls]
            return [f.result() for f in futures]

    def list_supported_sites(self):
        with yt_dlp.YoutubeDL() as ydl:
            print("Supported Sites:")
            print("---------------")
            for extractor in ydl._ies:
                if extractor._VALID_URL:
                    print(f"- {extractor.IE_NAME}")

    def show_menu(self):
        """Display improved menu layout"""
        print(f"\n{Fore.CYAN}╔══ Available Commands ══╗{Style.RESET_ALL}")
        print(f"{Fore.CYAN}║{Style.RESET_ALL}")
        
        # Quick Commands
        print(f"{Fore.CYAN}║ {Fore.GREEN}Quick Commands:{Style.RESET_ALL}")
        print(f"{Fore.CYAN}║{Style.RESET_ALL}   {Fore.YELLOW}Just paste URL{Style.RESET_ALL}     → Download in best quality")
        print(f"{Fore.CYAN}║{Style.RESET_ALL}   {Fore.YELLOW}URL mp3{Style.RESET_ALL}           → Download as MP3")
        print(f"{Fore.CYAN}║{Style.RESET_ALL}   {Fore.YELLOW}URL flac{Style.RESET_ALL}          → Download as FLAC")
        
        # Audio Options
        print(f"\n{Fore.CYAN}║ {Fore.GREEN}Audio Options:{Style.RESET_ALL}")
        for fmt in ['mp3', 'flac', 'wav', 'm4a']:
            print(f"{Fore.CYAN}║{Style.RESET_ALL}   {Fore.YELLOW}{fmt:4}{Style.RESET_ALL} → {self._get_format_description(fmt)}")
        
        # Video Options
        print(f"\n{Fore.CYAN}║ {Fore.GREEN}Video Quality:{Style.RESET_ALL}")
        print(f"{Fore.CYAN}║{Style.RESET_ALL}   {Fore.YELLOW}720{Style.RESET_ALL}  → HD Ready")
        print(f"{Fore.CYAN}║{Style.RESET_ALL}   {Fore.YELLOW}1080{Style.RESET_ALL} → Full HD")
        print(f"{Fore.CYAN}║{Style.RESET_ALL}   {Fore.YELLOW}2160{Style.RESET_ALL} → 4K")
        
        # Help & Exit
        print(f"\n{Fore.CYAN}║ {Fore.GREEN}Other Commands:{Style.RESET_ALL}")
        print(f"{Fore.CYAN}║{Style.RESET_ALL}   {Fore.YELLOW}help{Style.RESET_ALL} or {Fore.YELLOW}?{Style.RESET_ALL}  → Show this menu")
        print(f"{Fore.CYAN}║{Style.RESET_ALL}   {Fore.YELLOW}clear{Style.RESET_ALL}      → Clear screen")
        print(f"{Fore.CYAN}║{Style.RESET_ALL}   {Fore.YELLOW}exit{Style.RESET_ALL}       → Exit program")
        print(f"{Fore.CYAN}╚{'═' * 22}╝{Style.RESET_ALL}\n")

    def _get_format_description(self, fmt):
        descriptions = {
            'mp3': 'High quality MP3 (320kbps)',
            'flac': 'Lossless audio (best quality)',
            'wav': 'Uncompressed audio',
            'm4a': 'AAC audio (good quality)'
        }
        return descriptions.get(fmt, '')

    def interactive_mode(self):
        print_banner()
        self.show_menu()
        
        while True:
            try:
                user_input = input(f"\n{Fore.GREEN}→ {Style.RESET_ALL}").strip()
                # Split without forcing lowercase
                raw_args = user_input.split()
                if not raw_args:
                    continue
                
                # Lowercase only the first token (command) to detect help/exit/etc.
                cmd = raw_args[0].lower()

                if cmd in ['clear', 'cls']:
                    os.system('cls' if os.name == 'nt' else 'clear')
                    print_banner()
                    continue

                if cmd in ['help', '?', 'h']:
                    self.show_menu()
                    continue

                if cmd in ['exit', 'quit', 'q']:
                    print(f"\n{Fore.YELLOW}Thanks for using Universal Downloader!{Style.RESET_ALL}")
                    break

                # If the first token looks like a URL
                if '://' in raw_args[0]:
                    url = raw_args[0]  # Preserve exact case
                    options = self._parse_smart_options(raw_args[1:])
                    
                    # Show spinner during download
                    spinner = SpinnerAnimation("Downloading")
                    spinner.start()
                    try:
                        success = self.download(url, **options)
                    finally:
                        spinner.stop()
                    
                    if success:
                        print(f"\n{Fore.GREEN}✓ Download complete!{Style.RESET_ALL}")
                else:
                    # Try to find similar command
                    matched_cmd = fuzzy_match_command(cmd, self.valid_commands)
                    if matched_cmd:
                        print(f"{Fore.YELLOW}Did you mean '{matched_cmd}'?{Style.RESET_ALL}")
                    self.show_menu()

            except KeyboardInterrupt:
                print(f"\n{Fore.YELLOW}Operation cancelled{Style.RESET_ALL}")
            except Exception as e:
                print(f"\n{Fore.RED}Error: {str(e)}{Style.RESET_ALL}")

    def _parse_smart_options(self, args):
        """Enhanced smart option parsing"""
        # Convert each argument to lowercase only for format checks
        args_lower = [a.lower() for a in args]
        options = {
            'audio_only': False,
            'resolution': None,
            'audio_format': 'mp3',  # Default format
            'preserve_url': True  # Add this option
        }

        # Parse audio format first
        if 'mp3' in args_lower:
            options['audio_format'] = 'mp3'
            options['audio_only'] = True
        elif 'flac' in args_lower:
            options['audio_format'] = 'flac'
            options['audio_only'] = True
        elif 'wav' in args_lower:
            options['audio_format'] = 'wav'
            options['audio_only'] = True
        elif 'm4a' in args_lower:
            options['audio_format'] = 'm4a'
            options['audio_only'] = True

        # Parse resolution
        for res in ['720', '1080', '2160']:
            if res in args_lower:
                options['resolution'] = res
                break

        return options

def load_config() -> Dict:
    try:
        with open(CONFIG_FILE, 'r') as f:
            return {**DEFAULT_CONFIG, **json.load(f)}
    except FileNotFoundError:
        with open(CONFIG_FILE, 'w') as f:
            json.dump(DEFAULT_CONFIG, f, indent=4)
        return DEFAULT_CONFIG

def main():
    # If no arguments provided, run in interactive mode directly
    if len(sys.argv) == 1:
        config = load_config()
        manager = DownloadManager(config)
        manager.interactive_mode()
        sys.exit(0)
        
    # Rest of argument parsing for advanced usage
    parser = argparse.ArgumentParser(
        description="Universal Downloader - Download videos and audio from hundreds of websites including YouTube, Vimeo, Twitter, TikTok, Instagram, Twitch, and more!",
        formatter_class=CustomHelpFormatter,
        epilog=EXAMPLES,
    )

    # URL input group (mutually exclusive)
    url_group = parser.add_mutually_exclusive_group(required=True)
    url_group.add_argument(
        '--url',
        help="URL to download"
    )
    url_group.add_argument(
        'urls',
        nargs='*',
        help="One or more URLs to download (space-separated)",
        default=[]
    )

    # Add list-sites option
    parser.add_argument(
        '--list-sites',
        action='store_true',
        help="List all supported sites"
    )
    
    # Required arguments group
    required = parser.add_argument_group('Required Arguments')

    # Download options group
    download_opts = parser.add_argument_group('Download Options')
    download_opts.add_argument(
        '--resolution',
        help="Maximum video resolution (e.g., 720, 1080). If not specified, downloads best quality available",
        metavar="RES"
    )
    download_opts.add_argument(
        '--audio-only',
        action='store_true',
        help="Download audio only (default format: MP3)"
    )
    download_opts.add_argument(
        '--audio-format',
        default='mp3',
        choices=['mp3', 'flac', 'wav', 'm4a'],
        help="Audio format when using --audio-only"
    )

    # Advanced options group
    advanced.add_argument(
        '--format-id',
        help="Specific format ID for download (advanced users)",
        metavar="FMT"
    )
    advanced.add_argument(
        '--filename',
        help="Custom filename without extension",
        metavar="NAME"
    )
    advanced.add_argument(
        '--output-dir',
        help="Custom output directory path",
        metavar="DIR"
    )

    # Add version info
    parser.add_argument(
        '--version',
        action='version',
        version='Universal Downloader v1.1.0'
    )

    # Add interactive mode option
    parser.add_argument(
        '--interactive',
        action='store_true',
        help="Run in interactive mode (enter URLs one by one, --Q to quit)"
    )

    args = parser.parse_args()

    # Show supported sites if requested
    if args.list_sites:
        DownloadManager(load_config()).list_supported_sites()
        sys.exit(0)

    # Show full help if no arguments provided
    if len(sys.argv) == 1:
        parser.print_help()
        sys.exit(1)

    config = load_config()
    
    if args.output_dir:
        config['video_output'] = args.output_dir
        config['audio_output'] = args.output_dir

    manager = DownloadManager(config)

    # Handle interactive mode
    if args.interactive:
        manager.interactive_mode()
        sys.exit(0)

    # Combine --url and positional urls
    all_urls = [args.url] if args.url else args.urls
    
    if len(all_urls) == 1:
        success = manager.download(
            all_urls[0],
            audio_only=args.audio_only,
            resolution=args.resolution,
            format_id=args.format_id,
            filename=args.filename,
            audio_format=args.audio_format
        )
    else:
        successes = manager.batch_download(
            all_urls,
            audio_only=args.audio_only,
            resolution=args.resolution,
            format_id=args.format_id,
            audio_format=args.audio_format
        )
        success = all(successes)

    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()
