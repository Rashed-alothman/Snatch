# 📖 Snatch Usage Guide - Video Enhancement & Resolution Selection

## 🎯 Quick Reference

### Basic Commands

```bash
# Interactive mode (recommended for beginners)
snatch

# Direct download with best quality
snatch download "https://example.com/video"

# Download with specific resolution (FIXED in v1.8.0)
snatch download "https://example.com/video" --resolution 1080

# Download with video upscaling
snatch download "https://example.com/video" --upscale
```

## 🎬 Video Resolution Selection

### Fixed Resolution Selection

The `--resolution` flag now works correctly and reliably selects the requested quality:

```bash
# 4K/Ultra HD downloads
snatch download "URL" --resolution 2160

# 1440p/QHD downloads  
snatch download "URL" --resolution 1440

# 1080p/Full HD downloads
snatch download "URL" --resolution 1080

# 720p/HD downloads
snatch download "URL" --resolution 720

# 480p/SD downloads
snatch download "URL" --resolution 480
```

### Resolution Fallback Chain

If your requested resolution isn't available, Snatch automatically falls back through this chain:
**4K → 1440p → 1080p → 720p → 480p → Best Available**

```bash
# Request 4K, get best available if 4K not found
snatch download "URL" --resolution 2160

# Output: "4K not available, downloading 1440p instead"
```

## 🚀 Video Upscaling

### Basic Upscaling

```bash
# Enable upscaling with default settings (2x Lanczos)
snatch download "URL" --upscale

# Specify upscaling factor
snatch download "URL" --upscale --upscale-factor 4

# Use AI upscaling (Real-ESRGAN)
snatch download "URL" --upscale --upscale-method realesrgan
```

### Advanced Upscaling

```bash
# High-quality AI upscaling with 4x factor
snatch download "URL" --upscale --upscale-method realesrgan --upscale-factor 4 --upscale-quality high

# Fast traditional upscaling
snatch download "URL" --upscale --upscale-method bilinear --upscale-quality low

# Replace original file to save space
snatch download "URL" --upscale --replace-original
```

### Upscaling Method Comparison

| Use Case | Recommended Method | Command |
|----------|-------------------|---------|
| Anime/Cartoons | Real-ESRGAN | `--upscale-method realesrgan` |
| Live Action | Lanczos | `--upscale-method lanczos` |
| Quick Processing | Bilinear | `--upscale-method bilinear` |
| Maximum Quality | Real-ESRGAN High | `--upscale-method realesrgan --upscale-quality high` |

## 💡 Smart Combinations

### Bandwidth Optimization

```bash
# Download lower quality, then upscale (saves bandwidth)
snatch download "URL" --resolution 720 --upscale --upscale-factor 2 --replace-original

# Result: 720p download → upscaled to 1440p equivalent → original 720p deleted
```

### Quality Maximization

```bash
# Get highest quality and enhance further
snatch download "URL" --resolution 2160 --upscale --upscale-method realesrgan

# Result: 4K download → AI-enhanced 8K equivalent
```

### Batch Processing

```bash
# Process multiple URLs with upscaling
snatch batch video_urls.txt --upscale --upscale-method lanczos

# Playlist with enhancement
snatch download "PLAYLIST_URL" --playlist --upscale --replace-original
```

## 🎵 Audio Downloads

### Basic Audio

```bash
# Download audio only (Opus format - best quality/size ratio)
snatch download "URL" --audio-only

# Download in MP3 format
snatch download "URL" --audio-only --format mp3

# Download in FLAC format (lossless)
snatch download "URL" --audio-only --format flac
```

### Advanced Audio Options

```bash
# Surround sound audio
snatch download "URL" --audio-only --format flac --channels 8

# High-quality MP3
snatch download "URL" --audio-only --format mp3 --quality 320

# Audio with metadata organization
snatch download "URL" --audio-only --organize
```

## 🚀 Performance Options

### Download Acceleration

```bash
# Use aria2c for faster downloads
snatch download "URL" --aria2c

# Combine with upscaling
snatch download "URL" --aria2c --upscale --upscale-method lanczos
```

### System Resource Management

```bash
# Show system stats during download
snatch download "URL" --system-stats

# Limit download speed to preserve bandwidth
snatch download "URL" --throttle 5M --upscale

# Resume interrupted downloads
snatch download "URL" --resume
```

## 📁 File Organization

### Custom Output Directories

