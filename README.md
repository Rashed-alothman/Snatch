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

```
python --version
```

### Step 2: Get Snatch

1. Download ZIP: [Snatch Latest Release]()
2. Extract the ZIP file
3. Open Command Prompt in the extracted folder

### Step 3: Setup Environment

Run these commands in order:

```
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

```
python setup_ffmpeg.py
```

**Manual Installation (Alternative)**

1. Visit FFmpeg Builds: [https://github.com/BtbN/FFmpeg-Builds/releases/latest](https://github.com/BtbN/FFmpeg-Builds/releases/latest)
2. Download: `ffmpeg-master-latest-win64-gpl.zip`
3. Extract the ZIP file to `C:\ffmpeg`
4. The final path should look like: `C:\ffmpeg\ffmpeg-master-latest-win64-gpl\bin`

**Using Package Managers**

- Windows Chocolatey:

```
choco install ffmpeg
```

- Windows Winget:

```
winget install ffmpeg
```

### Step 5: Test Installation

```
# Test if everything works
python Snatch.py --test
```

### to see the version of the application

Run this command to see the version of the application:

1. Command Prompt: python Snatch.py --version

### Quick Start Guide

Run Snatch in interactive mode:

```
python Snatch.py
```

Then follow on-screen prompts to download videos or audio.

Alternatively, you can pass a URL directly:

```
python Snatch.py "https://youtube.com/watch?v=example"
```

Download your first video:

```
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

1. Start the App and Enter URLs Interactively:

   - Launch using:
     ```
     python Snatch.py
     ```
   - [Insert your interactive mode banner image here]
   - In interactive mode, simply paste a URL to download in best quality.

2. Quick Commands (Direct Execution):
   - You can also download without entering interactive mode. Just run:
     ```
     python Snatch.py "https://youtube.com/watch?v=example"
     ```
   - To download in a specific format or video quality, append the keyword or number:
     - For audio as MP3:
       ```
       python Snatch.py "https://youtube.com/watch?v=example" mp3
       ```
     - For high-quality FLAC audio:
       ```
       python Snatch.py "https://youtube.com/watch?v=example" flac
       ```
     - For a specific video resolution (e.g., 1080p):
       ```
       python Snatch.py "https://youtube.com/watch?v=example" 1080
       ```

### Advanced Usage

- In interactive mode, you have the flexibility to control downloads by simply typing commands:
  - Just the URL → Downloads the media in best quality.
  - URL followed by an audio format (mp3, flac, wav, or m4a) → Downloads audio in the specified format.
  - URL followed by a resolution (720, 1080, 2160) → Downloads video in that quality.
- You can use these Quick Commands directly from the terminal without entering interactive mode:
  ```
  python Snatch.py "https://vimeo.com/example" flac
  python Snatch.py "https://youtube.com/watch?v=example" 1080
  ```
- This approach lets users download the video or audio in the desired format or quality with a single command line call.

1. Multiple Videos at Once:

```
# Start interactive mode and paste multiple URLs:
→ https://youtube.com/watch?v=example1
→ https://youtube.com/watch?v=example2
→ https://youtube.com/watch?v=example3
```

2. Mixed Format Batch Downloads:

```
# Download multiple items with different formats:
 → python Snatch.py https://youtube.com/watch?v=example1 mp3 + https://youtube.com/watch?v=example2 flac + https://youtube.com/watch?v=example3 1080 + https://youtube.com/watch?v=example4 720
```

3. Playlist Downloads:

# Download entire playlist in specific format:

→ https://youtube.com/playlist?list=example mp3 # All as MP3
→ https://youtube.com/playlist?list=example flac # All as FLAC
→ https://youtube.com/playlist?list=example 1080 # All in 1080p

```

4. Quick Batch Commands:

```

# Download multiple videos in best quality

→ https://youtube.com/watch?v=ex1 + https://youtube.com/watch?v=ex2

# Download multiple audio files

→ https://youtube.com/watch?v=ex1 mp3 + https://youtube.com/watch?v=ex2 flac

# Mix video and audio downloads

→ https://youtube.com/watch?v=ex1 1080 + https://youtube.com/watch?v=ex2 mp3

````
5. Utility Commands:

```bash
# While in interactive mode:
→ help    # Show all commands
→ clear   # Clear screen
→ exit    # Exit program
````

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

```

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
```
