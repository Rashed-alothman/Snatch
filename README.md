# Snatch

## Overview

Snatch is a powerful and user-friendly tool for downloading media content from various online platforms. With support for multiple sites, high-quality audio extraction, and flexible output formats, Snatch makes it easy to download videos and audio from your favorite websites.

## Features

- 🎥 Download videos from multiple platforms
- 🎵 Extract audio in MP3/FLAC/WAV formats
- 📱 Support for various video qualities
- 📂 Custom output directory support
- 🚀 Concurrent downloads
- 🎨 Beautiful progress bars
- 🛠 Built-in FFmpeg setup

## Version

1.1.0

## Changelog

- 22 incremental updates improving stability, FLAC downloads, and more.

## Installation Guide

### Step 1: Install Python

1. Download Python (3.7 or later): [https://www.python.org/downloads/](https://www.python.org/downloads/)
2. During installation, ✅ CHECK "Add Python to PATH"
3. Verify installation:

```bash
python --version
```

making sure the pip is installed 
```bash
python -m ensurepip --upgrade
```

### Step 2: Get Snatch

1. Download ZIP: [Snatch Latest Release]()
2. Extract the ZIP file
3. Open Command Prompt in the extracted folder

### Step 3: Setup Environment

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

### Step 4: Download FFmpeg (Required)

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

### Step 5: Test Installation

```bash
# Test if everything works
python Snatch.py --test
```

### to see the version of the application

Run this command to see the version of the application:
```bash
 python Snatch.py --version
```
### Quick Start Guide

Run Snatch in interactive mode:

```bash
python Snatch.py
```

Then follow on-screen prompts to download videos or audio.

Alternatively, you can pass a URL directly:

```bash
python Snatch.py "https://youtube.com/watch?v=example"
```

Download your first video:

```bash
# Download video
python Snatch.py "https://youtube.com/watch?v=example"

# Download audio only
python Snatch.py "https://youtube.com/watch?v=example" --audio-only
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

1. Start the app and enter URLs interactively (Recommended):

```bash
python Snatch.py
```

After starting, you can:

- Simply paste any URL and press Enter for default video download
- Type "URL mp3" for MP3 audio download
- Type "URL flac" for high-quality FLAC audio
- Type "URL 1080" for 1080p video quality
- Type "help" or "?" to see all commands

Example interactive session:

```
→ https://youtube.com/watch?v=example
Downloading video in best quality...

→ https://youtube.com/watch?v=example mp3
Downloading as MP3...

→ https://youtube.com/watch?v=example flac
Downloading as FLAC...
```

2. Quick Commands in Interactive Mode:

```bash
# Just paste URL → Downloads in best quality
→ https://youtube.com/watch?v=example

# Add 'mp3' after URL → Downloads audio as MP3
→ https://youtube.com/watch?v=example mp3

# Add 'flac' → Downloads high-quality FLAC audio
→ https://youtube.com/watch?v=example flac

# Add resolution → Downloads specific quality
→ https://youtube.com/watch?v=example 1080
```

### Advanced Usage

1. Audio Features:

```bash
# Start interactive mode and use these commands:

# High-quality FLAC audio
→ https://example.com/video flac

# Multiple audio formats supported
→ https://example.com/video mp3    # MP3 format
→ https://example.com/video wav    # WAV format
→ https://example.com/video m4a    # M4A format
```

2. Video Quality Options:

```bash
# In interactive mode:

# Specific resolutions
→ https://example.com/video 720    # HD Ready
→ https://example.com/video 1080   # Full HD
→ https://example.com/video 2160   # 4K

# Best quality (default)
→ https://example.com/video best
```

3. Platform-Specific Features:

```bash
# Works with multiple platforms:
→ https://youtube.com/watch?v=...    # YouTube videos
→ https://vimeo.com/...             # Vimeo content
→ https://twitter.com/.../status/... # Twitter videos
→ https://www.tiktok.com/@user/...   # TikTok videos
→ https://www.instagram.com/p/...    # Instagram posts
→ https://clips.twitch.tv/...        # Twitch clips
```

4. Batch Operations:

```bash
# Download multiple URLs (paste multiple lines):
→ https://youtube.com/watch?v=example1
→ https://youtube.com/watch?v=example2
→ https://vimeo.com/example3

# Mix formats in batch:
→ https://example.com/video1 mp3
→ https://example.com/video2 flac
→ https://example.com/video3 1080
```

5. Utility Commands:

```bash
# While in interactive mode:
→ help    # Show all commands
→ clear   # Clear screen
→ exit    # Exit program
```

### Batch Download Examples

1. Multiple Videos at Once:

```bash
# Start interactive mode and paste multiple URLs:
→ https://youtube.com/watch?v=example1
→ https://youtube.com/watch?v=example2
→ https://youtube.com/watch?v=example3
```

2. Mixed Format Batch Downloads:

```bash
# Download multiple items with different formats:
→ https://youtube.com/watch?v=example1 mp3
→ https://youtube.com/watch?v=example2 flac
→ https://youtube.com/watch?v=example3 1080
→ https://youtube.com/watch?v=example4 720
```

3. Playlist Downloads:

```bash
# Download entire playlist in specific format:
→ https://youtube.com/playlist?list=example mp3    # All as MP3
→ https://youtube.com/playlist?list=example flac   # All as FLAC
→ https://youtube.com/playlist?list=example 1080   # All in 1080p
```

4. Quick Batch Commands:

```bash
# Download multiple videos in best quality
→ https://youtube.com/watch?v=ex1 + https://youtube.com/watch?v=ex2

# Download multiple audio files
→ https://youtube.com/watch?v=ex1 mp3 + https://youtube.com/watch?v=ex2 flac

# Mix video and audio downloads
→ https://youtube.com/watch?v=ex1 1080 + https://youtube.com/watch?v=ex2 mp3
```

5. Using Text File Input:

```bash
# Create urls.txt with URLs and formats:
→ load urls.txt

# Example urls.txt content:
https://youtube.com/watch?v=example1 mp3
https://youtube.com/watch?v=example2 flac
https://youtube.com/watch?v=example3 1080
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
python Snatch.py --list-sites
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
