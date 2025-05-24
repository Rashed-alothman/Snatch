# Snatch Technical Documentation

## Table of Contents

1. [Project Architecture Overview](#project-architecture-overview)
2. [File Structure Documentation](#file-structure-documentation)
3. [Class Documentation](#class-documentation)
4. [Module Documentation](#module-documentation)
5. [Plugin Development Guide](#plugin-development-guide)
6. [API Reference](#api-reference)
7. [Integration Points](#integration-points)

## Project Architecture Overview

### High-Level System Design

Snatch is a modular, asynchronous media downloader built on Python with support for peer-to-peer sharing, advanced audio processing, and extensible plugin architecture. The system follows a layered architecture pattern with clear separation of concerns.

```
┌─────────────────────────────────────────┐
│              CLI Interface              │
│  (cli.py, interactive_mode.py,         │
│   cyberpunk_ui.py, textual_interface)  │
├─────────────────────────────────────────┤
│           Core Management Layer         │
│     (manager.py, session.py)           │
├─────────────────────────────────────────┤
│         Processing & Enhancement        │
│  (audio_processor.py, file_organizer)  │
├─────────────────────────────────────────┤
│      Networking & P2P Layer           │
│    (network.py, p2p.py, cache.py)     │
├─────────────────────────────────────────┤
│         Configuration & Utils          │
│  (config.py, defaults.py, constants)   │
├─────────────────────────────────────────┤
│         Infrastructure Layer           │
│ (logging_config.py, error_handler.py) │
└─────────────────────────────────────────┘
```

### Component Interaction Diagrams

#### Download Flow
```
User Input → CLI → DownloadManager → SessionManager → Network Layer → File System
                ↓                      ↓                ↓
         ConfigManager ←─── Cache ←─── Progress ←─── AudioProcessor
```

#### Plugin System Architecture
```
Plugin Interface ← Hook Registry → Download Manager
       ↓                ↓              ↓
 Plugin Loader ←─ Event System ←─ Post Processors
```

### Data Flow Explanation

1. **Input Processing**: CLI receives user commands and validates URLs
2. **Configuration Loading**: System loads user preferences and default settings
3. **Session Management**: Creates and tracks download sessions
4. **Download Execution**: Async download manager handles concurrent downloads
5. **Post-Processing**: Audio enhancement and file organization
6. **Cache Management**: Stores metadata and enables resume functionality

### Dependency Relationships

- **Core Dependencies**: yt-dlp, aiohttp, typer, rich
- **Audio Processing**: ffmpeg, librosa, soundfile, noisereduce
- **P2P Networking**: pyp2p, twisted, cryptography
- **UI Framework**: textual, rich, prompt_toolkit

## File Structure Documentation

### Entry Points

#### `modules/__init__.py`
- **Purpose**: Package initialization and public API definition
- **Exports**: `main_app`, `DownloadManager`, `load_config`, `__version__`
- **Integration Points**: Primary entry point for external usage

#### `modules/cli.py`
- **Purpose**: Command-line interface implementation with Rich formatting
- **Key Classes**: `EnhancedCLI`
- **Dependencies**: typer, rich, asyncio
- **Integration Points**: Main application entry point

### Core Management

#### `modules/manager.py`
- **Purpose**: Central download management with async/sync support
- **Key Classes**: `AsyncDownloadManager`, `DownloadManager`, `DownloadHooks`
- **Features**: Error recovery, retry mechanisms, memory management
- **Plugin Hooks**: Pre/post download, chunk processing, custom processors

#### `modules/session.py`
- **Purpose**: Session persistence and state management
- **Key Classes**: `AsyncSessionManager`, `SessionManager`
- **Features**: Download resumption, session tracking, concurrent session handling

### Configuration System

#### `modules/config.py`
- **Purpose**: Configuration loading and validation
- **Key Functions**: `load_config`, `initialize_config_async`
- **Integration Points**: All components depend on configuration

#### `modules/defaults.py`
- **Purpose**: Default values and format presets
- **Constants**: `FORMAT_PRESETS`, `CACHE_DIR`, `MAX_RETRIES`

### Processing & Enhancement

#### `modules/audio_processor.py`
- **Purpose**: Advanced audio processing and enhancement
- **Key Classes**: `AudioProcessor`, `EnhancedAudioProcessor`
- **Features**: Surround sound upmixing, noise reduction, normalization
- **Plugin Integration**: Extensible filter chains, custom processing pipelines

#### `modules/file_organizer.py`
- **Purpose**: File system organization and metadata management
- **Key Classes**: `FileOrganizer`
- **Features**: Smart file organization, metadata extraction

### Networking

#### `modules/network.py`
- **Purpose**: Network utilities and connectivity management
- **Key Functions**: `check_internet_connection`, `run_speedtest`
- **Features**: Speed testing, network monitoring

#### `modules/p2p.py`
- **Purpose**: Peer-to-peer file sharing implementation
- **Features**: DHT support, file sharing, NAT traversal preparation

### User Interface

#### `modules/cyberpunk_ui.py` & `modules/cyberpunk_interactive.py`
- **Purpose**: Modern cyberpunk-themed interactive interface
- **Key Classes**: `CyberpunkInteractiveApp`
- **Features**: Rich UI, progress tracking, interactive controls

#### `modules/textual_interface.py`
- **Purpose**: Textual-based terminal user interface
- **Features**: Modern TUI with widgets, responsive design

### Utilities & Infrastructure

#### `modules/error_handler.py`
- **Purpose**: Centralized error handling and reporting
- **Key Classes**: `EnhancedErrorHandler`
- **Features**: Error categorization, logging, recovery strategies

#### `modules/logging_config.py`
- **Purpose**: Logging configuration and formatting
- **Features**: Rich formatting, module-level logging, colored output

#### `modules/cache.py`
- **Purpose**: Download caching and metadata storage
- **Key Classes**: `DownloadCache`
- **Features**: Resume support, metadata caching

#### `modules/progress.py`
- **Purpose**: Progress tracking and display
- **Key Classes**: `DownloadStats`, `Spinner`
- **Features**: Real-time progress, speed calculation

## Class Documentation

### Core Classes

#### `AsyncDownloadManager`
- **Purpose**: Manages asynchronous downloads with advanced features
- **Inheritance**: Inherits from base manager protocols
- **Key Methods**:
  - `download_async()`: Asynchronous download execution
  - `register_hooks()`: Plugin hook registration
  - `batch_download()`: Concurrent download management
- **Plugin Integration**: Provides hooks for pre/post processing, progress monitoring

#### `EnhancedCLI`
- **Purpose**: Rich command-line interface with preset support
- **Key Methods**:
  - `run_download()`: Execute download with context management
  - `get_or_create_event_loop()`: Async loop management
- **Usage Example**:
```python
config = load_config()
cli = EnhancedCLI(config)
await cli.run_download(urls, options)
```

#### `AudioProcessor`
- **Purpose**: Advanced audio processing and enhancement
- **Key Methods**:
  - `upmix_to_7_1()`: Surround sound processing
  - `denoise_audio()`: Noise reduction
  - `normalize_audio()`: Loudness normalization
- **Plugin Integration**: Extensible filter chains, custom audio effects

#### `DownloadHooks` (Abstract Base Class)
- **Purpose**: Define plugin interface for download lifecycle events
- **Required Methods**:
  - `pre_download()`: Called before download starts
  - `post_chunk()`: Called after each chunk download
  - `post_download()`: Called after download completion
- **Usage Example**:
```python
class CustomHook(DownloadHooks):
    async def pre_download(self, url, metadata):
        # Custom pre-processing logic
        pass
```

## Module Documentation

### `modules.cli`
- **Responsibility**: Command-line interface and user interaction
- **Public API**: `main()`, `EnhancedCLI`
- **Configuration**: Format presets, output options, UI preferences
- **Plugin Hooks**: Command extensions, custom UI elements

### `modules.manager`
- **Responsibility**: Core download management and coordination
- **Public API**: `AsyncDownloadManager`, `DownloadManager`, `DownloadHooks`
- **Configuration**: Retry settings, memory limits, concurrent downloads
- **Plugin Hooks**: Download lifecycle, custom processors, error handlers

### `modules.audio_processor`
- **Responsibility**: Audio enhancement and processing
- **Public API**: `AudioProcessor`, `EnhancedAudioProcessor`
- **Configuration**: FFmpeg settings, filter presets, quality options
- **Plugin Hooks**: Custom filters, processing pipelines, format converters

### `modules.session`
- **Responsibility**: Session persistence and state management
- **Public API**: `AsyncSessionManager`, `SessionManager`
- **Configuration**: Session storage location, cleanup policies
- **Plugin Hooks**: Session lifecycle, custom storage backends

### `modules.network`
- **Responsibility**: Network operations and monitoring
- **Public API**: Network utility functions, connectivity checks
- **Configuration**: Timeout settings, proxy configuration
- **Plugin Hooks**: Custom network adapters, monitoring extensions

## Plugin Development Guide

### Plugin Architecture

Snatch uses a hook-based plugin system that allows extensions at multiple levels:

1. **Download Hooks**: Extend download lifecycle
2. **Processing Hooks**: Add custom post-processing
3. **UI Hooks**: Custom interface elements
4. **Network Hooks**: Custom network adapters

### Plugin Interfaces

#### DownloadHooks Interface
```python
from abc import ABC, abstractmethod
from typing import Dict, Any

class DownloadHooks(ABC):
    @abstractmethod
    async def pre_download(self, url: str, metadata: Dict[str, Any]) -> None:
        """Called before download starts"""
        pass
        
    @abstractmethod
    async def post_chunk(self, chunk: DownloadChunk, sha256: str) -> None:
        """Called after each chunk is downloaded"""
        pass
        
    @abstractmethod
    async def post_download(self, url: str, file_path: str) -> None:
        """Called after download completes"""
        pass
```

### Hook System

#### Available Extension Points

1. **Download Lifecycle**
   - `pre_download`: Validate URLs, setup custom options
   - `post_chunk`: Progress monitoring, chunk validation
   - `post_download`: File processing, notification

2. **Processing Pipeline**
   - `register_post_processor`: Custom file processing
   - `register_download_hook`: Download event handling

3. **Audio Processing**
   - Custom FFmpeg filters
   - Audio enhancement pipelines
   - Format conversion extensions

### Plugin Registration

#### Hook Registration Example
```python
# Register download hooks
manager = AsyncDownloadManager(config)
manager.register_hooks("my_plugin", MyCustomHooks())

# Register post-processor
manager.register_post_processor(my_custom_processor)
```

#### Custom Processor Example
```python
async def my_custom_processor(file_path: str, options: Dict[str, Any]) -> None:
    """Custom post-processing function"""
    # Implement custom logic here
    logger.info(f"Processing {file_path} with options {options}")
```

### Best Practices

1. **Error Handling**: Always implement proper error handling in plugins
2. **Async/Await**: Use async patterns for I/O operations
3. **Logging**: Use module-level logging for debugging
4. **Configuration**: Make plugins configurable through the main config
5. **Testing**: Include unit tests for plugin functionality

### Example Plugin: Custom Notification

```python
import logging
from typing import Dict, Any
from modules.manager import DownloadHooks, DownloadChunk

logger = logging.getLogger(__name__)

class NotificationPlugin(DownloadHooks):
    """Plugin that sends notifications on download completion"""
    
    def __init__(self, notification_service):
        self.notification_service = notification_service
    
    async def pre_download(self, url: str, metadata: Dict[str, Any]) -> None:
        """Log download start"""
        logger.info(f"Starting download: {url}")
    
    async def post_chunk(self, chunk: DownloadChunk, sha256: str) -> None:
        """Validate chunk integrity"""
        logger.debug(f"Downloaded chunk: {chunk.start}-{chunk.end}")
    
    async def post_download(self, url: str, file_path: str) -> None:
        """Send completion notification"""
        await self.notification_service.send(
            f"Download completed: {file_path}"
        )

# Registration
def register_plugin(manager):
    notification_plugin = NotificationPlugin(notification_service)
    manager.register_hooks("notification", notification_plugin)
```

### Plugin Configuration

Plugins can be configured through the main configuration file:

```json
{
  "plugins": {
    "notification": {
      "enabled": true,
      "service": "email",
      "email": "user@example.com"
    },
    "custom_processor": {
      "enabled": true,
      "options": {
        "quality": "high",
        "format": "mp3"
      }
    }
  }
}
```

## API Reference

### Public API Overview

The Snatch public API is exposed through `modules/__init__.py`:

```python
from modules import main_app, DownloadManager, load_config, __version__
```

### Core Functions

#### `main_app()`
- **Purpose**: Main application entry point
- **Parameters**: None (uses CLI arguments)
- **Returns**: Exit code
- **Usage**: `python -m modules.cli`

#### `load_config(config_path: Optional[str] = None) -> Dict[str, Any]`
- **Purpose**: Load and validate configuration
- **Parameters**: Optional path to config file
- **Returns**: Configuration dictionary
- **Usage**: `config = load_config("custom_config.json")`

### Manager API

#### `AsyncDownloadManager`
```python
class AsyncDownloadManager:
    def __init__(self, config: Dict[str, Any], 
                 session_manager: SessionManager,
                 download_cache: DownloadCache)
    
    async def download_async(self, urls: List[str], 
                           options: Dict[str, Any]) -> List[str]
    
    def register_hooks(self, name: str, hooks: DownloadHooks) -> None
    
    def register_post_processor(self, processor: Callable) -> None
```

## Integration Points

### External System Integration

1. **yt-dlp Integration**: Core download engine
2. **FFmpeg Integration**: Audio/video processing
3. **P2P Network Integration**: Distributed file sharing
4. **Rich/Textual Integration**: Modern UI framework

### Configuration Integration

- JSON-based configuration system
- Environment variable support
- Profile-based configurations
- Runtime configuration updates

### Logging Integration

- Rich-formatted console output
- File-based error logging
- Module-level log configuration
- Structured logging for analysis

### Cache Integration

- Metadata caching for resume support
- Download history tracking
- Performance optimization through caching

This documentation provides a comprehensive technical overview of the Snatch project architecture, enabling developers to understand, extend, and contribute to the codebase effectively.
