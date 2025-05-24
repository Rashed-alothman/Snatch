# Module Detailed Documentation

## Core Module Analysis

### modules/manager.py - Download Management System

#### Architecture Overview

The manager module implements a sophisticated dual-mode download system supporting both synchronous and asynchronous operations. It features advanced error recovery, memory management, and cross-platform compatibility.

#### Key Components

##### `AsyncDownloadManager`

**Purpose**: Primary asynchronous download coordinator with advanced features
**Inheritance Hierarchy**:

- Implements context manager protocols (`__aenter__`, `__aexit__`)
- Uses Protocol-based interfaces for HTTP clients

**Constructor Parameters**:

```python
def __init__(self, config: Dict[str, Any], 
             session_manager: Optional[SessionManager] = None,
             download_cache: Optional[DownloadCache] = None,
             http_client: Optional[HTTPClientProtocol] = None)
```

**Key Methods**:

- `download_async(urls, options)`: Main async download orchestrator
- `register_hooks(name, hooks)`: Plugin hook registration system
- `batch_download(urls, options)`: Concurrent multi-URL downloads
- `resume_download(session_id)`: Resume interrupted downloads
- `validate_chunk(chunk, expected_hash)`: Integrity verification

**Plugin Integration Points**:

- Pre-download hooks for URL validation and metadata extraction
- Post-chunk hooks for progress monitoring and validation
- Post-download hooks for file processing and organization
- Error recovery hooks for custom retry strategies

**Usage Example**:

```python
async with AsyncDownloadManager(config, session_manager, cache) as manager:
    # Register custom hooks
    manager.register_hooks("analytics", AnalyticsHooks())
    
    # Execute download with progress tracking
    results = await manager.download_async(
        urls=["https://example.com/video"],
        options={"format": "bestaudio", "quality": "320k"}
    )
```

##### `DownloadHooks` Abstract Interface

**Purpose**: Defines plugin interface for download lifecycle events
**Required Methods**:

```python
async def pre_download(self, url: str, metadata: Dict[str, Any]) -> None
async def post_chunk(self, chunk: DownloadChunk, sha256: str) -> None  
async def post_download(self, url: str, file_path: str) -> None
```

**Implementation Example**:

```python
class TelemetryHooks(DownloadHooks):
    async def pre_download(self, url, metadata):
        self.start_time = time.time()
        await self.log_download_start(url, metadata)
    
    async def post_chunk(self, chunk, sha256):
        await self.update_progress_metrics(chunk.size)
    
    async def post_download(self, url, file_path):
        duration = time.time() - self.start_time
        await self.log_completion(url, file_path, duration)
```

#### Data Structures

##### `DownloadChunk`

```python
@dataclass
class DownloadChunk:
    start: int          # Byte range start
    end: int            # Byte range end  
    url: str            # Source URL
    data: bytes = None  # Chunk content
    retries: int = 0    # Retry count
```

##### Error Hierarchy

- `DownloadError`: Base exception for all download errors
- `NetworkError`: Network communication failures
- `ResourceError`: Resource availability issues
- `FileSystemError`: File I/O operations
- `SystemResourceError`: Memory/disk space issues

#### Memory Management

The manager implements sophisticated memory management:

- Dynamic memory monitoring using psutil
- Automatic garbage collection triggers
- Chunk size adaptation based on available memory
- Background memory cleanup tasks

#### Configuration Options

```json
{
  "max_concurrent_downloads": 3,
  "chunk_size": 8388608,
  "max_retries": 5,
  "retry_delay": 2.0,
  "memory_limit_percent": 80,
  "enable_resume": true,
  "verify_chunks": true
}
```

---

### modules/audio_processor.py - Audio Enhancement System

#### Architecture Overview

Implements professional-grade audio processing with FFmpeg integration, librosa-based analysis, and psychoacoustic enhancements.

#### Key Classes

##### `AudioProcessor`

**Purpose**: Core audio processing with FFmpeg integration
**Key Features**:

