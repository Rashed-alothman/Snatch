#!/usr/bin/env python3
"""
config_manager.py - Advanced Configuration Management System

Provides comprehensive configuration management including:
- Cache clearing functionality
- Interactive configuration editing
- Configuration display and validation
- Backup and restore capabilities
"""

import json
import logging
import os
import shutil
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Dict, Any, List, Optional, Union, Set
from dataclasses import dataclass, asdict
from enum import Enum
import threading
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.text import Text
from rich.prompt import Confirm, Prompt

from .cache import DownloadCache
from .defaults import CACHE_DIR
class ConfigCategory(Enum):
    """Configuration categories for better organization"""
    DOWNLOAD = "download"
    AUDIO = "audio"
    VIDEO = "video"
    NETWORK = "network"
    INTERFACE = "interface"
    ADVANCED = "advanced"


@dataclass
class ConfigOption:
    """Represents a single configuration option"""
    key: str
    display_name: str
    description: str
    value_type: str  # "string", "integer", "float", "boolean", "path", "choice"
    default_value: Any
    category: ConfigCategory
    choices: Optional[List[str]] = None
    min_value: Optional[Union[int, float]] = None
    max_value: Optional[Union[int, float]] = None
    validation_regex: Optional[str] = None
    requires_restart: bool = False


