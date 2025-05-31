"""
Enhanced session management system for Snatch.
Provides persistent session tracking for HTTP and P2P file transfers with robust recovery mechanisms.
"""

import asyncio
import json
import logging 
import os
from datetime import datetime, timedelta
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Union, Set, TypeVar, Type, cast, Callable, Tuple
import threading
import time
import shutil

import aiofiles
import aiofiles.os
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TimeElapsedColumn
from rich.panel import Panel
from colorama import Fore, Style, init

from .progress import SpinnerAnimation
from .common_utils import ensure_dir, safe_file_write, safe_json_read, compute_file_hash
from .defaults import DOWNLOAD_SESSIONS_FILE
from .logging_config import setup_logging
from .error_handler import EnhancedErrorHandler, handle_errors, ErrorCategory, ErrorSeverity

# Configure logging
setup_logging()
logger = logging.getLogger(__name__)
console = Console()

# Session status constants
SESSION_STATUS_UNKNOWN = "unknown"
SESSION_STATUS_STARTING = "starting"
SESSION_STATUS_DOWNLOADING = "downloading"
SESSION_STATUS_PAUSED = "paused"
SESSION_STATUS_COMPLETED = "completed"
SESSION_STATUS_FAILED = "failed"
SESSION_STATUS_CANCELLED = "cancelled"

@dataclass 
class DownloadSession:
    """Represents an active download session with enhanced metadata and resilience."""
    url: str
    file_path: str
    total_size: int
    downloaded_bytes: int
    chunks_downloaded: List[str] = field(default_factory=list)  # List of SHA256 hashes
    start_time: datetime = field(default_factory=datetime.now)
    last_updated: datetime = field(default_factory=datetime.now)
    status: str = SESSION_STATUS_UNKNOWN
    metadata: Dict[str, Any] = field(default_factory=dict)
    resume_data: Dict[str, Any] = field(default_factory=dict)
    
    @property
    def progress(self) -> float:
        """Calculate percentage progress of download."""
        if self.total_size <= 0:
            return 0.0
        return min(100.0, (self.downloaded_bytes / self.total_size) * 100)
        
    @property
    def is_active(self) -> bool:
        """Check if the session is actively downloading."""
        return self.status == SESSION_STATUS_DOWNLOADING
        
    @property
    def is_complete(self) -> bool:
        """Check if the session is completed."""
        return self.status == SESSION_STATUS_COMPLETED
        
    @property
    def is_failed(self) -> bool:
        """Check if the session has failed."""
        return self.status in (SESSION_STATUS_FAILED, SESSION_STATUS_CANCELLED)
        
    @property
    def elapsed_time(self) -> timedelta:
        """Calculate elapsed time since download started."""
        return datetime.now() - self.start_time
        
    @property
    def download_speed(self) -> float:
        """Calculate average download speed in bytes per second."""
        elapsed_seconds = self.elapsed_time.total_seconds()
        if elapsed_seconds <= 0:
            return 0.0
        return self.downloaded_bytes / elapsed_seconds
        
    @property
    def estimated_remaining_time(self) -> Optional[timedelta]:
        """Estimate remaining time to complete download."""
        if not self.is_active or self.progress >= 100:
            return None
            
        if self.download_speed <= 0:
            return None
            
        bytes_remaining = max(0, self.total_size - self.downloaded_bytes)
        seconds_remaining = bytes_remaining / self.download_speed
        return timedelta(seconds=seconds_remaining)
        
    def update(self, **kwargs) -> None:
        """Update session attributes."""
        for key, value in kwargs.items():
            if hasattr(self, key):
                setattr(self, key, value)
        self.last_updated = datetime.now()
        
