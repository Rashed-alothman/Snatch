# 🎵 Audio Enhancement Guide

## Overview

Snatch v1.8.0 introduces a comprehensive audio enhancement system that leverages AI-powered algorithms to improve audio quality, reduce noise, and optimize audio content for different use cases. This guide covers all aspects of the audio enhancement features.

## Table of Contents

- [Quick Start](#quick-start)
- [Audio Enhancement Commands](#audio-enhancement-commands)
- [Enhancement Presets](#enhancement-presets)
- [Audio Analysis](#audio-analysis)
- [Batch Processing](#batch-processing)
- [Custom Presets](#custom-presets)
- [Technical Details](#technical-details)
- [Troubleshooting](#troubleshooting)

## Quick Start

### Basic Audio Enhancement

```bash
# Enhance a music file with the music preset
snatch audio enhance "song.mp3" --preset music

# Enhance a podcast with speech optimization
snatch audio enhance "podcast.wav" --preset podcast --output "enhanced_podcast.wav"

# Restore old or low-quality audio
snatch audio enhance "old_recording.wav" --preset restoration
```

### Audio Quality Analysis

```bash
# Analyze audio quality and get recommendations
snatch audio analyze "myfile.wav"

# View available presets
snatch audio presets --detailed
```

### Batch Processing

```bash
# Process all MP3 files in current directory
snatch audio batch "*.mp3" --preset music

# Process all audio files recursively
snatch audio batch "**/*.{mp3,wav,flac}" --preset restoration
```

## Audio Enhancement Commands

### `snatch audio enhance`

Enhance individual audio files with AI-powered processing.

#### Syntax

```bash
snatch audio enhance <input_file> [options]
```

#### Options

| Option | Short | Description | Example |
|--------|-------|-------------|---------|
| `--preset` | `-p` | Enhancement preset to use | `--preset music` |
| `--output` | `-o` | Output file path | `--output enhanced.wav` |
| `--format` | `-f` | Output format | `--format flac` |
| `--quality` | `-q` | Quality level (1-10) | `--quality 9` |
| `--sample-rate` | `-sr` | Target sample rate | `--sample-rate 48000` |
| `--channels` | `-c` | Number of channels | `--channels 2` |
| `--normalize` | `-n` | Enable loudness normalization | `--normalize` |
| `--denoise` | `-d` | Enable noise reduction | `--denoise` |
| `--enhance-stereo` | `-s` | Enable stereo widening | `--enhance-stereo` |
| `--preserve-dynamics` | | Preserve original dynamics | `--preserve-dynamics` |

#### Examples

```bash
# Basic enhancement with music preset
snatch audio enhance "track.mp3" --preset music

# High-quality FLAC output with custom settings
snatch audio enhance "source.wav" --preset music --format flac --quality 10 --output "enhanced.flac"

# Speech enhancement with noise reduction
snatch audio enhance "interview.wav" --preset speech --denoise --normalize

# Custom processing without preset
snatch audio enhance "audio.mp3" --denoise --enhance-stereo --sample-rate 48000
```

### `snatch audio presets`

List and manage audio enhancement presets.

#### Syntax

```bash
snatch audio presets [options]
```

#### Options

| Option | Description | Example |
|--------|-------------|---------|
| `--list` | List preset names | `--list` |
| `--detailed` | Show detailed preset information | `--detailed` |
| `--show <name>` | Show specific preset details | `--show music` |

#### Examples

```bash
# List all available presets
snatch audio presets --list

# Show detailed information about all presets
snatch audio presets --detailed

# Show details for the music preset
snatch audio presets --show music
```

### `snatch audio analyze`

Analyze audio quality and get enhancement recommendations.

#### Syntax

```bash
snatch audio analyze <input_file> [options]
```

#### Options

| Option | Description | Example |
|--------|-------------|---------|
| `--detailed` | Show detailed analysis | `--detailed` |
| `--recommend` | Show preset recommendations | `--recommend` |
| `--output` | Save analysis to file | `--output analysis.json` |

#### Examples

```bash
# Basic audio analysis
snatch audio analyze "myfile.wav"

# Detailed analysis with recommendations
snatch audio analyze "podcast.mp3" --detailed --recommend

# Save analysis to JSON file
snatch audio analyze "music.flac" --output "analysis.json"
```

### `snatch audio batch`

Process multiple audio files with the same settings.

#### Syntax

```bash
snatch audio batch <pattern> [options]
```

#### Options

| Option | Short | Description | Example |
|--------|-------|-------------|---------|
| `--preset` | `-p` | Enhancement preset to use | `--preset music` |
| `--output-dir` | `-o` | Output directory | `--output-dir enhanced/` |
| `--format` | `-f` | Output format | `--format flac` |
| `--recursive` | `-r` | Process subdirectories | `--recursive` |
| `--overwrite` | | Overwrite existing files | `--overwrite` |
| `--parallel` | | Number of parallel processes | `--parallel 4` |

#### Examples

```bash
# Process all MP3 files in current directory
snatch audio batch "*.mp3" --preset music --output-dir enhanced/

# Recursively process all audio files
snatch audio batch "**/*.{mp3,wav,flac}" --preset restoration --recursive

# Parallel processing with custom settings
snatch audio batch "*.wav" --preset podcast --parallel 8 --format mp3
```

### `snatch audio create-preset`

Create custom enhancement presets.

#### Syntax

```bash
snatch audio create-preset <name> <description> [options]
```

#### Options

| Option | Description | Example |
|--------|-------------|---------|
| `--based-on` | Base on existing preset | `--based-on music` |
| `--settings` | JSON settings object | `--settings '{"denoise": true}'` |
| `--file` | Load settings from file | `--file settings.json` |

#### Examples

```bash
# Create a custom preset based on music
snatch audio create-preset "my-music" "Custom music settings" --based-on music

# Create preset with custom settings
snatch audio create-preset "vocals" "Vocal enhancement" --settings '{"denoise": true, "enhance_stereo": false}'

# Create preset from settings file
snatch audio create-preset "studio" "Studio processing" --file studio_settings.json
```

## Enhancement Presets

### Podcast Preset

- **Purpose**: Optimized for speech content
- **Features**: Strong noise reduction, clarity enhancement, speech optimization
- **Best For**: Podcasts, interviews, voice recordings, lectures
- **Settings**: Aggressive noise reduction, speech frequency emphasis, minimal stereo processing

### Music Preset

- **Purpose**: Optimized for music content
- **Features**: Stereo enhancement, dynamic preservation, harmonic restoration
- **Best For**: Music tracks, albums, instrumental recordings
- **Settings**: Moderate noise reduction, stereo widening, frequency extension

### Speech Preset

- **Purpose**: Maximum speech clarity
- **Features**: Strong noise reduction, speech frequency boost, clarity enhancement
- **Best For**: Audiobooks, presentations, voice recordings with background noise
- **Settings**: Maximum noise reduction, speech optimization, minimal dynamics processing

### Broadcast Preset

- **Purpose**: Professional broadcast standards
- **Features**: Consistent levels, broadcast-safe processing, professional quality
- **Best For**: Radio shows, professional content, broadcast preparation
- **Settings**: Loudness normalization, professional compression, broadcast limiting

### Restoration Preset

- **Purpose**: Maximum enhancement for damaged audio
- **Features**: Aggressive processing, artifact removal, quality restoration
- **Best For**: Old recordings, damaged audio, very low-quality sources
- **Settings**: Maximum noise reduction, frequency restoration, dynamic enhancement

## Audio Analysis

The audio analysis system provides detailed information about your audio files and recommendations for optimal enhancement.

### Quality Metrics

| Metric | Range | Description |
|--------|-------|-------------|
| **Noise Level** | 0.0 - 1.0 | 0.0 = clean, 1.0 = very noisy |
| **Dynamics** | 0.0 - 1.0 | 0.0 = compressed, 1.0 = dynamic |
| **RMS Level** | dB | Average audio level in decibels |
| **Peak Level** | dB | Maximum audio level in decibels |
| **Clipping** | 0.0 - 1.0 | 0.0 = no clipping, 1.0 = severe clipping |
| **Distortion** | 0.0 - 1.0 | 0.0 = clean, 1.0 = distorted |

### Automatic Recommendations

Based on the analysis, the system will recommend the most appropriate preset:

- **High noise + speech content** → `speech` preset
- **Music with good dynamics** → `music` preset
- **Voice recording** → `podcast` preset
- **Professional content** → `broadcast` preset
- **Low quality/damaged** → `restoration` preset

### Example Analysis Output

```
🔍 Audio Quality Analysis: podcast_episode.mp3
📊 Technical Information:
  - Sample Rate: 44100Hz
  - Channels: 2 (stereo)
  - Duration: 45.32 minutes
  - Bit Depth: 16-bit
  - Codec: MP3
  - Bitrate: 128 kbps

🎯 Quality Metrics:
  - Noise Level: 0.34 (moderate noise present)
  - Dynamics: 0.78 (good dynamic range)
  - RMS Level: -23.4 dB (appropriate level)
  - Peak Level: -3.2 dB (good headroom)
  - Clipping: 0.02 (minimal clipping)
  - Distortion: 0.15 (low distortion)

💡 Recommendation: Use 'podcast' preset
   Reason: Speech content with moderate background noise
```

## Batch Processing

Batch processing allows you to enhance multiple audio files efficiently with the same settings.

### File Patterns

Use glob patterns to select files:

```bash
# All MP3 files in current directory
"*.mp3"

# All audio files (multiple extensions)
"*.{mp3,wav,flac,m4a}"

# Recursive processing (all subdirectories)
"**/*.mp3"

# Specific directories
"music/**/*.{mp3,flac}"
"podcasts/**/*.wav"
```

### Output Organization

```bash
# Create organized output structure
snatch audio batch "**/*.mp3" --preset music --output-dir "enhanced/" --recursive

# This creates:
# enhanced/
#   ├── album1/
#   │   ├── track1_enhanced.mp3
#   │   └── track2_enhanced.mp3
#   └── album2/
#       ├── track3_enhanced.mp3
#       └── track4_enhanced.mp3
```

### Performance Optimization

For large batch operations:

```bash
# Use parallel processing (default: CPU cores)
snatch audio batch "*.wav" --preset music --parallel 8

# Process in chunks to manage memory
snatch audio batch "large_files/*.wav" --preset restoration --parallel 2

# Monitor progress
snatch audio batch "*.mp3" --preset music --verbose
```

## Custom Presets

Create custom presets for specialized use cases.

### Settings Structure

Custom presets use JSON settings format:

```json
{
  "denoise": true,
  "noise_reduction_strength": 0.8,
  "normalize": true,
  "target_lufs": -23.0,
  "enhance_stereo": true,
  "stereo_width": 1.2,
  "frequency_extension": true,
  "dynamic_compression": true,
  "compression_ratio": 2.0,
  "gate_threshold": -60.0,
  "sample_rate_upscale": true,
  "target_sample_rate": 48000
}
```

### Settings Reference

| Setting | Type | Default | Description |
|---------|------|---------|-------------|
| `denoise` | boolean | true | Enable noise reduction |
| `noise_reduction_strength` | float | 0.5 | Noise reduction intensity (0.0-1.0) |
| `normalize` | boolean | true | Enable loudness normalization |
| `target_lufs` | float | -23.0 | Target loudness in LUFS |
| `enhance_stereo` | boolean | false | Enable stereo widening |
| `stereo_width` | float | 1.0 | Stereo width multiplier |
| `frequency_extension` | boolean | false | Restore high frequencies |
| `dynamic_compression` | boolean | false | Apply dynamic compression |
| `compression_ratio` | float | 1.0 | Compression ratio |
| `gate_threshold` | float | -70.0 | Noise gate threshold |
| `sample_rate_upscale` | boolean | false | Upscale sample rate |
| `target_sample_rate` | integer | 44100 | Target sample rate in Hz |

### Example Custom Presets

#### Gaming/Streaming Preset

```json
{
  "denoise": true,
  "noise_reduction_strength": 0.9,
  "normalize": true,
  "target_lufs": -16.0,
  "enhance_stereo": false,
  "dynamic_compression": true,
  "compression_ratio": 3.0,
  "gate_threshold": -50.0
}
```

#### Archival Preset

```json
{
  "denoise": true,
  "noise_reduction_strength": 0.7,
  "normalize": true,
  "target_lufs": -23.0,
  "frequency_extension": true,
  "sample_rate_upscale": true,
  "target_sample_rate": 96000,
  "dynamic_compression": false
}
```

## Technical Details

### AI Enhancement Algorithms

The audio enhancement system uses several advanced algorithms:

1. **Spectral Subtraction**: For noise reduction
2. **Wiener Filtering**: For signal restoration
3. **Psychoacoustic Modeling**: For perceptually optimal processing
4. **Machine Learning**: For content-aware processing
5. **EBU R128**: For professional loudness standards

### Supported Formats

#### Input Formats

- WAV (PCM, IEEE float)
- MP3 (all bitrates)
- FLAC (all compression levels)
- M4A/AAC (all profiles)
- OGG Vorbis
- Opus
- AIFF
- AU/SND

#### Output Formats

- WAV (16/24/32-bit PCM, 32/64-bit float)
- FLAC (compression levels 0-8)
- MP3 (CBR/VBR, 8-320 kbps)
- M4A/AAC (multiple profiles)
- OGG Vorbis (quality levels 0-10)

### Processing Pipeline

1. **Input Validation**: File format and integrity check
2. **Audio Loading**: Convert to internal processing format
3. **Analysis**: Extract quality metrics and characteristics
4. **Enhancement**: Apply selected processing chain
5. **Normalization**: Apply loudness standards
6. **Output**: Encode to target format with quality settings

### Performance Characteristics

| Operation | Typical Speed | Memory Usage |
|-----------|---------------|--------------|
| Analysis | 10x real-time | 50MB per hour |
| Noise Reduction | 2x real-time | 100MB per hour |
| Stereo Enhancement | 5x real-time | 75MB per hour |
| Format Conversion | 20x real-time | 25MB per hour |
| Batch Processing | Parallel x cores | Variable |

## Troubleshooting

### Common Issues

#### 1. Import Error: Missing Dependencies

**Error**: `ImportError: No module named 'librosa'`

**Solution**:

```bash
pip install librosa soundfile noisereduce pyloudnorm
```

#### 2. Audio File Not Supported

**Error**: `AudioFileError: Unsupported audio format`

**Solution**: Convert the file to a supported format first:

```bash
ffmpeg -i input.file output.wav
snatch audio enhance output.wav --preset music
```

#### 3. Memory Error During Processing

**Error**: `MemoryError: Unable to allocate array`

**Solution**: Process files individually or use lower quality settings:

```bash
# Process one file at a time
snatch audio enhance large_file.wav --preset music

# Or use batch processing with limited parallelism
snatch audio batch "*.wav" --preset music --parallel 1
```

#### 4. Processing Too Slow

**Solution**: Optimize processing settings:

```bash
# Use faster preset
snatch audio enhance file.wav --preset speech

# Reduce parallel processing
snatch audio batch "*.mp3" --parallel 2

# Use lower quality for speed
snatch audio enhance file.wav --preset music --quality 6
```

#### 5. Output Quality Issues

**Check**: Input file quality

```bash
snatch audio analyze input.wav --detailed
```

**Solution**: Use appropriate preset for content type:

- Speech content: Use `speech` or `podcast` preset
- Music content: Use `music` preset
- Poor quality: Use `restoration` preset

### Getting Help

For additional help and support:

1. **Documentation**: Check the [Technical Documentation](./TECHNICAL_DOCUMENTATION.md)
2. **Issues**: Report bugs on the GitHub repository
3. **Discussions**: Join community discussions for tips and tricks
4. **Logs**: Check logs in `logs/snatch_errors.log` for detailed error information

### Debug Mode

Enable debug mode for detailed logging:

```bash
# Set environment variable
export SNATCH_LOG_LEVEL=DEBUG

# Or use the debug flag
snatch audio enhance file.wav --preset music --debug
```

This will provide detailed information about the processing pipeline and help identify issues.
