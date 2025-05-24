"""
Advanced Performance Monitor for Snatch Media Downloader

Monitors system resources, download performance, and provides optimization recommendations.
Features real-time metrics, bottleneck detection, and adaptive quality adjustments.
"""

import asyncio
import psutil
import logging
import time
import threading
from typing import Dict, Any, List, Optional, Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta
import json
import os
from pathlib import Path

logger = logging.getLogger(__name__)

@dataclass
class PerformanceMetrics:
    """Real-time performance metrics"""
    timestamp: datetime = field(default_factory=datetime.now)
    
    # System metrics
    cpu_percent: float = 0.0
    memory_percent: float = 0.0
    disk_io_read: float = 0.0
    disk_io_write: float = 0.0
    network_sent: float = 0.0
    network_recv: float = 0.0
    
    # Download metrics
    download_speed: float = 0.0  # MB/s
    active_downloads: int = 0
    queue_length: int = 0
    
    # Quality metrics
    audio_quality_score: float = 0.0
    video_quality_score: float = 0.0
    processing_efficiency: float = 0.0

@dataclass
class OptimizationRecommendation:
    """Performance optimization recommendation"""
    category: str
    priority: str  # LOW, MEDIUM, HIGH, CRITICAL
    message: str
    action: Optional[Callable] = None
    impact_score: float = 0.0