class AdvancedConfigManager:
    """Enhanced configuration manager with validation and user-friendly editing"""

    def __init__(self, config_file: str = "config.json"):
        self.config_file = config_file
        self.config: Dict[str, Any] = {}
        self.config_options = self._define_config_options()
        self.load_config()

    def _define_config_options(self) -> Dict[str, ConfigOption]:
        """Define all available configuration options with metadata"""
        options = {
            "download_dir": ConfigOption(
                "download_dir", "Download Directory",
                "Base directory for all downloads",
                "path", "downloads", ConfigCategory.DOWNLOAD
            ),
            "video_output": ConfigOption(
                "video_output", "Video Output Directory",
                "Directory for video downloads",
                "path", "downloads/video", ConfigCategory.VIDEO
            ),
            "audio_output": ConfigOption(
                "audio_output", "Audio Output Directory",
                "Directory for audio downloads",
                "path", "downloads/audio", ConfigCategory.AUDIO
            ),
            "max_concurrent": ConfigOption(
                "max_concurrent", "Max Concurrent Downloads",
                "Maximum number of simultaneous downloads",
                "integer", 3, ConfigCategory.DOWNLOAD, min_value=1, max_value=10
            ),
            "concurrent_downloads": ConfigOption(
                "concurrent_downloads", "Concurrent Fragment Downloads",
                "Number of concurrent fragment downloads per file",
                "integer", 16, ConfigCategory.DOWNLOAD, min_value=1, max_value=32
            ),
            "max_retries": ConfigOption(
                "max_retries", "Max Retries",
                "Maximum number of retry attempts for failed downloads",
                "integer", 3, ConfigCategory.DOWNLOAD, min_value=0, max_value=10
            ),
            "retry_delay": ConfigOption(
                "retry_delay", "Retry Delay (seconds)",
                "Delay between retry attempts",
                "integer", 5, ConfigCategory.DOWNLOAD, min_value=1, max_value=60
            ),
            "bandwidth_limit": ConfigOption(
                "bandwidth_limit", "Bandwidth Limit (MB/s)",
                "Download speed limit (0 = unlimited)",
                "integer", 0, ConfigCategory.NETWORK, min_value=0, max_value=1000
            ),
            "chunk_size": ConfigOption(
                "chunk_size", "Chunk Size (bytes)",
                "Size of download chunks",
                "integer", 1048576, ConfigCategory.NETWORK, min_value=1024, max_value=10485760
            ),
            "preferred_video_codec": ConfigOption(
                "preferred_video_codec", "Preferred Video Codec",
                "Preferred video codec for downloads",
                "choice", "h264", ConfigCategory.VIDEO,
                choices=["h264", "h265", "vp9", "av1", "any"]
            ),
            "preferred_video_quality": ConfigOption(
                "preferred_video_quality", "Preferred Video Quality",
                "Default video quality preference",
                "choice", "1080p", ConfigCategory.VIDEO,
                choices=["4320p", "2160p", "1440p", "1080p", "720p", "480p", "360p", "best", "worst"]
            ),
            "video_format_preference": ConfigOption(
                "video_format_preference", "Video Format Preference",
                "Preferred video container format",
                "choice", "mp4", ConfigCategory.VIDEO,
                choices=["mp4", "mkv", "webm", "avi", "any"]
            ),
            "preferred_audio_codec": ConfigOption(
                "preferred_audio_codec", "Preferred Audio Codec",
                "Preferred audio codec for downloads",
                "choice", "aac", ConfigCategory.AUDIO,
                choices=["aac", "mp3", "opus", "vorbis", "flac", "any"]
            ),
            "preferred_audio_quality": ConfigOption(
                "preferred_audio_quality", "Preferred Audio Quality",
                "Default audio quality preference",
                "choice", "192", ConfigCategory.AUDIO,
                choices=["320", "256", "192", "128", "96", "best", "worst"]
            ),
            "high_quality_audio": ConfigOption(
                "high_quality_audio", "High Quality Audio",
                "Always prefer highest quality audio",
                "boolean", True, ConfigCategory.AUDIO
            ),
            "theme": ConfigOption(
                "theme", "Interface Theme",
                "Color theme for the interface",
                "choice", "default", ConfigCategory.INTERFACE,
                choices=["default", "dark", "light", "cyberpunk", "matrix", "ocean"]
            ),
            "download_history": ConfigOption(
                "download_history", "Keep Download History",
                "Maintain history of completed downloads",
                "boolean", True, ConfigCategory.INTERFACE
            ),
            "auto_update_check": ConfigOption(
                "auto_update_check", "Auto Update Check",
                "Automatically check for updates",
                "boolean", True, ConfigCategory.INTERFACE
            ),
            "auto_organize": ConfigOption(
                "auto_organize", "Auto Organize Files",
                "Automatically organize downloaded files",
                "boolean", True, ConfigCategory.DOWNLOAD
            ),
            "organize": ConfigOption(
                "organize", "Enable File Organization",
                "Enable file organization features",
                "boolean", False, ConfigCategory.DOWNLOAD
            ),
            "ffmpeg_location": ConfigOption(
                "ffmpeg_location", "FFmpeg Location",
                "Path to FFmpeg installation",
                "path", "", ConfigCategory.ADVANCED, requires_restart=True
            ),
            "session_expiry": ConfigOption(
                "session_expiry", "Session Expiry (seconds)",
                "Time before download sessions expire",
                "integer", 604800, ConfigCategory.ADVANCED, min_value=3600, max_value=2592000
            ),
            "auto_save_interval": ConfigOption(
                "auto_save_interval", "Auto Save Interval (seconds)",
                "Interval for automatic session saves",
                "integer", 30, ConfigCategory.ADVANCED, min_value=10, max_value=300
            ),
            "exponential_backoff": ConfigOption(
                "exponential_backoff", "Exponential Backoff",
                "Use exponential backoff for retries",
                "boolean", True, ConfigCategory.ADVANCED
            ),
        }
        return options

    def load_config(self) -> None:
        """Load configuration from file"""
        try:
            if os.path.exists(self.config_file):
                with open(self.config_file, 'r') as f:
                    self.config = json.load(f)
            else:
                self.config = {}
            self._apply_defaults()
        except Exception as e:
            logging.error(f"Error loading config: {e}")
            self.config = {}
            self._apply_defaults()

    def _apply_defaults(self) -> None:
        """Apply default values for missing configuration options"""
        for key, option in self.config_options.items():
            if key not in self.config:
                self.config[key] = option.default_value

    def save_config(self) -> bool:
        """Save configuration to file"""
        try:
            if os.path.exists(self.config_file):
                backup_file = f"{self.config_file}.backup"
                with open(self.config_file, 'r') as src, open(backup_file, 'w') as dst:
                    dst.write(src.read())
            with open(self.config_file, 'w') as f:
                json.dump(self.config, f, indent=4)
            return True
        except Exception as e:
            logging.error(f"Error saving config: {e}")
            return False

    def get_value(self, key: str, default: Any = None) -> Any:
        """Get configuration value with optional default"""
        return self.config.get(key, default)

    def set_value(self, key: str, value: Any) -> bool:
        """Set configuration value with validation"""
        if key not in self.config_options:
            return False
        option = self.config_options[key]
        if not self._validate_value(option, value):
            return False
        self.config[key] = value
        return True

    def _validate_value(self, option: ConfigOption, value: Any) -> bool:
        """Validate a configuration value"""
        try:
            if option.value_type == "boolean":
                return isinstance(value, bool)
            elif option.value_type == "integer":
                if not isinstance(value, int):
                    return False
                if option.min_value is not None and value < option.min_value:
                    return False
                if option.max_value is not None and value > option.max_value:
                    return False
            elif option.value_type == "float":
                if not isinstance(value, (int, float)):
                    return False
                if option.min_value is not None and value < option.min_value:
                    return False
                if option.max_value is not None and value > option.max_value:
                    return False
            elif option.value_type == "string":
                return isinstance(value, str)
            elif option.value_type == "path":
                return isinstance(value, str)
            elif option.value_type == "choice":
                if option.choices and value not in option.choices:
                    return False
            return True
        except Exception:
            return False

    def get_options_by_category(self, category: ConfigCategory) -> Dict[str, ConfigOption]:
        """Get all configuration options for a specific category"""
        return {
            key: option for key, option in self.config_options.items()
            if option.category == category
        }

    def reset_to_defaults(self, category: Optional[ConfigCategory] = None) -> None:
        """Reset configuration to defaults (optionally for a specific category)"""
        if category:
            options = self.get_options_by_category(category)
            for key, option in options.items():
                self.config[key] = option.default_value
        else:
            for key, option in self.config_options.items():
                self.config[key] = option.default_value

    def export_config(self, file_path: str) -> bool:
        """Export configuration to a file"""
        try:
            with open(file_path, 'w') as f:
                json.dump(self.config, f, indent=4)
            return True
        except Exception as e:
            logging.error(f"Error exporting config: {e}")
            return False

    def import_config(self, file_path: str) -> bool:
        """Import configuration from a file"""
        try:
            with open(file_path, 'r') as f:
                imported_config = json.load(f)
            valid_config = {}
            for key, value in imported_config.items():
                if key in self.config_options:
                    option = self.config_options[key]
                    if self._validate_value(option, value):
                        valid_config[key] = value
            self.config.update(valid_config)
            return True
        except Exception as e:
            logging.error(f"Error importing config: {e}")
            return False

    def get_config_summary(self) -> Dict[str, Any]:
        """Get a summary of current configuration"""
        summary = {}
        for category in ConfigCategory:
            options = self.get_options_by_category(category)
            summary[category.value] = {
                key: {
                    "value": self.config.get(key),
                    "default": option.default_value,
                    "description": option.description
                }
                for key, option in options.items()
            }
        return summary

