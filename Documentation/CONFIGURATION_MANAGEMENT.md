# Configuration Management Guide

## Overview

Snatch now includes powerful configuration management features that provide enhanced control over the application settings, cache management, and backup functionality.

## New Commands

### 1. Cache Management (`--clear-cache`)

Clear cached data with safety checks and user feedback.

#### Usage
```bash
# Clear all cache with confirmation
python -m modules.cli --clear-cache

# Clear specific cache types
python -m modules.cli --clear-cache --type=metadata
python -m modules.cli --clear-cache --type=downloads
python -m modules.cli --clear-cache --type=sessions
python -m modules.cli --clear-cache --type=thumbnails
python -m modules.cli --clear-cache --type=temp

# Dry run to see what would be deleted
python -m modules.cli --clear-cache --dry-run

# Skip confirmation prompt
python -m modules.cli --clear-cache --yes
```

#### Cache Types
- `all` - Clear all cache data (default)
- `metadata` - Clear metadata cache
- `downloads` - Clear download cache
- `sessions` - Clear session data
- `thumbnails` - Clear thumbnail cache
- `temp` - Clear temporary files

#### Features
- **Safety Checks**: Shows what will be deleted before confirmation
- **Dry Run Mode**: Preview deletions without actually removing files
- **User Feedback**: Detailed statistics about files and space freed
- **Selective Clearing**: Target specific cache types
- **Error Handling**: Graceful handling of permission errors

### 2. Configuration Editor (`config edit`)

Interactive configuration file editing with validation and backup.

#### Usage
```bash
# Open config in default editor
python -m modules.cli config edit

# Specify custom editor
python -m modules.cli config edit --editor=notepad
python -m modules.cli config edit --editor=code

# Skip backup creation
python -m modules.cli config edit --no-backup
```

#### Features
- **Automatic Backup**: Creates timestamped backup before editing
- **Editor Detection**: Auto-detects available editors (VS Code, Notepad++, etc.)
- **Validation**: Validates JSON syntax after editing
- **Error Recovery**: Restores backup if validation fails
- **Cross-Platform**: Works on Windows, macOS, and Linux

### 3. Configuration Display (`config show`)

Display current configuration with multiple output formats and filtering.

#### Usage
```bash
# Show all configuration in table format
python -m modules.cli config show

# Different output formats
python -m modules.cli config show --format=json
python -m modules.cli config show --format=yaml
python -m modules.cli config show --format=table

# Filter by category
python -m modules.cli config show --category=download
python -m modules.cli config show --category=video
python -m modules.cli config show --category=audio
python -m modules.cli config show --category=network

# Show only non-default values
python -m modules.cli config show --non-default

# Save to file
python -m modules.cli config show --output=config_export.json
python -m modules.cli config show --format=yaml --output=config.yaml
```

#### Output Formats
- **Table**: Rich formatted table (default)
- **JSON**: Machine-readable JSON format
- **YAML**: Human-readable YAML format

#### Categories
- `download` - Download-related settings
- `video` - Video processing settings
- `audio` - Audio processing settings
- `network` - Network and connection settings
- `interface` - User interface settings
- `advanced` - Advanced system settings

### 4. Backup Management (`config backup`)

Manage configuration backups with create, list, and restore functionality.

#### Usage
```bash
# List available backups
python -m modules.cli config backup list

# Create new backup
python -m modules.cli config backup create

# Restore from backup
python -m modules.cli config backup restore --name=config_backup_20250527_220658.json
```

#### Features
- **Timestamped Backups**: Automatic timestamp naming
- **List View**: Shows all available backups with details
- **Safe Restore**: Validates backup before restoring
- **Backup Cleanup**: Automatic cleanup of old backups

### 5. Configuration Reset (`config reset`)

Reset configuration to default values with category support.

#### Usage
```bash
# Reset all configuration (with confirmation)
python -m modules.cli config reset

# Reset specific category
python -m modules.cli config reset --category=download

# Skip confirmation
python -m modules.cli config reset --yes
```

## Configuration Categories

