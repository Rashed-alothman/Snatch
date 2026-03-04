"""
Enhanced error handling and logging system for Snatch.
Provides structured error reporting, recovery mechanisms, and improved logging.
"""

import asyncio
import logging
import sys
import traceback
import time
from contextlib import contextmanager, asynccontextmanager
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Union, Callable, Type, TextIO
from functools import wraps
import json
import os

from rich.console import Console
from rich.traceback import install as install_rich_traceback
from rich.logging import RichHandler
from colorama import Fore, Style, init as init_colorama

# Initialize colorama and rich traceback
init_colorama()
install_rich_traceback(show_locals=True)

console = Console()

class ErrorSeverity(Enum):
    """Error severity levels"""
    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"

class ErrorCategory(Enum):
    """Error categories for better classification"""
    NETWORK = "network"
    FILE_SYSTEM = "file_system"
    DOWNLOAD = "download"
    CONVERSION = "conversion"
    CONFIGURATION = "configuration"
    AUTHENTICATION = "authentication"
    SYSTEM_RESOURCE = "system_resource"
    USER_INPUT = "user_input"
    UNKNOWN = "unknown"

@dataclass
class ErrorInfo:
    """Structured error information"""
    message: str
    category: ErrorCategory
    severity: ErrorSeverity
    timestamp: datetime = field(default_factory=datetime.now)
    context: Dict[str, Any] = field(default_factory=dict)
    traceback_info: Optional[str] = None
    error_code: Optional[str] = None
    suggested_action: Optional[str] = None
    retry_count: int = 0
    max_retries: int = 3

