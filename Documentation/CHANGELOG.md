# 📋 Changelog

All notable changes to the Snatch project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.8.1] - 2025-05-27

### 🔧 Fixed

#### Critical Bug Fixes

- **FIXED**: Resolution selection flags (`--resolution`, `-r`) now work correctly
  - Previously: Requesting 2160p would ignore the flag and download random quality
  - Now: Properly selects the requested resolution with fallback chains
  - Impact: Users can now reliably download videos in their preferred quality

#### Format Selection Improvements

- Fixed format string generation from `best[height>=1080]` to `bestvideo[height<=1080]+bestaudio/best[height<=1080]`
- Implemented proper fallback chains: 4K → 1440p → 1080p → 720p → 480p → best available
- Enhanced logging for debugging resolution selection issues

### 🚀 Added

#### AI-Powered Video Upscaling

- **NEW**: Real-ESRGAN integration for AI-enhanced video quality
- **NEW**: Support for multiple upscaling methods:
  - `realesrgan`: AI-powered upscaling (best for anime/cartoons)
  - `lanczos`: High-quality traditional upscaling
  - `bicubic`: Standard interpolation upscaling
  - `bilinear`: Fast basic upscaling
- **NEW**: Configurable upscaling factors (2x, 4x)
- **NEW**: Quality presets (low, medium, high)
- **NEW**: Option to replace original files after upscaling

#### New CLI Options

- `--upscale` / `-u`: Enable video upscaling
- `--upscale-method`: Choose upscaling algorithm
- `--upscale-factor`: Set scale factor (2 or 4)
- `--upscale-quality`: Set quality preset
- `--replace-original`: Replace source file after upscaling

#### Enhanced Architecture

- **NEW**: `VideoUpscaler` class in `modules/ffmpeg_helper.py`
- **NEW**: Upscaling configuration system in `modules/defaults.py`
- **NEW**: Integrated upscaling pipeline in download manager
- **NEW**: Automatic upscaling detection and processing

### 📚 Documentation

#### New Documentation Files

- **NEW**: `FEATURES_UPDATE.md` - Comprehensive guide to new features
- **NEW**: `USAGE_GUIDE.md` - Complete command examples and workflows
- **NEW**: `CHANGELOG.md` - Version history and changes (this file)

#### Updated Documentation

- **UPDATED**: Main README with new features and correct usage examples
- **UPDATED**: Documentation README with architecture changes
- **UPDATED**: Version numbers updated to 1.8.1

### 🧪 Testing

#### New Test Coverage

- **NEW**: `test_complete_pipeline.py` - Comprehensive system testing
- **NEW**: `test_final_verification.py` - Final verification tests
- **VERIFIED**: All resolution selection scenarios
- **VERIFIED**: Video upscaling functionality
- **VERIFIED**: CLI integration and argument parsing

### ⚡ Performance

#### Optimization Improvements

- Enhanced format string generation for faster resolution matching
- Optimized upscaling pipeline with progress tracking
- Improved error handling and logging for better debugging
- Memory-efficient video processing with temporary file management

### 🔄 Changed

#### Command Format Updates

- All examples now use correct `snatch download` format instead of legacy commands
- Updated CLI help text to reflect new upscaling options
- Improved error messages for resolution selection failures

## [1.8.0] - Previous Version

### Major Architectural Overhaul

- Complete package refactoring and modularization
- Enhanced plugin system with hook-based architecture
- Advanced audio processing with AI enhancement
- Peer-to-peer networking capabilities
- Smart performance optimization
- Cyberpunk-themed UI improvements
- Comprehensive documentation suite

## Usage Examples

### Resolution Selection (Fixed)

```bash
# Now works correctly - gets actual 4K video
snatch download "URL" --resolution 2160

# Gets actual 1080p video
snatch download "URL" --resolution 1080

# Gets actual 720p video
snatch download "URL" --resolution 720
```

### Video Upscaling (New)

```bash
# Basic AI upscaling
snatch download "URL" --upscale --upscale-method realesrgan

# Traditional high-quality upscaling
snatch download "URL" --upscale --upscale-method lanczos --upscale-factor 4

# Combine resolution + upscaling
snatch download "URL" --resolution 720 --upscale --upscale-factor 2 --replace-original
```

### Combined Workflow (Optimal)

```bash
# Download lower quality to save bandwidth, then upscale
snatch download "URL" --resolution 720 --upscale --upscale-method realesrgan --upscale-factor 4 --replace-original
```

## Migration Guide

### From Previous Versions

1. **Update Installation:**

   ```bash
   git pull
   pip install -e .
   ```

2. **Test Resolution Selection:**

   ```bash
   # This now works reliably
   snatch download "test-url" --resolution 1080
   ```

3. **Try Video Upscaling:**

   ```bash
   # New feature - enhance video quality
   snatch download "test-url" --upscale
   ```

4. **Update Scripts:**
   - Replace any hardcoded format strings
   - Update resolution selection logic
   - Consider adding upscaling to workflows

## Known Issues

### Resolved in 1.8.1

- ✅ Resolution flags not working correctly
- ✅ Format selection using wrong operators
- ✅ Inconsistent quality selection

### Current Limitations

- Real-ESRGAN requires automatic model download on first use
- Upscaling requires 2-3x storage space during processing
- AI upscaling methods require more system resources

## Acknowledgments

- **yt-dlp**: Core downloading functionality
- **FFmpeg**: Video/audio processing
- **Real-ESRGAN**: AI upscaling technology
- **Community**: Bug reports and feature requests

---

**For the complete feature documentation, see [FEATURES_UPDATE.md](./FEATURES_UPDATE.md)**

**For usage examples and workflows, see [USAGE_GUIDE.md](./USAGE_GUIDE.md)**