class PerformanceMonitor:
    """Advanced performance monitoring and optimization"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.metrics_history: List[PerformanceMetrics] = []
        self.is_monitoring = False
        self.monitor_thread = None
        self.optimization_callbacks: List[Callable] = []
        
        # Performance thresholds
        self.cpu_threshold = config.get('performance_cpu_threshold', 80.0)
        self.memory_threshold = config.get('performance_memory_threshold', 85.0)
        self.disk_threshold = config.get('performance_disk_threshold', 90.0)
        
        # Metrics collection interval
        self.collection_interval = config.get('metrics_interval', 5.0)
        
        # History retention (keep last 100 measurements)
        self.max_history = config.get('max_metrics_history', 100)
        
        logger.info("Performance monitor initialized")
    
    def start_monitoring(self) -> None:
        """Start real-time performance monitoring"""
        if self.is_monitoring:
            logger.warning("Performance monitoring is already running")
            return
            
        self.is_monitoring = True
        self.monitor_thread = threading.Thread(target=self._monitoring_loop, daemon=True)
        self.monitor_thread.start()
        logger.info("Performance monitoring started")
    
    def stop_monitoring(self) -> None:
        """Stop performance monitoring"""
        self.is_monitoring = False
        if self.monitor_thread:
            self.monitor_thread.join(timeout=5.0)
        logger.info("Performance monitoring stopped")
    
    def _monitoring_loop(self) -> None:
        """Main monitoring loop"""
        while self.is_monitoring:
            try:
                metrics = self._collect_metrics()
                self.metrics_history.append(metrics)
                
                # Trim history if needed
                if len(self.metrics_history) > self.max_history:
                    self.metrics_history = self.metrics_history[-self.max_history:]
                
                # Check for optimization opportunities
                recommendations = self._analyze_performance(metrics)
                if recommendations:
                    self._apply_optimizations(recommendations)
                
                time.sleep(self.collection_interval)
                
            except Exception as e:
                logger.error(f"Error in performance monitoring: {e}")
                time.sleep(self.collection_interval)
    
    def _collect_metrics(self) -> PerformanceMetrics:
        """Collect current system and application metrics"""
        try:
            # System metrics
            cpu_percent = psutil.cpu_percent(interval=1)
            memory = psutil.virtual_memory()
            disk_io = psutil.disk_io_counters()
            network_io = psutil.net_io_counters()
            
            return PerformanceMetrics(
                cpu_percent=cpu_percent,
                memory_percent=memory.percent,
                disk_io_read=disk_io.read_bytes / 1024 / 1024 if disk_io else 0,  # MB
                disk_io_write=disk_io.write_bytes / 1024 / 1024 if disk_io else 0,  # MB
                network_sent=network_io.bytes_sent / 1024 / 1024 if network_io else 0,  # MB
                network_recv=network_io.bytes_recv / 1024 / 1024 if network_io else 0,  # MB
            )
            
        except Exception as e:
            logger.error(f"Error collecting metrics: {e}")
            return PerformanceMetrics()
    
    def _analyze_performance(self, metrics: PerformanceMetrics) -> List[OptimizationRecommendation]:
        """Analyze performance and generate optimization recommendations"""
        recommendations = []
        
        # CPU analysis
        if metrics.cpu_percent > self.cpu_threshold:
            recommendations.append(OptimizationRecommendation(
                category="CPU",
                priority="HIGH" if metrics.cpu_percent > 90 else "MEDIUM",
                message=f"High CPU usage detected ({metrics.cpu_percent:.1f}%). Consider reducing concurrent downloads.",
                impact_score=metrics.cpu_percent / 100.0
            ))
        
        # Memory analysis
        if metrics.memory_percent > self.memory_threshold:
            recommendations.append(OptimizationRecommendation(
                category="MEMORY",
                priority="HIGH" if metrics.memory_percent > 95 else "MEDIUM",
                message=f"High memory usage detected ({metrics.memory_percent:.1f}%). Consider clearing cache or reducing quality.",
                impact_score=metrics.memory_percent / 100.0
            ))
        
        # Performance trends analysis
        if len(self.metrics_history) >= 10:
            recent_metrics = self.metrics_history[-10:]
            avg_cpu = sum(m.cpu_percent for m in recent_metrics) / len(recent_metrics)
            
            if avg_cpu > 70:
                recommendations.append(OptimizationRecommendation(
                    category="TREND",
                    priority="MEDIUM",
                    message="Sustained high CPU usage detected. Consider optimizing download settings.",
                    impact_score=0.6
                ))
        
        return recommendations
    
    def _apply_optimizations(self, recommendations: List[OptimizationRecommendation]) -> None:
        """Apply automatic optimizations where possible"""
        for rec in recommendations:
            logger.info(f"Performance recommendation [{rec.priority}]: {rec.message}")
            
            # Execute optimization callbacks
            for callback in self.optimization_callbacks:
                try:
                    callback(rec)
                except Exception as e:
                    logger.error(f"Error executing optimization callback: {e}")
    
    def get_current_metrics(self) -> Optional[PerformanceMetrics]:
        """Get the most recent performance metrics"""
        return self.metrics_history[-1] if self.metrics_history else None
    
    def get_performance_summary(self) -> Dict[str, Any]:
        """Get a summary of recent performance"""
        if not self.metrics_history:
            return {"status": "No data available"}
        
        recent_metrics = self.metrics_history[-20:] if len(self.metrics_history) >= 20 else self.metrics_history
        
        return {
            "status": "active" if self.is_monitoring else "inactive",
            "data_points": len(self.metrics_history),
            "avg_cpu": sum(m.cpu_percent for m in recent_metrics) / len(recent_metrics),
            "avg_memory": sum(m.memory_percent for m in recent_metrics) / len(recent_metrics),
            "peak_cpu": max(m.cpu_percent for m in recent_metrics),
            "peak_memory": max(m.memory_percent for m in recent_metrics),
            "last_updated": self.metrics_history[-1].timestamp.isoformat()
        }
    
    def register_optimization_callback(self, callback: Callable[[OptimizationRecommendation], None]) -> None:
        """Register a callback for optimization recommendations"""
        self.optimization_callbacks.append(callback)
    
    def export_metrics(self, file_path: str, duration_hours: int = 24) -> bool:
        """Export metrics to JSON file"""
        try:
            cutoff_time = datetime.now() - timedelta(hours=duration_hours)
            filtered_metrics = [
                {
                    "timestamp": m.timestamp.isoformat(),
                    "cpu_percent": m.cpu_percent,
                    "memory_percent": m.memory_percent,
                    "disk_io_read": m.disk_io_read,
                    "disk_io_write": m.disk_io_write,
                    "network_sent": m.network_sent,
                    "network_recv": m.network_recv,
                    "download_speed": m.download_speed,
                }
                for m in self.metrics_history
                if m.timestamp >= cutoff_time
            ]
            
            with open(file_path, 'w') as f:
                json.dump({
                    "export_time": datetime.now().isoformat(),
                    "duration_hours": duration_hours,
                    "metrics_count": len(filtered_metrics),
                    "metrics": filtered_metrics
                }, f, indent=2)
            
            logger.info(f"Metrics exported to {file_path}")
            return True
            
        except Exception as e:
            logger.error(f"Error exporting metrics: {e}")
            return False

class AdaptiveQualityManager:
    """Automatically adjusts download quality based on system performance"""
    
    def __init__(self, performance_monitor: PerformanceMonitor):
        self.performance_monitor = performance_monitor
        self.quality_levels = {
            "ultra": {"resolution": "2160", "audio_bitrate": "320"},
            "high": {"resolution": "1080", "audio_bitrate": "256"},
            "medium": {"resolution": "720", "audio_bitrate": "192"},
            "low": {"resolution": "480", "audio_bitrate": "128"}
        }
        
        self.current_quality = "high"
        self.adjustment_history = []
        
        # Register optimization callback
        performance_monitor.register_optimization_callback(self._handle_optimization)
    
    def _handle_optimization(self, recommendation: OptimizationRecommendation) -> None:
        """Handle performance optimization recommendations"""
        if recommendation.category in ["CPU", "MEMORY"] and recommendation.priority in ["HIGH", "CRITICAL"]:
            new_quality = self._downgrade_quality()
            if new_quality != self.current_quality:
                logger.info(f"Quality automatically adjusted: {self.current_quality} → {new_quality}")
                self.current_quality = new_quality
                self.adjustment_history.append({
                    "timestamp": datetime.now().isoformat(),
                    "from": self.current_quality,
                    "to": new_quality,
                    "reason": recommendation.message
                })
    
    def _downgrade_quality(self) -> str:
        """Downgrade quality to reduce system load"""
        quality_order = ["ultra", "high", "medium", "low"]
        current_index = quality_order.index(self.current_quality)
        if current_index < len(quality_order) - 1:
            return quality_order[current_index + 1]
        return self.current_quality
    
    def get_optimal_settings(self) -> Dict[str, str]:
        """Get current optimal quality settings"""
        return self.quality_levels[self.current_quality].copy()
    
    def force_quality(self, quality: str) -> bool:
        """Force a specific quality level"""
        if quality in self.quality_levels:
            self.current_quality = quality
            logger.info(f"Quality manually set to: {quality}")
            return True
        return False

# Integration helper functions
def create_performance_system(config: Dict[str, Any]) -> tuple[PerformanceMonitor, AdaptiveQualityManager]:
    """Create and configure the performance monitoring system"""
    monitor = PerformanceMonitor(config)
    quality_manager = AdaptiveQualityManager(monitor)
    
    return monitor, quality_manager

def setup_performance_logging(log_dir: str) -> None:
    """Setup performance-specific logging"""
    os.makedirs(log_dir, exist_ok=True)
    
    # Create performance logger
    perf_logger = logging.getLogger('performance')
    perf_logger.setLevel(logging.INFO)
    
    # Performance log file
    perf_handler = logging.FileHandler(os.path.join(log_dir, 'performance.log'))
    perf_formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    perf_handler.setFormatter(perf_formatter)
    perf_logger.addHandler(perf_handler)
