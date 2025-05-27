"""
Advanced Download Scheduler for Snatch Media Downloader

Implements intelligent download scheduling with priority queues, bandwidth management,
retry logic, and optimal resource utilization.
"""

import asyncio
import logging
import time
import heapq
from typing import Dict, Any, List, Optional, Callable, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
import json
import os

logger = logging.getLogger(__name__)

class Priority(Enum):
    """Download priority levels"""
    URGENT = 1
    HIGH = 2
    NORMAL = 3
    LOW = 4
    BACKGROUND = 5

class DownloadStatus(Enum):
    """Download status states"""
    PENDING = "pending"
    DOWNLOADING = "downloading"
    COMPLETED = "completed"
    FAILED = "failed"
    PAUSED = "paused"
    CANCELLED = "cancelled"

@dataclass
class ScheduledDownload:
    """Scheduled download task"""
    id: str
    url: str
    options: Dict[str, Any]
    priority: Priority = Priority.NORMAL
    scheduled_time: Optional[datetime] = None
    status: DownloadStatus = DownloadStatus.PENDING
    retry_count: int = 0
    max_retries: int = 3
    created_at: datetime = field(default_factory=datetime.now)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    error_message: Optional[str] = None
    estimated_size: Optional[int] = None  # bytes
    downloaded_size: int = 0
    progress: float = 0.0
    
    def __lt__(self, other):
        """For heap sorting by priority and scheduled time"""
        if self.priority.value != other.priority.value:
            return self.priority.value < other.priority.value
        
        self_time = self.scheduled_time or self.created_at
        other_time = other.scheduled_time or other.created_at
        return self_time < other_time

class BandwidthManager:
    """Manages bandwidth allocation across downloads"""
    
    def __init__(self, max_bandwidth_mbps: float = 100.0):
        self.max_bandwidth = max_bandwidth_mbps * 1024 * 1024  # Convert to bytes/sec
        self.allocated_bandwidth = {}  # download_id -> allocated_bytes_per_sec
        self.usage_history = []
        self.lock = asyncio.Lock()
    
    async def allocate_bandwidth(self, download_id: str, requested_bandwidth: float) -> float:
        """Allocate bandwidth for a download"""
        async with self.lock:
            current_usage = sum(self.allocated_bandwidth.values())
            available = self.max_bandwidth - current_usage
            
            # Allocate up to requested amount or available bandwidth
            allocated = min(requested_bandwidth, available)
            if allocated > 0:
                self.allocated_bandwidth[download_id] = allocated
            
            return allocated
    
    async def release_bandwidth(self, download_id: str) -> None:
        """Release bandwidth allocation for a download"""
        async with self.lock:
            self.allocated_bandwidth.pop(download_id, None)
    
    async def get_bandwidth_info(self) -> Dict[str, Any]:
        """Get current bandwidth allocation info"""
        async with self.lock:
            current_usage = sum(self.allocated_bandwidth.values())
            return {
                "max_bandwidth_mbps": self.max_bandwidth / 1024 / 1024,
                "current_usage_mbps": current_usage / 1024 / 1024,
                "available_mbps": (self.max_bandwidth - current_usage) / 1024 / 1024,
                "active_downloads": len(self.allocated_bandwidth),
                "allocations": {
                    k: v / 1024 / 1024 for k, v in self.allocated_bandwidth.items()
                }
            }

