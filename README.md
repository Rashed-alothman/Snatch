<p align="center">
  <img src="https://raw.githubusercontent.com/Rashed-alothman/Snatch/main/assets/logo.png" alt="Snatch Logo" width="200" />
</p>

<h1 align="center">🐍 Snatch 🎬</h1>
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
  <img src="https://img.shields.io/badge/version-1.3.0-blue" alt="Version 1.3.0" />
  <img src="https://img.shields.io/badge/python-3.7+-yellow" alt="Python 3.7+" />
  <img src="https://img.shields.io/badge/platforms-Windows%20|%20macOS%20|%20Linux-green" alt="Platforms" />
  <img src="https://img.shields.io/badge/license-MIT-orange" alt="License" />
</p>

## 🚀 Overview

**Snatch** is a powerful and user-friendly media downloader that lets you grab videos, audio, and more from hundreds of websites in various formats and qualities. With its sleek interface and powerful features, downloading media has never been easier or more satisfying!

<h2 id="features">✨ Features</h2>

- 🌈 **Beautiful Interactive Mode** - Easy-to-use interface with colorful progress bars
- 🎭 **Dynamic Resource Management** - Adaptive chunk sizes based on your system's resources
- 📋 **Site Explorer** - Browse and search through 1000+ supported sites
- 🔄 **Smart Conversion** - High-quality audio extraction with format options
- 🚄 **Concurrent Downloads** - Download multiple files simultaneously
- 🎚️ **Quality Selection** - Choose specific video resolutions
- 📦 **Playlist Support** - Download entire playlists with options to select specific videos
- 🔎 **Cache System** - Optimized repeat downloads with smart caching
- 🛡️ **Error Recovery** - Robust error handling and helpful suggestions
- 🧩 **Format Flexibility** - Video, MP3, FLAC, WAV, and more
- 🌐 **Universal Compatibility** - Works on Windows, macOS, and Linux


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

<h2 id="Quick Start">🏃‍♀️ Quick Start</h2>

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

# Download audio only (MP3)
python Snatch.py "https://youtube.com/watch?v=example" --audio-only

# Download in specific resolution
python Snatch.py "https://youtube.com/watch?v=example" --resolution 1080

# Download audio in FLAC format
python Snatch.py "https://youtube.com/watch?v=example" --audio-only --audio-format flac
```

<h2 id="Usage">💻 Usage</h2>

### Interactive Mode Commands

When in interactive mode, you can use these commands:

| Command                 | Description                           |
| ----------------------- | ------------------------------------- |
| `help` or `?`           | Show help and all available commands  |
| `URL`                   | Download media in best quality        |
| `URL mp3`               | Download audio in MP3 format          |
| `URL flac`              | Download audio in FLAC format         |
| `URL 720` or `URL 1080` | Download video in specific resolution |
| `list` or `sites`       | Show all supported sites              |
| `clear`                 | Clear the screen                      |
| `exit` or `quit`        | Exit the application                  |

### Advanced Features

#### 1. Playlist Downloads

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
## 🌎 Supported Sites
<h2 id="Supported Sites">🌎 Supported Sites</h2>
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

## 🔍 Troubleshooting
<h2 id="Troubleshooting">🔍 Troubleshooting</h2>
### Common Issues

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
   - Try with `--http-chunk-size 10485760` for larger chunks

### Need Help?

If you're still having issues:

- Check the logs in download_log.txt
- Run with `--verbose` for detailed output

## 🤝 Contributing

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
