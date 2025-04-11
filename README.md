<p align="center">
   <img src="https://github.com/Rashed-alothman/Snatch/blob/main/main/assets/logo.png" alt="Snatch Logo" width="350" />
 </p>
 
<h1 align="center">Snatch</h1>
<h3 align="center">Download Anything, Anywhere, Anytime</h3>

<p align="center">
  <a href="#features">Features</a> •
  <a href="#installation">Installation</a> •
  <a href="#quick-start">Quick Start</a> •
  <a href="#usage">Usage</a> •
  <a href="#supported-sites">Supported Sites</a> •
  <a href="#troubleshooting">Troubleshooting</a>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/version-1.7.0-blue" alt="Version 1.7.0" />
  <img src="https://img.shields.io/badge/python-3.7+-yellow" alt="Python 3.7+" />
  <img src="https://img.shields.io/badge/platforms-Windows%20|%20macOS%20|%20Linux-green" alt="Platforms" />
  <img src="https://img.shields.io/badge/license-MIT-orange" alt="License" />
</p>


<h2> What's New in v1.7.0</h2>

- **Smart Format Selection**: Automatically selects optimal formats without testing all possibilities
- **Network Speed Testing**: Optimizes download settings based on your connection speed
- **Advanced Temp File Management**: Better handling of locked files and cleanup of orphaned fragments
- **Performance Improvements**: Faster startup times and more efficient downloads
- **Enhanced User Experience**: Better progress displays and more intuitive interface
- **Improved Error Handling**: More robust error recovery and clearer error messages


## 🚀 Overview

**Snatch** is a powerful and user-friendly media downloader that lets you grab videos, audio, and more from hundreds of websites in various formats and qualities. With its sleek interface and powerful features, downloading media has never been easier or more satisfying!

<h2 id="features">✨ Features</h2>

- **Beautiful Interactive Mode** - Easy-to-use interface with colorful progress bars
- **Dynamic Resource Management** - Adaptive chunk sizes based on your system's resources
- **Site Explorer** - Browse and search through 1000+ supported sites
- **Advanced Audio Options** - Choose between Opus (default), MP3, FLAC formats and stereo/surround sound
- **Smart Conversion** - High-quality audio extraction with format options
- **Concurrent Downloads** - Download multiple files simultaneously
- **Quality Selection** - Choose specific video resolutions
- **Playlist Support** - Download entire playlists with options to select specific videos
- **Cache System** - Optimized repeat downloads with smart caching
- **Error Recovery** - Robust error handling and helpful suggestions
- **Format Flexibility** - Video, Opus, MP3, FLAC, WAV, and more
- **Universal Compatibility** - Works on Windows, macOS, and Linux
- **Automatic File Organization** - Organize downloads based on metadata
- **Resume Downloads** - Continue interrupted downloads from where they left off
- **Download Statistics** - Track and display download performance metrics
- **aria2c Support** - Optional high-speed download engine for better performance
- **Network Speed Testing** - Automatically optimize settings based on your connection speed
- **Smart Format Selection** - Intelligently selects best format without testing all possibilities
- **Temporary File Management** - Advanced handling of temporary files to prevent disk space waste

<h2 id="Installation">🔧 Installation</h2>

### One-Click Setup (Recommended)

Run this single command to set up everything automatically:

```bash
python setup.py
```

This will:

1. Install all dependencies
2. Set up FFmpeg automatically
3. Create convenient launcher files
4. Verify your installation

### Manual Installation

#### Step 1: Requirements

- Python 3.7 or newer
- FFmpeg (auto-installed by setup script)

#### Step 2: Install Dependencies

```bash
pip install -r requirements.txt
```

#### Step 3: FFmpeg Setup (if needed)

```bash
python setup_ffmpeg.py
```

<h2 id="quick-start">🏃‍♀️ Quick Start</h2>

### Using the Interactive Mode (Easiest)

Launch Snatch in interactive mode:

```bash
python Snatch.py --interactive
```

Or simply double-click **Snatch.bat** (Windows) / **snatch.sh** (macOS/Linux)

### Direct Command Examples

```bash
# Download video in best quality
python Snatch.py "https://youtube.com/watch?v=example"

# Download audio only (Opus format by default)
python Snatch.py "https://youtube.com/watch?v=example" --audio-only

# Download audio in MP3 format
python Snatch.py "https://youtube.com/watch?v=example" --audio-only --audio-format mp3

# Download audio in FLAC format
python Snatch.py "https://youtube.com/watch?v=example" --audio-only --audio-format flac

# Download in specific resolution
python Snatch.py "https://youtube.com/watch?v=example" --resolution 1080

# Specify audio channels (2=stereo, 8=7.1 surround)
python Snatch.py "https://youtube.com/watch?v=example" --audio-only --audio-channels 8

# Resume an interrupted download
python Snatch.py "https://youtube.com/watch?v=example" --resume

# Use aria2c for faster downloads
python Snatch.py "https://youtube.com/watch?v=example" --aria2c

# Show download statistics when finished
python Snatch.py "https://youtube.com/watch?v=example" --stats

# See detailed logs for troubleshooting
python Snatch.py "https://youtube.com/watch?v=example" --verbose
```

<h2 id="Usage">💻 Usage</h2>

### Interactive Mode Commands

When in interactive mode, you can use these commands:

| Command                 | Description                           |
| ----------------------- | ------------------------------------- |
| `help` or `?`           | Show help and all available commands  |
| `URL`                   | Download media in best quality        |
| `URL opus`              | Download audio in Opus format         |
| `URL mp3`               | Download audio in MP3 format          |
| `URL flac`              | Download audio in FLAC format         |
| `URL 720` or `URL 1080` | Download video in specific resolution |
| `list` or `sites`       | Show all supported sites              |
| `clear`                 | Clear the screen                      |
| `exit` or `quit`        | Exit the application                  |