class AsyncSessionManager:
    """Thread-safe and async-compatible session manager with enhanced recovery mechanisms."""
    
    def __init__(self, session_file: str, auto_save_interval: int = 30, max_backups: int = 5):
        self.session_file = session_file
        self._sessions: Dict[str, DownloadSession] = {}
        self.lock = threading.RLock()
        self.save_lock = asyncio.Lock()
        self.last_save = time.time()
        self.auto_save_interval = auto_save_interval
        self.save_task: Optional[asyncio.Task] = None
        self.max_backups = max_backups
        
        # Initialize error handler
        error_log_path = "logs/snatch_errors.log"
        self.error_handler = EnhancedErrorHandler(log_file=error_log_path)
        
        self._load_sessions()
        
    def _create_default_session_data(self, url: str, now: datetime) -> Dict[str, Any]:
        """Create a default session data structure."""
        return {
            'url': url,
            'start_time': now,
            'last_updated': now,
            'total_size': 0,
            'downloaded_bytes': 0,
            'chunks_downloaded': [],
            'file_path': '',
            'status': SESSION_STATUS_UNKNOWN,
            'metadata': {},
            'resume_data': {}
        }
        
    def _populate_missing_fields(self, session_data: Dict[str, Any], now: datetime) -> None:
        """Ensure all required fields exist in session data."""
        defaults = self._create_default_session_data(session_data.get('url', ''), now)
        for key, value in defaults.items():
            if key not in session_data:
                session_data[key] = value
                
    def _convert_datetime_fields(self, session_data: Dict[str, Any]) -> None:
        """Convert datetime strings to datetime objects."""
        for field in ['start_time', 'last_updated']:
            if isinstance(session_data[field], str):
                try:
                    session_data[field] = datetime.fromisoformat(session_data[field])
                except ValueError:
                    # Handle non-ISO format for backward compatibility
                    session_data[field] = datetime.now()
        
    def _convert_legacy_session(self, url: str, session_data: Dict[str, Any], now: datetime) -> Dict[str, Any]:
        """Convert a legacy session format to the new format with enhanced resilience."""
        converted_data = {}
        converted_data['url'] = url
        converted_data['file_path'] = session_data.get('file_path', url if url.startswith('C:') else '')
        converted_data['total_size'] = session_data.get('total_size', 0)
        converted_data['downloaded_bytes'] = session_data.get('downloaded_bytes', 0)
        converted_data['chunks_downloaded'] = session_data.get('chunks_downloaded', [])
        converted_data['status'] = session_data.get('status', session_data.get('metadata', {}).get('status', SESSION_STATUS_UNKNOWN))
        
        # Handle timestamps
        converted_data.update(self._convert_timestamps(session_data, now))
        
        # Calculate downloaded bytes from progress if needed
        if converted_data['downloaded_bytes'] == 0:
            progress = session_data.get('progress', 0)
            if progress and converted_data['total_size'] > 0:
                converted_data['downloaded_bytes'] = int((progress / 100.0) * converted_data['total_size'])
        
        # Handle metadata
        converted_data['metadata'] = self._convert_metadata(session_data, 
            converted_data['downloaded_bytes'] / converted_data['total_size'] * 100 if converted_data['total_size'] > 0 else 0)
            
        # Add resume data for resilience
        converted_data['resume_data'] = self._create_resume_data(converted_data)
        
        return converted_data
        
    def _create_resume_data(self, session_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create resume data for a session to enable download recovery."""
        resume_data = {}
        file_path = session_data.get('file_path', '')
        
        if file_path and os.path.exists(file_path):
            try:
                # Add file information for resumability
                file_stats = os.stat(file_path)
                resume_data['file_size'] = file_stats.st_size
                resume_data['file_mtime'] = file_stats.st_mtime
                resume_data['partial_file_hash'] = compute_file_hash(file_path, 'md5')
            except (OSError, IOError) as e:
                logger.error(f"Failed to get file stats for resume data: {str(e)}")
                
        # Add download position data
        resume_data['downloaded_bytes'] = session_data.get('downloaded_bytes', 0)
        resume_data['chunks_downloaded'] = session_data.get('chunks_downloaded', [])
        resume_data['last_position'] = session_data.get('downloaded_bytes', 0)
        
        return resume_data
    def _parse_timestamp(self, timestamp_str: str, now: datetime) -> datetime:
        """Parse a timestamp string with multiple format fallbacks.
        
        Args:
            timestamp_str: String representation of timestamp
            now: Current datetime to use as fallback
            
        Returns:
            Parsed datetime or fallback value
        """
        try:
            return datetime.strptime(timestamp_str, "%Y-%m-%d %H:%M:%S")
        except ValueError:
            try:
                # Try ISO format as fallback
                return datetime.fromisoformat(timestamp_str)
            except ValueError:
                return now
                
    def _timestamp_from_epoch(self, epoch_timestamp: Optional[Union[int, float]], now: datetime) -> datetime:
        """Convert an epoch timestamp to datetime with error handling.
        
        Args:
            epoch_timestamp: Unix timestamp as int or float
            now: Current datetime to use as fallback
            
        Returns:
            Parsed datetime or fallback value
        """
        if not epoch_timestamp:
            return now
            
        try:
            return datetime.fromtimestamp(epoch_timestamp)
        except (ValueError, TypeError, OverflowError):
            return now
    
    def _convert_timestamps(self, session_data: Dict[str, Any], now: datetime) -> Dict[str, datetime]:
        """Convert timestamp fields from legacy format with enhanced error handling."""
        result = {}
        
        # Extract timestamp fields
        timestamp = session_data.get('timestamp')
        last_active = session_data.get('last_active')
        
        # Process last_updated timestamp
        if last_active and isinstance(last_active, str):
            result['last_updated'] = self._parse_timestamp(last_active, now)
        else:
            result['last_updated'] = self._timestamp_from_epoch(timestamp, now)
            
        # Process start_time - either use existing or default to last_updated
        start_time = session_data.get('start_time')
        if start_time:
            if isinstance(start_time, str):
                result['start_time'] = self._parse_timestamp(start_time, result['last_updated'])
            else:
                result['start_time'] = self._timestamp_from_epoch(start_time, result['last_updated'])
        else:
            result['start_time'] = result['last_updated']
            
        return result
        
    def _convert_metadata(self, session_data: Dict[str, Any], progress: float) -> Dict[str, Any]:
        """Convert metadata from legacy format with enhanced data preservation."""
        metadata = session_data.get('metadata', {})
        if not isinstance(metadata, dict):
            metadata = {}
        
        # Preserve progress in metadata
        metadata['progress'] = progress
        
        # Add additional diagnostic metadata
        metadata['conversion_time'] = datetime.now().isoformat()
        metadata['converted_from_legacy'] = True
        
        # Preserve other fields from the session data
        for key, value in session_data.items():
            if key not in ['url', 'file_path', 'start_time', 'last_updated', 'total_size', 
                          'downloaded_bytes', 'chunks_downloaded', 'status', 'metadata']:
                metadata[f"legacy_{key}"] = value
                
        return metadata

    def _load_sessions(self) -> None:
        """Load sessions from disk with atomic read and error recovery."""
        try:
            if not os.path.exists(self.session_file):
                return
                
            # Try to load with the utility function first
            data = safe_json_read(self.session_file, default=None)
                
            # If safe_json_read failed, try direct load as fallback
            if data is None:
                with open(self.session_file, 'r') as f:
                    data = json.load(f)
                
            # Convert plain dicts to DownloadSession objects
            with self.lock:
                now = datetime.now()
                for url, session_data in data.items():
                    try:
                        # Convert legacy format to new format
                        converted_data = self._convert_legacy_session(url, session_data, now)
                        
                        # Ensure all required fields are present
                        self._populate_missing_fields(converted_data, now)
                        
                        # Convert datetime fields
                        self._convert_datetime_fields(converted_data)
                        
                        # Create DownloadSession object
                        self._sessions[url] = DownloadSession(**converted_data)                        
                    except (TypeError, ValueError) as error:
                        logging.error(f"Failed to load session for {url}: {str(error)}")
                        continue
        except (json.JSONDecodeError, IOError) as e:
            logging.error(f"Error loading sessions: {str(e)}")
            self._backup_corrupted_file()
            
            # Attempt to recover from backup
            self._recover_from_backup()

    def _recover_from_backup(self) -> bool:
        """Attempt to recover sessions from a backup file."""
        backup_dir = os.path.join(os.path.dirname(self.session_file), "backups")
        if not os.path.exists(backup_dir):
            return False
            
        backups = sorted([
            os.path.join(backup_dir, f) for f in os.listdir(backup_dir)
            if f.startswith(os.path.basename(self.session_file))
        ], key=os.path.getmtime, reverse=True)
        
        for backup in backups:
            try:
                with open(backup, 'r') as f:
                    data = json.load(f)
                    
                # If we got here, backup is valid JSON
                with self.lock:
                    now = datetime.now()
                    for url, session_data in data.items():
                        try:
                            converted_data = self._convert_legacy_session(url, session_data, now)
                            self._populate_missing_fields(converted_data, now)
                            self._convert_datetime_fields(converted_data)
                            self._sessions[url] = DownloadSession(**converted_data)
                        except (TypeError, ValueError) as e:
                            logging.error("Failed to load session from backup: %s", str(e))
                            continue  # Skip invalid sessions
                            logging.info(f"Successfully recovered sessions from backup: {backup}")
                return True
            except Exception as e:
                logging.warning(f"Failed to load backup {backup}: {e}")
                continue  # Try next backup
                
        return False

    async def _save_sessions_async(self) -> None:
        """Save sessions to disk atomically using async IO with backup rotation."""
        if not self._sessions:
            return
            
        async with self.save_lock:
            # Skip if last save was too recent
            if time.time() - self.last_save < self.auto_save_interval:
                return
                
            # Convert sessions to serializable format
            data = {}
            with self.lock:
                for url, session in self._sessions.items():
                    session_dict = asdict(session)
                    session_dict['start_time'] = session.start_time.isoformat()
                    session_dict['last_updated'] = session.last_updated.isoformat()
                    data[url] = session_dict
                    
            # Create backup directory if needed
            backup_dir = os.path.join(os.path.dirname(self.session_file), "backups")
            os.makedirs(backup_dir, exist_ok=True)
            
            # Create backup of current file if it exists
            if os.path.exists(self.session_file):
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                backup_file = os.path.join(backup_dir, f"{os.path.basename(self.session_file)}.{timestamp}")
                try:
                    shutil.copy2(self.session_file, backup_file)
                    
                    # Rotate backups to keep only max_backups
                    self._rotate_backups(backup_dir)
                except (IOError, OSError) as e:
                    logging.error(f"Error creating backup: {str(e)}")
                    
            # Write to temp file first
            temp_path = f"{self.session_file}.{os.urandom(4).hex()}.tmp"
            try:
                async with aiofiles.open(temp_path, 'w') as f:
                    await f.write(json.dumps(data, indent=2))
                    await f.flush()
                    os.fsync(f.fileno())
                    
                # Atomic rename
                await aiofiles.os.replace(temp_path, self.session_file)
                self.last_save = time.time()
                
            except (IOError, OSError) as e:
                logging.error(f"Error saving sessions: {str(e)}")
                if os.path.exists(temp_path):
                    try:
                        os.unlink(temp_path)
                    except (IOError, OSError) as e:
                        logging.error(f"Failed to remove temp file: {str(e)}")
                        
    def _rotate_backups(self, backup_dir: str) -> None:
        """Rotate backup files to keep only max_backups."""
        try:
            backups = [
                os.path.join(backup_dir, f) for f in os.listdir(backup_dir)
                if f.startswith(os.path.basename(self.session_file))
            ]
            
            # Sort by modification time (oldest first)
            backups.sort(key=os.path.getmtime)
            
            # Remove oldest backups if we have too many
            while len(backups) > self.max_backups:
                to_remove = backups.pop(0)
                try:
                    os.unlink(to_remove)
                except (IOError, OSError) as e:
                    logging.error(f"Failed to remove old backup {to_remove}: {str(e)}")
        except Exception as e:
            logging.error(f"Error rotating backups: {str(e)}")
                        
    async def start_auto_save(self) -> None:
        """Start background auto-save task."""
        async def _auto_save():
            while True:
                try:
                    await self._save_sessions_async()
                except Exception as e:
                    logging.error(f"Error in auto-save: {str(e)}")
                await asyncio.sleep(self.auto_save_interval)
                
        if not self.save_task:
            self.save_task = asyncio.create_task(_auto_save())
            
    def stop_auto_save(self) -> None:
        """Stop background auto-save task."""
        if self.save_task:
            self.save_task.cancel()
            self.save_task = None
            
    def _backup_corrupted_file(self) -> None:
        """Create backup of corrupted session file."""
        if not os.path.exists(self.session_file):
            return
            
        backup_dir = os.path.join(os.path.dirname(self.session_file), "backups")
        os.makedirs(backup_dir, exist_ok=True)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = os.path.join(backup_dir, f"{os.path.basename(self.session_file)}.corrupted.{timestamp}")
        
        try:
            shutil.copy2(self.session_file, backup_path)
            logging.info(f"Backed up corrupted file to {backup_path}")
        except IOError as e:
            logging.error(f"Failed to backup corrupted file: {str(e)}")
            
    def create_session(self, url: str, file_path: str, total_size: int, metadata: Dict[str, Any] = None) -> None:
        """Create new download session with enhanced metadata."""
        now = datetime.now()
        metadata = metadata or {}
        
        # Create resume data
        resume_data = {
            'downloaded_bytes': 0,
            'chunks_downloaded': [],
            'last_position': 0
        }
        
        session = DownloadSession(
            url=url,
            file_path=file_path, 
            total_size=total_size,
            downloaded_bytes=0,
            chunks_downloaded=[],
            start_time=now,
            last_updated=now,
            status=SESSION_STATUS_STARTING,
            metadata=metadata,
            resume_data=resume_data
        )
        with self.lock:self._sessions[url] = session
            
    @handle_errors(ErrorCategory.DOWNLOAD, ErrorSeverity.WARNING)
    def update_session(self, url: str, bytes_downloaded: int, status: Optional[str] = None, 
                       chunk_hash: Optional[str] = None, metadata: Optional[Dict[str, Any]] = None) -> None:
        """Update session progress thread-safely with enhanced status and metadata handling."""
        with self.lock:
            if url not in self._sessions:
                return
                
            session = self._sessions[url]
            session.downloaded_bytes = bytes_downloaded
            session.last_updated = datetime.now()
            
            if status:
                session.status = status
                
            if chunk_hash and chunk_hash not in session.chunks_downloaded:
                session.chunks_downloaded.append(chunk_hash)
                
            if metadata:
                session.metadata.update(metadata)
                
            # Update resume data
            session.resume_data['downloaded_bytes'] = bytes_downloaded
            session.resume_data['last_position'] = bytes_downloaded
            if chunk_hash:
                if 'chunks_downloaded' not in session.resume_data:
                    session.resume_data['chunks_downloaded'] = []
                if chunk_hash not in session.resume_data['chunks_downloaded']:
                    session.resume_data['chunks_downloaded'].append(chunk_hash)
                    
    def get_session(self, url: str) -> Optional[DownloadSession]:
        """Get session info thread-safely."""
        with self.lock:
            return self._sessions.get(url)
            
    def get_session_copy(self, url: str) -> Optional[Dict[str, Any]]:
        """Get a copy of the session as a dictionary to avoid thread safety issues."""
        with self.lock:
            session = self._sessions.get(url)
            if session:
                session_dict = asdict(session)
                session_dict['start_time'] = session.start_time.isoformat()
                session_dict['last_updated'] = session.last_updated.isoformat()
                session_dict['progress'] = session.progress
                session_dict['download_speed'] = session.download_speed
                session_dict['elapsed_time'] = session.elapsed_time.total_seconds()
                
                remaining = session.estimated_remaining_time
                session_dict['estimated_remaining_seconds'] = remaining.total_seconds() if remaining else None
                
                return session_dict
            return None
            
    def remove_session(self, url: str) -> None:
        """Remove completed/failed session."""
        with self.lock:
            self._sessions.pop(url, None)
            
    def prune_stale_sessions(self, max_age_hours: int = 24) -> None:
        """Remove sessions older than max_age_hours."""
        cutoff = datetime.now() - timedelta(hours=max_age_hours)
        
        with self.lock:
            stale_urls = [
                url for url, session in self._sessions.items()
                if session.last_updated < cutoff
            ]
            
            for url in stale_urls:
                self._sessions.pop(url)
                
    def get_active_sessions(self) -> List[DownloadSession]:
        """Get all non-completed sessions."""
        with self.lock:
            return [
                session for session in self._sessions.values()
                if session.status not in (SESSION_STATUS_COMPLETED, SESSION_STATUS_FAILED, SESSION_STATUS_CANCELLED)
            ]
            
    def list_sessions(self, filter_status: Optional[str] = None) -> List[DownloadSession]:
        """List all sessions, optionally filtered by status."""
        with self.lock:
            sessions = list(self._sessions.values())
            if filter_status:
                sessions = [s for s in sessions if s.status == filter_status]
            return sessions
            
    def cancel_session(self, url: str) -> bool:
        """Cancel an active session and cleanup."""
        with self.lock:
            if url not in self._sessions:
                return False
            
            session = self._sessions[url]
            if session.status not in (SESSION_STATUS_COMPLETED, SESSION_STATUS_FAILED, SESSION_STATUS_CANCELLED):
                session.status = SESSION_STATUS_CANCELLED
                session.last_updated = datetime.now()
                return True
            return False
    
    def resume_session(self, url: str) -> bool:
        """
        Resume a paused or failed session.
        
        Args:
            url: The download URL
            
        Returns:
            bool: True if session was resumed, False otherwise
        """
        with self.lock:
            if url not in self._sessions:
                return False
                
            session = self._sessions[url]
            if session.status in (SESSION_STATUS_PAUSED, SESSION_STATUS_FAILED):
                session.status = SESSION_STATUS_DOWNLOADING
                session.last_updated = datetime.now()
                session.metadata['resume_count'] = session.metadata.get('resume_count', 0) + 1
                session.metadata['last_resumed'] = datetime.now().isoformat()
                return True
            return False
            
    def pause_session(self, url: str) -> bool:
        """
        Pause an active download session.
        
        Args:
            url: The download URL
            
        Returns:
            bool: True if session was paused, False otherwise
        """
        with self.lock:
            if url not in self._sessions:
                return False
                
            session = self._sessions[url]
            if session.status == SESSION_STATUS_DOWNLOADING:
                session.status = SESSION_STATUS_PAUSED
                session.last_updated = datetime.now()
                session.metadata['pause_count'] = session.metadata.get('pause_count', 0) + 1
                session.metadata['last_paused'] = datetime.now().isoformat()
                return True
        return False
            
    def batch_update(self, updates: Dict[str, Dict[str, Any]]) -> None:
        """Batch update multiple sessions atomically."""
        with self.lock:
            for url, update_data in updates.items():
                self._update_single_session(url, update_data)
                        
    def _update_session_field(self, session: DownloadSession, field: str, value: Any) -> None:
        """Update a specific field in a session."""
        if field == 'downloaded_bytes':
            session.downloaded_bytes = value
        elif field == 'status':
            session.status = value
        elif field == 'metadata':
            session.metadata.update(value)
        elif field == 'resume_data':
            session.resume_data.update(value)
        elif field == 'chunks_downloaded':
            for chunk in value:
                if chunk not in session.chunks_downloaded:
                    session.chunks_downloaded.append(chunk)
    
    def _update_single_session(self, url: str, update_data: Dict[str, Any]) -> None:
        """Update a single session with the provided data."""
        if url not in self._sessions:
            return
            
        session = self._sessions[url]
        
        # Update each field that's present in update_data
        for field, value in update_data.items():
            if field in ['downloaded_bytes', 'status', 'metadata', 'resume_data', 'chunks_downloaded']:
                self._update_session_field(session, field, value)
        
        session.last_updated = datetime.now()

    def query_sessions(self, predicate: Callable[[DownloadSession], bool]) -> List[DownloadSession]:
        """Query sessions using a custom predicate."""
        with self.lock:
            return [s for s in self._sessions.values() if predicate(s)]
    
    def verify_file_integrity(self, url: str) -> Tuple[bool, Optional[str]]:
        """
        Verify the integrity of a downloaded file using checksums in session data.
        
        Args:
            url: The download URL
            
        Returns:
            Tuple[bool, Optional[str]]: (is_valid, error_message)
        """
        with self.lock:
            if url not in self._sessions:
                return False, "Session not found"
                
            session = self._sessions[url]
            if not session.file_path or not os.path.exists(session.file_path):
                return False, "File not found"
                
            # Check if we have a checksum in metadata
            checksum = session.metadata.get('checksum')
            if not checksum:
                return True, None  # No checksum to verify against
                
            algorithm = session.metadata.get('checksum_algorithm', 'sha256')
            computed = compute_file_hash(session.file_path, algorithm)
            
            if not computed:
                return False, f"Failed to compute {algorithm} hash"
                
            if computed.lower() != checksum.lower():
                return False, f"Checksum mismatch: expected {checksum}, got {computed}"
                
            return True, None
                
    def get_session_stats(self) -> Dict[str, Any]:
        """Get detailed statistics about current sessions."""
        with self.lock:
            total = len(self._sessions)
            by_status = {}
            total_bytes = 0
            active_bytes = 0
            completed_bytes = 0
            started_last_hour = 0
            completed_last_hour = 0
            active_speed = 0
            
            one_hour_ago = datetime.now() - timedelta(hours=1)
            
            for session in self._sessions.values():
                # Count by status
                by_status[session.status] = by_status.get(session.status, 0) + 1
                
                # Sum bytes
                total_bytes += session.total_size
                
                if session.status == SESSION_STATUS_DOWNLOADING:
                    active_bytes += session.downloaded_bytes
                    active_speed += session.download_speed
                    
                if session.status == SESSION_STATUS_COMPLETED:
                    completed_bytes += session.total_size
                    
                # Count recent sessions
                if session.start_time > one_hour_ago:
                    started_last_hour += 1
                    
                if session.status == SESSION_STATUS_COMPLETED and session.last_updated > one_hour_ago:
                    completed_last_hour += 1
                    
            return {
                'total_sessions': total,
                'by_status': by_status,
                'total_bytes': total_bytes,
                'active_bytes': active_bytes,
                'completed_bytes': completed_bytes,
                'started_last_hour': started_last_hour,
                'completed_last_hour': completed_last_hour,
                'active_speed': active_speed,
                'active_sessions': len([s for s in self._sessions.values() if s.is_active]),
                'timestamp': datetime.now().isoformat()
            }
            
    async def __aenter__(self) -> 'AsyncSessionManager':
        """Async context manager support."""
        await self.start_auto_save()
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Ensure final save on exit."""
        self.stop_auto_save()
        await self._save_sessions_async()

class SessionManager:
    """Synchronous wrapper around AsyncSessionManager with enhanced backwards compatibility."""
    
    def __init__(self, session_file: Optional[str] = None):
        """Initialize session manager with sync interface.
        
        Args:
            session_file: Path to the sessions data file. If None, uses default path.
        """        # Use config directory for sessions file if no path provided
        if session_file is None:
            session_file = os.path.join(
                os.path.dirname(os.path.dirname(__file__)), 
                'sessions',
                DOWNLOAD_SESSIONS_FILE
            )
            os.makedirs(os.path.dirname(session_file), exist_ok=True)
            
        self._async_manager = AsyncSessionManager(session_file)
        
        # Initialize error handler
        error_log_path = "logs/snatch_errors.log" 
        self.error_handler = EnhancedErrorHandler(log_file=error_log_path)
        
    def update_session(self, url: str, percentage: float, **metadata) -> None:
        """Update session state synchronously.
        
        Args:
            url: The download URL.
            percentage: Download progress percentage.
            **metadata: Additional session metadata.
        """
        now = datetime.now()
        session = self._async_manager._sessions.get(url)
        
        if session is None:
            session = DownloadSession(
                url=url,
                file_path=metadata.get('file_path', ''),
                total_size=metadata.get('total_size', 0),
                downloaded_bytes=int(metadata.get('total_size', 0) * percentage / 100),
                chunks_downloaded=[],
                start_time=now,
                last_updated=now,
                status=SESSION_STATUS_DOWNLOADING,
                metadata={
                    'percentage': percentage,
                    **metadata
                },
                resume_data={
                    'downloaded_bytes': int(metadata.get('total_size', 0) * percentage / 100),
                    'last_position': int(metadata.get('total_size', 0) * percentage / 100),
                    'chunks_downloaded': []
                }
            )
        else:
            session.downloaded_bytes = int(session.total_size * percentage / 100)
            session.last_updated = now
            session.metadata.update({
                'percentage': percentage,
                **metadata
            })
            
            # Update resume data
            session.resume_data['downloaded_bytes'] = session.downloaded_bytes
            session.resume_data['last_position'] = session.downloaded_bytes
            
        with self._async_manager.lock:
            self._async_manager._sessions[url] = session
            
        # Trigger sync save
        asyncio.run(self._async_manager._save_sessions_async())
        
    def get_session(self, url: str) -> Optional[Dict[str, Any]]:
        """Get session data synchronously.
        
        Args:
            url: The download URL.
            
        Returns:
            Session data dict or None if not found.
        """
        return self._async_manager.get_session_copy(url)
        
    def remove_session(self, url: str) -> None:
        """Remove a session synchronously.
        
        Args:
            url: The download URL to remove.
        """
        with self._async_manager.lock:
            if url in self._async_manager._sessions:
                del self._async_manager._sessions[url]
                asyncio.run(self._async_manager._save_sessions_async())
                
    def cancel_session(self, url: str) -> bool:
        """Cancel a download session synchronously.
        
        Args:
            url: The download URL.
            
        Returns:
            bool: True if session was cancelled, False otherwise.
        """
        result = self._async_manager.cancel_session(url)
        asyncio.run(self._async_manager._save_sessions_async())
        return result
        
    def resume_session(self, url: str) -> bool:
        """Resume a paused or failed session synchronously.
        
        Args:
            url: The download URL.
            
        Returns:
            bool: True if session was resumed, False otherwise.
        """
        result = self._async_manager.resume_session(url)
        asyncio.run(self._async_manager._save_sessions_async())
        return result
        
    def list_sessions(self, filter_status: Optional[str] = None) -> List[Dict[str, Any]]:
        """List sessions synchronously.
        
        Args:
            filter_status: Optional status string to filter by
            
        Returns:
            List of session dictionaries.
        """
        sessions = self._async_manager.list_sessions(filter_status)
        return [self._async_manager.get_session_copy(session.url) for session in sessions]
        
    def get_stats(self) -> Dict[str, Any]:
        """Get session statistics synchronously.
        
        Returns:
            Statistics dictionary.
        """
        return self._async_manager.get_session_stats()

    def create_session(self, url: str, file_path: str, total_size: int, metadata: Dict[str, Any] = None) -> str:
        """Create new download session synchronously.
        
        Args:
            url: The download URL.
            file_path: Path where the file will be downloaded.
            total_size: Total file size in bytes.
            metadata: Optional metadata dictionary.
            
        Returns:
            str: The session URL (used as ID).
        """
        self._async_manager.create_session(url, file_path, total_size, metadata)
        asyncio.run(self._async_manager._save_sessions_async())
        return url