### Download Settings
- `sessions_dir` - Session files directory
- `cache_dir` - Cache directory
- `download_dir` - Default download directory
- `auto_organize` - Auto-organize downloads
- `max_retries` - Maximum retry attempts
- `concurrent_downloads` - Concurrent download limit

### Video Settings
- `video_quality` - Default video quality
- `video_format` - Preferred video format
- `resolution` - Default resolution
- `upscale_settings` - Video upscaling configuration

### Audio Settings
- `audio_quality` - Default audio quality
- `audio_format` - Preferred audio format
- `denoise` - Audio noise reduction
- `upmix_settings` - Audio upmixing configuration

### Network Settings
- `connection_timeout` - Network timeout
- `max_concurrent` - Maximum concurrent connections
- `proxy_settings` - Proxy configuration
- `rate_limit` - Download rate limiting

## Safety Features

### Backup System
- Automatic backups before configuration changes
- Timestamped backup files
- Backup validation and integrity checks
- Easy restore functionality

### Cache Safety
- Dry-run mode for preview
- User confirmation prompts
- Detailed deletion reports
- Graceful error handling

### Validation
- JSON syntax validation
- Configuration schema validation
- Value range checking
- Dependency validation

## Examples

### Complete Workflow Example
```bash
# 1. Show current configuration
python -m modules.cli config show --category=download

# 2. Create backup before changes
python -m modules.cli config backup create

# 3. Edit configuration
python -m modules.cli config edit

# 4. Verify changes
python -m modules.cli config show --non-default

# 5. Clear cache after changes
python -m modules.cli --clear-cache --type=metadata --dry-run
python -m modules.cli --clear-cache --type=metadata
```

### Maintenance Workflow
```bash
# Weekly cache cleanup
python -m modules.cli --clear-cache --type=temp
python -m modules.cli --clear-cache --type=thumbnails

# Monthly full cleanup
python -m modules.cli --clear-cache --dry-run
python -m modules.cli --clear-cache

# Export configuration for backup
python -m modules.cli config show --format=yaml --output=weekly_backup.yaml
```

## Error Handling

All configuration commands include comprehensive error handling:

- **File Permission Errors**: Graceful handling with clear error messages
- **JSON Syntax Errors**: Automatic backup restoration
- **Network Issues**: Retry mechanisms for downloads
- **Disk Space**: Warnings for low disk space during operations

## Best Practices

1. **Always Use Dry Run**: Test cache clearing with `--dry-run` first
2. **Regular Backups**: Create backups before major configuration changes
3. **Category Filtering**: Use category filters for targeted configuration viewing
4. **Validation**: Always validate configuration after manual edits
5. **Cleanup**: Regularly clean temporary and thumbnail caches

## Troubleshooting

### Common Issues

#### Configuration Editor Won't Open
- Ensure a text editor is installed and accessible
- Try specifying editor manually: `--editor=notepad`
- Check file permissions on config directory

#### Cache Clearing Fails
- Run with elevated permissions if needed
- Check disk space and permissions
- Use dry-run mode to identify problematic files

#### Backup Restore Fails
- Verify backup file exists and is readable
- Check JSON syntax of backup file
- Ensure sufficient disk space

### Getting Help

Use the built-in help system for detailed command information:

```bash
python -m modules.cli --help
python -m modules.cli config --help
python -m modules.cli config show --help
python -m modules.cli config edit --help
python -m modules.cli config backup --help
python -m modules.cli --clear-cache --help
```

## Integration with Existing Features

The new configuration management system integrates seamlessly with:

- **Download Manager**: Automatic cache management during downloads
- **Session Manager**: Configuration-aware session handling
- **Performance Monitor**: Configuration impact monitoring
- **Error Handler**: Enhanced error reporting for configuration issues
- **Interactive Modes**: Configuration commands available in all interfaces

## Technical Implementation

### Thread Safety
All configuration operations are thread-safe with proper locking mechanisms.

### Performance
- Lazy loading of configuration data
- Efficient cache scanning algorithms
- Minimal memory footprint during operations

### Extensibility
The system is designed for easy extension with new configuration categories and cache types.