- 7.1 surround sound upmixing
- EBU R128 loudness normalization
- Multi-stage noise reduction
- FLAC integrity validation

**Method Signatures**:

```python
async def upmix_to_7_1(self, input_file: str, 
                       output_file: Optional[str] = None,
                       content_type: str = "auto") -> bool

async def denoise_audio(self, input_file: str,
                       strength: str = "medium",
                       preserve_quality: bool = True) -> bool

async def normalize_audio(self, input_file: str,
                         target_lufs: float = -14.0,
                         true_peak: float = -1.0) -> bool
```

**Filter Chain Architecture**:

```python
FFMPEG_FILTERS = {
    "spatial": {
        "default": (
            "afir=dry=5:wet=5:length=100:lpf=1000:hpf=20,"
            "firequalizer=gain_entry='entry(0,0);entry(250,-6);entry(1000,0)'"
        )
    },
    "denoise": {
        "light": "anlmdn=s=3:p=0.001:m=15:b=256",
        "heavy": "anlmdn=s=7:p=0.003:m=25:b=256"
    },
    "normalize": {
        "standard": "loudnorm=I=-14:TP=-1:LRA=11",
        "podcast": "loudnorm=I=-16:TP=-1:LRA=9"
    }
}
```

##### `EnhancedAudioProcessor`

**Purpose**: Advanced processing with librosa and AI-based enhancements
**Dependencies**: librosa, noisereduce, pyloudnorm, scipy

**Advanced Features**:

- Spectral analysis and visualization
- AI-enhanced noise reduction
- Psychoacoustic processing
- Advanced 7.1 upmixing with content detection

**Usage Example**:

```python
processor = EnhancedAudioProcessor(config)

# Process with full enhancement chain
await processor.process_with_enhancements(
    input_file="audio.flac",
    enhance_surround=True,
    denoise_level="medium", 
    normalize_target=-14.0
)
```

#### Plugin Integration

The audio processor supports extensible filter chains:

```python
# Register custom filter
processor.register_filter("custom_eq", {
    "filter": "equalizer=f=1000:t=h:w=200:g=3",
    "description": "Boost mid frequencies"
})

# Apply custom processing chain
await processor.apply_filter_chain([
    "custom_eq",
    "normalize_standard",
    "spatial_default"
])
```

---

### modules/p2p.py - Peer-to-Peer System

#### Architecture Overview

Implements secure P2P file sharing with NAT traversal, encryption, and DHT-based peer discovery.

#### Key Components

##### `P2PManager`

**Purpose**: Central coordinator for P2P operations
**Features**:

- STUN/TURN NAT traversal
- UPnP automatic port mapping
- End-to-end encryption with RSA/AES
- DHT-based peer discovery
- Resumable file transfers

**Network Architecture**:

```python
@dataclass
class PeerInfo:
    peer_id: str
    public_key: bytes
    external_ip: str
    external_port: int
    nat_type: str
    capabilities: List[str]
```

##### Encryption System

**Key Exchange Protocol**:

1. RSA keypair generation (2048-bit)
2. Diffie-Hellman key exchange
3. AES-256-CBC for data encryption
4. HMAC-SHA256 for authentication

**Implementation**:

```python
class EncryptionManager:
    def __init__(self):
        self.private_key = rsa.generate_private_key(
            public_exponent=65537,
            key_size=2048,
            backend=default_backend()
        )
        self.public_key = self.private_key.public_key()
    
    async def encrypt_chunk(self, data: bytes, session_key: bytes) -> bytes:
        # AES-256-CBC encryption with PKCS7 padding
        cipher = Cipher(
            algorithms.AES(session_key),
            modes.CBC(os.urandom(16)),
            backend=default_backend()
        )
        # ... encryption logic
```

##### NAT Traversal

**STUN Protocol Implementation**:

- External IP/port discovery
- NAT type detection
- Keep-alive mechanisms

**UPnP Integration**:

