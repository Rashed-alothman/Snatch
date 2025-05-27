#!/usr/bin/env python3
"""
customization_manager.py - Comprehensive Customization System

Provides a robust framework for personalizing Snatch including:
- Theme customization (colors, styles, formatting)
- Performance settings (download speeds, connection limits, timeout values)
- Behavior preferences (default actions, confirmation prompts)
- Output formatting options (verbose levels, progress display styles)
- Interface preferences (compact mode, detailed mode)
"""

import json
import yaml
import toml
import logging
import os
import shutil
import threading
from pathlib import Path
from typing import Dict, Any, List, Optional, Union, Tuple
from dataclasses import dataclass, asdict, field
from enum import Enum
from rich.console import Console
from rich.style import Style
from rich.theme import Theme
from rich.table import Table
from rich.panel import Panel
from rich.prompt import Confirm, Prompt, IntPrompt, FloatPrompt
import time

# Initialize console and logger
console = Console()
logger = logging.getLogger(__name__)

class ConfigFormat(Enum):
    """Supported configuration file formats"""
    JSON = "json"
    YAML = "yaml"
    TOML = "toml"

class ThemePreset(Enum):
    """Predefined theme presets"""
    DEFAULT = "default"
    DARK = "dark"
    LIGHT = "light"
    HIGH_CONTRAST = "high_contrast"
    CYBERPUNK = "cyberpunk"
    MINIMAL = "minimal"
    OCEAN = "ocean"
    FOREST = "forest"

class InterfaceMode(Enum):
    """Interface display modes"""
    COMPACT = "compact"
    DETAILED = "detailed"
    VERBOSE = "verbose"
    MINIMAL = "minimal"

class ProgressStyle(Enum):
    """Progress bar display styles"""
    DEFAULT = "default"
    MINIMAL = "minimal"
    DETAILED = "detailed"
    PERCENTAGE_ONLY = "percentage_only"
    BAR_ONLY = "bar_only"

class NotificationLevel(Enum):
    """Notification verbosity levels"""
    SILENT = 0
    ERROR = 1
    WARNING = 2
    INFO = 3
    DEBUG = 4
    VERBOSE = 5

@dataclass
class ThemeColors:
    """Theme color configuration"""
    primary: str = "#00d7ff"
    secondary: str = "#ff6b6b"
    success: str = "#51cf66"
    warning: str = "#ffd43b"
    error: str = "#ff6b6b"
    info: str = "#74c0fc"
    text: str = "#ffffff"
    background: str = "#000000"
    accent: str = "#845ef7"
    muted: str = "#868e96"

@dataclass
class PerformanceSettings:
    """Performance-related configuration"""
    # Download settings
    max_concurrent_downloads: int = 3
    concurrent_fragment_downloads: int = 16
    chunk_size: int = 1048576  # 1MB
    buffer_size: int = 8192    # 8KB
    
    # Network settings
    connection_timeout: float = 30.0
    read_timeout: float = 60.0
    max_retries: int = 3
    retry_delay: float = 1.0
    exponential_backoff: bool = True
    
    # Bandwidth limits (bytes per second, 0 = unlimited)
    global_bandwidth_limit: int = 0
    per_download_bandwidth_limit: int = 0
    
    # Memory management
    max_memory_usage_mb: int = 512
    cache_size_mb: int = 100
    temp_cleanup_interval: int = 3600  # seconds
    
    # Background operations
    background_thread_priority: str = "normal"  # low, normal, high
    background_throttle_delay: float = 0.1

@dataclass
class BehaviorPreferences:
    """User behavior and interaction preferences"""
    # Confirmation prompts
    confirm_file_overwrite: bool = True
    confirm_large_downloads: bool = True
    confirm_cache_clear: bool = True
    confirm_config_reset: bool = True
    large_download_threshold_mb: int = 100
    
    # Default actions
    auto_organize_downloads: bool = True
    auto_update_metadata: bool = True
    auto_generate_thumbnails: bool = True
    auto_extract_subtitles: bool = False
    resume_incomplete_downloads: bool = True
    
    # Error handling
    continue_on_error: bool = False
    log_all_errors: bool = True
    show_detailed_errors: bool = False
    
    # Session management
    auto_save_sessions: bool = True
    session_auto_save_interval: int = 30  # seconds
    keep_session_history: bool = True
    max_session_history: int = 50

