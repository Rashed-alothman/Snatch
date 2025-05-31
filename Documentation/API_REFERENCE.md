# API Reference Documentation

## Overview

This document provides complete API reference for the Snatch Media Downloader, including all public interfaces, methods, parameters, and usage examples.

## Table of Contents

1. [Core API](#core-api)
2. [Manager API](#manager-api)  
3. [Configuration API](#configuration-api)
4. [Session Management API](#session-management-api)
5. [Audio Processing API](#audio-processing-api)
6. [Network API](#network-api)
7. [P2P API](#p2p-api)
8. [UI Components API](#ui-components-api)
9. [Plugin API](#plugin-api)
10. [Utility Functions](#utility-functions)

---

## Core API

### Main Entry Points

#### `modules.main_app()`

**Description**: Primary application entry point
**Parameters**: None (uses CLI arguments)
**Returns**: `int` - Exit code (0 for success, non-zero for error)
**Usage**:

```python
from modules import main_app
exit_code = main_app()
```

#### `modules.load_config(config_path: Optional[str] = None) -> Dict[str, Any]`

**Description**: Load and validate configuration from file or defaults
**Parameters**:

- `config_path` (optional): Path to configuration file
**Returns**: `Dict[str, Any]` - Merged configuration dictionary
**Raises**: `ConfigurationError` if configuration is invalid
**Usage**:

```python
from modules import load_config

# Load default configuration
config = load_config()

# Load from specific file
config = load_config("/path/to/custom_config.json")
```

---

## Manager API

### AsyncDownloadManager

#### Constructor

```python
AsyncDownloadManager(
    config: Dict[str, Any],
    session_manager: Optional[SessionManager] = None,
    download_cache: Optional[DownloadCache] = None,
    http_client: Optional[HTTPClientProtocol] = None
)
```

**Parameters**:

- `config`: Configuration dictionary
- `session_manager`: Session persistence manager
- `download_cache`: Cache for metadata and partial downloads
- `http_client`: Custom HTTP client implementation

#### Methods

##### `download_async(urls: List[str], options: Dict[str, Any]) -> List[str]`

**Description**: Download multiple URLs asynchronously
**Parameters**:

- `urls`: List of URLs to download
- `options`: Download options dictionary
**Returns**: List of downloaded file paths
**Raises**: `DownloadError`, `NetworkError`, `ResourceError`

**Options Dictionary**:

```python
options = {
    "format": "bestvideo+bestaudio/best",  # Format selection
    "quality": "1080",                     # Video quality
    "audio_only": False,                   # Audio-only download
    "output_path": "downloads/",           # Output directory
    "organize_files": True,                # Auto-organize files
    "extract_audio": False,                # Extract audio from video
    "upmix_7_1": False,                   # 7.1 surround upmix
    "denoise_audio": False,               # Audio denoising
    "normalize_audio": False,             # Audio normalization
    "concurrent_downloads": 3,            # Parallel downloads
    "chunk_size": 1048576,               # Download chunk size
    "retry_attempts": 5,                 # Retry on failure
    "verify_ssl": True,                  # SSL verification
    "user_agent": "custom_ua",           # Custom user agent
    "cookies": "cookies.txt",            # Cookie file
    "proxy": "http://proxy:8080",        # Proxy server
    "rate_limit": "1M",                  # Bandwidth limit
}
```

**Usage Example**:

```python
async with AsyncDownloadManager(config) as manager:
    files = await manager.download_async(
        urls=["https://example.com/video1", "https://example.com/video2"],
        options={"quality": "720", "audio_only": True}
    )
    print(f"Downloaded: {files}")
```

##### `register_hooks(name: str, hooks: DownloadHooks) -> None`

**Description**: Register plugin hooks for download lifecycle events
**Parameters**:

- `name`: Unique identifier for the hook set
- `hooks`: Hook implementation instance

**Usage**:

```python
class CustomHooks(DownloadHooks):
    async def pre_download(self, url, metadata):
        print(f"Starting download: {url}")
    
    async def post_chunk(self, chunk, sha256):
        print(f"Downloaded chunk: {chunk.start}-{chunk.end}")
    
    async def post_download(self, url, file_path):
        print(f"Completed: {file_path}")

manager.register_hooks("custom", CustomHooks())
```

##### `register_post_processor(processor: Callable[[str, Dict[str, Any]], None]) -> None`

**Description**: Register custom post-processing function
**Parameters**:

- `processor`: Function to process downloaded files

**Usage**:

```python
async def custom_processor(file_path: str, metadata: Dict[str, Any]) -> None:
    # Custom processing logic
    print(f"Processing {file_path}")

manager.register_post_processor(custom_processor)
```

##### `batch_download(urls: List[str], options: Dict[str, Any]) -> Dict[str, Any]`

**Description**: Download multiple URLs with progress tracking
**Returns**: Dictionary with download results and statistics

##### `resume_download(session_id: str) -> bool`

**Description**: Resume a paused or interrupted download
**Parameters**:

- `session_id`: Session identifier from session manager
**Returns**: `True` if resume successful, `False` otherwise

##### `cancel_download(session_id: str) -> bool`

**Description**: Cancel an active download
**Parameters**:

- `session_id`: Session identifier
**Returns**: `True` if cancellation successful

---

## Configuration API

### Configuration Functions

#### `initialize_config_async() -> Dict[str, Any]`

**Description**: Asynchronously initialize configuration with validation
**Returns**: Validated configuration dictionary
**Features**:

- FFmpeg validation
- Directory creation
- Network connectivity check
- Plugin discovery

#### `check_for_updates() -> Tuple[bool, Optional[str]]`

**Description**: Check for application updates
**Returns**: Tuple of (update_available, latest_version)

#### `validate_config(config: Dict[str, Any]) -> List[str]`

**Description**: Validate configuration and return any errors
**Parameters**:

- `config`: Configuration dictionary to validate
**Returns**: List of validation error messages

### Configuration Schema

#### Core Configuration

```python
{
    "version": "2.0.0",
    "download_dir": "downloads/",
    "temp_dir": "temp/",
    "cache_dir": "cache/",
    "sessions_dir": "sessions/",
    "config_dir": "config/",
    "max_concurrent_downloads": 3,
    "chunk_size": 1048576,
    "timeout": 30,
    "user_agent": "Snatch Media Downloader/2.0.0",
    "retry_attempts": 5,
    "verify_ssl": True
}
```

#### Audio Processing Configuration

```python
{
    "audio_processing": {
        "ffmpeg_path": "/usr/bin/ffmpeg",
        "enable_upmix": True,
        "enable_denoise": True, 
        "enable_normalize": True,
        "default_format": "flac",
        "quality": "320k",
        "sample_rate": 96000,
        "upmix_settings": {
            "content_detection": True,
            "spatial_enhancement": True,
            "center_boost": 0.15
        },
        "denoise_settings": {
            "strength": "medium",
            "preserve_quality": True
        },
        "normalize_settings": {
            "target_lufs": -14.0,
            "true_peak": -1.0
        }
    }
}
```

#### Network Configuration

```python
{
    "network": {
        "enable_ipv6": True,
        "proxy": null,
        "cookies_file": null,
        "rate_limit": null,
        "connection_pool_size": 10,
        "keepalive_timeout": 30
    }
}
```

---

## Session Management API

### AsyncSessionManager

#### Constructor

```python
AsyncSessionManager(session_file: str = "sessions/download_sessions.json")
```

#### Methods

##### `create_session(url: str, options: Dict[str, Any]) -> str`

**Description**: Create new download session
**Returns**: Session ID (UUID)

##### `update_session(session_id: str, updates: Dict[str, Any]) -> bool`

**Description**: Update session with new information
**Parameters**:

- `session_id`: Session identifier
- `updates`: Dictionary of fields to update

##### `get_session(session_id: str) -> Optional[Dict[str, Any]]`

**Description**: Retrieve session by ID
**Returns**: Session data or None if not found

##### `list_sessions(status: Optional[str] = None) -> List[Dict[str, Any]]`

**Description**: List all sessions, optionally filtered by status
**Parameters**:

- `status`: Filter by status ("active", "paused", "completed", "failed")

##### `delete_session(session_id: str) -> bool`

**Description**: Delete session from storage

##### `cleanup_old_sessions(max_age_days: int = 30) -> int`

**Description**: Remove old completed/failed sessions
**Returns**: Number of sessions cleaned up

**Session Data Structure**:

```python
{
    "session_id": "uuid4_string",
    "url": "source_url",
    "status": "active|paused|completed|failed|cancelled",
    "created_at": "2023-12-01T10:30:00Z",
    "updated_at": "2023-12-01T10:35:00Z",
    "completed_at": null,
    "progress": {
        "downloaded_bytes": 1048576,
        "total_bytes": 10485760,
        "percentage": 10.0,
        "speed": 1024000,  # bytes per second
        "eta": 300         # seconds
    },
    "metadata": {
        "title": "Video Title",
        "uploader": "Channel Name",
        "duration": 600,
        "format": "mp4",
        "quality": "1080p"
    },
    "options": {
        "audio_only": false,
        "quality": "1080",
        "output_path": "downloads/"
    },
    "files": [
        {
            "path": "downloads/video.mp4",
            "size": 10485760,
            "format": "mp4",
            "type": "video"
        }
    ],
    "error_info": {
        "error_type": "NetworkError",
        "error_message": "Connection timeout",
        "retry_count": 2,
        "last_error_at": "2023-12-01T10:35:00Z"
    }
}
```

---

## Audio Processing API

### AudioProcessor

#### Constructor

```python
AudioProcessor(config: Dict[str, Any])
```

#### Methods

##### `upmix_to_7_1(input_file: str, output_file: Optional[str] = None, content_type: str = "auto") -> bool`

**Description**: Convert audio to 7.1 surround sound
**Parameters**:

- `input_file`: Path to input audio file
- `output_file`: Output path (auto-generated if None)
- `content_type`: "music", "speech", "movie", or "auto"
**Returns**: `True` if successful

##### `denoise_audio(input_file: str, strength: str = "medium", preserve_quality: bool = True) -> bool`

**Description**: Apply noise reduction to audio
**Parameters**:

- `input_file`: Input audio file path
- `strength`: "light", "medium", "heavy"
- `preserve_quality`: Preserve audio quality during processing

##### `normalize_audio(input_file: str, target_lufs: float = -14.0, true_peak: float = -1.0) -> bool`

**Description**: Normalize audio levels using EBU R128 standard
**Parameters**:

- `input_file`: Input audio file path
- `target_lufs`: Target loudness in LUFS
- `true_peak`: Maximum true peak level in dBTP

##### `extract_audio(video_file: str, audio_format: str = "flac", quality: str = "best") -> Optional[str]`

**Description**: Extract audio from video file
**Parameters**:

- `video_file`: Input video file path
- `audio_format`: Output audio format
- `quality`: Audio quality ("best", "320k", "256k", etc.)
**Returns**: Path to extracted audio file

##### `convert_format(input_file: str, output_format: str, quality: str = "best") -> Optional[str]`

**Description**: Convert audio to different format
**Parameters**:

- `input_file`: Input audio file
- `output_format`: Target format ("mp3", "flac", "wav", etc.)
- `quality`: Quality setting

### EnhancedAudioProcessor

Enhanced processor with AI-based improvements, professional presets, and advanced algorithms introduced in v1.8.0.

#### Constructor

```python
EnhancedAudioProcessor(config: Dict[str, Any])
```

#### Core Enhancement Methods

##### `enhance_audio(input_file: str, preset: str = "music", output_file: Optional[str] = None, custom_settings: Optional[AudioEnhancementSettings] = None) -> str`

**Description**: Enhance audio using professional presets and AI algorithms
**Parameters**:

- `input_file`: Path to input audio file
- `preset`: Enhancement preset ("podcast", "music", "speech", "broadcast", "restoration")
- `output_file`: Output path (auto-generated if None)
- `custom_settings`: Override preset with custom AudioEnhancementSettings
**Returns**: Path to enhanced audio file
**Raises**: `AudioProcessingError`, `FileNotFoundError`

##### `get_available_presets() -> Dict[str, Dict[str, Any]]`

**Description**: Get all available enhancement presets with descriptions and settings
**Returns**: Dictionary mapping preset names to configuration details

```python
{
    "podcast": {
        "description": "Optimized for speech content with noise reduction and clarity",
        "noise_reduction": 0.8,
        "normalize_loudness": True,
        "target_lufs": -16.0,
        "enhance_speech": True,
        "stereo_width": 1.0
    },
    "music": {
        "description": "Optimized for music with stereo enhancement and dynamic preservation",
        "noise_reduction": 0.3,
        "normalize_loudness": True,
        "target_lufs": -14.0,
        "stereo_width": 1.2,
        "preserve_dynamics": True
    }
    # ... other presets
}
```

##### `analyze_audio_quality(file_path: str) -> AudioQuality`

**Description**: Comprehensive audio quality analysis with AI-powered recommendations
**Parameters**:

- `file_path`: Path to audio file to analyze
**Returns**: AudioQuality dataclass with analysis results
**AudioQuality Structure**:

```python
@dataclass
class AudioQuality:
    noise_level: float          # 0.0-1.0, lower is better
    dynamic_range: float        # dB, higher is better
    spectral_balance: float     # 0.0-1.0, closer to 1.0 is better
    distortion_level: float     # 0.0-1.0, lower is better
    loudness_lufs: float        # EBU R128 loudness
    peak_db: float             # Peak level in dB
    recommended_preset: str     # AI-recommended enhancement preset
    quality_score: float       # Overall quality score 0.0-10.0
```

##### `get_audio_stats(file_path: str) -> AudioStats`

**Description**: Extract comprehensive audio file statistics
**Parameters**:

- `file_path`: Path to audio file
**Returns**: AudioStats dataclass with file information
**AudioStats Structure**:

```python
@dataclass
class AudioStats:
    sample_rate: int           # Hz
    channels: int              # Number of audio channels
    duration: float            # Duration in seconds
    bitrate: Optional[int]     # Bitrate in kbps
    codec: str                 # Audio codec
    file_size: int             # File size in bytes
    format: str                # Container format
```

#### Batch Processing Methods

##### `batch_enhance(file_pattern: str, preset: str = "music", output_dir: Optional[str] = None, max_workers: int = 4) -> List[str]`

**Description**: Batch enhance multiple audio files with parallel processing
**Parameters**:

- `file_pattern`: Glob pattern for input files (e.g., "*.mp3", "audio/**/*.wav")
- `preset`: Enhancement preset to apply
- `output_dir`: Output directory (defaults to input directory)
- `max_workers`: Maximum concurrent processing threads
**Returns**: List of enhanced file paths
**Example**:

```python
# Enhance all MP3 files in a directory
enhanced_files = processor.batch_enhance(
    "music_collection/*.mp3", 
    preset="music",
    max_workers=8
)
```

##### `create_custom_preset(name: str, description: str, settings: AudioEnhancementSettings) -> bool`

**Description**: Create and save a custom enhancement preset
**Parameters**:

- `name`: Unique preset name
- `description`: Human-readable description
- `settings`: AudioEnhancementSettings configuration
**Returns**: True if preset created successfully

#### Advanced Processing Methods

##### `advanced_7_1_upmix(input_file: str, content_analysis: bool = True, spatial_enhancement: bool = True) -> bool`

**Description**: Advanced upmixing with content analysis and AI spatial enhancement
**Parameters**:

- `input_file`: Input audio file
- `content_analysis`: Enable automatic content type detection
- `spatial_enhancement`: Apply AI-powered spatial enhancement
**Returns**: True if successful

##### `frequency_extension(input_file: str, target_frequency: int = 20000) -> bool`

**Description**: Extend frequency range using AI-powered bandwidth extension
**Parameters**:

- `input_file`: Input audio file path
- `target_frequency`: Target upper frequency in Hz
**Returns**: True if successful

##### `stereo_widening(input_file: str, width_factor: float = 1.5, preserve_mono: bool = True) -> bool`

**Description**: Apply stereo widening with configurable intensity
**Parameters**:

- `input_file`: Input audio file path
- `width_factor`: Widening factor (1.0 = original, >1.0 = wider)
- `preserve_mono`: Preserve mono compatibility
**Returns**: True if successful

#### Configuration Classes

##### AudioEnhancementSettings

```python
@dataclass
class AudioEnhancementSettings:
    # Noise Reduction
    noise_reduction: float = 0.5           # 0.0-1.0 noise reduction strength
    preserve_quality: bool = True          # Preserve audio quality during NR
    
    # Loudness Normalization
    normalize_loudness: bool = True        # Apply EBU R128 normalization
    target_lufs: float = -14.0            # Target loudness in LUFS
    max_true_peak: float = -1.0           # Maximum true peak in dBTP
    
    # Dynamic Processing
    apply_compression: bool = False        # Apply dynamic compression
    compression_ratio: float = 3.0        # Compression ratio
    compression_threshold: float = -12.0   # Threshold in dB
    
    # Frequency Processing
    extend_frequency: bool = False         # Enable frequency extension
    target_frequency: int = 20000         # Target upper frequency Hz
    
    # Stereo Enhancement
    stereo_width: float = 1.0             # Stereo width factor
    enhance_stereo: bool = False          # Apply stereo enhancement
    
    # Content-Specific
    enhance_speech: bool = False          # Speech-specific enhancements
    preserve_dynamics: bool = True        # Preserve original dynamics
    
    # Output Settings
    output_sample_rate: Optional[int] = None  # Resample to specific rate
    output_bit_depth: int = 24            # Output bit depth
```

---

## Network API

### Network Utilities

#### `check_internet_connection(timeout: int = 5) -> bool`

**Description**: Check internet connectivity
**Parameters**:

- `timeout`: Connection timeout in seconds
**Returns**: `True` if connected

#### `run_speedtest(duration: int = 10) -> Dict[str, float]`

**Description**: Perform network speed test
**Parameters**:

- `duration`: Test duration in seconds
**Returns**: Dictionary with speed test results

```python
{
    "download_mbps": 85.2,
    "upload_mbps": 12.1,
    "ping_ms": 15.8,
    "jitter_ms": 2.3,
    "packet_loss_percent": 0.1
}
```

#### `get_network_info() -> Dict[str, Any]`

**Description**: Get detailed network interface information
**Returns**: Network configuration details

#### `test_url_accessibility(url: str, timeout: int = 10) -> Tuple[bool, int, str]`

**Description**: Test if URL is accessible
**Returns**: Tuple of (accessible, status_code, response_time)

---

## P2P API

### P2PManager

#### Constructor

```python
P2PManager(config: Dict[str, Any])
```

#### Methods

##### `share_file(file_path: str, max_peers: int = 10, encryption: bool = True) -> str`

**Description**: Share file via P2P network
**Parameters**:

- `file_path`: Path to file to share
- `max_peers`: Maximum concurrent connections
- `encryption`: Enable end-to-end encryption
**Returns**: Share code for other peers

##### `fetch_file(share_code: str, output_path: str) -> bool`

**Description**: Download file using share code
**Parameters**:

- `share_code`: Code received from file sharer
- `output_path`: Directory to save downloaded file
**Returns**: `True` if download successful

##### `start() -> bool`

**Description**: Start P2P service
**Returns**: `True` if startup successful

##### `stop() -> None`

**Description**: Stop P2P service and cleanup

##### `get_peer_info() -> Dict[str, Any]`

**Description**: Get local peer information
**Returns**: Peer details and network status

### P2P Configuration

```python
{
    "p2p": {
        "enabled": True,
        "port_range": [49152, 65535],
        "max_connections": 50,
        "enable_upnp": True,
        "stun_servers": [
            "stun.l.google.com:19302",
            "stun1.l.google.com:19302"
        ],
        "turn_servers": [],
        "encryption": {
            "enabled": True,
            "key_size": 2048,
            "cipher": "AES-256-CBC"
        },
        "dht": {
            "enabled": True,
            "bootstrap_nodes": [
                "bootstrap.snatch.network:8080"
            ]
        }
    }
}
```

---

## UI Components API

### CyberpunkUI Components

#### CyberpunkBanner

```python
banner = CyberpunkBanner(theme="dark_city")
panel = banner.create_banner()
console.print(panel)
```

#### HolographicProgress

```python
progress = HolographicProgress(theme="matrix")
panel = progress.create_download_progress(
    filename="video.mp4",
    progress=65.5,
    speed="2.5 MB/s", 
    eta="45s"
)
console.print(panel)
```

#### MatrixDataTable

```python
table = MatrixDataTable(theme="synthwave")
format_table = table.create_format_table(formats)
console.print(format_table)
```

### Available Themes

- `"dark_city"`: Blue/cyan cyberpunk theme
- `"matrix"`: Green matrix-style theme  
- `"synthwave"`: Pink/purple synthwave theme

---

## Plugin API

### Hook Interfaces

#### DownloadHooks

```python
class DownloadHooks(ABC):
    @abstractmethod
    async def pre_download(self, url: str, metadata: Dict[str, Any]) -> None:
        """Called before download starts"""
        
    @abstractmethod  
    async def post_chunk(self, chunk: DownloadChunk, sha256: str) -> None:
        """Called after each chunk download"""
        
    @abstractmethod
    async def post_download(self, url: str, file_path: str) -> None:
        """Called after download completion"""
```

#### ProcessingPlugin

```python
class ProcessingPlugin(PluginInterface):
    @abstractmethod
    async def process_file(self, file_path: str, metadata: Dict[str, Any],
                          options: Dict[str, Any]) -> Optional[str]:
        """Process downloaded file"""
        
    @abstractmethod
    def supports_format(self, file_extension: str) -> bool:
        """Check format support"""
```

### Plugin Registration

#### Manual Registration

```python
# Register hooks
manager.register_hooks("plugin_name", hooks_instance)

# Register post-processor
manager.register_post_processor(processor_function)
```

#### Automatic Discovery

Plugins placed in the `plugins/` directory are automatically discovered and loaded based on configuration.

---

## Utility Functions

### File Operations

#### `sanitize_filename(filename: str) -> str`

**Description**: Remove invalid characters from filename
**Parameters**:

- `filename`: Original filename
**Returns**: Sanitized filename safe for filesystem

#### `format_size(bytes_value: float, precision: int = 2) -> str`

**Description**: Format byte size in human-readable format
**Parameters**:

- `bytes_value`: Size in bytes
- `precision`: Decimal precision
**Returns**: Formatted size string (e.g., "1.5 GB")

#### `ensure_dir(path: str) -> bool`

**Description**: Ensure directory exists, create if necessary
**Parameters**:

- `path`: Directory path
**Returns**: `True` if directory exists/created

### Validation Functions

#### `validate_url(url: str) -> bool`

**Description**: Validate URL format and accessibility
**Parameters**:

- `url`: URL to validate
**Returns**: `True` if valid

#### `is_supported_site(url: str) -> bool`

**Description**: Check if site is supported by downloader
**Parameters**:

- `url`: URL to check
**Returns**: `True` if supported

### System Information

#### `get_system_info() -> Dict[str, Any]`

**Description**: Get system information and resource usage
**Returns**: System details dictionary

```python
{
    "platform": "Windows-10",
    "python_version": "3.11.0",
    "cpu_count": 8,
    "memory_total_gb": 16.0,
    "memory_available_gb": 8.5,
    "disk_free_gb": 250.0,
    "ffmpeg_version": "4.4.0"
}
```

#### `display_system_stats() -> None`

**Description**: Display formatted system statistics to console

---

## Error Handling

### Exception Hierarchy

```python
class DownloadError(Exception):
    """Base exception for download errors"""

class NetworkError(DownloadError):
    """Network-related errors"""

class ResourceError(DownloadError):
    """Resource not found or access errors"""

class FileSystemError(DownloadError):
    """File I/O errors"""

class SystemResourceError(DownloadError):
    """System resource exhaustion"""

class AudioProcessingError(DownloadError):
    """Audio processing failures"""

class ConfigurationError(DownloadError):
    """Configuration validation errors"""
```

### Error Handling Best Practices

```python
try:
    async with AsyncDownloadManager(config) as manager:
        files = await manager.download_async(urls, options)
except NetworkError as e:
    print(f"Network error: {e}")
    # Retry with different options
except ResourceError as e:
    print(f"Resource not found: {e}")
    # Skip this URL
except SystemResourceError as e:
    print(f"System resources exhausted: {e}")
    # Reduce concurrent downloads
except DownloadError as e:
    print(f"Download failed: {e}")
    # Generic error handling
```

---

## Return Codes

### CLI Exit Codes

- `0`: Success
- `1`: General error
- `2`: Invalid arguments
- `3`: Configuration error
- `4`: Network error
- `5`: Resource error
- `6`: System resource error

### HTTP Status Integration

The API respects standard HTTP status codes when applicable and provides meaningful error messages based on server responses.

This API reference provides comprehensive documentation for all public interfaces in the Snatch Media Downloader, enabling developers to effectively integrate and extend the system.
