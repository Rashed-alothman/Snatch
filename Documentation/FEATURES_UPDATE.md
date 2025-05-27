# 🚀 Snatch v1.8.0 - Resolution & Video Upscaling Update

## 📋 Overview

This update addresses critical resolution selection issues and introduces AI-powered video upscaling capabilities to enhance your media downloading experience.

## 🔧 Critical Fixes

### Resolution Selection Bug Fix

**Problem Solved:** The `--resolution` (`-r`) flag was not working correctly. When requesting 2160p/4K videos, the system would ignore the flag and download in random quality.

**Solution Implemented:**

- Fixed format string generation from `best[height>=1080]` to `bestvideo[height<=1080]+bestaudio/best[height<=1080]`
- Implemented proper fallback chains: 4K → 1440p → 1080p → 720p → 480p → best available
- Added enhanced logging for debugging resolution selection

**Before:**

```bash
# This would often fail or ignore the resolution
snatch download "URL" --resolution 2160
```

**After:**

```bash
# Now works reliably with proper format selection
snatch download "URL" --resolution 2160  # Gets actual 4K/2160p video
snatch download "URL" --resolution 1080  # Gets actual 1080p video
snatch download "URL" --resolution 720   # Gets actual 720p video
```

## 🎨 New Feature: AI Video Upscaling

### What is Video Upscaling?

Video upscaling enhances video quality by increasing resolution and improving visual details using advanced algorithms, including AI-powered methods.

### Supported Upscaling Methods

| Method | Type | Best For | Quality | Speed |
|--------|------|----------|---------|-------|
| `realesrgan` | AI-powered | Anime, cartoons, graphics | Highest | Slower |
| `lanczos` | Traditional | Live action, photographs | High | Medium |
| `bicubic` | Traditional | General purpose | Good | Fast |
| `bilinear` | Traditional | Quick processing | Basic | Fastest |

### Upscaling Configuration

**Factors Available:**

- `2x`: Double the resolution (e.g., 1080p → 2160p)
- `4x`: Quadruple the resolution (e.g., 720p → 2880p)

**Quality Presets:**

- `low`: Fast processing, basic enhancement
- `medium`: Balanced quality and speed (default)
- `high`: Maximum quality, slower processing

## 💻 Command Examples

### Basic Upscaling

```bash
# Enable basic 2x upscaling with AI
snatch download "https://example.com/video" --upscale

# Use specific AI method with 4x upscaling
snatch download "https://example.com/video" --upscale --upscale-method realesrgan --upscale-factor 4

# Traditional upscaling with high quality
snatch download "https://example.com/video" --upscale --upscale-method lanczos --upscale-quality high
```

### Combined Resolution & Upscaling

```bash
# Download 720p and upscale to 1440p equivalent
snatch download "https://example.com/video" --resolution 720 --upscale --upscale-factor 2

# Download 1080p and upscale to 4K equivalent
snatch download "https://example.com/video" --resolution 1080 --upscale --upscale-factor 2

# Download lowest quality and upscale to high quality
snatch download "https://example.com/video" --resolution 480 --upscale --upscale-factor 4
```

### Advanced Options

```bash
# Replace original file after upscaling (saves space)
snatch download "https://example.com/video" --upscale --replace-original

# Combine with other features
snatch download "https://example.com/video" --upscale --upscale-method realesrgan --aria2c --stats
```

## 🎯 CLI Options Reference

### Video Enhancement Options

| Option | Short | Type | Default | Description |
|--------|-------|------|---------|-------------|
| `--upscale` | `-u` | Flag | `False` | Enable video upscaling |
| `--upscale-method` | | String | `lanczos` | Upscaling algorithm |
| `--upscale-factor` | | Integer | `2` | Scale factor (2x or 4x) |
| `--upscale-quality` | | String | `medium` | Quality preset |
| `--replace-original` | | Flag | `False` | Replace source file |

### Fixed Resolution Options

| Option | Short | Type | Description |
|--------|-------|------|-------------|
| `--resolution` | `-r` | Integer | Target resolution (now works correctly) |

