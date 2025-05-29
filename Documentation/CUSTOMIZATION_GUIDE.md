# 🎨 Snatch Customization Guide

Complete guide to personalizing and configuring Snatch to match your workflow and preferences.

## 📋 Table of Contents

- [🎭 Theme System](#theme-system)
- [🖥️ Interactive Interfaces](#interactive-interfaces)
- [⚙️ Performance Settings](#performance-settings)
- [🎛️ Interface Configuration](#interface-configuration)
- [🎯 Behavior Settings](#behavior-settings)
- [🔗 Command Aliases](#command-aliases)
- [📁 Profile Management](#profile-management)
- [📤 Import/Export](#import-export)
- [⌨️ Keyboard Shortcuts](#keyboard-shortcuts)
- [🎨 Custom Themes](#custom-themes)

## 🎭 Theme System

Snatch includes 8 built-in themes and support for custom themes.

### Available Themes

| Theme | Description | Best For |
|-------|-------------|----------|
| `default` | Standard Snatch colors | General use |
| `dark` | Dark mode with comfortable contrast | Low-light environments |
| `light` | Clean light theme | Bright environments |
| `high_contrast` | Enhanced visibility | Accessibility needs |
| `cyberpunk` | Futuristic neon aesthetics | Style preference |
| `minimal` | Clean, distraction-free | Focus on content |
| `ocean` | Calming blue tones | Relaxing experience |
| `forest` | Nature-inspired green palette | Outdoor feel |

### Theme Commands

```bash
# View current theme
snatch customize theme show

# List all available themes
snatch customize theme list

# Switch themes
snatch customize theme set --theme cyberpunk
snatch customize theme set --theme dark
snatch customize theme set --theme ocean

# Create custom theme
snatch customize theme create --colors '{
  "primary": "#ff6b6b",
  "secondary": "#4ecdc4", 
  "success": "#45b7d1",
  "warning": "#f9ca24",
  "error": "#f0932b",
  "info": "#6c5ce7"
}'
```

## 🖥️ Interactive Interfaces

Snatch offers multiple interface modes for different user preferences.

### Interface Modes

1. **Enhanced Interactive** (`snatch interactive`)
   - Rich CLI with progress bars
   - Color-coded status updates
   - Interactive prompts

2. **Modern Interface** (`snatch modern`)
   - Beautiful graphical elements
   - Smooth animations
   - Contemporary design

3. **Textual TUI** (`snatch textual`)
   - Advanced terminal UI
   - Responsive components
   - Full-screen experience

### Launching Interfaces

```bash
# Default enhanced interactive
snatch interactive

# Modern beautiful interface
snatch modern

# Advanced Textual TUI
snatch textual

# Quick launch (uses current theme)
snatch
```

## ⚙️ Performance Settings

Fine-tune Snatch's performance for your system and network.

### Key Performance Settings

```bash
# View all performance settings
snatch customize performance --show

# Core Performance Settings
snatch customize performance --setting max_concurrent_downloads --value 5
snatch customize performance --setting concurrent_fragment_downloads --value 16
snatch customize performance --setting chunk_size --value 1048576

# Network Settings
snatch customize performance --setting connection_timeout --value 30.0
snatch customize performance --setting read_timeout --value 60.0
snatch customize performance --setting max_retries --value 3

# Bandwidth Management
snatch customize performance --setting global_bandwidth_limit --value 0  # 0 = unlimited
snatch customize performance --setting per_download_bandwidth_limit --value 0

# Memory Management
snatch customize performance --setting max_memory_usage_mb --value 512
snatch customize performance --setting cache_size_mb --value 100

# Background Processing
snatch customize performance --setting background_thread_priority --value normal
snatch customize performance --setting temp_cleanup_interval --value 3600
```

### Performance Optimization Tips

| Setting | Recommended Value | Purpose |
|---------|-------------------|---------|
| `max_concurrent_downloads` | 3-8 | Balance speed vs system load |
| `chunk_size` | 1048576 (1MB) | Optimal for most connections |
| `connection_timeout` | 30.0 | Prevent hanging connections |
| `max_memory_usage_mb` | 512-1024 | Prevent memory issues |

## 🎛️ Interface Configuration

Customize the interface appearance and behavior.

### Interface Settings

```bash
# View all interface settings
snatch customize interface --show

# Display Mode
snatch customize interface --setting interface_mode --value detailed  # or compact

# Visual Elements
snatch customize interface --setting animate_progress --value true
snatch customize interface --setting show_progress_bars --value true
snatch customize interface --setting show_status_bar --value true
snatch customize interface --setting show_menu_bar --value true

# Interaction
snatch customize interface --setting enable_keyboard_shortcuts --value true
snatch customize interface --setting auto_complete --value true

# Display Limits
snatch customize interface --setting max_display_items --value 50
snatch customize interface --setting sidebar_width --value 30
snatch customize interface --setting history_size --value 100

# Accessibility
snatch customize interface --setting high_contrast_mode --value false
snatch customize interface --setting large_text_mode --value false
snatch customize interface --setting screen_reader_mode --value false
```

### Interface Modes

- **`detailed`**: Shows all information and options
- **`compact`**: Minimized interface for small screens

## 🎯 Behavior Settings

Control how Snatch behaves during operations.

### Behavior Configuration

```bash
# View all behavior settings
snatch customize behavior --show

# Confirmations
snatch customize behavior --setting confirm_file_overwrite --value true
snatch customize behavior --setting confirm_large_downloads --value true
snatch customize behavior --setting confirm_cache_clear --value true
snatch customize behavior --setting confirm_config_reset --value true

# Automation
snatch customize behavior --setting auto_organize_downloads --value true
snatch customize behavior --setting auto_save_sessions --value true
snatch customize behavior --setting auto_update_metadata --value true
snatch customize behavior --setting auto_generate_thumbnails --value true
snatch customize behavior --setting auto_extract_subtitles --value false

# Error Handling
snatch customize behavior --setting continue_on_error --value false
snatch customize behavior --setting log_all_errors --value true
snatch customize behavior --setting show_detailed_errors --value false

# Session Management
snatch customize behavior --setting keep_session_history --value true
snatch customize behavior --setting max_session_history --value 50
snatch customize behavior --setting session_auto_save_interval --value 30

# Download Behavior
snatch customize behavior --setting resume_incomplete_downloads --value true
snatch customize behavior --setting large_download_threshold_mb --value 100
```

## 🔗 Command Aliases

Create shortcuts for frequently used commands.

### Managing Aliases

```bash
# List current aliases
snatch customize alias list

# Add useful aliases
snatch customize alias add --alias "dl" --command "download"
snatch customize alias add --alias "4k" --command "download --resolution 2160"
snatch customize alias add --alias "1080p" --command "download --resolution 1080"
snatch customize alias add --alias "audio" --command "download --audio-only"
snatch customize alias add --alias "playlist" --command "download --yes-playlist"

# Remove aliases
snatch customize alias remove --alias "old-alias"
```

### Practical Alias Examples

```bash
# Quality shortcuts
snatch customize alias add --alias "uhd" --command "download --resolution 2160"
snatch customize alias add --alias "hd" --command "download --resolution 1080"
snatch customize alias add --alias "sd" --command "download --resolution 720"

# Format shortcuts
snatch customize alias add --alias "mp3" --command "download --audio-only --audio-format mp3"
snatch customize alias add --alias "flac" --command "download --audio-only --audio-format flac"

# Feature combinations
snatch customize alias add --alias "upscale4k" --command "download --upscale --upscale-factor 4"
snatch customize alias add --alias "fast" --command "download --aria2c"

# Using aliases
snatch uhd "https://example.com/video"      # Downloads in 4K
snatch mp3 "https://example.com/audio"      # Audio-only MP3
snatch upscale4k "https://example.com/vid"  # Downloads and upscales 4x
```

## 📁 Profile Management

Save and switch between different configuration sets.

### Profile Commands

```bash
# List available profiles
snatch customize profile list

# Create new profiles
snatch customize profile create --name "work"
snatch customize profile create --name "personal"
snatch customize profile create --name "low-bandwidth"

# Load profiles
snatch customize profile load --name "work"
snatch customize profile load --name "personal"

# Delete profiles
snatch customize profile delete --name "old-profile"
```

### Example Profile Setups

**Work Profile:**

```bash
snatch customize profile create --name "work"
snatch customize profile load --name "work"
snatch customize theme set --theme minimal
snatch customize performance --setting max_concurrent_downloads --value 2
snatch customize behavior --setting confirm_large_downloads --value true
```

**High-Performance Profile:**

```bash
snatch customize profile create --name "speed"
snatch customize profile load --name "speed"
snatch customize performance --setting max_concurrent_downloads --value 8
snatch customize performance --setting concurrent_fragment_downloads --value 32
snatch customize performance --setting global_bandwidth_limit --value 0
```

## 📤 Import/Export

Share configurations or backup your settings.

### Export Configurations

```bash
# Export to YAML (default)
snatch customize export my-config.yaml

# Export to JSON
snatch customize export my-config.json --format json

# Export to TOML
snatch customize export my-config.toml --format toml
```

### Import Configurations

```bash
# Import from any supported format
snatch customize import my-config.yaml
snatch customize import shared-config.json
snatch customize import team-config.toml
```

### Reset to Defaults

```bash
# Reset all customization (with confirmation)
snatch customize reset

# Reset without confirmation
snatch customize reset --yes
```

## ⌨️ Keyboard Shortcuts

Configure keyboard shortcuts for interactive modes.

### Default Shortcuts

| Shortcut | Action | Context |
|----------|--------|---------|
| `Enter` | Start download | Interactive mode |
| `Ctrl+C` | Copy URL | Interactive mode |
| `Ctrl+L` | Clear screen | Interactive mode |
| `h` | Show help | Interactive mode |
| `q` | Quit application | Interactive mode |
| `p` | Pause download | During download |
| `r` | Refresh | Interactive mode |
| `d` | Toggle details | Interactive mode |
| `l` | Toggle logs | Interactive mode |
| `o` | Open file | After download |
| `f` | Open folder | After download |

### Customizing Shortcuts

```bash
# View current shortcuts
snatch customize interface --show | grep shortcuts

# Enable/disable shortcuts
snatch customize interface --setting enable_keyboard_shortcuts --value true
```

## 🎨 Custom Themes

Create your own themes with custom colors.

### Creating Custom Themes

```bash
# Create theme with custom colors
snatch customize theme create --colors '{
  "primary": "#e74c3c",
  "secondary": "#3498db",
  "success": "#2ecc71",
  "warning": "#f39c12",
  "error": "#e74c3c",
  "info": "#9b59b6",
  "background": "#2c3e50",
  "text": "#ecf0f1"
}'
```

### Color Scheme Guidelines

**Primary Colors:**

- `primary`: Main accent color
- `secondary`: Secondary accent color
- `background`: Background color
- `text`: Primary text color

**Status Colors:**

- `success`: Success messages and indicators
- `warning`: Warning messages
- `error`: Error messages and alerts
- `info`: Informational messages

### Theme Examples

**Sunset Theme:**

```json
{
  "primary": "#ff6b6b",
  "secondary": "#ffa726",
  "success": "#66bb6a",
  "warning": "#ffca28",
  "error": "#ef5350",
  "info": "#42a5f5",
  "background": "#263238",
  "text": "#ffffff"
}
```

**Ocean Theme:**

```json
{
  "primary": "#00acc1",
  "secondary": "#0277bd",
  "success": "#00c853",
  "warning": "#ffc107",
  "error": "#d32f2f",
  "info": "#1976d2",
  "background": "#004d5c",
  "text": "#e0f2f1"
}
```

## 📊 Configuration Reference

### Complete Settings List

#### Performance Settings

- `max_concurrent_downloads`: Maximum simultaneous downloads (1-20)
- `concurrent_fragment_downloads`: Fragments per download (1-50)
- `chunk_size`: Download chunk size in bytes
- `connection_timeout`: Connection timeout in seconds
- `read_timeout`: Read timeout in seconds
- `retry_delay`: Delay between retries in seconds
- `max_retries`: Maximum retry attempts
- `global_bandwidth_limit`: Global bandwidth limit (0 = unlimited)
- `per_download_bandwidth_limit`: Per-download limit (0 = unlimited)
- `max_memory_usage_mb`: Memory limit in MB
- `cache_size_mb`: Cache size in MB
- `exponential_backoff`: Enable exponential backoff
- `background_thread_priority`: Thread priority (low/normal/high)
- `temp_cleanup_interval`: Cleanup interval in seconds

#### Interface Settings

- `interface_mode`: Display mode (detailed/compact)
- `enable_keyboard_shortcuts`: Enable shortcuts (true/false)
- `auto_complete`: Enable auto-completion (true/false)
- `show_progress_bars`: Show progress bars (true/false)
- `show_status_bar`: Show status bar (true/false)
- `show_menu_bar`: Show menu bar (true/false)
- `animate_progress`: Animate progress (true/false)
- `high_contrast_mode`: High contrast mode (true/false)
- `large_text_mode`: Large text mode (true/false)
- `screen_reader_mode`: Screen reader mode (true/false)
- `sidebar_width`: Sidebar width in characters
- `max_display_items`: Maximum items to display
- `history_size`: Command history size

#### Behavior Settings

- `confirm_file_overwrite`: Confirm before overwriting (true/false)
- `confirm_large_downloads`: Confirm large downloads (true/false)
- `confirm_cache_clear`: Confirm cache clearing (true/false)
- `confirm_config_reset`: Confirm config reset (true/false)
- `auto_organize_downloads`: Auto-organize files (true/false)
- `auto_save_sessions`: Auto-save sessions (true/false)
- `auto_update_metadata`: Auto-update metadata (true/false)
- `auto_generate_thumbnails`: Auto-generate thumbnails (true/false)
- `auto_extract_subtitles`: Auto-extract subtitles (true/false)
- `continue_on_error`: Continue on errors (true/false)
- `log_all_errors`: Log all errors (true/false)
- `show_detailed_errors`: Show detailed errors (true/false)
- `keep_session_history`: Keep session history (true/false)
- `max_session_history`: Maximum session history entries
- `session_auto_save_interval`: Auto-save interval in seconds
- `resume_incomplete_downloads`: Resume incomplete downloads (true/false)
- `large_download_threshold_mb`: Large download threshold in MB

## 🚀 Quick Start Examples

### Gaming Setup

```bash
# Create gaming profile with cyberpunk theme
snatch customize profile create --name "gaming"
snatch customize theme set --theme cyberpunk
snatch customize performance --setting max_concurrent_downloads --value 8
snatch customize interface --setting animate_progress --value true
```

### Work Environment

```bash
# Professional setup with minimal theme
snatch customize profile create --name "work"
snatch customize theme set --theme minimal
snatch customize performance --setting max_concurrent_downloads --value 3
snatch customize behavior --setting confirm_large_downloads --value true
```

### Low Bandwidth Setup

```bash
# Optimize for slow connections
snatch customize profile create --name "slow-internet"
snatch customize performance --setting max_concurrent_downloads --value 1
snatch customize performance --setting chunk_size --value 524288
snatch customize performance --setting global_bandwidth_limit --value 500
```

---

*This guide covers all customization options available in Snatch. For additional help, use `snatch --help` or visit the [main documentation](./README.md).*
