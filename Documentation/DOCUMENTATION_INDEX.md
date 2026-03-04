# Snatch Documentation Index

Welcome to the Snatch v2.0.0 documentation.

## Quick Start

**New to Snatch?** Start here:

1. [Installation Guide](../README.md#Installation) (in main README)
2. [Usage Guide](USAGE_GUIDE.md) - Complete command examples
3. [Changelog](CHANGELOG.md) - What's new in v2.0.0

## Documentation Structure

### User Documentation

| Document | Description | Best For |
|----------|-------------|----------|
| [Main README](../README.md) | Overview, installation, basic usage | Everyone |
| [Usage Guide](USAGE_GUIDE.md) | Complete command examples and workflows | Users wanting comprehensive examples |
| [Configuration Management](CONFIGURATION_MANAGEMENT.md) | Cache clearing, config editing, backups | Users managing application settings |
| [Customization Guide](CUSTOMIZATION_GUIDE.md) | Themes, profiles, aliases | Users personalizing Snatch |
| [Audio Enhancement Guide](AUDIO_ENHANCEMENT_GUIDE.md) | Audio processing presets and workflows | Audio processing users |
| [Interactive Mode Guide](INTERACTIVE_MODE_GUIDE.md) | TUI and interactive features | Interactive mode users |
| [Changelog](CHANGELOG.md) | Version history and changes | Users tracking updates |
| [Disclaimer](Disclaimer.md) | Legal notice | Everyone |

### Technical Documentation

| Document | Description | Best For |
|----------|-------------|----------|
| [Technical Architecture](TECHNICAL_ARCHITECTURE.md) | System architecture overview | Developers |
| [Technical Documentation](TECHNICAL_DOCUMENTATION.md) | Detailed technical reference | Developers |
| [Module Documentation](MODULE_DOCUMENTATION.md) | Module-level API docs | Contributors |
| [API Reference](API_REFERENCE.md) | Function signatures and usage | Developers |
| [Plugin Development](PLUGIN_DEVELOPMENT_GUIDE.md) | Plugin system guide | Plugin developers |
| [Performance Guide](PERFORMANCE_OPTIMIZATION_GUIDE.md) | Optimization strategies | Advanced users |

### Setup & Troubleshooting

| Document | Description | Best For |
|----------|-------------|----------|
| [Deployment Guide](DEPLOYMENT_GUIDE.md) | Installation & deployment | System administrators |
| [Troubleshooting Guide](TROUBLESHOOTING_GUIDE.md) | Common issues & solutions | Users with problems |

## Common Use Cases

### Basic Downloads

```bash
# Download best quality video
snatch download "URL"

# Download specific resolution
snatch download "URL" --resolution 1080

# Download audio only
snatch download "URL" --audio-only --format flac
```

### Video Enhancement

```bash
# AI upscaling
snatch download "URL" --upscale --upscale-method realesrgan

# Combine resolution + upscaling
snatch download "URL" --resolution 720 --upscale --upscale-factor 2
```

### Audio Enhancement

```bash
# Enhance with preset
snatch audio enhance "myfile.mp3" --preset music

# Analyze audio quality
snatch audio analyze "myfile.wav"
```

## Getting Help

1. Check the [Troubleshooting Guide](TROUBLESHOOTING_GUIDE.md)
2. Run `snatch info` for system diagnostics
3. Use `snatch --help` for command reference
4. Add `--verbose` for detailed output

---

**Snatch v2.0.0** | [Main README](../README.md) | [Usage Guide](USAGE_GUIDE.md) | [Changelog](CHANGELOG.md)
