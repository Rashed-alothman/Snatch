# Performance Optimization Guide

## Overview

This guide provides comprehensive strategies and techniques for optimizing the performance of the Snatch media downloader across different system configurations and use cases.

## Table of Contents

1. [Performance Analysis](#performance-analysis)
2. [System Resource Optimization](#system-resource-optimization)
3. [Network Performance](#network-performance)
4. [Download Optimization](#download-optimization)
5. [Memory Management](#memory-management)
6. [CPU Optimization](#cpu-optimization)
7. [Storage Optimization](#storage-optimization)
8. [Caching Strategies](#caching-strategies)
9. [Monitoring and Profiling](#monitoring-and-profiling)
10. [Platform-Specific Optimizations](#platform-specific-optimizations)

## Performance Analysis

### Performance Metrics

#### Key Performance Indicators (KPIs)

```python
# performance/metrics.py
import time
import psutil
from dataclasses import dataclass
from typing import Dict, List, Optional

@dataclass
class PerformanceMetrics:
    download_speed: float  # MB/s
    cpu_usage: float       # Percentage
    memory_usage: float    # MB
    disk_usage: float      # MB/s
    network_latency: float # ms
    success_rate: float    # Percentage
    concurrent_downloads: int
    
class PerformanceTracker:
    def __init__(self):
        self.metrics_history: List[PerformanceMetrics] = []
        self.start_time = time.time()
    
    def collect_metrics(self) -> PerformanceMetrics:
        cpu_percent = psutil.cpu_percent(interval=1)
        memory = psutil.virtual_memory()
        disk_io = psutil.disk_io_counters()
        network_io = psutil.net_io_counters()
        
        return PerformanceMetrics(
            download_speed=self.calculate_download_speed(),
            cpu_usage=cpu_percent,
            memory_usage=memory.used / 1024 / 1024,
            disk_usage=self.calculate_disk_speed(disk_io),
            network_latency=self.measure_network_latency(),
            success_rate=self.calculate_success_rate(),
            concurrent_downloads=self.get_active_downloads()
        )
    
    def get_performance_summary(self) -> Dict[str, float]:
        if not self.metrics_history:
            return {}
        
        return {
            'avg_download_speed': sum(m.download_speed for m in self.metrics_history) / len(self.metrics_history),
            'max_download_speed': max(m.download_speed for m in self.metrics_history),
            'avg_cpu_usage': sum(m.cpu_usage for m in self.metrics_history) / len(self.metrics_history),
            'peak_memory_usage': max(m.memory_usage for m in self.metrics_history),
            'avg_success_rate': sum(m.success_rate for m in self.metrics_history) / len(self.metrics_history)
        }
```

### Benchmarking

#### Performance Benchmarks

```python
# performance/benchmark.py
import asyncio
import time
from typing import List, Dict, Any

class PerformanceBenchmark:
    def __init__(self):
        self.results = {}
    
    async def run_download_benchmark(self, urls: List[str]) -> Dict[str, Any]:
        """Benchmark download performance with different configurations"""
        configurations = [
            {'concurrent_downloads': 1, 'chunk_size': 1024*1024},
            {'concurrent_downloads': 2, 'chunk_size': 1024*1024},
            {'concurrent_downloads': 4, 'chunk_size': 1024*1024},
            {'concurrent_downloads': 2, 'chunk_size': 8*1024*1024},
        ]
        
        results = {}
        
        for config in configurations:
            start_time = time.time()
            
            # Run downloads with current configuration
            download_results = await self.run_downloads_with_config(urls, config)
            
            end_time = time.time()
            total_time = end_time - start_time
            
            results[f"config_{config['concurrent_downloads']}_{config['chunk_size']}"] = {
                'total_time': total_time,
                'avg_speed': sum(r['speed'] for r in download_results) / len(download_results),
                'success_rate': sum(1 for r in download_results if r['success']) / len(download_results),
                'config': config
            }
        
        return results
    
    async def run_memory_benchmark(self) -> Dict[str, Any]:
        """Benchmark memory usage patterns"""
        import tracemalloc
        
        tracemalloc.start()
        
        # Simulate heavy workload
        await self.simulate_heavy_workload()
        
        current, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        
        return {
            'current_memory_mb': current / 1024 / 1024,
            'peak_memory_mb': peak / 1024 / 1024,
            'memory_efficiency': current / peak if peak > 0 else 0
        }
```

## System Resource Optimization

### CPU Optimization

#### Multi-threading Configuration

```python
# optimization/cpu.py
import multiprocessing
import concurrent.futures
from typing import List, Callable, Any

class CPUOptimizer:
    def __init__(self):
        self.cpu_count = multiprocessing.cpu_count()
        self.optimal_workers = self.calculate_optimal_workers()
    
    def calculate_optimal_workers(self) -> int:
        """Calculate optimal number of worker threads"""
        # Rule of thumb: CPU cores * 2 for I/O bound tasks
        return min(self.cpu_count * 2, 8)
    
    def optimize_thread_pool(self, tasks: List[Callable], task_type: str = 'io') -> List[Any]:
        """Execute tasks with optimized thread pool"""
        if task_type == 'cpu':
            max_workers = self.cpu_count
        else:  # I/O bound tasks
            max_workers = self.optimal_workers
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = [executor.submit(task) for task in tasks]
            return [future.result() for future in concurrent.futures.as_completed(futures)]
    
    def set_cpu_affinity(self, process_id: int = None):
        """Set CPU affinity for better performance"""
        if process_id is None:
            process_id = os.getpid()
        
        try:
            import psutil
            process = psutil.Process(process_id)
            
            # Use all available cores for download processes
            available_cores = list(range(self.cpu_count))
            process.cpu_affinity(available_cores)
        except Exception as e:
            print(f"Could not set CPU affinity: {e}")
```

#### Process Priority Optimization

```python
# optimization/priority.py
import os
import psutil

class ProcessOptimizer:
    @staticmethod
    def set_high_priority():
        """Set process to high priority for better performance"""
        try:
            current_process = psutil.Process()
            
            if os.name == 'nt':  # Windows
                current_process.nice(psutil.HIGH_PRIORITY_CLASS)
            else:  # Unix-like systems
                current_process.nice(-10)  # Higher priority
        except PermissionError:
            print("Warning: Could not set high priority. Run as administrator/root for better performance.")
        except Exception as e:
            print(f"Could not optimize process priority: {e}")
    
    @staticmethod
    def optimize_io_priority():
        """Optimize I/O priority for downloads"""
        try:
            current_process = psutil.Process()
            
            if hasattr(current_process, 'ionice'):
                # Set I/O priority to high
                current_process.ionice(psutil.IOPRIO_CLASS_RT, value=4)
        except Exception as e:
            print(f"Could not optimize I/O priority: {e}")
```

### Memory Management

#### Memory Pool Implementation

```python
# optimization/memory.py
import mmap
import gc
from typing import Dict, Any, Optional

class MemoryPool:
    def __init__(self, pool_size_mb: int = 100):
        self.pool_size = pool_size_mb * 1024 * 1024
        self.allocated_chunks: Dict[str, mmap.mmap] = {}
        self.free_chunks: List[mmap.mmap] = []
        
    def allocate_chunk(self, chunk_id: str, size: int) -> Optional[mmap.mmap]:
        """Allocate a memory chunk for download buffer"""
        if size > self.pool_size:
            return None
        
        # Try to reuse existing chunk
        if self.free_chunks:
            chunk = self.free_chunks.pop()
            if chunk.size() >= size:
                self.allocated_chunks[chunk_id] = chunk
                return chunk
        
        # Create new chunk
        try:
            chunk = mmap.mmap(-1, size)
            self.allocated_chunks[chunk_id] = chunk
            return chunk
        except OSError:
            return None
    
    def free_chunk(self, chunk_id: str):
        """Free a memory chunk"""
        if chunk_id in self.allocated_chunks:
            chunk = self.allocated_chunks.pop(chunk_id)
            chunk.seek(0)
            self.free_chunks.append(chunk)
    
    def cleanup(self):
        """Clean up all allocated memory"""
        for chunk in self.allocated_chunks.values():
            chunk.close()
        for chunk in self.free_chunks:
            chunk.close()
        self.allocated_chunks.clear()
        self.free_chunks.clear()
        gc.collect()

class MemoryOptimizer:
    @staticmethod
    def optimize_garbage_collection():
        """Optimize garbage collection for better performance"""
        import gc
        
        # Tune garbage collection thresholds
        gc.set_threshold(700, 10, 10)
        
        # Enable garbage collection debug (development only)
        # gc.set_debug(gc.DEBUG_STATS)
    
    @staticmethod
    def monitor_memory_usage() -> Dict[str, float]:
        """Monitor current memory usage"""
        import psutil
        
        process = psutil.Process()
        memory_info = process.memory_info()
        
        return {
            'rss_mb': memory_info.rss / 1024 / 1024,
            'vms_mb': memory_info.vms / 1024 / 1024,
            'percent': process.memory_percent(),
            'available_mb': psutil.virtual_memory().available / 1024 / 1024
        }
```

### Disk I/O Optimization

#### Optimized File Operations

```python
# optimization/disk.py
import os
import mmap
import aiofiles
from pathlib import Path
from typing import Optional

class DiskOptimizer:
    def __init__(self):
        self.temp_dir = Path("./temp")
        self.temp_dir.mkdir(exist_ok=True)
    
    async def optimized_write(self, file_path: str, data: bytes, use_mmap: bool = True) -> bool:
        """Optimized file writing with memory mapping"""
        try:
            if use_mmap and len(data) > 1024 * 1024:  # Use mmap for files > 1MB
                return await self._mmap_write(file_path, data)
            else:
                return await self._async_write(file_path, data)
        except Exception as e:
            print(f"Error writing file {file_path}: {e}")
            return False
    
    async def _mmap_write(self, file_path: str, data: bytes) -> bool:
        """Memory-mapped file writing"""
        try:
            with open(file_path, 'wb') as f:
                f.write(b'\0' * len(data))  # Pre-allocate file
            
            with open(file_path, 'r+b') as f:
                with mmap.mmap(f.fileno(), len(data)) as mm:
                    mm[:] = data
                    mm.flush()
            return True
        except Exception:
            return False
    
    async def _async_write(self, file_path: str, data: bytes) -> bool:
        """Asynchronous file writing"""
        try:
            async with aiofiles.open(file_path, 'wb') as f:
                await f.write(data)
            return True
        except Exception:
            return False
    
    def optimize_temp_files(self):
        """Optimize temporary file handling"""
        # Set temporary directory to fastest available drive
        import tempfile
        
        # Check if SSD is available
        temp_candidates = [
            "/tmp",  # Linux
            "C:\\Temp",  # Windows
            str(Path.home() / "temp")  # Fallback
        ]
        
        for candidate in temp_candidates:
            if os.path.exists(candidate) and os.access(candidate, os.W_OK):
                tempfile.tempdir = candidate
                break
    
    def set_file_flags(self, file_path: str):
        """Set optimal file flags for performance"""
        try:
            if os.name == 'posix':
                # Linux: Use O_DIRECT for large files to bypass page cache
                fd = os.open(file_path, os.O_WRONLY | os.O_CREAT)
                os.close(fd)
        except Exception:
            pass
```

## Network Performance

### Connection Optimization

#### Connection Pool Management

```python
# optimization/network.py
import aiohttp
import asyncio
from typing import Optional, Dict, Any

class OptimizedHTTPSession:
    def __init__(self, max_connections: int = 100, max_connections_per_host: int = 10):
        self.connector = aiohttp.TCPConnector(
            limit=max_connections,
            limit_per_host=max_connections_per_host,
            ttl_dns_cache=300,
            use_dns_cache=True,
            keepalive_timeout=30,
            enable_cleanup_closed=True
        )
        
        self.timeout = aiohttp.ClientTimeout(
            total=300,  # 5 minutes total timeout
            connect=30,  # 30 seconds to connect
            sock_read=30  # 30 seconds to read socket
        )
        
        self.session: Optional[aiohttp.ClientSession] = None
    
    async def __aenter__(self):
        self.session = aiohttp.ClientSession(
            connector=self.connector,
            timeout=self.timeout,
            headers={
                'User-Agent': 'Snatch/1.8.0 (Advanced Media Downloader)',
                'Accept-Encoding': 'gzip, deflate',
                'Connection': 'keep-alive'
            }
        )
        return self.session
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()

class NetworkOptimizer:
    @staticmethod
    def calculate_optimal_chunk_size(connection_speed_mbps: float) -> int:
        """Calculate optimal chunk size based on connection speed"""
        # Base chunk size: 1MB for connections < 10 Mbps
        # Scale up for faster connections
        if connection_speed_mbps < 10:
            return 1024 * 1024  # 1MB
        elif connection_speed_mbps < 50:
            return 4 * 1024 * 1024  # 4MB
        elif connection_speed_mbps < 100:
            return 8 * 1024 * 1024  # 8MB
        else:
            return 16 * 1024 * 1024  # 16MB
    
    @staticmethod
    def optimize_tcp_settings():
        """Optimize TCP settings for downloads"""
        import socket
        
        # These settings may require root/admin privileges
        optimizations = {
            'TCP_NODELAY': 1,  # Disable Nagle's algorithm
            'SO_REUSEADDR': 1,  # Allow socket reuse
        }
        
        return optimizations
```

### Bandwidth Management

#### Adaptive Rate Limiting

```python
# optimization/bandwidth.py
import time
import asyncio
from typing import Dict, List
from collections import deque

class AdaptiveBandwidthManager:
    def __init__(self, initial_limit_mbps: float = 10.0):
        self.bandwidth_limit = initial_limit_mbps * 1024 * 1024 / 8  # Convert to bytes/sec
        self.download_history = deque(maxlen=100)
        self.last_adjustment = time.time()
        self.adjustment_interval = 10  # seconds
    
    async def throttle_download(self, chunk_size: int, download_time: float):
        """Throttle download speed if necessary"""
        current_speed = chunk_size / download_time
        self.download_history.append((time.time(), current_speed))
        
        # Check if we need to adjust throttling
        if time.time() - self.last_adjustment > self.adjustment_interval:
            await self._adjust_bandwidth_limit()
            self.last_adjustment = time.time()
        
        # Apply throttling if current speed exceeds limit
        if current_speed > self.bandwidth_limit:
            sleep_time = (chunk_size / self.bandwidth_limit) - download_time
            if sleep_time > 0:
                await asyncio.sleep(sleep_time)
    
    async def _adjust_bandwidth_limit(self):
        """Adjust bandwidth limit based on network conditions"""
        if len(self.download_history) < 10:
            return
        
        recent_speeds = [speed for _, speed in self.download_history[-10:]]
        avg_speed = sum(recent_speeds) / len(recent_speeds)
        
        # Increase limit if consistently under-utilizing
        if avg_speed < self.bandwidth_limit * 0.8:
            self.bandwidth_limit *= 1.1
        # Decrease limit if network seems congested
        elif avg_speed > self.bandwidth_limit * 1.2:
            self.bandwidth_limit *= 0.9
    
    def get_current_limit_mbps(self) -> float:
        """Get current bandwidth limit in Mbps"""
        return self.bandwidth_limit * 8 / 1024 / 1024
```

## Download Optimization

### Concurrent Download Management

#### Smart Download Scheduler

```python
# optimization/scheduler.py
import asyncio
import heapq
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field
from enum import Enum

class Priority(Enum):
    LOW = 1
    NORMAL = 2
    HIGH = 3
    URGENT = 4

@dataclass
class DownloadTask:
    url: str
    priority: Priority
    estimated_size: int
    estimated_duration: float
    created_at: float = field(default_factory=time.time)
    
    def __lt__(self, other):
        # Higher priority tasks come first
        return self.priority.value > other.priority.value

class SmartDownloadScheduler:
    def __init__(self, max_concurrent: int = 4):
        self.max_concurrent = max_concurrent
        self.active_downloads: Dict[str, asyncio.Task] = {}
        self.pending_queue: List[DownloadTask] = []
        self.completed_downloads: List[str] = []
        
    async def add_download(self, task: DownloadTask):
        """Add a download task to the queue"""
        heapq.heappush(self.pending_queue, task)
        await self._process_queue()
    
    async def _process_queue(self):
        """Process the download queue"""
        while (len(self.active_downloads) < self.max_concurrent and 
               self.pending_queue):
            
            task = heapq.heappop(self.pending_queue)
            
            # Start download
            download_coroutine = self._download_with_monitoring(task)
            async_task = asyncio.create_task(download_coroutine)
            self.active_downloads[task.url] = async_task
    
    async def _download_with_monitoring(self, task: DownloadTask):
        """Download with performance monitoring"""
        try:
            start_time = time.time()
            
            # Perform actual download
            result = await self._perform_download(task)
            
            end_time = time.time()
            actual_duration = end_time - start_time
            
            # Learn from this download for future scheduling
            self._update_performance_model(task, actual_duration)
            
            self.completed_downloads.append(task.url)
            
        except Exception as e:
            print(f"Download failed for {task.url}: {e}")
        finally:
            # Remove from active downloads
            self.active_downloads.pop(task.url, None)
            # Process next item in queue
            await self._process_queue()
    
    def _update_performance_model(self, task: DownloadTask, actual_duration: float):
        """Update performance prediction model"""
        # Simple learning: adjust future estimates
        error_ratio = actual_duration / task.estimated_duration
        
        # This could be expanded to use machine learning
        # For now, just log the performance data
        print(f"Download {task.url}: estimated {task.estimated_duration:.2f}s, "
              f"actual {actual_duration:.2f}s, error ratio: {error_ratio:.2f}")
```

### Format Selection Optimization

#### Intelligent Format Chooser

```python
# optimization/format_selection.py
import re
from typing import List, Dict, Any, Optional, Tuple

class FormatOptimizer:
    def __init__(self):
        self.format_preferences = {
            'video': ['mp4', 'webm', 'mkv'],
            'audio': ['opus', 'm4a', 'mp3'],
            'quality_priorities': ['1080p', '720p', '480p', '360p']
        }
        
        self.codec_efficiency = {
            'h264': 1.0,
            'h265': 0.7,  # 30% smaller files
            'vp9': 0.8,   # 20% smaller files
            'av1': 0.6    # 40% smaller files (when available)
        }
    
    def select_optimal_format(self, available_formats: List[Dict[str, Any]], 
                            preferences: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Select the optimal format based on preferences and efficiency"""
        
        # Filter formats based on type
        if preferences.get('audio_only', False):
            candidates = [f for f in available_formats if f.get('vcodec') == 'none']
        else:
            candidates = [f for f in available_formats if f.get('vcodec') != 'none']
        
        if not candidates:
            return None
        
        # Score each format
        scored_formats = []
        for fmt in candidates:
            score = self._calculate_format_score(fmt, preferences)
            scored_formats.append((score, fmt))
        
        # Return highest scoring format
        scored_formats.sort(key=lambda x: x[0], reverse=True)
        return scored_formats[0][1] if scored_formats else None
    
    def _calculate_format_score(self, fmt: Dict[str, Any], preferences: Dict[str, Any]) -> float:
        """Calculate a score for a format based on multiple factors"""
        score = 0.0
        
        # Quality score
        height = fmt.get('height', 0)
        if height >= 1080:
            score += 100
        elif height >= 720:
            score += 80
        elif height >= 480:
            score += 60
        else:
            score += 40
        
        # Codec efficiency score
        vcodec = fmt.get('vcodec', '').lower()
        for codec, efficiency in self.codec_efficiency.items():
            if codec in vcodec:
                score += (1.0 / efficiency) * 20  # Higher score for more efficient codecs
                break
        
        # File size consideration (smaller is better for same quality)
        filesize = fmt.get('filesize', 0)
        if filesize and height:
            size_per_pixel = filesize / (height * 16/9 * height)  # Rough estimation
            score += max(0, 50 - size_per_pixel * 1000)  # Penalty for large file sizes
        
        # Audio quality score
        abr = fmt.get('abr', 0)
        if abr >= 320:
            score += 30
        elif abr >= 192:
            score += 20
        elif abr >= 128:
            score += 10
        
        return score
    
    def estimate_download_time(self, fmt: Dict[str, Any], 
                              connection_speed_mbps: float) -> float:
        """Estimate download time for a format"""
        filesize = fmt.get('filesize')
        if not filesize:
            # Estimate based on quality and duration
            duration = fmt.get('duration', 300)  # Default 5 minutes
            height = fmt.get('height', 720)
            
            # Rough estimation: higher quality = larger files
            estimated_bitrate = self._estimate_bitrate(height)
            filesize = (estimated_bitrate * duration) / 8  # Convert to bytes
        
        # Convert connection speed to bytes per second
        speed_bps = connection_speed_mbps * 1024 * 1024 / 8
        
        # Add 20% overhead for protocol overhead, retries, etc.
        return (filesize / speed_bps) * 1.2
    
    def _estimate_bitrate(self, height: int) -> float:
        """Estimate bitrate based on resolution"""
        bitrate_map = {
            2160: 25000000,  # 4K: ~25 Mbps
            1440: 16000000,  # 1440p: ~16 Mbps
            1080: 8000000,   # 1080p: ~8 Mbps
            720: 5000000,    # 720p: ~5 Mbps
            480: 2500000,    # 480p: ~2.5 Mbps
            360: 1000000,    # 360p: ~1 Mbps
        }
        
        for res, bitrate in sorted(bitrate_map.items(), reverse=True):
            if height >= res:
                return bitrate
        
        return 500000  # Default low bitrate
```

## Caching Strategies

### Multi-Level Caching

#### Intelligent Cache Manager

```python
# optimization/cache.py
import hashlib
import pickle
import time
import asyncio
from typing import Any, Optional, Dict, List
from pathlib import Path

class MultiLevelCache:
    def __init__(self, cache_dir: str = "./cache"):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(exist_ok=True)
        
        # Memory cache (L1)
        self.memory_cache: Dict[str, Tuple[Any, float]] = {}
        self.max_memory_items = 1000
        
        # Disk cache (L2)
        self.disk_cache_dir = self.cache_dir / "disk"
        self.disk_cache_dir.mkdir(exist_ok=True)
        
        # Cache statistics
        self.stats = {
            'hits': 0,
            'misses': 0,
            'memory_hits': 0,
            'disk_hits': 0
        }
    
    def _get_cache_key(self, key: str) -> str:
        """Generate a cache key hash"""
        return hashlib.md5(key.encode()).hexdigest()
    
    async def get(self, key: str, max_age: int = 3600) -> Optional[Any]:
        """Get item from cache with TTL support"""
        cache_key = self._get_cache_key(key)
        current_time = time.time()
        
        # Try memory cache first (L1)
        if cache_key in self.memory_cache:
            value, timestamp = self.memory_cache[cache_key]
            if current_time - timestamp < max_age:
                self.stats['hits'] += 1
                self.stats['memory_hits'] += 1
                return value
            else:
                # Expired, remove from memory cache
                del self.memory_cache[cache_key]
        
        # Try disk cache (L2)
        disk_file = self.disk_cache_dir / f"{cache_key}.cache"
        if disk_file.exists():
            try:
                with open(disk_file, 'rb') as f:
                    cached_data = pickle.load(f)
                
                if current_time - cached_data['timestamp'] < max_age:
                    # Move to memory cache for faster access
                    self.memory_cache[cache_key] = (cached_data['value'], cached_data['timestamp'])
                    self._cleanup_memory_cache()
                    
                    self.stats['hits'] += 1
                    self.stats['disk_hits'] += 1
                    return cached_data['value']
                else:
                    # Expired, remove from disk
                    disk_file.unlink()
            except Exception:
                # Corrupted cache file, remove it
                disk_file.unlink()
        
        self.stats['misses'] += 1
        return None
    
    async def set(self, key: str, value: Any, persist_to_disk: bool = True):
        """Set item in cache"""
        cache_key = self._get_cache_key(key)
        timestamp = time.time()
        
        # Store in memory cache (L1)
        self.memory_cache[cache_key] = (value, timestamp)
        self._cleanup_memory_cache()
        
        # Store in disk cache (L2) if requested
        if persist_to_disk:
            disk_file = self.disk_cache_dir / f"{cache_key}.cache"
            try:
                with open(disk_file, 'wb') as f:
                    pickle.dump({
                        'value': value,
                        'timestamp': timestamp
                    }, f)
            except Exception as e:
                print(f"Failed to write to disk cache: {e}")
    
    def _cleanup_memory_cache(self):
        """Clean up memory cache if it gets too large"""
        if len(self.memory_cache) > self.max_memory_items:
            # Remove oldest items
            sorted_items = sorted(self.memory_cache.items(), 
                                key=lambda x: x[1][1])  # Sort by timestamp
            
            # Keep only the newest 80% of items
            keep_count = int(self.max_memory_items * 0.8)
            items_to_keep = sorted_items[-keep_count:]
            
            self.memory_cache = dict(items_to_keep)
    
    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics"""
        total_requests = self.stats['hits'] + self.stats['misses']
        hit_rate = self.stats['hits'] / total_requests if total_requests > 0 else 0
        
        return {
            'hit_rate': hit_rate,
            'total_requests': total_requests,
            'memory_cache_size': len(self.memory_cache),
            'disk_cache_size': len(list(self.disk_cache_dir.glob("*.cache"))),
            **self.stats
        }
    
    async def clear(self, memory_only: bool = False):
        """Clear cache"""
        self.memory_cache.clear()
        
        if not memory_only:
            for cache_file in self.disk_cache_dir.glob("*.cache"):
                try:
                    cache_file.unlink()
                except Exception:
                    pass
        
        # Reset stats
        self.stats = {key: 0 for key in self.stats}
```

### Predictive Caching

#### Smart Prefetch System

```python
# optimization/prefetch.py
import asyncio
from typing import List, Set, Dict, Any
from collections import defaultdict, deque

class PredictiveCacheManager:
    def __init__(self, cache_manager):
        self.cache = cache_manager
        self.access_patterns: Dict[str, List[str]] = defaultdict(list)
        self.access_frequency: Dict[str, int] = defaultdict(int)
        self.recent_accesses = deque(maxlen=1000)
        
    def record_access(self, key: str):
        """Record access pattern for predictive caching"""
        self.access_frequency[key] += 1
        self.recent_accesses.append((key, time.time()))
        
        # Update access patterns
        if len(self.recent_accesses) >= 2:
            prev_key = self.recent_accesses[-2][0]
            if prev_key != key:
                self.access_patterns[prev_key].append(key)
                
                # Keep only recent patterns (last 100 accesses per key)
                if len(self.access_patterns[prev_key]) > 100:
                    self.access_patterns[prev_key] = self.access_patterns[prev_key][-100:]
    
    async def predict_and_prefetch(self, current_key: str, prefetch_count: int = 3):
        """Predict and prefetch likely next accesses"""
        if current_key not in self.access_patterns:
            return
        
        # Get patterns for current key
        patterns = self.access_patterns[current_key]
        
        # Count frequency of next accesses
        next_access_freq = defaultdict(int)
        for next_key in patterns:
            next_access_freq[next_key] += 1
        
        # Sort by frequency and get top candidates
        candidates = sorted(next_access_freq.items(), 
                          key=lambda x: x[1], reverse=True)[:prefetch_count]
        
        # Prefetch candidates that aren't already cached
        prefetch_tasks = []
        for candidate_key, _ in candidates:
            cached_value = await self.cache.get(candidate_key)
            if cached_value is None:
                # This would be replaced with actual data fetching logic
                task = asyncio.create_task(self._prefetch_data(candidate_key))
                prefetch_tasks.append(task)
        
        # Execute prefetch tasks in background
        if prefetch_tasks:
            asyncio.create_task(self._execute_prefetch_tasks(prefetch_tasks))
    
    async def _prefetch_data(self, key: str) -> Any:
        """Prefetch data for a given key"""
        # This would contain the actual logic to fetch data
        # For example, fetching video metadata, format info, etc.
        await asyncio.sleep(0.1)  # Simulate async operation
        return f"prefetched_data_for_{key}"
    
    async def _execute_prefetch_tasks(self, tasks: List[asyncio.Task]):
        """Execute prefetch tasks without blocking main operations"""
        try:
            results = await asyncio.gather(*tasks, return_exceptions=True)
            for i, result in enumerate(results):
                if not isinstance(result, Exception):
                    # Cache the prefetched data
                    await self.cache.set(f"prefetch_{i}", result)
        except Exception as e:
            print(f"Prefetch error: {e}")
```

## Monitoring and Profiling

### Real-time Performance Monitor

#### System Resource Monitor

```python
# monitoring/system_monitor.py
import psutil
import asyncio
import time
from typing import Dict, List, Any
from dataclasses import dataclass

@dataclass
class SystemSnapshot:
    timestamp: float
    cpu_percent: float
    memory_percent: float
    memory_used_mb: float
    disk_io_read_mb: float
    disk_io_write_mb: float
    network_sent_mb: float
    network_recv_mb: float
    active_downloads: int

class SystemMonitor:
    def __init__(self, sample_interval: float = 1.0):
        self.sample_interval = sample_interval
        self.snapshots: List[SystemSnapshot] = []
        self.max_snapshots = 3600  # Keep 1 hour of data at 1s intervals
        self.monitoring = False
        
        # Baseline measurements
        self.baseline_disk_io = psutil.disk_io_counters()
        self.baseline_network_io = psutil.net_io_counters()
    
    async def start_monitoring(self):
        """Start real-time system monitoring"""
        self.monitoring = True
        await self._monitoring_loop()
    
    def stop_monitoring(self):
        """Stop system monitoring"""
        self.monitoring = False
    
    async def _monitoring_loop(self):
        """Main monitoring loop"""
        while self.monitoring:
            snapshot = self._take_snapshot()
            self.snapshots.append(snapshot)
            
            # Limit number of snapshots to prevent memory growth
            if len(self.snapshots) > self.max_snapshots:
                self.snapshots = self.snapshots[-self.max_snapshots:]
            
            await asyncio.sleep(self.sample_interval)
    
    def _take_snapshot(self) -> SystemSnapshot:
        """Take a system resource snapshot"""
        current_disk_io = psutil.disk_io_counters()
        current_network_io = psutil.net_io_counters()
        
        # Calculate rates since baseline
        disk_read_mb = (current_disk_io.read_bytes - self.baseline_disk_io.read_bytes) / 1024 / 1024
        disk_write_mb = (current_disk_io.write_bytes - self.baseline_disk_io.write_bytes) / 1024 / 1024
        network_sent_mb = (current_network_io.bytes_sent - self.baseline_network_io.bytes_sent) / 1024 / 1024
        network_recv_mb = (current_network_io.bytes_recv - self.baseline_network_io.bytes_recv) / 1024 / 1024
        
        memory = psutil.virtual_memory()
        
        return SystemSnapshot(
            timestamp=time.time(),
            cpu_percent=psutil.cpu_percent(),
            memory_percent=memory.percent,
            memory_used_mb=memory.used / 1024 / 1024,
            disk_io_read_mb=disk_read_mb,
            disk_io_write_mb=disk_write_mb,
            network_sent_mb=network_sent_mb,
            network_recv_mb=network_recv_mb,
            active_downloads=0  # This would be populated by the download manager
        )
    
    def get_performance_summary(self, duration_minutes: int = 10) -> Dict[str, Any]:
        """Get performance summary for the last N minutes"""
        cutoff_time = time.time() - (duration_minutes * 60)
        recent_snapshots = [s for s in self.snapshots if s.timestamp >= cutoff_time]
        
        if not recent_snapshots:
            return {}
        
        return {
            'avg_cpu_percent': sum(s.cpu_percent for s in recent_snapshots) / len(recent_snapshots),
            'max_cpu_percent': max(s.cpu_percent for s in recent_snapshots),
            'avg_memory_percent': sum(s.memory_percent for s in recent_snapshots) / len(recent_snapshots),
            'max_memory_mb': max(s.memory_used_mb for s in recent_snapshots),
            'total_disk_read_mb': recent_snapshots[-1].disk_io_read_mb if recent_snapshots else 0,
            'total_disk_write_mb': recent_snapshots[-1].disk_io_write_mb if recent_snapshots else 0,
            'total_network_recv_mb': recent_snapshots[-1].network_recv_mb if recent_snapshots else 0,
            'total_network_sent_mb': recent_snapshots[-1].network_sent_mb if recent_snapshots else 0,
            'sample_count': len(recent_snapshots),
            'duration_minutes': duration_minutes
        }
```

### Profiling Tools

#### Performance Profiler

```python
# monitoring/profiler.py
import cProfile
import pstats
import time
import functools
from typing import Dict, Any, Callable
from io import StringIO

class PerformanceProfiler:
    def __init__(self):
        self.profiler = cProfile.Profile()
        self.profiling_active = False
        self.function_timings: Dict[str, List[float]] = {}
    
    def start_profiling(self):
        """Start comprehensive profiling"""
        self.profiler.enable()
        self.profiling_active = True
    
    def stop_profiling(self) -> Dict[str, Any]:
        """Stop profiling and return results"""
        if self.profiling_active:
            self.profiler.disable()
            self.profiling_active = False
        
        # Capture profiling results
        s = StringIO()
        ps = pstats.Stats(self.profiler, stream=s)
        ps.sort_stats('cumulative')
        ps.print_stats()
        
        return {
            'profile_output': s.getvalue(),
            'function_timings': dict(self.function_timings)
        }
    
    def profile_function(self, func: Callable) -> Callable:
        """Decorator to profile specific functions"""
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            start_time = time.time()
            
            try:
                result = func(*args, **kwargs)
                return result
            finally:
                end_time = time.time()
                duration = end_time - start_time
                
                func_name = f"{func.__module__}.{func.__name__}"
                if func_name not in self.function_timings:
                    self.function_timings[func_name] = []
                
                self.function_timings[func_name].append(duration)
        
        return wrapper
    
    async def profile_async_function(self, func: Callable) -> Callable:
        """Decorator to profile async functions"""
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            start_time = time.time()
            
            try:
                result = await func(*args, **kwargs)
                return result
            finally:
                end_time = time.time()
                duration = end_time - start_time
                
                func_name = f"{func.__module__}.{func.__name__}"
                if func_name not in self.function_timings:
                    self.function_timings[func_name] = []
                
                self.function_timings[func_name].append(duration)
        
        return wrapper
    
    def get_function_stats(self, func_name: str) -> Dict[str, Any]:
        """Get statistics for a specific function"""
        if func_name not in self.function_timings:
            return {}
        
        timings = self.function_timings[func_name]
        
        return {
            'call_count': len(timings),
            'total_time': sum(timings),
            'avg_time': sum(timings) / len(timings),
            'min_time': min(timings),
            'max_time': max(timings),
            'last_call_time': timings[-1] if timings else 0
        }
```

## Platform-Specific Optimizations

### Windows Optimizations

```python
# optimization/windows.py
import os
import sys
import ctypes
from ctypes import wintypes

if sys.platform == 'win32':
    class WindowsOptimizer:
        @staticmethod
        def set_process_priority():
            """Set high process priority on Windows"""
            try:
                import psutil
                p = psutil.Process()
                p.nice(psutil.HIGH_PRIORITY_CLASS)
            except Exception as e:
                print(f"Could not set high priority: {e}")
        
        @staticmethod
        def disable_windows_defender_scanning(directory: str):
            """Add directory to Windows Defender exclusions"""
            try:
                import subprocess
                cmd = f'powershell -Command "Add-MpPreference -ExclusionPath \'{directory}\'"'
                subprocess.run(cmd, shell=True, check=True)
                print(f"Added {directory} to Windows Defender exclusions")
            except Exception as e:
                print(f"Could not add Defender exclusion: {e}")
        
        @staticmethod
        def optimize_file_system():
            """Optimize file system operations"""
            try:
                # Set file system cache to aggressive
                kernel32 = ctypes.windll.kernel32
                # SetSystemFileCacheSize - requires admin privileges
                # This is a placeholder for actual implementation
                pass
            except Exception as e:
                print(f"Could not optimize file system: {e}")
```

### Linux Optimizations

```python
# optimization/linux.py
import os
import subprocess

class LinuxOptimizer:
    @staticmethod
    def set_nice_priority(priority: int = -10):
        """Set process nice priority"""
        try:
            os.nice(priority)
        except PermissionError:
            print("Warning: Could not set nice priority. Run with sudo for better performance.")
        except Exception as e:
            print(f"Could not set nice priority: {e}")
    
    @staticmethod
    def optimize_tcp_settings():
        """Optimize TCP settings for downloads"""
        optimizations = [
            "echo 'net.core.rmem_max = 134217728' >> /etc/sysctl.conf",
            "echo 'net.core.wmem_max = 134217728' >> /etc/sysctl.conf",
            "echo 'net.ipv4.tcp_rmem = 4096 87380 134217728' >> /etc/sysctl.conf",
            "echo 'net.ipv4.tcp_wmem = 4096 65536 134217728' >> /etc/sysctl.conf",
            "sysctl -p"
        ]
        
        for cmd in optimizations:
            try:
                subprocess.run(cmd, shell=True, check=True, capture_output=True)
            except subprocess.CalledProcessError:
                print(f"Could not apply optimization: {cmd}")
    
    @staticmethod
    def set_io_scheduler(device: str = "sda", scheduler: str = "deadline"):
        """Set I/O scheduler for better download performance"""
        try:
            scheduler_path = f"/sys/block/{device}/queue/scheduler"
            if os.path.exists(scheduler_path):
                with open(scheduler_path, 'w') as f:
                    f.write(scheduler)
                print(f"Set I/O scheduler to {scheduler} for {device}")
        except Exception as e:
            print(f"Could not set I/O scheduler: {e}")
```

### macOS Optimizations

```python
# optimization/macos.py
import subprocess

class MacOSOptimizer:
    @staticmethod
    def optimize_network_buffer():
        """Optimize network buffer sizes on macOS"""
        try:
            commands = [
                "sudo sysctl -w net.inet.tcp.sendspace=131072",
                "sudo sysctl -w net.inet.tcp.recvspace=131072",
                "sudo sysctl -w net.inet.udp.recvspace=131072"
            ]
            
            for cmd in commands:
                subprocess.run(cmd.split(), check=True, capture_output=True)
                
            print("Network buffers optimized")
        except subprocess.CalledProcessError as e:
            print(f"Could not optimize network buffers: {e}")
    
    @staticmethod
    def disable_app_nap():
        """Disable App Nap for consistent performance"""
        try:
            import Cocoa
            
            # This would require pyobjc
            # Cocoa.NSProcessInfo.processInfo().setAutomaticTerminationSupportEnabled_(False)
            # Cocoa.NSProcessInfo.processInfo().disableAutomaticTermination_("Snatch downloading")
            
            print("App Nap disabled")
        except ImportError:
            print("Could not disable App Nap (pyobjc not available)")
        except Exception as e:
            print(f"Could not disable App Nap: {e}")
```

## Performance Testing and Validation

### Automated Performance Tests

```python
# testing/performance_tests.py
import asyncio
import time
import statistics
from typing import List, Dict, Any

class PerformanceTestSuite:
    def __init__(self):
        self.test_results: Dict[str, Any] = {}
    
    async def run_all_tests(self) -> Dict[str, Any]:
        """Run comprehensive performance test suite"""
        tests = [
            self.test_download_speeds,
            self.test_memory_usage,
            self.test_cpu_usage,
            self.test_concurrent_downloads,
            self.test_cache_performance
        ]
        
        results = {}
        for test in tests:
            test_name = test.__name__
            print(f"Running {test_name}...")
            
            try:
                result = await test()
                results[test_name] = result
                print(f"✓ {test_name} completed")
            except Exception as e:
                results[test_name] = {'error': str(e)}
                print(f"✗ {test_name} failed: {e}")
        
        return results
    
    async def test_download_speeds(self) -> Dict[str, Any]:
        """Test download speeds with different configurations"""
        test_urls = [
            "https://httpbin.org/drip?duration=5&numbytes=1048576",  # 1MB over 5 seconds
            "https://httpbin.org/drip?duration=10&numbytes=5242880", # 5MB over 10 seconds
        ]
        
        results = []
        for url in test_urls:
            start_time = time.time()
            
            # Simulate download (replace with actual download logic)
            await asyncio.sleep(2)  # Simulate download time
            
            end_time = time.time()
            download_time = end_time - start_time
            
            results.append({
                'url': url,
                'download_time': download_time,
                'estimated_speed_mbps': 1.0 / download_time  # Rough estimation
            })
        
        return {
            'tests_run': len(results),
            'avg_speed_mbps': statistics.mean(r['estimated_speed_mbps'] for r in results),
            'results': results
        }
    
    async def test_memory_usage(self) -> Dict[str, Any]:
        """Test memory usage patterns"""
        import psutil
        
        process = psutil.Process()
        initial_memory = process.memory_info().rss
        
        # Simulate memory-intensive operations
        large_data = []
        for i in range(100):
            large_data.append(b'x' * 1024 * 1024)  # 1MB chunks
            if i % 10 == 0:
                await asyncio.sleep(0.1)
        
        peak_memory = process.memory_info().rss
        
        # Cleanup
        del large_data
        import gc
        gc.collect()
        
        final_memory = process.memory_info().rss
        
        return {
            'initial_memory_mb': initial_memory / 1024 / 1024,
            'peak_memory_mb': peak_memory / 1024 / 1024,
            'final_memory_mb': final_memory / 1024 / 1024,
            'memory_growth_mb': (peak_memory - initial_memory) / 1024 / 1024,
            'memory_cleaned_mb': (peak_memory - final_memory) / 1024 / 1024
        }
    
    async def test_concurrent_downloads(self) -> Dict[str, Any]:
        """Test performance with concurrent downloads"""
        concurrent_levels = [1, 2, 4, 8]
        results = {}
        
        for level in concurrent_levels:
            start_time = time.time()
            
            # Simulate concurrent downloads
            tasks = []
            for i in range(level):
                task = asyncio.create_task(self._simulate_download(i))
                tasks.append(task)
            
            await asyncio.gather(*tasks)
            
            end_time = time.time()
            total_time = end_time - start_time
            
            results[f'concurrent_{level}'] = {
                'total_time': total_time,
                'avg_time_per_download': total_time / level,
                'efficiency': 1.0 / total_time  # Higher is better
            }
        
        return results
    
    async def _simulate_download(self, download_id: int):
        """Simulate a download operation"""
        # Simulate variable download times
        download_time = 1.0 + (download_id * 0.1)
        await asyncio.sleep(download_time)
        return f"download_{download_id}_completed"
```

This comprehensive Performance Optimization Guide provides detailed strategies for optimizing every aspect of the Snatch media downloader, from system resources to network performance, caching, and platform-specific optimizations.