# Initialize console and logger
console = Console()
logger = logging.getLogger(__name__)

class CacheType(Enum):
    """Types of cache that can be cleared"""
    ALL = "all"
    METADATA = "metadata"
    DOWNLOADS = "downloads"
    SESSIONS = "sessions"
    THUMBNAILS = "thumbnails"
    TEMP = "temp"

@dataclass
class CacheStats:
    """Statistics about cache usage"""
    total_files: int = 0
    total_size_bytes: int = 0
    oldest_file_date: Optional[str] = None
    newest_file_date: Optional[str] = None
    cache_directories: List[str] = None

    def __post_init__(self):
        if self.cache_directories is None:
            self.cache_directories = []

class ConfigurationManager:
    """Enhanced configuration manager with advanced features"""
    
    def __init__(self, config_file: str = "config.json"):
        self.config_file = config_file
        self.backup_dir = Path("config_backups")
        self.backup_dir.mkdir(exist_ok=True)
        self.lock = threading.Lock()
        
        # Initialize advanced config manager
        self.advanced_config = AdvancedConfigManager(config_file)
        
        # Cache directories mapping
        self.cache_directories = {
            CacheType.ALL: [CACHE_DIR, "cache", "downloads/cache", "sessions", "thumbnails", "temp"],
            CacheType.METADATA: [CACHE_DIR, "cache"],
            CacheType.DOWNLOADS: ["downloads/cache", "temp"],
            CacheType.SESSIONS: ["sessions"],
            CacheType.THUMBNAILS: ["thumbnails"],
            CacheType.TEMP: ["temp", "downloads/temp"]
        }

    def clear_cache(self, cache_types: List[CacheType] = None, 
                   confirm: bool = True, dry_run: bool = False) -> Dict[str, Any]:
        """
        Clear cache data with safety checks and user feedback
        
        Args:
            cache_types: List of cache types to clear (default: [CacheType.ALL])
            confirm: Whether to ask for user confirmation
            dry_run: If True, only show what would be deleted without actually deleting
            
        Returns:
            Dictionary with clearing results and statistics
        """
        if cache_types is None:
            cache_types = [CacheType.ALL]
            
        results = {
            "success": False,
            "cache_types_processed": [],
            "files_deleted": 0,
            "bytes_freed": 0,
            "errors": [],
            "warnings": [],
            "dry_run": dry_run
        }
        
        try:
            # Get cache statistics before clearing
            cache_stats = self._get_cache_stats(cache_types)
            
            if cache_stats.total_files == 0:
                console.print("[yellow]No cache files found to clear.[/]")
                results["success"] = True
                return results
                
            # Show what will be cleared
            self._display_cache_info(cache_stats, cache_types)
            
            if dry_run:
                console.print("\n[cyan]Dry run mode - no files will actually be deleted.[/]")
                results["success"] = True
                results["files_deleted"] = cache_stats.total_files
                results["bytes_freed"] = cache_stats.total_size_bytes
                return results
                
            # Ask for confirmation if required
            if confirm and not self._confirm_cache_clear(cache_stats):
                console.print("[yellow]Cache clearing cancelled by user.[/]")
                return results
                
            # Perform the actual clearing
            with self.lock:
                for cache_type in cache_types:
                    try:
                        type_result = self._clear_cache_type(cache_type)
                        results["cache_types_processed"].append(cache_type.value)
                        results["files_deleted"] += type_result["files_deleted"]
                        results["bytes_freed"] += type_result["bytes_freed"]
                        
                        if type_result["errors"]:
                            results["errors"].extend(type_result["errors"])
                            
                    except Exception as e:
                        error_msg = f"Error clearing {cache_type.value} cache: {str(e)}"
                        results["errors"].append(error_msg)
                        logger.error(error_msg)
                        
            results["success"] = len(results["errors"]) == 0
            
            # Display results
            self._display_clear_results(results)
            
        except Exception as e:
            error_msg = f"Unexpected error during cache clearing: {str(e)}"
            results["errors"].append(error_msg)
            logger.error(error_msg)
            console.print(f"[red]Error: {error_msg}[/]")
            
        return results

    def _get_cache_stats(self, cache_types: List[CacheType]) -> CacheStats:
        """Get statistics about cache files"""
        stats = CacheStats()
        all_dirs = set()
        
        for cache_type in cache_types:
            for cache_dir in self.cache_directories.get(cache_type, []):
                all_dirs.add(cache_dir)
                
        oldest_time = None
        newest_time = None
        
        for cache_dir in all_dirs:
            if os.path.exists(cache_dir):
                stats.cache_directories.append(cache_dir)
                
                for root, dirs, files in os.walk(cache_dir):
                    for file in files:
                        file_path = os.path.join(root, file)
                        try:
                            file_stat = os.stat(file_path)
                            stats.total_files += 1
                            stats.total_size_bytes += file_stat.st_size
                            
                            mtime = file_stat.st_mtime
                            if oldest_time is None or mtime < oldest_time:
                                oldest_time = mtime
                            if newest_time is None or mtime > newest_time:
                                newest_time = mtime
                                
                        except OSError:
                            continue
                            
        if oldest_time:
            stats.oldest_file_date = time.strftime("%Y-%m-%d %H:%M:%S", 
                                                 time.localtime(oldest_time))
        if newest_time:
            stats.newest_file_date = time.strftime("%Y-%m-%d %H:%M:%S", 
                                                  time.localtime(newest_time))
            
        return stats

    def _display_cache_info(self, cache_stats: CacheStats, cache_types: List[CacheType]):
        """Display cache information before clearing"""
        table = Table(title="Cache Information")
        table.add_column("Property", style="cyan")
        table.add_column("Value", style="green")
        
        table.add_row("Cache Types", ", ".join([ct.value for ct in cache_types]))
        table.add_row("Total Files", str(cache_stats.total_files))
        table.add_row("Total Size", self._format_bytes(cache_stats.total_size_bytes))
        table.add_row("Directories", str(len(cache_stats.cache_directories)))
        
        if cache_stats.oldest_file_date:
            table.add_row("Oldest File", cache_stats.oldest_file_date)
        if cache_stats.newest_file_date:
            table.add_row("Newest File", cache_stats.newest_file_date)
            
        console.print(table)

    def _confirm_cache_clear(self, cache_stats: CacheStats) -> bool:
        """Ask user to confirm cache clearing"""
        size_str = self._format_bytes(cache_stats.total_size_bytes)
        
        console.print(f"\n[yellow]⚠️  Warning: This will delete {cache_stats.total_files} files ({size_str})![/]")
        console.print("[yellow]This action cannot be undone.[/]")
        
        return Confirm.ask("Are you sure you want to continue?", default=False)

    def _clear_cache_type(self, cache_type: CacheType) -> Dict[str, Any]:
        """Clear a specific type of cache"""
        result = {
            "files_deleted": 0,
            "bytes_freed": 0,
            "errors": []
        }
        
        # Special handling for memory cache
        if cache_type in [CacheType.ALL, CacheType.METADATA]:
            try:
                cache = DownloadCache()
                cache.clear()
                console.print("[green]✓ Memory cache cleared[/]")
            except Exception as e:
                result["errors"].append(f"Error clearing memory cache: {str(e)}")
        
        # Clear file-based caches
        cache_dirs = self.cache_directories.get(cache_type, [])
        
        for cache_dir in cache_dirs:
            if os.path.exists(cache_dir):
                try:
                    dir_result = self._clear_directory(cache_dir)
                    result["files_deleted"] += dir_result["files_deleted"]
                    result["bytes_freed"] += dir_result["bytes_freed"]
                    result["errors"].extend(dir_result["errors"])
                    
                except Exception as e:
                    error_msg = f"Error clearing directory {cache_dir}: {str(e)}"
                    result["errors"].append(error_msg)
                    
        return result

    def _clear_directory(self, directory: str) -> Dict[str, Any]:
        """Clear all files in a directory"""
        result = {
            "files_deleted": 0,
            "bytes_freed": 0,
            "errors": []
        }
        
        try:
            for root, dirs, files in os.walk(directory, topdown=False):
                # Remove files
                for file in files:
                    file_path = os.path.join(root, file)
                    try:
                        file_size = os.path.getsize(file_path)
                        os.remove(file_path)
                        result["files_deleted"] += 1
                        result["bytes_freed"] += file_size
                    except OSError as e:
                        result["errors"].append(f"Failed to delete {file_path}: {str(e)}")
                
                # Remove empty directories (but keep the root cache directory)
                for dir_name in dirs:
                    dir_path = os.path.join(root, dir_name)
                    try:
                        if dir_path != directory:  # Don't remove the root cache directory
                            os.rmdir(dir_path)
                    except OSError:
                        pass  # Directory not empty or other error - that's fine
                        
        except Exception as e:
            result["errors"].append(f"Error walking directory {directory}: {str(e)}")
            
        return result

    def _display_clear_results(self, results: Dict[str, Any]):
        """Display the results of cache clearing"""
        if results["success"]:
            console.print(f"\n[green]✅ Cache cleared successfully![/]")
            console.print(f"[green]Files deleted: {results['files_deleted']}[/]")
            console.print(f"[green]Space freed: {self._format_bytes(results['bytes_freed'])}[/]")
        else:
            console.print(f"\n[yellow]⚠️  Cache clearing completed with {len(results['errors'])} errors[/]")
            
        if results["errors"]:
            console.print("\n[red]Errors:[/]")
            for error in results["errors"]:
                console.print(f"[red]  • {error}[/]")

    def _format_bytes(self, bytes_count: int) -> str:
        """Format bytes in human readable format"""
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if bytes_count < 1024.0:
                return f"{bytes_count:.1f} {unit}"
            bytes_count /= 1024.0
        return f"{bytes_count:.1f} PB"    
    def edit_config(self, editor: Optional[str] = None, create_backup: bool = True) -> Dict[str, Any]:
        """
        Open configuration file in editor with validation and backup
        
        Args:
            editor: Preferred editor command (auto-detect if None)
            create_backup: Whether to create a backup before editing
            
        Returns:
            Dictionary with success status and details
        """
        try:
            # Create backup if requested
            if create_backup:
                backup_path = self._create_config_backup()
                console.print(f"[cyan]Backup created: {backup_path}[/]")
            
            # Detect editor if not specified
            if editor is None:
                editor = self._detect_editor()
                
            if not editor:
                return {
                    "success": False,
                    "error": "No suitable editor found",
                    "message": "No suitable editor found. Please specify an editor."
                }
                
            # Add helpful comments to config file
            commented_config = self._add_config_comments()
            
            # Create temporary file with comments
            with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as tmp:
                tmp.write(commented_config)
                temp_path = tmp.name
            
            try:
                console.print(f"[cyan]Opening configuration in {editor}...[/]")
                
                # Open editor
                result = subprocess.run([editor, temp_path], check=True)
                
                # Read back the edited configuration
                with open(temp_path, 'r') as f:
                    edited_content = f.read()
                
                # Validate and save the configuration
                if self._validate_and_save_config(edited_content):
                    console.print("[green]✅ Configuration saved successfully![/]")
                    return {
                        "success": True,
                        "message": "Configuration edited and saved successfully"
                    }
                else:
                    console.print("[red]❌ Configuration validation failed![/]")
                    if create_backup:
                        self._restore_from_backup(backup_path)
                    return {
                        "success": False,
                        "error": "Configuration validation failed",
                        "message": "Configuration validation failed, restored from backup"
                    }
                    
            finally:
                # Clean up temporary file
                try:
                    os.unlink(temp_path)
                except OSError:
                    pass
                    
        except subprocess.CalledProcessError:
            console.print("[red]Editor process was cancelled or failed.[/]")
            return {
                "success": False,
                "error": "Editor process failed",
                "message": "Editor process was cancelled or failed"
            }
        except Exception as e:
            console.print(f"[red]Error editing configuration: {str(e)}[/]")
            logger.error(f"Config edit error: {e}")
            return {
                "success": False,
                "error": str(e),
                "message": f"Error editing configuration: {str(e)}"
            }

    def _create_config_backup(self) -> str:
        """Create a timestamped backup of the current configuration"""
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        backup_filename = f"config_backup_{timestamp}.json"
        backup_path = self.backup_dir / backup_filename
        
        shutil.copy2(self.config_file, backup_path)
        
        # Keep only the last 10 backups
        self._cleanup_old_backups()
        
        return str(backup_path)

    def _cleanup_old_backups(self, keep_count: int = 10):
        """Clean up old configuration backups"""
        try:
            backup_files = list(self.backup_dir.glob("config_backup_*.json"))
            backup_files.sort(key=lambda x: x.stat().st_mtime, reverse=True)
            
            for backup_file in backup_files[keep_count:]:
                backup_file.unlink()
                
        except Exception as e:
            logger.warning(f"Error cleaning up old backups: {e}")

    def _detect_editor(self) -> Optional[str]:
        """Detect available text editor"""
        editors = [
            # Windows editors
            "notepad++.exe", "notepad.exe", "code.exe", "vim.exe",
            # Unix editors  
            "code", "vim", "nano", "gedit", "kate", "emacs"
        ]
        
        for editor in editors:
            if shutil.which(editor):
                return editor
                
        return None

    def _add_config_comments(self) -> str:
        """Add helpful comments to configuration file"""
        # Load current config
        try:
            with open(self.config_file, 'r') as f:
                config = json.load(f)
        except Exception:
            config = {}
            
        # Create commented version
        commented_lines = [
            "//",
            "// Snatch Configuration File",
            "// This file contains all configuration settings for Snatch.",
            "// Edit the values below to customize your download experience.",
            "//",
            "// IMPORTANT: Remove these comment lines (starting with //) before saving!",
            "// JSON format does not support comments, so they must be removed.",
            "//"
        ]
        
        # Add section comments for each category
        category_comments = {
            "download": "Download Settings - Control how downloads are handled",
            "video": "Video Settings - Video quality and format preferences", 
            "audio": "Audio Settings - Audio quality and format preferences",
            "network": "Network Settings - Bandwidth and connection options",
            "interface": "Interface Settings - UI themes and display options",
            "advanced": "Advanced Settings - Technical configuration options"
        }
        
        # Group config by categories for better organization
        categorized_config = {}
        for key, value in config.items():
            option = self.advanced_config.config_options.get(key)
            if option:
                category = option.category.value.lower()
                if category not in categorized_config:
                    categorized_config[category] = {}
                categorized_config[category][key] = value
            else:
                # Uncategorized items go in 'other'
                if 'other' not in categorized_config:
                    categorized_config['other'] = {}
                categorized_config['other'][key] = value
        
        # Build the commented JSON
        result_lines = commented_lines + ["{"]
        
        category_keys = list(categorized_config.keys())
        for i, category in enumerate(category_keys):
            if category in category_comments:
                result_lines.append(f'  // {category_comments[category]}')
            
            category_items = list(categorized_config[category].items())
            for j, (key, value) in enumerate(category_items):
                # Add individual option comment if available
                option = self.advanced_config.config_options.get(key)
                if option:
                    result_lines.append(f'  // {option.description}')
                
                # Add the actual config line
                comma = "," if j < len(category_items) - 1 or i < len(category_keys) - 1 else ""
                result_lines.append(f'  "{key}": {json.dumps(value)}{comma}')
                
            if i < len(category_keys) - 1:
                result_lines.append('  //')  # Spacer between categories
                
        result_lines.append("}")
        
        return "\n".join(result_lines)

    def _validate_and_save_config(self, config_content: str) -> bool:
        """Validate and save edited configuration"""
        try:
            # Remove comment lines
            lines = config_content.split('\n')
            json_lines = [line for line in lines if not line.strip().startswith('//')]
            clean_content = '\n'.join(json_lines)
            
            # Parse JSON
            new_config = json.loads(clean_content)
            
            # Validate configuration using advanced config manager
            validation_errors = []
            for key, value in new_config.items():
                if key in self.advanced_config.config_options:
                    option = self.advanced_config.config_options[key]
                    if not self.advanced_config._validate_value(option, value):
                        validation_errors.append(f"Invalid value for '{key}': {value}")
                        
            if validation_errors:
                console.print("[red]Validation errors:[/]")
                for error in validation_errors:
                    console.print(f"[red]  • {error}[/]")
                return False
                
            # Save the validated configuration
            with open(self.config_file, 'w') as f:
                json.dump(new_config, f, indent=4)
                
            return True
            
        except json.JSONDecodeError as e:
            console.print(f"[red]JSON syntax error: {str(e)}[/]")
            return False
        except Exception as e:
            console.print(f"[red]Error validating configuration: {str(e)}[/]")
            return False

    def _restore_from_backup(self, backup_path: str):
        """Restore configuration from backup"""
        try:
            shutil.copy2(backup_path, self.config_file)
            console.print(f"[yellow]Configuration restored from backup: {backup_path}[/]")
        except Exception as e:
            console.print(f"[red]Error restoring from backup: {str(e)}[/]")

    def show_config(self, format_type: str = "table", 
                   filter_category: Optional[str] = None,
                   filter_non_default: bool = False,
                   output_file: Optional[str] = None) -> bool:
        """
        Display current configuration in various formats
        
        Args:
            format_type: Output format ("table", "json", "yaml")
            filter_category: Only show settings from this category
            filter_non_default: Only show non-default values
            output_file: Save output to file instead of displaying
            
        Returns:
            True if successful, False otherwise
        """
        try:
            config = self.advanced_config.config
            
            # Apply filters
            filtered_config = self._filter_config(config, filter_category, filter_non_default)
            
            if format_type == "table":
                output = self._format_config_table(filtered_config)
            elif format_type == "json":
                output = json.dumps(filtered_config, indent=4)
            elif format_type == "yaml":
                try:
                    import yaml
                    output = yaml.dump(filtered_config, default_flow_style=False, indent=2)
                except ImportError:
                    console.print("[red]PyYAML is required for YAML format. Install with: pip install pyyaml[/]")
                    return False
            else:
                console.print(f"[red]Unknown format: {format_type}[/]")
                return False
                
            # Output to file or console
            if output_file:
                with open(output_file, 'w') as f:
                    if format_type == "table":
                        # For table format, create a simplified text version for file output
                        f.write(self._format_config_text(filtered_config))
                    else:
                        f.write(output)
                console.print(f"[green]Configuration saved to: {output_file}[/]")
            else:
                if format_type == "table":
                    console.print(output)
                else:
                    console.print(output)
                    
            return True
            
        except Exception as e:
            console.print(f"[red]Error displaying configuration: {str(e)}[/]")
            logger.error(f"Config display error: {e}")
            return False

    def _filter_config(self, config: Dict[str, Any], 
                      filter_category: Optional[str] = None,
                      filter_non_default: bool = False) -> Dict[str, Any]:
        """Apply filters to configuration"""
        filtered = {}
        
        for key, value in config.items():
            # Check category filter
            if filter_category:
                option = self.advanced_config.config_options.get(key)
                if option and option.category.value.lower() != filter_category.lower():
                    continue
                    
            # Check non-default filter
            if filter_non_default:
                option = self.advanced_config.config_options.get(key)
                if option and value == option.default_value:
                    continue
                    
            filtered[key] = value
            
        return filtered

    def _format_config_table(self, config: Dict[str, Any]) -> Table:
        """Format configuration as a Rich table"""
        # Group by categories
        categorized = {}
        for key, value in config.items():
            option = self.advanced_config.config_options.get(key)
            category = option.category.value if option else "Other"
            
            if category not in categorized:
                categorized[category] = []
                
            is_default = option and value == option.default_value if option else False
            description = option.description if option else "No description available"
            
            categorized[category].append({
                "key": key,
                "value": value,
                "description": description,
                "is_default": is_default
            })
        
        # Create table
        table = Table(title="Snatch Configuration")
        table.add_column("Category", style="bold cyan")
        table.add_column("Setting", style="yellow")
        table.add_column("Value", style="green")
        table.add_column("Description", style="blue")
        table.add_column("Status", style="magenta")
        
        for category, items in categorized.items():
            for i, item in enumerate(items):
                category_name = category if i == 0 else ""
                
                # Highlight non-default values
                value_style = "green" if item["is_default"] else "bold green"
                status = "Default" if item["is_default"] else "Modified"
                status_style = "dim" if item["is_default"] else "bold yellow"
                
                table.add_row(
                    category_name,
                    item["key"],
                    Text(str(item["value"]), style=value_style),
                    item["description"][:50] + "..." if len(item["description"]) > 50 else item["description"],
                    Text(status, style=status_style)
                )
                
        return table

    def _format_config_text(self, config: Dict[str, Any]) -> str:
        """Format configuration as plain text"""
        lines = ["Snatch Configuration", "=" * 50, ""]
        
        # Group by categories
        categorized = {}
        for key, value in config.items():
            option = self.advanced_config.config_options.get(key)
            category = option.category.value if option else "Other"
            
            if category not in categorized:
                categorized[category] = []
                
            categorized[category].append((key, value, option))
        
        for category, items in categorized.items():
            lines.append(f"{category}:")
            lines.append("-" * len(category))
            
            for key, value, option in items:
                description = option.description if option else "No description"
                is_default = option and value == option.default_value if option else False
                status = " (default)" if is_default else " (modified)"
                
                lines.append(f"  {key}: {value}{status}")
                lines.append(f"    {description}")
                lines.append("")
                
        return "\n".join(lines)

    def get_cache_info(self, cache_types: List[CacheType] = None) -> Dict[str, Any]:
        """Get detailed cache information without clearing"""
        if cache_types is None:
            cache_types = [CacheType.ALL]
            
        cache_stats = self._get_cache_stats(cache_types)
        
        return {
            "total_files": cache_stats.total_files,
            "total_size_bytes": cache_stats.total_size_bytes,
            "total_size_formatted": self._format_bytes(cache_stats.total_size_bytes),
            "cache_directories": cache_stats.cache_directories,
            "oldest_file": cache_stats.oldest_file_date,
            "newest_file": cache_stats.newest_file_date,
            "cache_types": [ct.value for ct in cache_types]
        }

    def list_backups(self) -> List[Dict[str, Any]]:
        """List all available configuration backups"""
        backups = []
        
        try:
            backup_files = list(self.backup_dir.glob("config_backup_*.json"))
            backup_files.sort(key=lambda x: x.stat().st_mtime, reverse=True)
            
            for backup_file in backup_files:
                stat = backup_file.stat()
                backups.append({
                    "filename": backup_file.name,
                    "path": str(backup_file),
                    "created": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(stat.st_mtime)),
                    "size": stat.st_size,
                    "size_formatted": self._format_bytes(stat.st_size)
                })
                
        except Exception as e:
            logger.error(f"Error listing backups: {e}")
            
        return backups

    def restore_config_backup(self, backup_filename: str) -> bool:
        """Restore configuration from a specific backup"""
        try:
            backup_path = self.backup_dir / backup_filename
            
            if not backup_path.exists():
                console.print(f"[red]Backup file not found: {backup_filename}[/]")
                return False
                
            # Create a backup of current config before restoring
            current_backup = self._create_config_backup()
            console.print(f"[cyan]Current configuration backed up to: {current_backup}[/]")
            
            # Restore from backup
            shutil.copy2(backup_path, self.config_file)
            console.print(f"[green]✅ Configuration restored from: {backup_filename}[/]")
            
            return True
            
        except Exception as e:
            console.print(f"[red]Error restoring backup: {str(e)}[/]")
            logger.error(f"Backup restore error: {e}")
            return False

    def create_backup(self) -> Dict[str, Any]:
        """Create a new configuration backup and return result"""
        try:
            backup_path = self._create_config_backup()
            return {
                "success": True,
                "backup_file": backup_path,
                "message": f"Backup created successfully: {backup_path}"
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "message": f"Failed to create backup: {str(e)}"
            }

    def restore_backup(self, backup_name: str) -> Dict[str, Any]:
        """Restore configuration from backup and return result"""
        try:
            success = self.restore_config_backup(backup_name)
            if success:
                return {
                    "success": True,
                    "message": f"Configuration restored from: {backup_name}"
                }
            else:
                return {
                    "success": False,
                    "error": "Restore operation failed",
                    "message": f"Failed to restore from backup: {backup_name}"
                }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "message": f"Error restoring backup: {str(e)}"
            }

    def list_backups_simple(self) -> List[str]:
        """Return a simple list of backup filenames"""
        try:
            backups = self.list_backups()
            return [backup["filename"] for backup in backups]
        except Exception:
            return []

    def reset_config(self, category: Optional[str] = None) -> Dict[str, Any]:
        """Reset configuration to defaults"""
        try:
            # Create backup before reset
            backup_path = self._create_config_backup()
            
            if category:
                # Reset specific category
                result = self._reset_category(category)
            else:
                # Reset all configuration
                result = self._reset_all_config()
            
            if result["success"]:
                return {
                    "success": True,
                    "backup_created": backup_path,
                    "message": f"Configuration reset completed. Backup: {backup_path}"
                }
            else:
                return result
                
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "message": f"Error resetting configuration: {str(e)}"
            }

    def _reset_category(self, category: str) -> Dict[str, Any]:
        """Reset a specific configuration category to defaults"""
        try:
            # Get current config
            current_config = self.advanced_config.config.copy()
            
            # Find options in the specified category
            reset_count = 0
            for key, option in self.advanced_config.config_options.items():
                if option.category.value.lower() == category.lower():
                    current_config[key] = option.default_value
                    reset_count += 1
            
            if reset_count == 0:
                return {
                    "success": False,
                    "error": f"No options found in category: {category}",
                    "message": f"Category '{category}' not found or has no options"
                }
            
            # Save the updated configuration
            with open(self.config_file, 'w') as f:
                json.dump(current_config, f, indent=4)
            
            # Reload the advanced config manager
            self.advanced_config = AdvancedConfigManager(self.config_file)
            
            return {
                "success": True,
                "reset_count": reset_count,
                "message": f"Reset {reset_count} options in category '{category}'"
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "message": f"Error resetting category: {str(e)}"
            }

    def _reset_all_config(self) -> Dict[str, Any]:
        """Reset all configuration to defaults"""
        try:
            # Create default configuration
            default_config = {}
            for key, option in self.advanced_config.config_options.items():
                default_config[key] = option.default_value
            
            # Save the default configuration
            with open(self.config_file, 'w') as f:
                json.dump(default_config, f, indent=4)
            
            # Reload the advanced config manager
            self.advanced_config = AdvancedConfigManager(self.config_file)
            
            return {
                "success": True,
                "reset_count": len(default_config),
                "message": f"Reset all {len(default_config)} configuration options to defaults"
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "message": f"Error resetting all configuration: {str(e)}"
            }
