#!/usr/bin/env python3
"""
advanced_config.py - Enhanced Configuration Management

Provides advanced configuration management with validation, 
user-friendly editing, and configuration profiles.
"""

import json
import os
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional, Union
from dataclasses import dataclass, asdict
from enum import Enum

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
            # Download Settings
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
            
            # Network Settings
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
            
            # Video Settings
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
            
            # Audio Settings
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
            
            # Interface Settings
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
            
            # Organization Settings
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
            
            # Advanced Settings
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
                logging.info(f"Configuration loaded from {self.config_file}")
            else:
                logging.info("No config file found, using defaults")
                self.config = {}
            
            # Ensure all required keys exist with defaults
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
            # Create backup of existing config
            if os.path.exists(self.config_file):
                backup_file = f"{self.config_file}.backup"
                with open(self.config_file, 'r') as src, open(backup_file, 'w') as dst:
                    dst.write(src.read())
            
            # Save new config
            with open(self.config_file, 'w') as f:
                json.dump(self.config, f, indent=4)
            
            logging.info(f"Configuration saved to {self.config_file}")
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
            logging.warning(f"Unknown configuration key: {key}")
            return False
        
        option = self.config_options[key]
        
        # Validate the value
        if not self._validate_value(option, value):
            return False
        
        self.config[key] = value
        return True
    
    def _validate_value(self, option: ConfigOption, value: Any) -> bool:
        """Validate a configuration value"""
        try:
            # Type validation
            if option.value_type == "boolean":
                if not isinstance(value, bool):
                    return False
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
                if not isinstance(value, str):
                    return False
            elif option.value_type == "path":
                if not isinstance(value, str):
                    return False
                # Additional path validation could be added here
            elif option.value_type == "choice":
                if option.choices and value not in option.choices:
                    return False
            
            return True
            
        except Exception as e:
            logging.error(f"Error validating value for {option.key}: {e}")
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
            
            # Validate imported values
            valid_config = {}
            for key, value in imported_config.items():
                if key in self.config_options:
                    option = self.config_options[key]
                    if self._validate_value(option, value):
                        valid_config[key] = value
                    else:
                        logging.warning(f"Invalid value for {key}: {value}")
            
            # Update config with valid values
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