class AdvancedScheduler:
    """Advanced download scheduler with intelligent queuing"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.download_queue = []  # Priority heap
        self.active_downloads = {}  # download_id -> task
        self.completed_downloads = {}
        self.failed_downloads = {}
        
        # Configuration
        self.max_concurrent = config.get('max_concurrent_downloads', 3)
        self.max_bandwidth_mbps = config.get('max_bandwidth_mbps', 100.0)
        self.retry_delay_base = config.get('retry_delay_base', 5.0)  # seconds
        self.retry_delay_multiplier = config.get('retry_delay_multiplier', 2.0)
        
        # Components
        self.bandwidth_manager = BandwidthManager(self.max_bandwidth_mbps)
        self.is_running = False
        self.scheduler_task = None
        
        # Callbacks
        self.download_started_callbacks = []
        self.download_completed_callbacks = []
        self.download_failed_callbacks = []
        self.progress_callbacks = []
        
        logger.info("Advanced scheduler initialized")
    
    async def start(self) -> None:
        """Start the scheduler"""
        if self.is_running:
            logger.warning("Scheduler is already running")
            return
        
        self.is_running = True
        self.scheduler_task = asyncio.create_task(self._scheduler_loop())
        logger.info("Advanced scheduler started")
    
    async def stop(self) -> None:
        """Stop the scheduler"""
        self.is_running = False
        
        if self.scheduler_task:
            self.scheduler_task.cancel()
            try:
                await self.scheduler_task
            except asyncio.CancelledError:
                pass
        
        # Cancel all active downloads
        for task in self.active_downloads.values():
            task.cancel()
        
        logger.info("Advanced scheduler stopped")
    
    async def schedule_download(
        self, 
        url: str, 
        options: Dict[str, Any], 
        priority: Priority = Priority.NORMAL,
        scheduled_time: Optional[datetime] = None
    ) -> str:
        """Schedule a new download"""
        download_id = f"dl_{int(time.time() * 1000)}_{len(self.download_queue)}"
        
        download = ScheduledDownload(
            id=download_id,
            url=url,
            options=options,
            priority=priority,
            scheduled_time=scheduled_time
        )
        
        heapq.heappush(self.download_queue, download)
        logger.info(f"Download scheduled: {download_id} with priority {priority.name}")
        
        return download_id
    
    async def cancel_download(self, download_id: str) -> bool:
        """Cancel a download"""
        # Check if it's in active downloads
        if download_id in self.active_downloads:
            task = self.active_downloads[download_id]
            task.cancel()
            await self.bandwidth_manager.release_bandwidth(download_id)
            del self.active_downloads[download_id]
            logger.info(f"Active download cancelled: {download_id}")
            return True
        
        # Check if it's in the queue
        for i, download in enumerate(self.download_queue):
            if download.id == download_id:
                download.status = DownloadStatus.CANCELLED
                logger.info(f"Queued download cancelled: {download_id}")
                return True
        
        logger.warning(f"Download not found for cancellation: {download_id}")
        return False
    
    async def pause_download(self, download_id: str) -> bool:
        """Pause a download"""
        if download_id in self.active_downloads:
            # For now, we cancel and re-queue with paused status
            await self.cancel_download(download_id)
            # Mark as paused in queue
            for download in self.download_queue:
                if download.id == download_id:
                    download.status = DownloadStatus.PAUSED
                    break
            return True
        return False
    
    async def resume_download(self, download_id: str) -> bool:
        """Resume a paused download"""
        for download in self.download_queue:
            if download.id == download_id and download.status == DownloadStatus.PAUSED:
                download.status = DownloadStatus.PENDING
                logger.info(f"Download resumed: {download_id}")
                return True
        return False
    
    async def get_queue_status(self) -> Dict[str, Any]:
        """Get current queue status"""
        pending_count = sum(1 for d in self.download_queue if d.status == DownloadStatus.PENDING)
        paused_count = sum(1 for d in self.download_queue if d.status == DownloadStatus.PAUSED)
        
        bandwidth_info = await self.bandwidth_manager.get_bandwidth_info()
        
        return {
            "queue_length": len(self.download_queue),
            "pending_downloads": pending_count,
            "paused_downloads": paused_count,
            "active_downloads": len(self.active_downloads),
            "completed_downloads": len(self.completed_downloads),
            "failed_downloads": len(self.failed_downloads),
            "bandwidth": bandwidth_info,
            "is_running": self.is_running
        }
    
    async def get_download_info(self, download_id: str) -> Optional[Dict[str, Any]]:
        """Get information about a specific download"""
        # Check active downloads
        if download_id in self.active_downloads:
            # Find the download in queue for full info
            for download in self.download_queue:
                if download.id == download_id:
                    return self._download_to_dict(download)
        
        # Check completed downloads
        if download_id in self.completed_downloads:
            return self._download_to_dict(self.completed_downloads[download_id])
        
        # Check failed downloads
        if download_id in self.failed_downloads:
            return self._download_to_dict(self.failed_downloads[download_id])
        
        # Check queue
        for download in self.download_queue:
            if download.id == download_id:
                return self._download_to_dict(download)
        
        return None
    
    def _download_to_dict(self, download: ScheduledDownload) -> Dict[str, Any]:
        """Convert download object to dictionary"""
        return {
            "id": download.id,
            "url": download.url,
            "priority": download.priority.name,
            "status": download.status.value,
            "progress": download.progress,
            "retry_count": download.retry_count,
            "created_at": download.created_at.isoformat(),
            "started_at": download.started_at.isoformat() if download.started_at else None,
            "completed_at": download.completed_at.isoformat() if download.completed_at else None,
            "estimated_size": download.estimated_size,
            "downloaded_size": download.downloaded_size,
            "error_message": download.error_message
        }
    
    async def _scheduler_loop(self) -> None:
        """Main scheduler loop"""
        while self.is_running:
            try:
                await self._process_queue()
                await asyncio.sleep(1.0)  # Check every second
            except Exception as e:
                logger.error(f"Error in scheduler loop: {e}")
                await asyncio.sleep(5.0)  # Wait longer on error
    async def _process_queue(self) -> None:
        """Process the download queue with optimized flow control"""
        current_time = datetime.now()
        
        # Start new downloads if we have capacity
        while (len(self.active_downloads) < self.max_concurrent and 
               self.download_queue):
            
            eligible_download = self._find_next_eligible_download(current_time)
            if not eligible_download:
                break  # No eligible downloads
            
            await self._prepare_and_start_download(eligible_download)
    
    def _find_next_eligible_download(self, current_time: datetime) -> Optional[ScheduledDownload]:
        """Find the next eligible download from the queue"""
        for i, download in enumerate(self.download_queue):
            if self._is_download_eligible(download, current_time):
                return download
        return None
    
    def _is_download_eligible(self, download: ScheduledDownload, current_time: datetime) -> bool:
        """Check if a download is eligible to start"""
        return (download.status == DownloadStatus.PENDING and
                (download.scheduled_time is None or download.scheduled_time <= current_time))
    
    async def _prepare_and_start_download(self, download: ScheduledDownload) -> None:
        """Prepare and start a download with proper queue management"""
        # Remove from queue and start
        self.download_queue.remove(download)
        heapq.heapify(self.download_queue)  # Re-heapify after removal
        
        await self._start_download(download)
    
    async def _start_download(self, download: ScheduledDownload) -> None:
        """Start a download"""
        download.status = DownloadStatus.DOWNLOADING
        download.started_at = datetime.now()
        
        # Allocate bandwidth
        requested_bandwidth = self.max_bandwidth_mbps * 1024 * 1024 / self.max_concurrent
        allocated = await self.bandwidth_manager.allocate_bandwidth(
            download.id, requested_bandwidth
        )
        
        # Create download task
        task = asyncio.create_task(self._execute_download(download))
        self.active_downloads[download.id] = task
        
        # Notify callbacks
        for callback in self.download_started_callbacks:
            try:
                await callback(download)
            except Exception as e:
                logger.error(f"Error in download started callback: {e}")
        
        logger.info(f"Download started: {download.id} (allocated {allocated/1024/1024:.1f} MB/s)")
    
    async def _execute_download(self, download: ScheduledDownload) -> None:
        """Execute the actual download"""
        try:
            # Import download manager here to avoid circular imports
            from .manager import AsyncDownloadManager
            
            # This would integrate with your existing download manager
            # For now, simulate a download
            logger.info(f"Executing download: {download.id}")
            
            # Simulate download progress
            for progress in range(0, 101, 10):
                download.progress = progress / 100.0
                
                # Notify progress callbacks
                for callback in self.progress_callbacks:
                    try:
                        await callback(download)
                    except Exception as e:
                        logger.error(f"Error in progress callback: {e}")
                
                await asyncio.sleep(0.5)  # Simulate work
            
            # Mark as completed
            download.status = DownloadStatus.COMPLETED
            download.completed_at = datetime.now()
            download.progress = 1.0
            
            self.completed_downloads[download.id] = download
            
            # Notify completion callbacks
            for callback in self.download_completed_callbacks:
                try:
                    await callback(download)
                except Exception as e:
                    logger.error(f"Error in download completed callback: {e}")
            
            logger.info(f"Download completed: {download.id}")
            
        except asyncio.CancelledError:
            download.status = DownloadStatus.CANCELLED
            logger.info(f"Download cancelled: {download.id}")
            raise
            
        except Exception as e:
            download.status = DownloadStatus.FAILED
            download.error_message = str(e)
            
            # Handle retries
            if download.retry_count < download.max_retries:
                download.retry_count += 1
                delay = self.retry_delay_base * (self.retry_delay_multiplier ** (download.retry_count - 1))
                download.scheduled_time = datetime.now() + timedelta(seconds=delay)
                download.status = DownloadStatus.PENDING
                
                # Re-queue for retry
                heapq.heappush(self.download_queue, download)
                logger.info(f"Download retry scheduled: {download.id} (attempt {download.retry_count})")
            else:
                self.failed_downloads[download.id] = download
                
                # Notify failure callbacks
                for callback in self.download_failed_callbacks:
                    try:
                        await callback(download)
                    except Exception as e:
                        logger.error(f"Error in download failed callback: {e}")
                
                logger.error(f"Download failed permanently: {download.id} - {e}")
        
        finally:
            # Clean up
            await self.bandwidth_manager.release_bandwidth(download.id)
            self.active_downloads.pop(download.id, None)
    
    # Callback registration methods
    def on_download_started(self, callback: Callable[[ScheduledDownload], None]) -> None:
        """Register callback for download started events"""
        self.download_started_callbacks.append(callback)
    
    def on_download_completed(self, callback: Callable[[ScheduledDownload], None]) -> None:
        """Register callback for download completed events"""
        self.download_completed_callbacks.append(callback)
    
    def on_download_failed(self, callback: Callable[[ScheduledDownload], None]) -> None:
        """Register callback for download failed events"""
        self.download_failed_callbacks.append(callback)
    
    def on_progress_update(self, callback: Callable[[ScheduledDownload], None]) -> None:
        """Register callback for progress updates"""
        self.progress_callbacks.append(callback)

# Utility functions
async def create_smart_scheduler(config: Dict[str, Any]) -> AdvancedScheduler:
    """Create and configure an advanced scheduler"""
    scheduler = AdvancedScheduler(config)
    await scheduler.start()
    return scheduler
