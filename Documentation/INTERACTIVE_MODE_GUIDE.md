# 🖥️ Interactive Mode Guide

## Overview

Snatch offers multiple interactive interface modes, each designed for different user preferences and workflows. From futuristic cyberpunk aesthetics to clean modern designs and advanced terminal interfaces, you can choose the experience that works best for you.

## 🚀 Quick Launch Commands

```bash
# Enhanced interactive mode (default)
snatch interactive

# Modern beautiful interface
snatch modern

# Advanced Textual TUI
snatch textual

# Standard CLI mode
snatch
```

## 🎮 Available Interface Modes

### 1. Enhanced Interactive Mode (`snatch interactive`)

**Features:**

- Rich-powered console interface with syntax highlighting
- Interactive prompts and confirmations
- Real-time progress tracking
- Comprehensive help system
- Theme-aware display

**Best For:**

- New users learning Snatch
- Users who prefer guided interactions
- Sessions requiring detailed feedback

**Key Features:**

- URL validation with helpful suggestions
- Format selection wizards
- Quality preference dialogs
- Download progress visualization
- Error handling with recovery options

### 2. Modern Interface (`snatch modern`)

**Features:**

- Clean, contemporary design
- Beautiful animations and transitions
- Intuitive menu navigation
- Visual feedback and indicators
- Responsive layout

**Best For:**

- Users who appreciate modern aesthetics
- Visual learners
- Regular downloading sessions
- Presentation or demonstration scenarios

**Key Features:**

- Card-based information display
- Smooth progress animations
- Context-sensitive menus
- Visual status indicators
- Drag-and-drop URL support (where available)

### 3. Textual TUI (`snatch textual`)

**Features:**

- Advanced terminal user interface
- Rich components and widgets
- Keyboard navigation
- Multi-panel layout
- Real-time updates

**Best For:**

- Power users
- Terminal enthusiasts
- Multi-tasking workflows
- Advanced configuration management

**Key Features:**

- Split-screen layouts
- Tabbed interfaces
- Live data grids
- Interactive forms
- Keyboard shortcuts

### 4. Standard CLI Mode (`snatch`)

**Features:**

- Traditional command-line interface
- Direct command execution
- Scriptable operations
- Minimal resource usage

**Best For:**

- Automation and scripting
- Batch operations
- Remote server usage
- Resource-constrained environments

## 🎨 Theme Integration

All interactive modes respect your current theme setting:

```bash
# Set theme before launching interface
snatch customize theme set --theme cyberpunk
snatch interactive  # Launches with cyberpunk theme

# Or switch to a clean theme
snatch customize theme set --theme minimal
snatch modern  # Launches with minimal theme
```

## 🎯 Interface-Specific Features

### Enhanced Interactive Mode Features

#### URL Processing

- **Smart URL Detection**: Automatically detects and validates URLs
- **Batch URL Input**: Support for multiple URLs at once
- **URL History**: Recent URLs for quick re-access
- **Format Preview**: Shows available formats before download

#### Download Management

- **Quality Selection Wizard**: Interactive quality picker
- **Format Options**: Audio/video format selection
- **Output Configuration**: Custom naming and organization
- **Progress Monitoring**: Real-time download status

#### Navigation Commands

```
Available Commands in Interactive Mode:
- download <url>     : Download media from URL
- queue             : Show download queue
- history           : Show download history
- config            : Configuration management
- themes            : Theme management
- help              : Show help information
- clear             : Clear screen
- exit              : Exit application
```

### Modern Interface Features

#### Visual Elements

- **Progress Cards**: Elegant download progress displays
- **Status Dashboard**: Overview of system status
- **Media Previews**: Thumbnails and metadata display
- **Interactive Menus**: Click-based navigation

#### Advanced Functions

- **Drag & Drop**: URL input via drag and drop
- **Batch Processing**: Visual batch download management
- **Live Previews**: Real-time format and quality previews
- **Settings Panel**: Visual configuration interface

### Textual TUI Features

#### Panel Layout

- **Main Panel**: Download management and controls
- **Side Panel**: Configuration and settings
- **Status Bar**: System information and notifications
- **Command Palette**: Quick command access

#### Keyboard Shortcuts