```bash
# Save to specific directory
snatch download "URL" --output "D:\Videos\4K"

# Organize by metadata
snatch download "URL" --organize --output "D:\Media"

# Combine with upscaling and organization
snatch download "URL" --upscale --organize --output "D:\Enhanced Videos"
```

### File Naming and Organization

```bash
# Automatic organization with upscaling
snatch download "URL" --organize --upscale --replace-original

# Custom naming with quality info
snatch download "URL" --upscale --upscale-method realesrgan --organize
```

## 🔍 Troubleshooting Commands

### Diagnostic Commands

```bash
# Check available formats before downloading
snatch download "URL" --list-formats

# Test network speed
snatch speedtest

# Verify system capabilities
snatch info

# Enable verbose logging
snatch download "URL" --verbose
```

### Error Recovery

```bash
# Skip cache if having issues
snatch download "URL" --no-cache

# Disable retry logic for testing
snatch download "URL" --no-retry

# Force format selection
snatch download "URL" --format-id 137+140
```

## 📊 Interactive Mode Commands

When running `snatch` in interactive mode:

| Command | Description | Example |
|---------|-------------|---------|
| `download <URL>` | Download with options | `download URL --upscale` |
| `queue` | Show active downloads | `queue` |
| `stats` | Show download statistics | `stats` |
| `config edit` | Edit configuration | `config edit` |
| `sites` | List supported sites | `sites` |
| `speed` | Run speed test | `speed` |
| `help` | Show help | `help` |
| `clear` | Clear screen | `clear` |
| `exit` | Exit application | `exit` |

### Interactive Mode Examples

```
> download https://example.com/video --resolution 1080 --upscale
> queue
> stats
> config edit
> exit
```

## 🛠️ Configuration Examples

### Environment Variables

```bash
# Set default output directory
set SNATCH_OUTPUT=D:\Downloads

# Set custom FFmpeg path
set SNATCH_FFMPEG=C:\ffmpeg\bin\ffmpeg.exe

# Set cache directory
set SNATCH_CACHE=D:\Cache\Snatch

# Set log level
set SNATCH_LOG_LEVEL=INFO
```

### Config File Customization

```bash
# Edit main configuration
snatch config edit

# Show current configuration
snatch config show

# Reset to defaults
snatch config reset
```

## 📈 Performance Optimization

### System Requirements for Upscaling

| Upscaling Method | RAM Required | CPU Usage | Recommended For |
|------------------|--------------|-----------|-----------------|
| Bilinear | 1GB | Low | Quick processing |
| Bicubic | 2GB | Medium | General use |
| Lanczos | 4GB | High | Quality priority |
| Real-ESRGAN | 8GB+ | Very High | Maximum quality |

### Optimization Tips

```bash
# For older systems - use fast methods
snatch download "URL" --upscale --upscale-method bilinear --upscale-quality low

# For modern systems - maximize quality
snatch download "URL" --upscale --upscale-method realesrgan --upscale-quality high

# Balance performance and quality
snatch download "URL" --upscale --upscale-method lanczos --upscale-quality medium
```

## 🎯 Real-World Scenarios

### Scenario 1: Content Creator

```bash
# Download source material and enhance for editing
snatch download "source-video" --resolution 1080 --upscale --upscale-method realesrgan --output "D:\Projects\Sources"
```

### Scenario 2: Archive Building

```bash
# Create high-quality archive from older content
snatch batch old_videos.txt --upscale --upscale-method realesrgan --organize --replace-original
```

### Scenario 3: Mobile Data Conservation

```bash
# Download low quality on mobile data, enhance at home
snatch download "URL" --resolution 480 --output "D:\Mobile Downloads"
# Later at home:
snatch download "URL" --resolution 480 --upscale --upscale-factor 4 --replace-original
```

### Scenario 4: Playlist Enhancement

```bash
# Download entire playlist with enhancement
snatch download "PLAYLIST_URL" --playlist --resolution 720 --upscale --upscale-factor 2 --organize
```

## 🚀 Getting Started Checklist

1. **Install/Update Snatch:**
   ```bash
   git pull
   pip install -e .
   ```

2. **Verify FFmpeg:**
   ```bash
   ffmpeg -version
   ```

3. **Test basic download:**
   ```bash
   snatch download "test-url"
   ```

4. **Test resolution selection:**
   ```bash
   snatch download "test-url" --resolution 1080
   ```

5. **Test upscaling:**
   ```bash
   snatch download "test-url" --upscale
   ```

6. **Configure for your needs:**
   ```bash
   snatch config edit
   ```

---

**Need more help?** Run `snatch --help` or check the troubleshooting section in the main README.
