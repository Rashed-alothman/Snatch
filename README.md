# Universal Downloader

A powerful and user-friendly tool to download videos and audio from various platforms including YouTube, Vimeo, Twitter, TikTok, Instagram, Twitch, and more!

## Features

- 🎥 Download videos from multiple platforms
- 🎵 Extract audio in MP3/FLAC/WAV formats
- 📱 Support for various video qualities
- 📂 Custom output directory support
- 🚀 Concurrent downloads
- 🎨 Beautiful progress bars
- 🛠 Built-in FFmpeg setup

## Installation Guide

### Step 1: Download FFmpeg (Required)

**Automatic Installation (Recommended)**

1. After downloading this tool, just run:

```bash
python setup_ffmpeg.py
```

**Manual Installation (Alternative)**

1. Visit FFmpeg Builds: [https://github.com/BtbN/FFmpeg-Builds/releases/latest](https://github.com/BtbN/FFmpeg-Builds/releases/latest)
2. Download: `ffmpeg-master-latest-win64-gpl.zip`
3. Extract the ZIP file to `C:\ffmpeg`
4. The final path should look like: `C:\ffmpeg\ffmpeg-master-latest-win64-gpl\bin`

**Using Package Managers**

- Windows Chocolatey:

```bash
choco install ffmpeg
```

- Windows Winget:

```bash
winget install ffmpeg
```

### Step 2: Install Python

1. Download Python (3.7 or later): [https://www.python.org/downloads/](https://www.python.org/downloads/)
2. During installation, ✅ CHECK "Add Python to PATH"
3. Verify installation:

```bash
python --version
```

### Step 3: Get Universal Downloader

**Quick Download**

1. Download ZIP: [Universal-downloader Latest Release]()
2. Extract the ZIP file
3. Open Command Prompt in the extracted folder

### Step 4: Setup Environment

Run these commands in order:

```bash
# 1. Create virtual environment
python -m venv venv

# 2. Activate it (choose one):
venv\Scripts\activate        # For CMD
.\venv\Scripts\Activate.ps1  # For PowerShell

# 3. Install requirements
pip install -r requirements.txt
```

### Step 5: Test Installation

```bash
# Test if everything works
python UniversalDownloader.py --version
```

### Quick Start Guide

Download your first video:

```bash
# Download video
python UniversalDownloader.py "https://youtube.com/watch?v=example"

# Download audio only
python UniversalDownloader.py "https://youtube.com/watch?v=example" --audio-only
```

### Need Help?

If you see "FFmpeg not found" error:

1. Run `python setup_ffmpeg.py` (recommended)
2. Or follow the manual FFmpeg installation steps above
3. Still having issues? Check the Troubleshooting section below

### Common Installation Issues

1. **Python Not Found**

   - Make sure Python is added to PATH during installation
   - Download Python from [python.org](https://python.org)

2. **pip Not Found**

   - Run: `python -m ensurepip --upgrade`
   - Or download: `get-pip.py` from [pip documentation](https://pip.pypa.io)

3. **Permission Errors**

   - Run Command Prompt as Administrator
   - Check antivirus settings
   - Ensure write permissions in installation directory

4. **FFmpeg Setup Fails**

   - Try manual FFmpeg installation:
     1. Download from [FFmpeg official site](https://ffmpeg.org/download.html)
     2. Extract to C:\ffmpeg
     3. Add C:\ffmpeg\bin to system PATH
     4. Update config.json with correct path

5. **SSL Errors**
   - Update Python to latest version
   - Install required certificates: `pip install --upgrade certifi`

## Usage

### Basic Examples

1. Download a video:

```bash
python UniversalDownloader.py "https://youtube.com/watch?v=example"
```

2. Download audio only (MP3):

```bash
python UniversalDownloader.py "https://youtube.com/watch?v=example" --audio-only
```

3. Download in specific resolution:

```bash
python UniversalDownloader.py "https://youtube.com/watch?v=example" --resolution 1080
```

### Advanced Usage

- Download multiple videos:

```bash
python UniversalDownloader.py "URL1" "URL2" "URL3"
```

- Download audio in FLAC format:

```bash
python UniversalDownloader.py "URL" --audio-only --audio-format flac
```

- Custom output directory:

```bash
python UniversalDownloader.py "URL" --output-dir "path/to/directory"
```

## Configuration

The config.json file contains settings for:

- FFmpeg location
- Default output directories
- Maximum concurrent downloads

## Supported Sites

- YouTube
- Vimeo
- Twitter
- TikTok
- Instagram
- Twitch
- SoundCloud
- And hundreds more!

To see all supported sites:

```bash
python UniversalDownloader.py --list-sites
```

## Troubleshooting

1. FFmpeg not found:

   - Run `python setup_ffmpeg.py` to automatically install FFmpeg
   - Or manually install FFmpeg and update config.json

2. SSL Errors:

   - Update Python and yt-dlp: `pip install -U yt-dlp`

3. Permission Errors:
   - Run with administrator privileges
   - Check folder permissions

## Requirements

- Python 3.7+
- FFmpeg
- See requirements.txt for Python packages

## License

MIT License - Feel free to use and modify!

## Contributing

1. Fork the repository
2. Create your feature branch
3. Commit your changes
4. Push to the branch
5. Create a Pull Request

## Credits

- Built with [yt-dlp](https://github.com/yt-dlp/yt-dlp)
- Uses [FFmpeg](https://ffmpeg.org/) for media processing