```
Navigation:
- Tab / Shift+Tab   : Move between panels
- Enter             : Activate/confirm
- Esc               : Cancel/back
- Ctrl+C            : Quit application

Downloads:
- Ctrl+D            : New download
- Ctrl+P            : Pause/resume
- Ctrl+Q            : Queue management
- Ctrl+H            : Download history

Configuration:
- Ctrl+S            : Settings
- Ctrl+T            : Themes
- Ctrl+,            : Preferences
```

#### Advanced Widgets

- **Data Tables**: Sortable download lists
- **Progress Bars**: Multi-progress tracking
- **Log Viewer**: Real-time log monitoring
- **Configuration Forms**: Interactive settings

## ⚙️ Configuration Options

### Interface Preferences

You can customize interface behavior through the customization system:

```bash
# Show current interface settings
snatch customize interface --show

# Set interface mode preference
snatch customize interface --setting interface_mode --value detailed

# Enable animations
snatch customize interface --setting animate_progress --value true

# Configure keyboard shortcuts
snatch customize interface --setting enable_keyboard_shortcuts --value true
```

### Performance Settings

Optimize interface performance for your system:

```bash
# Reduce animations for slower systems
snatch customize interface --setting animate_progress --value false

# Limit display items for better performance
snatch customize interface --setting max_display_items --value 50

# Enable high contrast mode for accessibility
snatch customize interface --setting high_contrast_mode --value true
```

## 🔧 Troubleshooting

### Common Issues

#### Interface Won't Launch

```bash
# Check dependencies
pip install -r setupfiles/requirements.txt

# Verify installation
snatch --version

# Test fallback mode
snatch interactive
```

#### Theme Issues

```bash
# Reset theme to default
snatch customize theme set --theme default

# Check current theme
snatch customize theme show

# List available themes
snatch customize theme list
```

#### Performance Issues

```bash
# Disable animations
snatch customize interface --setting animate_progress --value false

# Reduce concurrent operations
snatch customize performance --setting max_concurrent_downloads --value 3

# Clear cache
snatch clear-cache --type all
```

### Fallback Behavior

If an interface mode fails to launch, Snatch automatically falls back:

1. **Modern → Enhanced Interactive**
2. **Textual → Enhanced Interactive**
3. **Enhanced Interactive → Standard CLI**

### Dependencies

Different interfaces have different requirements:

- **Enhanced Interactive**: Rich library (included in requirements)
- **Modern Interface**: Additional UI components
- **Textual TUI**: Textual library (optional dependency)

## 🎛️ Advanced Usage

### Custom Interface Configuration

Create custom interface profiles:

```bash
# Create work profile with minimal interface
snatch customize profile create --name work
snatch customize interface --setting interface_mode --value compact
snatch customize theme set --theme minimal

# Create media profile with full features
snatch customize profile create --name media
snatch customize interface --setting interface_mode --value detailed
snatch customize theme set --theme cyberpunk
```

### Scripting with Interactive Modes

```bash
# Launch specific interface from script
echo "snatch modern" | cmd

# Use environment variables
set SNATCH_INTERFACE=textual
snatch

# Batch operations with interface
snatch modern --batch urls.txt
```

### Integration with Workflows

```bash
# Development workflow
snatch customize theme set --theme cyberpunk
snatch textual

# Presentation mode
snatch customize theme set --theme minimal
snatch modern

# Production/server mode
snatch customize theme set --theme default
snatch  # CLI mode
```

## 📚 Additional Resources

- **[Customization Guide](./CUSTOMIZATION_GUIDE.md)** - Complete customization options
- **[Usage Guide](./USAGE_GUIDE.md)** - Command examples and workflows
- **[Configuration Management](./CONFIGURATION_MANAGEMENT.md)** - Settings and profiles
- **[Troubleshooting Guide](./TROUBLESHOOTING_GUIDE.md)** - Common issues and solutions

## 🤝 Interface Comparison

| Feature | Enhanced | Modern | Textual | CLI |
|---------|----------|---------|---------|-----|
| **Ease of Use** | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐ |
| **Visual Appeal** | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐ |
| **Performance** | ⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ |
| **Power User Features** | ⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ |
| **Customization** | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ |
| **Accessibility** | ⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ |

Choose the interface that best matches your workflow and preferences!