@dataclass
class OutputFormatting:
    """Output formatting and display preferences"""
    # Progress display
    progress_style: ProgressStyle = ProgressStyle.DEFAULT
    show_speed: bool = True
    show_eta: bool = True
    show_file_size: bool = True
    show_percentage: bool = True
    
    # Logging and verbosity
    console_log_level: NotificationLevel = NotificationLevel.INFO
    file_log_level: NotificationLevel = NotificationLevel.DEBUG
    show_timestamps: bool = False
    use_colors: bool = True
    
    # Table formatting
    table_style: str = "rounded"  # ascii, rounded, heavy, double
    table_max_width: Optional[int] = None
    table_show_header: bool = True
    table_show_lines: bool = True
    
    # Interface elements
    show_banners: bool = True
    show_tips: bool = True
    compact_mode: bool = False
    use_unicode: bool = True

@dataclass
class InterfacePreferences:
    """Interface layout and interaction preferences"""
    # Display mode
    interface_mode: InterfaceMode = InterfaceMode.DETAILED
    
    # Interactive mode settings
    enable_keyboard_shortcuts: bool = True
    auto_complete: bool = True
    history_size: int = 100
    
    # Visual elements
    show_progress_bars: bool = True
    show_status_bar: bool = True
    show_menu_bar: bool = True
    animate_progress: bool = True
    
    # Layout preferences
    sidebar_width: int = 30
    content_width: Optional[int] = None
    max_display_items: int = 50
    
    # Accessibility
    high_contrast_mode: bool = False
    large_text_mode: bool = False
    screen_reader_mode: bool = False

@dataclass
class KeyboardShortcuts:
    """Customizable keyboard shortcuts"""
    # Navigation
    quit_app: str = "q"
    help: str = "h"
    refresh: str = "r"
    
    # Download operations
    start_download: str = "enter"
    pause_download: str = "p"
    cancel_download: str = "c"
    
    # View operations
    toggle_details: str = "d"
    toggle_logs: str = "l"
    clear_screen: str = "ctrl+l"
    
    # File operations
    open_file: str = "o"
    open_folder: str = "f"
    copy_url: str = "ctrl+c"

@dataclass
class CommandAliases:
    """User-defined command aliases"""
    aliases: Dict[str, str] = field(default_factory=dict)
    
    def __post_init__(self):
        if not self.aliases:
            # Default aliases
            self.aliases = {
                "dl": "download",
                "ls": "list-sites",
                "q": "quit",
                "h": "help",
                "cfg": "config",
                "cc": "clear-cache",
                "v": "version",
                "info": "system-info"
            }

@dataclass
class CustomizationConfig:
    """Complete customization configuration"""
    # Metadata
    config_version: str = "1.0.0"
    last_modified: Optional[str] = None
    user_profile: str = "default"
    
    # Theme and appearance
    theme_preset: ThemePreset = ThemePreset.DEFAULT
    custom_theme_colors: Optional[ThemeColors] = None
    
    # Performance settings
    performance: PerformanceSettings = field(default_factory=PerformanceSettings)
    
    # Behavior preferences
    behavior: BehaviorPreferences = field(default_factory=BehaviorPreferences)
    
    # Output formatting
    output: OutputFormatting = field(default_factory=OutputFormatting)
    
    # Interface preferences
    interface: InterfacePreferences = field(default_factory=InterfacePreferences)
    
    # Keyboard shortcuts
    shortcuts: KeyboardShortcuts = field(default_factory=KeyboardShortcuts)
    
    # Command aliases
    aliases: CommandAliases = field(default_factory=CommandAliases)

