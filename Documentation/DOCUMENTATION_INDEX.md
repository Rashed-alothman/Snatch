# 📚 Snatch Documentation Index

Welcome to the Snatch v1.8.1 documentation! This page provides an overview of all available documentation and guides.

## 🎯 Quick Start

**New to Snatch?** Start here:

1. [Installation Guide](#installation) (in main README)
2. [Usage Guide](Documentation/USAGE_GUIDE.md) - Complete command examples
3. [Features Update](Documentation/FEATURES_UPDATE.md) - What's new in v1.8.1

## 📋 Documentation Structure

### 🚀 User Documentation

| Document | Description | Best For |
|----------|-------------|----------|
| [📖 Main README](./README.md) | Overview, installation, basic usage | Everyone |
| [📝 Usage Guide](./USAGE_GUIDE.md) | Complete command examples and workflows | Users wanting comprehensive examples |
| [✨ Features Update](./FEATURES_UPDATE.md) | New features in v1.8.1 | Users upgrading from previous versions |
| [📋 Changelog](./CHANGELOG.md) | Version history and changes | Users tracking updates |

### 🔧 Technical Documentation

| Document | Description | Best For |
|----------|-------------|----------|
| [🏗️ Technical Documentation](../Documentation/TECHNICAL_DOCUMENTATION.md) | System architecture | Developers |
| [📦 Module Documentation](../Documentation/MODULE_DOCUMENTATION.md) | Detailed module analysis | Contributors |
| [🔌 Plugin Development](../Documentation/PLUGIN_DEVELOPMENT_GUIDE.md) | Plugin system guide | Plugin developers |
| [⚡ Performance Guide](../Documentation/PERFORMANCE_OPTIMIZATION_GUIDE.md) | Optimization tips | Advanced users |

### 🛠️ Setup & Troubleshooting

| Document | Description | Best For |
|----------|-------------|----------|
| [🚀 Deployment Guide](../Documentation/DEPLOYMENT_GUIDE.md) | Installation & deployment | System administrators |
| [🔍 Troubleshooting Guide](../Documentation/TROUBLESHOOTING_GUIDE.md) | Common issues & solutions | Users with problems |
| [🧪 Integration Testing](../Documentation/INTEGRATION_TESTING.md) | Testing procedures | Quality assurance |

## 🔥 What's New in v1.8.1

### Critical Fixes

- ✅ **Fixed Resolution Selection**: `--resolution` flags now work correctly
- ✅ **Proper Quality Selection**: Requesting 2160p actually gets 4K video

### New Features  

- 🚀 **AI Video Upscaling**: Enhance video quality with Real-ESRGAN
- 🎨 **Multiple Upscaling Methods**: AI and traditional upscaling options
- ⚙️ **Configurable Settings**: Quality presets and scale factors

## 🎯 Common Use Cases

### Basic Downloads

```bash
# Download best quality video
snatch download "URL"

# Download specific resolution (now works correctly!)
snatch download "URL" --resolution 1080
```

### Video Enhancement

```bash
# AI upscaling for better quality
snatch download "URL" --upscale --upscale-method realesrgan

# Combine resolution + upscaling
snatch download "URL" --resolution 720 --upscale --upscale-factor 2
```

### Audio Downloads

```bash
# High-quality audio
snatch download "URL" --audio-only --format flac

# Standard MP3
snatch download "URL" --audio-only --format mp3
```

## 🚀 Getting Help

### Step-by-Step Process

1. **Check the FAQ** (in main README troubleshooting section)
2. **Run diagnostics**: `python test_features_verification.py`
3. **Check logs**: Look in `logs/snatch_errors.log`
4. **Review documentation**: Use this index to find relevant guides
5. **Test with verbose output**: Add `--verbose` to your commands

### Quick Diagnostics

```bash
# Verify installation
snatch --version

# Test system capabilities  
snatch info

# Check network speed
snatch speedtest

# Verify new features
python test_features_verification.py
```

## 📊 Performance Tips

### Optimize Downloads

- Use `--aria2c` for faster downloads
- Set appropriate `--resolution` to balance quality and speed
- Use `--throttle` to limit bandwidth usage

### Optimize Upscaling

- Use `realesrgan` for animated content
- Use `lanczos` for live-action videos
- Use `--replace-original` to save disk space
- Consider `--upscale-quality low` for faster processing

## 🔧 Configuration

### Environment Variables

```bash
set SNATCH_OUTPUT=D:\Downloads    # Default download directory
set SNATCH_FFMPEG=C:\ffmpeg\bin   # FFmpeg location
set SNATCH_LOG_LEVEL=INFO         # Logging verbosity
```

### Config File

```bash
# Edit configuration
snatch config edit

# View current settings
snatch config show
```

## 🌟 Advanced Features

### Batch Processing

```bash
# Download multiple URLs
snatch batch urls.txt --upscale

# Process playlists
snatch download "PLAYLIST_URL" --playlist --upscale
```

### Automation

```bash
# Download and enhance in one command
snatch download "URL" --resolution 720 --upscale --upscale-factor 4 --replace-original --organize
```

## 📈 Migration Guide

### From v1.8.0 to v1.8.1

1. **Update installation:**

   ```bash
   git pull
   pip install -e .
   ```

2. **Test resolution selection:**

   ```bash
   # This now works reliably
   snatch download "test-url" --resolution 1080
   ```

3. **Try new upscaling:**

   ```bash
   snatch download "test-url" --upscale
   ```

### Update Existing Scripts

- Replace hardcoded resolution workarounds
- Add upscaling options where beneficial
- Update error handling for new features

## 📞 Support

### Documentation Hierarchy

1. **Quick issues**: Main README troubleshooting section
2. **Detailed guides**: This documentation index
3. **Technical details**: Technical documentation folder
4. **Code examples**: Usage guide and features update

### Self-Service Tools

- `test_features_verification.py` - Verify installation
- `snatch info` - System information
- `snatch --help` - Command reference
- Log files in `logs/` directory

---

**📝 Note**: This documentation is for Snatch v1.8.1. For older versions, check the changelog for compatibility information.

**🔗 Quick Links:**

- [Main README](./README.md) | [Usage Guide](Documentation/USAGE_GUIDE.md) | [Features Update](Documentation/FEATURES_UPDATE.md) | [Changelog](Documentation/CHANGELOG.md)
