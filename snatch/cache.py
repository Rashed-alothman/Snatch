"""Cache management for downloaded media information"""
import threading
import logging
import json
import time
import os
from typing import Optional, Dict, Any
from pathlib import Path
from .defaults import CACHE_DIR

logger = logging.getLogger(__name__)

class DownloadCache:
    """Thread-safe cache with memory efficiency and disk persistence"""
    
    def __init__(self, max_memory_entries: int = 1000, cache_ttl: int = 3600):
        self._memory_cache = {}  # In-memory LRU cache
        self._access_times = {}  # Track last access time
        self._lock = threading.RLock()
        self._last_cleanup = time.time()
        self.max_memory_entries = max_memory_entries
        self.cache_ttl = cache_ttl
        self.cleanup_interval = 300  # Cleanup every 5 minutes
        
        # Ensure cache directory exists
        os.makedirs(CACHE_DIR, exist_ok=True)
        
    def _get_cache_path(self, key: str) -> Path:
        """Get filesystem path for cached item"""
        # Use first 2 chars of key for sharding to prevent too many files in one directory
        if len(key) >= 2:
            shard = key[:2]
        else:
            shard = "00"
            
        shard_dir = Path(CACHE_DIR) / shard
        os.makedirs(shard_dir, exist_ok=True)
        
        # Use URL-safe filename
        safe_key = "".join(c if c.isalnum() else '_' for c in key)
        return shard_dir / f"{safe_key}.json"
        
    def _cleanup_memory(self, force: bool = False) -> None:
        """Clean up old entries from memory cache"""
        now = time.time()
        if not force and now - self._last_cleanup < self.cleanup_interval:
            return
            
        with self._lock:
            # Remove expired entries
            expired = [
                k for k, t in self._access_times.items() 
                if now - t > self.cache_ttl
            ]
            for k in expired:
                self._memory_cache.pop(k, None)
                self._access_times.pop(k, None)
                
            # If still too many entries, remove oldest
            if len(self._memory_cache) > self.max_memory_entries:
                sorted_items = sorted(
                    self._access_times.items(),
                    key=lambda x: x[1]
                )
                to_remove = len(self._memory_cache) - self.max_memory_entries
                for k, _ in sorted_items[:to_remove]:
                    self._memory_cache.pop(k, None)
                    self._access_times.pop(k, None)
                    
            self._last_cleanup = now
            
    def get(self, key: str) -> Optional[Dict[str, Any]]:
        """Get item from cache with memory/disk fallback"""
        if not key:
            return None
            
        # Check memory cache first
        with self._lock:
            if key in self._memory_cache:
                self._access_times[key] = time.time()
                return self._memory_cache[key].copy()  # Return copy for thread safety
                
        # Check disk cache
        try:
            cache_path = self._get_cache_path(key)
            if cache_path.exists():
                with open(cache_path, 'r') as f:
                    data = json.load(f)
                    
                # Check if expired
                if time.time() - data.get('timestamp', 0) > self.cache_ttl:
                    os.unlink(cache_path)
                    return None
                    
                # Cache in memory for future access
                with self._lock:
                    self._memory_cache[key] = data['content']
                    self._access_times[key] = time.time()
                    return data['content'].copy()
                    
        except (IOError, json.JSONDecodeError) as e:
            logger.debug(f"Cache read error for {key}: {e}")
            
        return None
        
    def set(self, key: str, value: Dict[str, Any]) -> bool:
        """Store item in cache with both memory and disk persistence"""
        if not key or not value:
            return False
            
        try:
            # Store in memory
            with self._lock:
                self._memory_cache[key] = value.copy()  # Store copy for thread safety
                self._access_times[key] = time.time()
                self._cleanup_memory()  # Cleanup if needed
                
            # Store on disk
            cache_path = self._get_cache_path(key)
            cache_data = {
                'timestamp': time.time(),
                'content': value
            }
            
            # Use atomic write with temporary file
            temp_path = cache_path.with_suffix('.tmp')
            with open(temp_path, 'w') as f:
                json.dump(cache_data, f)
            os.replace(temp_path, cache_path)
            
            return True
            
        except Exception as e:
            logger.error(f"Cache write error for {key}: {e}")
            return False
            
    def invalidate(self, key: str) -> None:
        """Remove item from both memory and disk cache"""
        with self._lock:
            self._memory_cache.pop(key, None)
            self._access_times.pop(key, None)
            
        try:
            cache_path = self._get_cache_path(key)
            if cache_path.exists():
                os.unlink(cache_path)
        except OSError as e:
            logger.debug(f"Cache invalidation error for {key}: {e}")
            
    def clear(self) -> None:
        """Clear all cached data from memory and disk"""
        with self._lock:
            self._memory_cache.clear()
            self._access_times.clear()
            
        try:
            # Clear all cache files
            for shard_dir in Path(CACHE_DIR).iterdir():
                if shard_dir.is_dir():
                    for cache_file in shard_dir.glob('*.json'):
                        try:
                            os.unlink(cache_file)
                        except OSError:
                            pass
        except OSError as e:
            logger.error(f"Error clearing cache directory: {e}")
            
    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics"""
        with self._lock:
            memory_size = len(self._memory_cache)
            memory_bytes = sum(
                len(str(v)) for v in self._memory_cache.values()
            )
            
        # Count disk cache files
        disk_count = 0
        disk_bytes = 0
        try:
            for shard_dir in Path(CACHE_DIR).iterdir():
                if shard_dir.is_dir():
                    for cache_file in shard_dir.glob('*.json'):
                        disk_count += 1
                        disk_bytes += cache_file.stat().st_size
        except OSError:
            pass
            
        return {
            'memory_entries': memory_size,
            'memory_bytes': memory_bytes,
            'disk_entries': disk_count,
            'disk_bytes': disk_bytes,
            'max_memory_entries': self.max_memory_entries,
            'cache_ttl': self.cache_ttl
        }