**Available Resolutions:**

- `2160` - 4K/UHD (3840×2160)
- `1440` - QHD (2560×1440)
- `1080` - Full HD (1920×1080)
- `720` - HD (1280×720)
- `480` - SD (854×480)

## 🔄 Workflow Examples

### Scenario 1: Enhance Old Videos

```bash
# Download older content and upscale for modern displays
snatch download "old-video-url" --upscale --upscale-method realesrgan --upscale-factor 4
```

### Scenario 2: Save Bandwidth, Enhance Later

```bash
# Download in lower quality to save bandwidth, then upscale
snatch download "video-url" --resolution 720 --upscale --upscale-factor 2 --replace-original
```

### Scenario 3: Maximum Quality

```bash
# Get highest available resolution and enhance further
snatch download "video-url" --resolution 2160 --upscale --upscale-quality high
```

## 🛠️ Technical Implementation

### Architecture

The video upscaling system is implemented through:

1. **VideoUpscaler Class** (`modules/ffmpeg_helper.py`)
   - Handles Real-ESRGAN and traditional upscaling methods
   - Manages upscaling configuration and execution
   - Provides progress tracking and error handling

2. **Pipeline Integration** (`modules/manager.py`)
   - Automatic upscaling detection based on CLI arguments
   - Seamless integration with download workflow
   - File management and cleanup

3. **Configuration System** (`modules/defaults.py`)
   - Predefined upscaling presets and configurations
   - Quality and performance optimization settings

### Dependencies

- **FFmpeg**: Required for all video processing
- **Real-ESRGAN**: Optional, for AI-powered upscaling (automatically downloaded when needed)
- **Python 3.8+**: Core system requirements

## 📊 Performance Considerations

### Processing Time

| Resolution | Method | Factor | Estimated Time* |
|------------|--------|--------|----------------|
| 720p | Lanczos | 2x | 1-2 minutes |
| 720p | Real-ESRGAN | 2x | 5-10 minutes |
| 1080p | Lanczos | 2x | 2-4 minutes |
| 1080p | Real-ESRGAN | 2x | 10-20 minutes |

*Times vary based on system specifications and video length

### Storage Requirements

- **Temporary Space**: 2-3x the original file size during processing
- **Final Size**: 2-4x larger than original (depends on upscaling factor)
- **Use `--replace-original`**: To save space by removing the source file

## 🚀 Getting Started

### Quick Start

1. **Update to latest version:**

   ```bash
   git pull
   pip install -e .
   ```

2. **Test resolution selection:**

   ```bash
   snatch download "test-url" --resolution 1080
   ```

3. **Try video upscaling:**

   ```bash
   snatch download "test-url" --upscale
   ```

### Requirements Check

```bash
# Verify FFmpeg installation
ffmpeg -version

# Check system resources
snatch info

# Test network speed
snatch speedtest
```

## 🐛 Troubleshooting

### Common Issues

**Resolution not working:**

- Update to latest version - this bug is now fixed
- Check available formats: `snatch download "URL" --list-formats`

**Upscaling fails:**

- Ensure FFmpeg is properly installed
- Check available disk space (need 2-3x file size)
- Try different upscaling method: `--upscale-method lanczos`

**Real-ESRGAN errors:**

- Allow automatic download of Real-ESRGAN models
- Check internet connection for model downloads
- Fall back to traditional methods if needed

### Performance Tips

1. **Use appropriate upscaling methods:**
   - Real-ESRGAN for animated content
   - Lanczos for live action
   - Bilinear for quick processing

2. **Optimize for your system:**
   - Lower quality preset for older hardware
   - Use `--replace-original` to save space
   - Monitor system resources during processing

3. **Batch processing:**
   - Process multiple files sequentially
   - Use lower factors for faster processing
   - Consider processing overnight for large batches

## 📈 Future Enhancements

- Additional AI upscaling models
- Batch upscaling capabilities
- GPU acceleration support
- Custom upscaling profiles
- Quality comparison tools

---