<h2 id="Advanced Features">Advanced Features</h2>
<h4> 1. Playlist Downloads</h4>

When downloading a playlist, Snatch will present options to:

- Download the entire playlist
- Download only the first few videos
- Select specific videos to download

#### 2. Batch Downloads

Download multiple URLs at once:

```bash
python Snatch.py "URL1" "URL2" "URL3"
```

#### 3. Custom Output Directory

```bash
python Snatch.py "URL" --output-dir "path/to/directory"
```

#### 4. Format Specification

```bash
python Snatch.py "URL" --format-id 137+140  # For advanced users
```

#### 5. Automatic File Organization

Snatch can automatically organize your downloaded files based on metadata extracted from the media. This creates a clean folder structure for your library.

Enable organization with:

```bash
python Snatch.py --organize URL
```

Or set it permanently in the configuration:

```bash
python setup_ffmpeg.py
```

#### Organization Templates

You can customize how files are organized using templates in the config:

- Audio: `{uploader}/{album}/{title}`
- Video: `{uploader}/{year}/{title}`
- Podcast: `Podcasts/{uploader}/{year}-{month}/{title}`
- Audiobook: `Audiobooks/{uploader}/{title}`

Available variables include:

- `{title}` - Media title
- `{uploader}` - Channel or uploader name
- `{album}` - Album name (for music)
- `{artist}` - Artist name
- `{year}` - Release year
- `{month}` - Release month
- `{day}` - Release day
- `{track_number}` - Track number

#### 6. Advanced Audio Options

Snatch now offers enhanced audio conversion options:

- **Default Format**: Opus audio format (superior quality-to-size ratio)
- **Channel Configuration**:
  - Interactive prompt to choose between stereo (2.0) and surround sound (7.1)
  - Command-line option: `--audio-channels 2` (stereo) or `--audio-channels 8` (7.1)
- **Format Options**:
  - Opus: `--audio-format opus` (default, excellent quality at smaller file sizes)
  - MP3: `--audio-format mp3` (maximum compatibility)
  - FLAC: `--audio-format flac` (lossless audio)
  - WAV: `--audio-format wav` (uncompressed)
  - M4A: `--audio-format m4a` (AAC audio)

```bash
# Download with 7.1 surround sound in Opus format
python Snatch.py "URL" --audio-only --audio-channels 8

# Skip interactive prompts (useful for scripting)
python Snatch.py "URL" --audio-only --non-interactive
```

#### 7. Advanced Command-line Options

Snatch supports several advanced options for more control over your downloads:

```bash
# Resume interrupted downloads
python Snatch.py "URL" --resume

# Show download statistics after completion
python Snatch.py "URL" --stats

# Display system resource statistics
python Snatch.py "URL" --system-stats

# Skip using cached media information
python Snatch.py "URL" --no-cache

# Disable automatic retry logic
python Snatch.py "URL" --no-retry

# Limit download speed (e.g., 2M = 2MB/s)
python Snatch.py "URL" --throttle 2M

# Use aria2c as the download engine for better performance
python Snatch.py "URL" --aria2c

# Enable detailed logging for troubleshooting
python Snatch.py "URL" --verbose

# Test all available formats for best quality (slower)
python Snatch.py "URL" --test-formats

# Use fast format selection (default)
python Snatch.py "URL" --fast
```

#### 8. Network Speed Testing

Snatch can automatically test your network speed to optimize download settings:

```bash
# Run a standalone speed test
python Snatch.py speedtest

# Get detailed speed test results
python Snatch.py test
```

<h2 id="supported-sites">🌎 Supported Sites</h2>
Snatch supports over 1000 websites including:

- YouTube
- Vimeo
- Twitter/X
- Instagram
- TikTok
- Facebook
- Twitch
- SoundCloud
- Reddit
- Daily Motion
- And many more!

To see the full list of supported sites:

```bash
python Snatch.py --list-sites
```

<h2 id="Troubleshooting">🔍 Troubleshooting</h2>

<h3>Common Issues</h3>

1. **FFmpeg not found**

   ```bash
   python setup_ffmpeg.py  # Run this to fix automatically
   ```

2. **SSL Errors**

   - Update Python and dependencies:

   ```bash
   pip install -U yt-dlp requests
   ```

3. **Permission Errors**

   - Run as administrator (Windows)
   - Use sudo (Linux/macOS)

4. **Slow Downloads**
   - Check your internet connection
   - Try with `--aria2c` for faster downloading
   - Use `--http-chunk-size 10485760` for larger chunks

### Need Help?

If you're still having issues:

- Check the logs in download_log.txt
- Run with `--verbose` for detailed output
- Try `--system-stats` to check if your system has enough resources

<h2 id="Contributing"> 🤝 Contributing</h2>
Contributions are welcome! Feel free to:

- Report bugs
- Suggest new features
- Submit pull requests

## 📜 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 📊 System Requirements

- **Minimum**: 2GB RAM, 1GHz CPU, 100MB free space
- **Recommended**: 4GB RAM, 2GHz dual-core CPU, 500MB free space

## 🙏 Acknowledgements

- Built with [yt-dlp](https://github.com/yt-dlp)
- Uses [FFmpeg](https://ffmpeg.org/) for media processing

---

<p align="center">
Made with ❤️ by <a href="https://github.com/Rashed-alothman">Rashed Alothman</a>
</p>
````
