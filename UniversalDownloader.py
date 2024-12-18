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
-------------
1. FFMPEG not found: Install FFMPEG and update config.json
2. SSL Error: Update Python and yt-dlp
3. Permission Error: Run with admin privileges
"""

CONFIG_FILE = 'config.json'
DEFAULT_CONFIG = {
    'ffmpeg_location': r'C:\ffmpeg\ffmpeg-master-latest-win64-gpl\bin',
    'video_output': str(Path.home() / 'Videos'),
    'audio_output': str(Path.home() / 'Music'),
    'max_concurrent': 3
}

class DownloadManager:
    def __init__(self, config: Dict):
        self.config = config
        self.setup_logging()
        self.verify_paths()

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
            if total > 0:
                percentage = (downloaded / total) * 100
                sys.stdout.write(f"\rDownloading: {percentage:.1f}% of {total/1024/1024:.1f}MB")
                sys.stdout.flush()
        elif d['status'] == 'finished':
            print("\nDownload completed!")

    def get_download_options(self, url: str, audio_only: bool, resolution: Optional[str] = None,
                           format_id: Optional[str] = None, filename: Optional[str] = None,
                           audio_format: str = 'mp3') -> Dict:
        output_path = self.config['audio_output'] if audio_only else self.config['video_output']
        
        # Extract nested conditional into separate format_option
        if audio_only:
            format_option = 'bestaudio/best'
        elif resolution:
            format_option = f'bestvideo[height<={resolution}]+bestaudio/best'
        else:
            format_option = 'best'
        
        options = {
            'format': format_option,
            'outtmpl': os.path.join(output_path, f"{filename or '%(title)s'}.%(ext)s"),
            'ffmpeg_location': self.config['ffmpeg_location'],
            'progress_hooks': [self.progress_hook],
            'ignoreerrors': True,
            'continue': True,
            'format_sort': ['res:1080', 'ext:mp4:m4a'],
            'concurrent_fragment_downloads': 3,
        }

        if audio_only:
            options['postprocessors'] = [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': audio_format,
                'preferredquality': '0',
            }]

        if format_id:
            options['format'] = format_id

        return options

    def download(self, url: str, **kwargs):
        try:
            with yt_dlp.YoutubeDL(self.get_download_options(url, **kwargs)) as ydl:
                ydl.download([url])
            return True
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

def load_config() -> Dict:
    try:
        with open(CONFIG_FILE, 'r') as f:
            return {**DEFAULT_CONFIG, **json.load(f)}
    except FileNotFoundError:
        with open(CONFIG_FILE, 'w') as f:
            json.dump(DEFAULT_CONFIG, f, indent=4)
        return DEFAULT_CONFIG

def main():
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
        help="Video resolution (e.g., 720, 1080). Default: best available",
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
    advanced = parser.add_argument_group('Advanced Options')
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
        version='Universal Downloader v1.0.0'
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