```python
class UPnPManager:
    def __init__(self):
        self.upnp = miniupnpc.UPnP()
    
    async def map_port(self, internal_port: int, 
                      external_port: int = None) -> bool:
        # Automatic port mapping with fallback
```

#### Usage Examples

##### File Sharing

```python
# Initialize P2P manager
p2p = P2PManager(config)
await p2p.start()

# Share a file
share_code = await p2p.share_file(
    file_path="video.mp4",
    encryption=True,
    max_peers=10
)

# Fetch shared file
await p2p.fetch_file(
    share_code="ABC123XYZ",
    output_path="downloads/"
)
```

##### Custom Peer Discovery

```python
class CustomDiscovery(PeerDiscovery):
    async def discover_peers(self, file_hash: str) -> List[PeerInfo]:
        # Custom peer discovery logic
        return discovered_peers

p2p.register_discovery_method(CustomDiscovery())
```

---

### modules/session.py - Session Management

#### Purpose

Provides persistent session management for download resumption and state tracking across application restarts.

#### Key Classes

##### `AsyncSessionManager`

**Responsibility**: Async session persistence and coordination
**Features**:

- JSON-based session storage
- Concurrent session handling
- Automatic cleanup and maintenance
- Cross-process session sharing

**Session Schema**:

```python
{
    "session_id": "uuid4",
    "url": "source_url", 
    "status": "active|paused|completed|failed",
    "created_at": "iso_timestamp",
    "updated_at": "iso_timestamp",
    "progress": {
        "downloaded_bytes": 0,
        "total_bytes": 0,
        "percentage": 0.0
    },
    "metadata": {
        "title": "extracted_title",
        "format": "selected_format",
        "quality": "quality_setting"
    },
    "options": {},
    "error_info": null
}
```

**Plugin Hooks**:

- Session creation/update events
- Progress milestone notifications
- Error state transitions
- Cleanup operations

---

### modules/config.py - Configuration System

#### Purpose

Centralized configuration management with validation, defaults, and environment integration.

#### Configuration Hierarchy

1. **Default Configuration**: Hard-coded fallbacks
2. **Config File**: JSON configuration file
3. **Environment Variables**: Runtime overrides
4. **Command Line Arguments**: Immediate overrides

#### Key Functions

##### `load_config(config_path: Optional[str] = None) -> Dict[str, Any]`

**Purpose**: Load and merge configuration from multiple sources
**Validation**:

- Path existence and permissions
- FFmpeg installation verification
- Directory creation and access rights
- Format preset validation

##### `initialize_config_async() -> Dict[str, Any]`

**Purpose**: Async configuration initialization with background validation
**Features**:

- Concurrent FFmpeg validation
- Network connectivity checks
- Plugin discovery and loading
- Performance profiling

#### Plugin Integration

```python
# Configuration schema for plugins
{
    "plugins": {
        "plugin_name": {
            "enabled": True,
            "priority": 10,
            "config": {
                "plugin_specific_options": "values"
            }
        }
    }
}
```

---

### modules/cache.py - Caching System

#### Purpose

Intelligent caching for metadata, thumbnails, and partial downloads to optimize performance.

#### Cache Categories

1. **Metadata Cache**: Video/audio information
2. **Thumbnail Cache**: Preview images
3. **Fragment Cache**: Partial download chunks
4. **Session Cache**: Active download states

#### Cache Policies

- **LRU Eviction**: Least recently used items removed first
- **Size Limits**: Configurable maximum cache sizes
- **TTL Expiration**: Time-based cache invalidation
- **Integrity Verification**: Hash-based validation

#### Usage Example

```python
cache = DownloadCache(config)

# Cache metadata
await cache.store_metadata(url, metadata, ttl=3600)

# Retrieve with fallback
metadata = await cache.get_metadata(url, fetch_if_missing=True)

# Cache management
await cache.cleanup_expired()
await cache.compact_storage()
```

This detailed module documentation provides developers with the specific information needed to understand, extend, and integrate with each component of the Snatch system.