class CustomizationManager:
    """Comprehensive customization management system"""
    
    def __init__(self, config_file: str = "customization.yaml"):
        self.config_file = Path(config_file)
        self.backup_dir = Path("customization_backups")
        self.profiles_dir = Path("profiles")
        self.themes_dir = Path("themes")
        
        # Create directories
        for directory in [self.backup_dir, self.profiles_dir, self.themes_dir]:
            directory.mkdir(exist_ok=True)
        
        self.lock = threading.Lock()
        self._config: Optional[CustomizationConfig] = None
        self._theme_cache: Dict[str, Theme] = {}
        
        # Predefined themes
        self._predefined_themes = self._load_predefined_themes()
        
        # Initialize with default config if file doesn't exist
        if not self.config_file.exists():
            self._create_default_config()

    def _load_predefined_themes(self) -> Dict[ThemePreset, Dict[str, str]]:
        """Load predefined theme configurations"""
        return {
            ThemePreset.DEFAULT: {
                "info": "cyan",
                "warning": "yellow",
                "error": "red",
                "success": "green",
                "primary": "blue",
                "secondary": "magenta",
                "text": "white",
                "muted": "dim white"
            },
            ThemePreset.DARK: {
                "info": "bright_cyan",
                "warning": "bright_yellow",
                "error": "bright_red",
                "success": "bright_green",
                "primary": "bright_blue",
                "secondary": "bright_magenta",
                "text": "bright_white",
                "muted": "dim bright_white"
            },
            ThemePreset.LIGHT: {
                "info": "blue",
                "warning": "dark_orange",
                "error": "dark_red",
                "success": "dark_green",
                "primary": "navy_blue",
                "secondary": "purple",
                "text": "black",
                "muted": "dim black"
            },
            ThemePreset.HIGH_CONTRAST: {
                "info": "bright_white on blue",
                "warning": "black on bright_yellow",
                "error": "bright_white on red",
                "success": "black on bright_green",
                "primary": "bright_white on black",
                "secondary": "black on bright_white",
                "text": "bright_white",
                "muted": "bright_white"
            },
            ThemePreset.CYBERPUNK: {
                "info": "#00ff00",
                "warning": "#ffff00",
                "error": "#ff0040",
                "success": "#00ff80",
                "primary": "#00d7ff",
                "secondary": "#ff40ff",
                "text": "#00ff00",
                "muted": "#008000"
            },
            ThemePreset.MINIMAL: {
                "info": "white",
                "warning": "white",
                "error": "white",
                "success": "white",
                "primary": "white",
                "secondary": "white",
                "text": "white",
                "muted": "dim white"
            },
            ThemePreset.OCEAN: {
                "info": "#0077be",
                "warning": "#ffa500",
                "error": "#dc143c",
                "success": "#20b2aa",
                "primary": "#4169e1",
                "secondary": "#9370db",
                "text": "#f0f8ff",
                "muted": "#708090"
            },
            ThemePreset.FOREST: {
                "info": "#228b22",
                "warning": "#daa520",
                "error": "#8b0000",
                "success": "#32cd32",
                "primary": "#006400",
                "secondary": "#8b4513",
                "text": "#f5fffa",
                "muted": "#556b2f"
            }
        }

    def _create_default_config(self):
        """Create default customization configuration"""
        default_config = CustomizationConfig()
        self._save_config(default_config)
        logger.info(f"Created default customization config at {self.config_file}")

    def load_config(self) -> CustomizationConfig:
        """Load customization configuration from file"""
        with self.lock:
            if self._config is not None:
                return self._config
                
            try:
                if self.config_file.suffix == '.yaml' or self.config_file.suffix == '.yml':
                    with open(self.config_file, 'r') as f:
                        data = yaml.safe_load(f)
                elif self.config_file.suffix == '.toml':
                    with open(self.config_file, 'r') as f:
                        data = toml.load(f)
                else:  # Default to JSON
                    with open(self.config_file, 'r') as f:
                        data = json.load(f)
                
                # Convert data to CustomizationConfig
                self._config = self._dict_to_config(data)
                return self._config
                
            except Exception as e:
                logger.error(f"Error loading customization config: {e}")
                # Return default config on error
                self._config = CustomizationConfig()
                return self._config    
    def _save_config(self, config: CustomizationConfig):
        """Save customization configuration to file"""
        try:
            # Update timestamp
            config.last_modified = time.strftime("%Y-%m-%d %H:%M:%S")
            
            # Convert to dict with enum handling
            data = self._config_to_dict(config)
            
            # Save based on file extension
            if self.config_file.suffix == '.yaml' or self.config_file.suffix == '.yml':
                with open(self.config_file, 'w') as f:
                    yaml.dump(data, f, default_flow_style=False, indent=2)
            elif self.config_file.suffix == '.toml':
                with open(self.config_file, 'w') as f:
                    toml.dump(data, f)
            else:  # Default to JSON
                with open(self.config_file, 'w') as f:
                    json.dump(data, f, indent=2)
                    
            self._config = config
            logger.info(f"Customization config saved to {self.config_file}")
            
        except Exception as e:
            logger.error(f"Error saving customization config: {e}")
            raise

    def _dict_to_config(self, data: Dict[str, Any]) -> CustomizationConfig:
        """Convert dictionary to CustomizationConfig"""
        try:
            # Handle nested dataclasses
            config = CustomizationConfig()
            
            # Basic fields
            config.config_version = data.get('config_version', '1.0.0')
            config.last_modified = data.get('last_modified')
            config.user_profile = data.get('user_profile', 'default')
            
            # Theme settings
            theme_preset = data.get('theme_preset', 'default')
            if isinstance(theme_preset, str):
                config.theme_preset = ThemePreset(theme_preset)
            
            # Custom theme colors
            if 'custom_theme_colors' in data and data['custom_theme_colors']:
                config.custom_theme_colors = ThemeColors(**data['custom_theme_colors'])            # Performance settings
            if 'performance' in data and data['performance'] is not None:
                performance_data = data['performance'].copy()
                # Filter out None values to use defaults
                performance_data = {k: v for k, v in performance_data.items() if v is not None}
                config.performance = PerformanceSettings(**performance_data)
            
            # Behavior preferences
            if 'behavior' in data and data['behavior'] is not None:
                behavior_data = data['behavior'].copy()
                # Filter out None values to use defaults
                behavior_data = {k: v for k, v in behavior_data.items() if v is not None}
                config.behavior = BehaviorPreferences(**behavior_data)# Output formatting
            if 'output' in data and data['output'] is not None:
                output_data = data['output'].copy()  # Make a copy to avoid modifying original
                # Handle enum fields
                if 'progress_style' in output_data and output_data['progress_style'] is not None:
                    output_data['progress_style'] = ProgressStyle(output_data['progress_style'])
                if 'console_log_level' in output_data and output_data['console_log_level'] is not None:
                    output_data['console_log_level'] = NotificationLevel(output_data['console_log_level'])
                if 'file_log_level' in output_data and output_data['file_log_level'] is not None:
                    output_data['file_log_level'] = NotificationLevel(output_data['file_log_level'])
                # Filter out None values to use defaults
                output_data = {k: v for k, v in output_data.items() if v is not None}
                config.output = OutputFormatting(**output_data)# Interface preferences
            if 'interface' in data and data['interface'] is not None:
                interface_data = data['interface'].copy()  # Make a copy to avoid modifying original
                # Handle enum fields
                if 'interface_mode' in interface_data and interface_data['interface_mode'] is not None:
                    interface_data['interface_mode'] = InterfaceMode(interface_data['interface_mode'])
                # Filter out None values to use defaults
                interface_data = {k: v for k, v in interface_data.items() if v is not None}
                config.interface = InterfacePreferences(**interface_data)            # Keyboard shortcuts
            if 'shortcuts' in data and data['shortcuts'] is not None:
                shortcuts_data = data['shortcuts'].copy()
                # Filter out None values to use defaults
                shortcuts_data = {k: v for k, v in shortcuts_data.items() if v is not None}
                config.shortcuts = KeyboardShortcuts(**shortcuts_data)
              # Command aliases
            if 'aliases' in data and data['aliases'] is not None:
                aliases_data = data['aliases'].copy()
                # Filter out None values to use defaults
                aliases_data = {k: v for k, v in aliases_data.items() if v is not None}
                # CommandAliases expects an 'aliases' field containing the dict
                config.aliases = CommandAliases(aliases=aliases_data)
            
            return config
            
        except Exception as e:
            logger.error(f"Error converting dict to config: {e}")
            return CustomizationConfig()  # Return default on error

    def _config_to_dict(self, config: CustomizationConfig) -> Dict[str, Any]:
        """Convert CustomizationConfig to dictionary with proper enum handling"""
        data = asdict(config)
        
        # Convert enums to their string values
        if 'theme_preset' in data:
            data['theme_preset'] = data['theme_preset'].value if hasattr(data['theme_preset'], 'value') else data['theme_preset']
        
        # Handle output formatting enums
        if 'output' in data and data['output']:
            output = data['output']
            if 'progress_style' in output:
                output['progress_style'] = output['progress_style'].value if hasattr(output['progress_style'], 'value') else output['progress_style']
            if 'console_log_level' in output:
                output['console_log_level'] = output['console_log_level'].value if hasattr(output['console_log_level'], 'value') else output['console_log_level']
            if 'file_log_level' in output:
                output['file_log_level'] = output['file_log_level'].value if hasattr(output['file_log_level'], 'value') else output['file_log_level']
        
        # Handle interface mode enum
        if 'interface' in data and data['interface']:
            interface = data['interface']
            if 'interface_mode' in interface:
                interface['interface_mode'] = interface['interface_mode'].value if hasattr(interface['interface_mode'], 'value') else interface['interface_mode']
        
        return data
    
    def get_theme(self) -> Theme:
        """Get the current Rich theme based on configuration"""
        config = self.load_config()
        
        # Check cache first
        cache_key = f"{config.theme_preset.value}_{id(config.custom_theme_colors)}"
        if cache_key in self._theme_cache:
            return self._theme_cache[cache_key]
        
        # Build theme
        if config.custom_theme_colors:
            # Use custom colors
            theme_dict = {
                "info": config.custom_theme_colors.info,
                "warning": config.custom_theme_colors.warning,
                "error": config.custom_theme_colors.error,
                "success": config.custom_theme_colors.success,
                "primary": config.custom_theme_colors.primary,
                "secondary": config.custom_theme_colors.secondary,
                "text": config.custom_theme_colors.text,
                "muted": config.custom_theme_colors.muted
            }
        else:
            # Use predefined theme
            theme_dict = self._predefined_themes.get(config.theme_preset, 
                                                   self._predefined_themes[ThemePreset.DEFAULT])
        
        theme = Theme(theme_dict)
        self._theme_cache[cache_key] = theme
        return theme

    def update_theme(self, theme_preset: Optional[ThemePreset] = None, 
                    custom_colors: Optional[ThemeColors] = None) -> bool:
        """Update theme configuration"""
        try:
            config = self.load_config()
            
            if theme_preset:
                config.theme_preset = theme_preset
                config.custom_theme_colors = None  # Clear custom colors when using preset
            
            if custom_colors:
                config.custom_theme_colors = custom_colors
                config.theme_preset = ThemePreset.DEFAULT  # Reset to default preset
            
            self._save_config(config)
            self._theme_cache.clear()  # Clear theme cache
            return True
            
        except Exception as e:
            logger.error(f"Error updating theme: {e}")
            return False

    def update_performance(self, **kwargs) -> bool:
        """Update performance settings"""
        try:
            config = self.load_config()
            
            # Update performance settings
            for key, value in kwargs.items():
                if hasattr(config.performance, key):
                    setattr(config.performance, key, value)
                else:
                    logger.warning(f"Unknown performance setting: {key}")
            
            self._save_config(config)
            return True
            
        except Exception as e:
            logger.error(f"Error updating performance settings: {e}")
            return False

    def update_behavior(self, **kwargs) -> bool:
        """Update behavior preferences"""
        try:
            config = self.load_config()
            
            # Update behavior settings
            for key, value in kwargs.items():
                if hasattr(config.behavior, key):
                    setattr(config.behavior, key, value)
                else:
                    logger.warning(f"Unknown behavior setting: {key}")
            
            self._save_config(config)
            return True
            
        except Exception as e:
            logger.error(f"Error updating behavior preferences: {e}")
            return False

    def update_output_formatting(self, **kwargs) -> bool:
        """Update output formatting preferences"""
        try:
            config = self.load_config()
            
            # Handle enum conversions
            if 'progress_style' in kwargs:
                kwargs['progress_style'] = ProgressStyle(kwargs['progress_style'])
            if 'console_log_level' in kwargs:
                kwargs['console_log_level'] = NotificationLevel(kwargs['console_log_level'])
            if 'file_log_level' in kwargs:
                kwargs['file_log_level'] = NotificationLevel(kwargs['file_log_level'])
            
            # Update output settings
            for key, value in kwargs.items():
                if hasattr(config.output, key):
                    setattr(config.output, key, value)
                else:
                    logger.warning(f"Unknown output setting: {key}")
            
            self._save_config(config)
            return True
            
        except Exception as e:
            logger.error(f"Error updating output formatting: {e}")
            return False

    def update_interface(self, **kwargs) -> bool:
        """Update interface preferences"""
        try:
            config = self.load_config()
            
            # Handle enum conversions
            if 'interface_mode' in kwargs:
                kwargs['interface_mode'] = InterfaceMode(kwargs['interface_mode'])
            
            # Update interface settings
            for key, value in kwargs.items():
                if hasattr(config.interface, key):
                    setattr(config.interface, key, value)
                else:
                    logger.warning(f"Unknown interface setting: {key}")
            
            self._save_config(config)
            return True
            
        except Exception as e:
            logger.error(f"Error updating interface preferences: {e}")
            return False

    def add_alias(self, alias: str, command: str) -> bool:
        """Add or update a command alias"""
        try:
            config = self.load_config()
            config.aliases.aliases[alias] = command
            self._save_config(config)
            return True
            
        except Exception as e:
            logger.error(f"Error adding alias: {e}")
            return False

    def remove_alias(self, alias: str) -> bool:
        """Remove a command alias"""
        try:
            config = self.load_config()
            if alias in config.aliases.aliases:
                del config.aliases.aliases[alias]
                self._save_config(config)
                return True
            return False
            
        except Exception as e:
            logger.error(f"Error removing alias: {e}")
            return False

    def get_aliases(self) -> Dict[str, str]:
        """Get all command aliases"""
        config = self.load_config()
        return config.aliases.aliases.copy()

    def create_profile(self, profile_name: str, config: Optional[CustomizationConfig] = None) -> bool:
        """Create a new configuration profile"""
        try:
            if config is None:
                config = self.load_config()
            
            profile_file = self.profiles_dir / f"{profile_name}.yaml"
            
            # Save profile
            with open(profile_file, 'w') as f:
                yaml.dump(asdict(config), f, default_flow_style=False, indent=2)
            
            logger.info(f"Created profile: {profile_name}")
            return True
            
        except Exception as e:
            logger.error(f"Error creating profile: {e}")
            return False

    def load_profile(self, profile_name: str) -> bool:
        """Load a configuration profile"""
        try:
            profile_file = self.profiles_dir / f"{profile_name}.yaml"
            
            if not profile_file.exists():
                logger.error(f"Profile not found: {profile_name}")
                return False
            
            with open(profile_file, 'r') as f:
                data = yaml.safe_load(f)
            
            config = self._dict_to_config(data)
            config.user_profile = profile_name
            self._save_config(config)
            
            logger.info(f"Loaded profile: {profile_name}")
            return True
            
        except Exception as e:
            logger.error(f"Error loading profile: {e}")
            return False

    def list_profiles(self) -> List[str]:
        """List available configuration profiles"""
        try:
            profiles = []
            for profile_file in self.profiles_dir.glob("*.yaml"):
                profiles.append(profile_file.stem)
            return sorted(profiles)
            
        except Exception as e:
            logger.error(f"Error listing profiles: {e}")
            return []

    def validate_config(self, config: Optional[CustomizationConfig] = None) -> Tuple[bool, List[str]]:
        """Validate configuration for errors and inconsistencies"""
        if config is None:
            config = self.load_config()
        
        errors = []
        
        try:
            # Validate performance settings
            perf = config.performance
            if perf.max_concurrent_downloads < 1:
                errors.append("max_concurrent_downloads must be >= 1")
            if perf.chunk_size < 1024:
                errors.append("chunk_size must be >= 1024 bytes")
            if perf.connection_timeout <= 0:
                errors.append("connection_timeout must be > 0")
            if perf.max_retries < 0:
                errors.append("max_retries must be >= 0")
            
            # Validate behavior settings
            behavior = config.behavior
            if behavior.large_download_threshold_mb < 0:
                errors.append("large_download_threshold_mb must be >= 0")
            if behavior.session_auto_save_interval < 1:
                errors.append("session_auto_save_interval must be >= 1")
            
            # Validate interface settings
            interface = config.interface
            if interface.sidebar_width < 10:
                errors.append("sidebar_width must be >= 10")
            if interface.max_display_items < 1:
                errors.append("max_display_items must be >= 1")
            
            return len(errors) == 0, errors
            
        except Exception as e:
            errors.append(f"Validation error: {e}")
            return False, errors

    def export_config(self, output_file: str, format_type: ConfigFormat = ConfigFormat.YAML) -> bool:
        """Export current configuration to file"""
        try:
            config = self.load_config()
            data = asdict(config)
            
            output_path = Path(output_file)
            
            if format_type == ConfigFormat.YAML:
                with open(output_path, 'w') as f:
                    yaml.dump(data, f, default_flow_style=False, indent=2)
            elif format_type == ConfigFormat.TOML:
                with open(output_path, 'w') as f:
                    toml.dump(data, f)
            else:  # JSON
                with open(output_path, 'w') as f:
                    json.dump(data, f, indent=2)
            
            logger.info(f"Configuration exported to {output_path}")
            return True
            
        except Exception as e:
            logger.error(f"Error exporting configuration: {e}")
            return False

    def import_config(self, input_file: str) -> bool:
        """Import configuration from file"""
        try:
            input_path = Path(input_file)
            
            if not input_path.exists():
                logger.error(f"Import file not found: {input_file}")
                return False
            
            # Determine format by extension
            if input_path.suffix in ['.yaml', '.yml']:
                with open(input_path, 'r') as f:
                    data = yaml.safe_load(f)
            elif input_path.suffix == '.toml':
                with open(input_path, 'r') as f:
                    data = toml.load(f)
            else:  # JSON
                with open(input_path, 'r') as f:
                    data = json.load(f)
            
            # Convert and validate
            config = self._dict_to_config(data)
            is_valid, errors = self.validate_config(config)
            
            if not is_valid:
                logger.error(f"Invalid configuration: {errors}")
                return False
            
            # Create backup before importing
            self.create_backup()
            
            # Save imported config
            self._save_config(config)
            
            logger.info(f"Configuration imported from {input_path}")
            return True
            
        except Exception as e:
            logger.error(f"Error importing configuration: {e}")
            return False

    def create_backup(self) -> str:
        """Create a backup of current configuration"""
        try:
            timestamp = time.strftime("%Y%m%d_%H%M%S")
            backup_file = self.backup_dir / f"customization_backup_{timestamp}.yaml"
            
            config = self.load_config()
            with open(backup_file, 'w') as f:
                yaml.dump(asdict(config), f, default_flow_style=False, indent=2)
            
            logger.info(f"Created backup: {backup_file}")
            return str(backup_file)
            
        except Exception as e:
            logger.error(f"Error creating backup: {e}")
            return ""

    def restore_backup(self, backup_file: str) -> bool:
        """Restore configuration from backup"""
        try:
            backup_path = Path(backup_file)
            
            if not backup_path.exists():
                # Try looking in backup directory
                backup_path = self.backup_dir / backup_file
                if not backup_path.exists():
                    logger.error(f"Backup file not found: {backup_file}")
                    return False
            
            return self.import_config(str(backup_path))
            
        except Exception as e:
            logger.error(f"Error restoring backup: {e}")
            return False

    def reset_to_defaults(self) -> bool:
        """Reset configuration to default values"""
        try:
            # Create backup first
            self.create_backup()
            
            # Create new default config
            default_config = CustomizationConfig()
            self._save_config(default_config)
            
            # Clear caches
            self._theme_cache.clear()
            
            logger.info("Configuration reset to defaults")
            return True
            
        except Exception as e:
            logger.error(f"Error resetting to defaults: {e}")
            return False

    def get_config_summary(self) -> Dict[str, Any]:
        """Get a summary of current configuration"""
        config = self.load_config()
        
        return {
            "profile": config.user_profile,
            "theme": config.theme_preset.value,
            "performance": {
                "concurrent_downloads": config.performance.max_concurrent_downloads,
                "bandwidth_limit": config.performance.global_bandwidth_limit,
                "memory_limit": config.performance.max_memory_usage_mb
            },
            "interface": {
                "mode": config.interface.interface_mode.value,
                "shortcuts_enabled": config.interface.enable_keyboard_shortcuts,
                "progress_style": config.output.progress_style.value
            },
            "behavior": {
                "auto_organize": config.behavior.auto_organize_downloads,
                "confirm_overwrites": config.behavior.confirm_file_overwrite,
                "log_level": config.output.console_log_level.value
            },
            "aliases_count": len(config.aliases.aliases),
            "last_modified": config.last_modified
        }