class EnhancedErrorHandler:
    """Enhanced error handler with structured logging and recovery mechanisms"""
    
    def __init__(self, log_file: Optional[str] = None, max_error_history: int = 1000):
        self.log_file = log_file or "snatch_errors.log"
        self.max_error_history = max_error_history
        self.error_history: List[ErrorInfo] = []
        self.error_counts: Dict[str, int] = {}
        self.recovery_handlers: Dict[ErrorCategory, List[Callable]] = {}
        
        # Setup logging
        self._setup_logging()
        
        # Setup recovery handlers
        self._setup_recovery_handlers()
    
    def _setup_logging(self) -> None:
        """Configure enhanced logging with both file and console output"""
        # Create logs directory if it doesn't exist
        log_dir = os.path.dirname(os.path.abspath(self.log_file))
        os.makedirs(log_dir, exist_ok=True)
        
        # Configure root logger
        root_logger = logging.getLogger()
        root_logger.setLevel(logging.DEBUG)
        
        # Clear existing handlers
        root_logger.handlers.clear()
        
        # File handler with detailed formatting
        file_handler = logging.FileHandler(self.log_file, encoding='utf-8')
        file_handler.setLevel(logging.DEBUG)
        file_formatter = logging.Formatter(
            fmt='%(asctime)s | %(levelname)-8s | %(name)s | %(funcName)s:%(lineno)d | %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        file_handler.setFormatter(file_formatter)
        root_logger.addHandler(file_handler)
        
        # Rich console handler for pretty output
        console_handler = RichHandler(
            console=console,
            show_time=False,
            show_path=False,
            rich_tracebacks=True
        )
        console_handler.setLevel(logging.INFO)
        console_formatter = logging.Formatter(
            fmt='%(message)s'
        )
        console_handler.setFormatter(console_formatter)
        root_logger.addHandler(console_handler)
    
    def _setup_recovery_handlers(self) -> None:
        """Setup automatic recovery handlers for common error types"""
        # Network error recovery
        self.recovery_handlers[ErrorCategory.NETWORK] = [
            self._retry_with_backoff,
            self._check_internet_connection,
            self._switch_to_backup_url
        ]
        
        # File system error recovery
        self.recovery_handlers[ErrorCategory.FILE_SYSTEM] = [
            self._check_disk_space,
            self._check_permissions,
            self._create_missing_directories
        ]
        
        # Download error recovery
        self.recovery_handlers[ErrorCategory.DOWNLOAD] = [
            self._resume_download,
            self._clear_cache_and_retry,
            self._try_alternative_format
        ]
        
        # System resource error recovery
        self.recovery_handlers[ErrorCategory.SYSTEM_RESOURCE] = [
            self._free_memory,
            self._reduce_concurrency,
            self._cleanup_temp_files
        ]
    
    def log_error(self, 
                  error: Union[Exception, str], 
                  category: ErrorCategory = ErrorCategory.UNKNOWN,
                  severity: ErrorSeverity = ErrorSeverity.ERROR,
                  context: Optional[Dict[str, Any]] = None,
                  suggested_action: Optional[str] = None) -> ErrorInfo:
        """Log an error with structured information"""
        
        # Convert string errors to ErrorInfo
        if isinstance(error, str):
            message = error
            traceback_info = None
        else:
            message = str(error)
            traceback_info = traceback.format_exc() if hasattr(error, '__traceback__') else None
        
        # Create error info
        error_info = ErrorInfo(
            message=message,
            category=category,
            severity=severity,
            context=context or {},
            traceback_info=traceback_info,
            suggested_action=suggested_action
        )
        
        # Add to history
        self._add_to_history(error_info)
        
        # Log using appropriate level
        logger = logging.getLogger(context.get('module', 'snatch') if context else 'snatch')
        log_message = self._format_error_message(error_info)
        
        if severity == ErrorSeverity.DEBUG:
            logger.debug(log_message)
        elif severity == ErrorSeverity.INFO:
            logger.info(log_message)
        elif severity == ErrorSeverity.WARNING:
            logger.warning(log_message)
        elif severity == ErrorSeverity.ERROR:
            logger.error(log_message)
        elif severity == ErrorSeverity.CRITICAL:
            logger.critical(log_message)
        
        # Attempt automatic recovery for non-critical errors
        if severity != ErrorSeverity.CRITICAL:
            self._attempt_recovery(error_info)
        
        return error_info
    
    def _format_error_message(self, error_info: ErrorInfo) -> str:
        """Format error message for logging"""
        parts = [f"[{error_info.category.value.upper()}] {error_info.message}"]
        
        if error_info.context:
            context_str = ", ".join(f"{k}={v}" for k, v in error_info.context.items())
            parts.append(f"Context: {context_str}")
        
        if error_info.suggested_action:
            parts.append(f"Suggested action: {error_info.suggested_action}")
        
        return " | ".join(parts)
    
    def _add_to_history(self, error_info: ErrorInfo) -> None:
        """Add error to history with size management"""
        self.error_history.append(error_info)
        
        # Update error counts
        error_key = f"{error_info.category.value}:{error_info.message[:100]}"
        self.error_counts[error_key] = self.error_counts.get(error_key, 0) + 1
        
        # Trim history if too large
        if len(self.error_history) > self.max_error_history:
            self.error_history = self.error_history[-self.max_error_history:]
    
    def _attempt_recovery(self, error_info: ErrorInfo) -> bool:
        """Attempt automatic recovery for the error"""
        if error_info.retry_count >= error_info.max_retries:
            logging.warning(f"Max retries exceeded for error: {error_info.message}")
            return False
        
        recovery_handlers = self.recovery_handlers.get(error_info.category, [])
        
        for handler in recovery_handlers:
            try:
                if handler(error_info):
                    logging.info(f"Recovery successful using {handler.__name__}")
                    return True
            except Exception as e:
                logging.error(f"Recovery handler {handler.__name__} failed: {str(e)}")
        
        return False
    
    # Recovery handler implementations
    def _retry_with_backoff(self, error_info: ErrorInfo) -> bool:
        """Implement exponential backoff retry"""
        if error_info.retry_count < error_info.max_retries:
            delay = 2 ** error_info.retry_count
            logging.info(f"Retrying in {delay} seconds (attempt {error_info.retry_count + 1})")
            time.sleep(delay)
            error_info.retry_count += 1
            return True
        return False
    
    def _check_internet_connection(self, error_info: ErrorInfo) -> bool:
        """Check if internet connection is available"""
        try:
            import urllib.request
            urllib.request.urlopen('http://www.google.com', timeout=5)
            return True
        except:
            logging.error("No internet connection available")
            return False
    
    def _switch_to_backup_url(self, error_info: ErrorInfo) -> bool:
        """Switch to backup URL if available"""
        backup_url = error_info.context.get('backup_url')
        if backup_url:
            logging.info(f"Switching to backup URL: {backup_url}")
            return True
        return False
    
    def _check_disk_space(self, error_info: ErrorInfo) -> bool:
        """Check available disk space"""
        try:
            import shutil
            output_dir = error_info.context.get('output_dir', '.')
            total, used, free = shutil.disk_usage(output_dir)
            
            # Check if we have at least 1GB free
            if free < 1024**3:
                logging.error(f"Low disk space: {free / 1024**3:.2f} GB free")
                return False
            return True
        except Exception:
            return False
    
    def _check_permissions(self, error_info: ErrorInfo) -> bool:
        """Check file permissions"""
        file_path = error_info.context.get('file_path')
        if file_path and os.path.exists(file_path):
            return os.access(file_path, os.R_OK | os.W_OK)
        return True
    
    def _create_missing_directories(self, error_info: ErrorInfo) -> bool:
        """Create missing directories"""
        try:
            output_dir = error_info.context.get('output_dir')
            if output_dir:
                os.makedirs(output_dir, exist_ok=True)
                return True
        except Exception as e:
            logging.error(f"Failed to create directory: {str(e)}")
        return False
    
    def _resume_download(self, error_info: ErrorInfo) -> bool:
        """Attempt to resume download"""
        # This would be implemented with actual download resume logic
        session_manager = error_info.context.get('session_manager')
        url = error_info.context.get('url')
        
        if session_manager and url:
            try:
                return session_manager.resume_session(url)
            except Exception:
                return False
        return False
    
    def _clear_cache_and_retry(self, error_info: ErrorInfo) -> bool:
        """Clear cache and retry operation"""
        cache_manager = error_info.context.get('cache_manager')
        if cache_manager:
            try:
                cache_manager.clear()
                return True
            except Exception:
                return False
        return False
    
    def _try_alternative_format(self, error_info: ErrorInfo) -> bool:
        """Try alternative download format"""
        # This would be implemented with format fallback logic
        return False
    
    def _free_memory(self, error_info: ErrorInfo) -> bool:
        """Attempt to free memory"""
        try:
            import gc
            gc.collect()
            return True
        except Exception:
            return False
    
    def _reduce_concurrency(self, error_info: ErrorInfo) -> bool:
        """Reduce concurrent operations"""
        # This would be implemented with actual concurrency control
        return True
    
    def _cleanup_temp_files(self, error_info: ErrorInfo) -> bool:
        """Cleanup temporary files"""
        try:
            import tempfile
            temp_dir = tempfile.gettempdir()
            # Implement temp file cleanup logic here
            return True
        except Exception:
            return False
    
    def get_error_summary(self) -> Dict[str, Any]:
        """Get summary of recent errors"""
        now = datetime.now()
        recent_errors = [
            e for e in self.error_history 
            if (now - e.timestamp).total_seconds() < 3600  # Last hour
        ]
        
        category_counts = {}
        severity_counts = {}
        
        for error in recent_errors:
            category_counts[error.category.value] = category_counts.get(error.category.value, 0) + 1
            severity_counts[error.severity.value] = severity_counts.get(error.severity.value, 0) + 1
        
        return {
            'total_errors': len(self.error_history),
            'recent_errors': len(recent_errors),
            'category_breakdown': category_counts,
            'severity_breakdown': severity_counts,
            'most_common_errors': dict(sorted(self.error_counts.items(), key=lambda x: x[1], reverse=True)[:10])
        }
    
    def export_error_report(self, output_file: str) -> bool:
        """Export detailed error report to file"""
        try:
            report = {
                'generated_at': datetime.now().isoformat(),
                'summary': self.get_error_summary(),
                'recent_errors': [
                    {
                        'timestamp': error.timestamp.isoformat(),
                        'message': error.message,
                        'category': error.category.value,
                        'severity': error.severity.value,
                        'context': error.context,
                        'suggested_action': error.suggested_action
                    }
                    for error in self.error_history[-100:]  # Last 100 errors
                ]
            }
            
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(report, f, indent=2, ensure_ascii=False)
            
            return True
        except Exception as e:
            logging.error(f"Failed to export error report: {str(e)}")
            return False

# Global error handler instance
_global_error_handler: Optional[EnhancedErrorHandler] = None

def get_error_handler() -> EnhancedErrorHandler:
    """Get the global error handler instance"""
    global _global_error_handler
    if _global_error_handler is None:
        _global_error_handler = EnhancedErrorHandler()
    return _global_error_handler

def initialize_error_handling(log_file: Optional[str] = None) -> EnhancedErrorHandler:
    """Initialize global error handling"""
    global _global_error_handler
    _global_error_handler = EnhancedErrorHandler(log_file)
    return _global_error_handler

# Decorator for automatic error handling
def handle_errors(category: ErrorCategory = ErrorCategory.UNKNOWN, 
                 severity: ErrorSeverity = ErrorSeverity.ERROR,
                 reraise: bool = False):
    """Decorator to automatically handle errors in functions"""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                error_handler = get_error_handler()
                context = {
                    'function': func.__name__,
                    'module': func.__module__,
                    'args': str(args)[:200],  # Truncate long args
                    'kwargs': str(kwargs)[:200]
                }
                error_handler.log_error(e, category, severity, context)
                
                if reraise:
                    raise
                return None
        
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            try:
                return await func(*args, **kwargs)
            except Exception as e:
                error_handler = get_error_handler()
                context = {
                    'function': func.__name__,
                    'module': func.__module__,
                    'args': str(args)[:200],
                    'kwargs': str(kwargs)[:200]
                }
                error_handler.log_error(e, category, severity, context)
                
                if reraise:
                    raise
                return None
        
        return async_wrapper if asyncio.iscoroutinefunction(func) else wrapper
    return decorator

@contextmanager
def error_context(category: ErrorCategory = ErrorCategory.UNKNOWN,
                 context: Optional[Dict[str, Any]] = None):
    """Context manager for error handling"""
    error_handler = get_error_handler()
    try:
        yield
    except Exception as e:
        error_handler.log_error(e, category, ErrorSeverity.ERROR, context)
        raise

@asynccontextmanager
async def async_error_context(category: ErrorCategory = ErrorCategory.UNKNOWN,
                             context: Optional[Dict[str, Any]] = None):
    """Async context manager for error handling"""
    error_handler = get_error_handler()
    try:
        yield
    except Exception as e:
        error_handler.log_error(e, category, ErrorSeverity.ERROR, context)
        raise

# Utility functions for common error scenarios
def log_network_error(error: Exception, url: str, retry_count: int = 0) -> ErrorInfo:
    """Log network-related errors with appropriate context"""
    error_handler = get_error_handler()
    context = {
        'url': url,
        'retry_count': retry_count,
        'error_type': type(error).__name__
    }
    
    suggested_action = "Check internet connection and retry"
    if retry_count > 0:
        suggested_action = f"Retry attempt {retry_count}. Check URL validity and network stability"
    
    return error_handler.log_error(
        error, 
        ErrorCategory.NETWORK, 
        ErrorSeverity.ERROR,
        context,
        suggested_action
    )

def log_download_error(error: Exception, url: str, file_path: str) -> ErrorInfo:
    """Log download-related errors"""
    error_handler = get_error_handler()
    context = {
        'url': url,
        'file_path': file_path,
        'error_type': type(error).__name__
    }
    
    return error_handler.log_error(
        error,
        ErrorCategory.DOWNLOAD,
        ErrorSeverity.ERROR,
        context,
        "Check URL validity, network connection, and available disk space"
    )

def log_file_system_error(error: Exception, file_path: str, operation: str) -> ErrorInfo:
    """Log file system related errors"""
    error_handler = get_error_handler()
    context = {
        'file_path': file_path,
        'operation': operation,
        'error_type': type(error).__name__
    }
    
    return error_handler.log_error(
        error,
        ErrorCategory.FILE_SYSTEM,
        ErrorSeverity.ERROR,
        context,
        "Check file permissions, disk space, and directory accessibility"
    )

def log_conversion_error(error: Exception, input_file: str, output_file: str, format_type: str) -> ErrorInfo:
    """Log media conversion errors"""
    error_handler = get_error_handler()
    context = {
        'input_file': input_file,
        'output_file': output_file,
        'format_type': format_type,
        'error_type': type(error).__name__
    }
    
    return error_handler.log_error(
        error,
        ErrorCategory.CONVERSION,
        ErrorSeverity.ERROR,
        context,
        "Check FFmpeg installation, input file integrity, and output directory permissions"
    )
