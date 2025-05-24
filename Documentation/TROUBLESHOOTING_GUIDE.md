# Troubleshooting Guide

## Overview

This comprehensive troubleshooting guide covers common issues, error diagnosis, debugging procedures, and solutions for the Snatch media downloader across different platforms and scenarios.

## Table of Contents

1. [Quick Diagnostics](#quick-diagnostics)
2. [Installation Issues](#installation-issues)
3. [Download Problems](#download-problems)
4. [Network Issues](#network-issues)
5. [Audio/Video Processing Issues](#audiovideo-processing-issues)
6. [Performance Problems](#performance-problems)
7. [Error Codes Reference](#error-codes-reference)
8. [Platform-Specific Issues](#platform-specific-issues)
9. [Debug Mode and Logging](#debug-mode-and-logging)
10. [Advanced Troubleshooting](#advanced-troubleshooting)

## Quick Diagnostics

### System Health Check

Run the built-in diagnostic tool to quickly identify common issues:

```bash
# Basic system check
snatch info

# Comprehensive health check
snatch --health-check

# Network connectivity test
snatch speedtest

# Dependencies verification
snatch --verify-deps
```

### Common Quick Fixes

| Problem | Quick Fix | Command |
|---------|-----------|---------|
| FFmpeg not found | Install/configure FFmpeg | `python setupfiles/setup_ffmpeg.py` |
| Permission denied | Run as administrator | Right-click → Run as administrator |
| Network timeout | Check internet connection | `ping google.com` |
| Corrupted cache | Clear cache | `snatch --clear-cache` |
| Python module missing | Reinstall dependencies | `pip install -r requirements.txt` |

## Installation Issues

### Python Version Problems

#### Issue: "Python version not supported"

**Symptoms:**

- Error during installation: "Python 3.8+ required"
- Module import failures

**Solutions:**

```bash
# Check Python version
python --version

# Install Python 3.8+ if needed
# Windows: Download from python.org
# macOS: brew install python@3.8
# Linux: sudo apt-get install python3.8

# Update PATH to use correct Python version
# Windows: Add Python installation to PATH
# Linux/macOS: Use update-alternatives or alias
```

#### Issue: Multiple Python versions conflict

**Symptoms:**

- Wrong Python version used
- Module not found errors

**Solutions:**

```bash
# Use specific Python version
python3.8 -m pip install -r requirements.txt
python3.8 -m snatch

# Create virtual environment with specific version
python3.8 -m venv .venv
source .venv/bin/activate  # Linux/macOS
.\.venv\Scripts\Activate.ps1  # Windows
```

### Dependency Installation Issues

#### Issue: pip install failures

**Symptoms:**

- Package installation errors
- Compilation failures
- Permission denied errors

**Solutions:**

```bash
# Upgrade pip first
python -m pip install --upgrade pip

# Install with user flag if permission denied
pip install --user -r requirements.txt

# Use pre-compiled wheels
pip install --only-binary=all -r requirements.txt

# Clear pip cache if corrupted
pip cache purge
```

#### Issue: FFmpeg installation problems

**Symptoms:**

- "FFmpeg not found" error
- Audio/video processing failures

**Platform-specific Solutions:**

```bash
# Windows (automated)
python setupfiles/setup_ffmpeg.py

# Windows (manual)
# 1. Download from https://ffmpeg.org/download.html
# 2. Extract to C:\ffmpeg
# 3. Add C:\ffmpeg\bin to PATH

# Linux
sudo apt-get update
sudo apt-get install ffmpeg

# macOS
brew install ffmpeg

# Verify installation
ffmpeg -version
```

### Virtual Environment Issues

#### Issue: Virtual environment not working

**Symptoms:**

- Modules not found despite installation
- Wrong Python version in venv

**Solutions:**

```bash
# Recreate virtual environment
rm -rf .venv  # Linux/macOS
rmdir /s .venv  # Windows
python -m venv .venv

# Activate properly
source .venv/bin/activate  # Linux/macOS
.\.venv\Scripts\Activate.ps1  # Windows PowerShell
.\.venv\Scripts\activate.bat  # Windows CMD

# Verify activation
which python  # Should show venv path
pip list  # Should show only venv packages
```

## Download Problems

### URL Recognition Issues

#### Issue: "URL not supported" or "No extractors found"

**Symptoms:**

- Error: "No suitable extractor found for URL"
- Site not recognized

**Diagnosis Steps:**

```bash
# Check if site is supported
snatch sites | grep -i "sitename"

# Test with yt-dlp directly
yt-dlp --list-extractors | grep -i "sitename"

# Try different URL formats
# Original: https://www.youtube.com/watch?v=VIDEO_ID
# Alternative: https://youtu.be/VIDEO_ID
```

**Solutions:**

1. **Update yt-dlp:**

   ```bash
   pip install --upgrade yt-dlp
   ```

2. **Try alternative URL formats:**

   ```bash
   # YouTube examples
   https://www.youtube.com/watch?v=dQw4w9WgXcQ
   https://youtu.be/dQw4w9WgXcQ
   https://m.youtube.com/watch?v=dQw4w9WgXcQ
   ```

3. **Use debug mode to see exact error:**

   ```bash
   snatch download "URL" --debug
   ```

### Download Interruption Issues

#### Issue: Downloads frequently interrupted

**Symptoms:**

- Downloads stop at random percentages
- "Connection reset" errors
- Timeout errors

**Solutions:**

1. **Increase timeout values:**

   ```bash
   snatch download "URL" --socket-timeout 60 --read-timeout 300
   ```

2. **Enable retry mechanism:**

   ```bash
   snatch download "URL" --retries 5 --retry-sleep 10
   ```

3. **Use smaller chunk sizes:**

   ```bash
   snatch download "URL" --http-chunk-size 1048576  # 1MB chunks
   ```

4. **Try with aria2c:**

   ```bash
   snatch download "URL" --aria2c
   ```

### Quality Selection Problems

#### Issue: Requested quality not available

**Symptoms:**

- "Format not available" error
- Lower quality downloaded than requested

**Diagnosis:**

```bash
# List all available formats
snatch download "URL" --list-formats

# Check what quality was actually downloaded
snatch download "URL" --verbose
```

**Solutions:**

1. **Use flexible quality selection:**

   ```bash
   # Instead of exact quality
   snatch download "URL" --resolution 1080
   # Try best available
   snatch download "URL" --quality best
   ```

2. **Check format availability:**

   ```bash
   # List available formats first
   yt-dlp -F "URL"
   ```

### Playlist Download Issues

#### Issue: Playlist downloads fail or incomplete

**Symptoms:**

- Only first video downloads
- "Playlist not found" error
- Some videos skipped

**Solutions:**

1. **Use playlist-specific options:**

   ```bash
   snatch download "PLAYLIST_URL" --playlist --playlist-start 1 --playlist-end 10
   ```

2. **Handle private/deleted videos:**

   ```bash
   snatch download "PLAYLIST_URL" --ignore-errors --continue-on-error
   ```

3. **For large playlists:**

   ```bash
   snatch download "PLAYLIST_URL" --playlist-items 1-50  # Download first 50
   ```

## Network Issues

### Connection Problems

#### Issue: Network timeouts and connection failures

**Symptoms:**

- "Connection timed out" errors
- "Network unreachable" errors
- Slow download speeds

**Diagnosis Commands:**

```bash
# Test basic connectivity
ping google.com
ping youtube.com

# Test DNS resolution
nslookup youtube.com

# Test download speed
snatch speedtest

# Check network interface
# Windows: ipconfig /all
# Linux: ip addr show
# macOS: ifconfig
```

**Solutions:**

1. **Network configuration:**

   ```bash
   # Use different DNS servers
   # Set DNS to 8.8.8.8 and 8.8.4.4 (Google DNS)
   # Or 1.1.1.1 and 1.0.0.1 (Cloudflare DNS)
   ```

2. **Proxy configuration:**

   ```bash
   # If behind proxy
   snatch download "URL" --proxy http://proxy.company.com:8080
   
   # Or set environment variables
   export HTTP_PROXY=http://proxy.company.com:8080
   export HTTPS_PROXY=https://proxy.company.com:8080
   ```

3. **Firewall/antivirus:**
   - Add Snatch to firewall exceptions
   - Temporarily disable antivirus to test
   - Check corporate firewall rules

### SSL/TLS Issues

#### Issue: SSL certificate errors

**Symptoms:**

- "SSL certificate verify failed" errors
- "SSL: CERTIFICATE_VERIFY_FAILED" errors

**Solutions:**

1. **Update certificates:**

   ```bash
   # Update CA certificates
   pip install --upgrade certifi
   
   # On Linux
   sudo apt-get update && sudo apt-get install ca-certificates
   ```

2. **Bypass SSL verification (temporary):**

   ```bash
   snatch download "URL" --no-check-certificate
   ```

   ⚠️ **Warning:** Only use this for testing, not in production

3. **Corporate network issues:**

   ```bash
   # Export corporate certificate
   # Contact IT department for proper certificate installation
   ```

### Bandwidth and Speed Issues

#### Issue: Slow download speeds

**Symptoms:**

- Downloads much slower than expected
- Speed decreases over time
- Inconsistent speeds

**Diagnosis:**

```bash
# Test actual internet speed
snatch speedtest

# Monitor network usage
# Windows: Task Manager → Performance → Ethernet
# Linux: iftop or nethogs
# macOS: Activity Monitor → Network
```

**Solutions:**

1. **Optimize download settings:**

   ```bash
   # Increase concurrent connections
   snatch download "URL" --concurrent-fragments 4
   
   # Use larger chunk sizes
   snatch download "URL" --http-chunk-size 8388608  # 8MB
   
   # Enable aria2c for better speeds
   snatch download "URL" --aria2c
   ```

2. **Network optimization:**

   ```bash
   # Disable other bandwidth-heavy applications
   # Use wired connection instead of WiFi
   # Try downloading at different times of day
   ```

## Audio/Video Processing Issues

### FFmpeg Problems

#### Issue: FFmpeg processing failures

**Symptoms:**

- "FFmpeg error" messages
- Audio/video conversion failures
- Post-processing errors

**Diagnosis:**

```bash
# Test FFmpeg directly
ffmpeg -version

# Test with simple conversion
ffmpeg -i input.mp4 -c copy output.mp4

# Check Snatch FFmpeg detection
snatch info | grep -i ffmpeg
```

**Solutions:**

1. **Reinstall FFmpeg:**

   ```bash
   # Windows
   python setupfiles/setup_ffmpeg.py
   
   # Linux
   sudo apt-get remove ffmpeg
   sudo apt-get install ffmpeg
   
   # macOS
   brew uninstall ffmpeg
   brew install ffmpeg
   ```

2. **Manual FFmpeg path:**

   ```bash
   # Set FFmpeg path explicitly
   snatch download "URL" --ffmpeg-location "/path/to/ffmpeg"
   ```

3. **Skip post-processing:**

   ```bash
   # Download without post-processing
   snatch download "URL" --no-post-overwrites
   ```

### Audio Format Issues

#### Issue: Audio conversion failures

**Symptoms:**

- "Unable to convert audio" errors
- Missing audio in output
- Codec not supported errors

**Solutions:**

1. **Use different audio formats:**

   ```bash
   # Try different formats
   snatch download "URL" --audio-only --format mp3
   snatch download "URL" --audio-only --format opus
   snatch download "URL" --audio-only --format m4a
   ```

2. **Check codec availability:**

   ```bash
   # List available codecs
   ffmpeg -codecs | grep -i audio
   ```

3. **Install additional codecs:**

   ```bash
   # Linux: Install additional codec packages
   sudo apt-get install ubuntu-restricted-extras
   ```

### Video Processing Problems

#### Issue: Video processing errors

**Symptoms:**

- Video corruption
- Sync issues between audio and video
- Processing hangs

**Solutions:**

1. **Use different video containers:**

   ```bash
   snatch download "URL" --format mp4
   snatch download "URL" --format mkv
   ```

2. **Disable problematic processing:**

   ```bash
   # Skip video processing
   snatch download "URL" --no-video-postprocessing
   
   # Use copy codec (no re-encoding)
   snatch download "URL" --video-codec copy
   ```

## Performance Problems

### Memory Issues

#### Issue: High memory usage or out-of-memory errors

**Symptoms:**

- System becomes unresponsive
- "MemoryError" exceptions
- Application crashes

**Diagnosis:**

```bash
# Monitor memory usage
# Windows: Task Manager
# Linux: htop or top
# macOS: Activity Monitor

# Check Snatch memory usage
snatch download "URL" --monitor-memory
```

**Solutions:**

1. **Reduce concurrent downloads:**

   ```bash
   # Limit concurrent downloads
   snatch config set max_concurrent_downloads 2
   ```

2. **Optimize chunk sizes:**

   ```bash
   # Use smaller chunks for large files
   snatch download "URL" --http-chunk-size 1048576  # 1MB
   ```

3. **Clear cache regularly:**

   ```bash
   snatch --clear-cache
   ```

### CPU Usage Issues

#### Issue: High CPU usage

**Symptoms:**

- System becomes slow
- High CPU usage in task manager
- Overheating

**Solutions:**

1. **Lower process priority:**

   ```bash
   # Windows: Use Task Manager to set lower priority
   # Linux: nice -n 10 snatch download "URL"
   ```

2. **Reduce processing:**

   ```bash
   # Skip post-processing
   snatch download "URL" --no-post-overwrites
   
   # Use hardware acceleration (if available)
   snatch download "URL" --use-hw-accel
   ```

### Disk Space Issues

#### Issue: Insufficient disk space

**Symptoms:**

- "No space left on device" errors
- Downloads fail near completion
- System warnings about disk space

**Solutions:**

1. **Check available space:**

   ```bash
   # Windows: dir
   # Linux/macOS: df -h
   ```

2. **Clean up temporary files:**

   ```bash
   # Clean Snatch cache
   snatch --clear-cache
   
   # Clean system temp files
   # Windows: Disk Cleanup utility
   # Linux: sudo apt-get autoclean
   ```

3. **Change download location:**

   ```bash
   snatch download "URL" --output "/path/to/larger/drive"
   ```

## Error Codes Reference

### HTTP Error Codes

| Code | Meaning | Solution |
|------|---------|----------|
| 403 | Forbidden | Try different user agent or IP |
| 404 | Not Found | Check URL validity |
| 429 | Too Many Requests | Wait and retry with delays |
| 500 | Server Error | Retry later |
| 503 | Service Unavailable | Server overloaded, try later |

### Snatch Error Codes

| Code | Category | Description | Solution |
|------|----------|-------------|----------|
| E001 | Network | Connection timeout | Check internet, increase timeout |
| E002 | Network | DNS resolution failed | Check DNS settings |
| E003 | Format | No supported formats | Update yt-dlp, try different URL |
| E004 | File | Permission denied | Check file permissions |
| E005 | Processing | FFmpeg error | Check FFmpeg installation |
| E006 | Memory | Out of memory | Reduce concurrent downloads |
| E007 | Disk | No disk space | Free up disk space |
| E008 | Config | Invalid configuration | Check config file syntax |

### Platform Error Codes

#### Windows

```bash
# Error code meanings
# 0x80070005 - Access denied
# 0x80070020 - File in use
# 0x8007000E - Out of memory
```

#### Linux

```bash
# Common errno values
# EACCES (13) - Permission denied
# ENOENT (2) - File not found
# ENOSPC (28) - No space left on device
# ETIMEDOUT (110) - Connection timed out
```

## Platform-Specific Issues

### Windows Issues

#### Issue: Windows Defender blocking downloads

**Symptoms:**

- Downloads deleted immediately
- "Virus detected" false positives
- Quarantine notifications

**Solutions:**

1. **Add exclusions:**

   ```powershell
   # Add folder exclusion (Run as Administrator)
   Add-MpPreference -ExclusionPath "C:\path\to\snatch"
   Add-MpPreference -ExclusionProcess "snatch.exe"
   ```

2. **Disable real-time protection temporarily:**
   - Windows Security → Virus & threat protection
   - Turn off Real-time protection (temporarily)

#### Issue: PATH environment variable problems

**Symptoms:**

- "Command not found" errors
- Wrong Python version used

**Solutions:**

```powershell
# Check current PATH
echo $env:PATH

# Add to PATH permanently
[Environment]::SetEnvironmentVariable("PATH", "$env:PATH;C:\path\to\snatch", "User")

# Or use System Properties → Environment Variables
```

### Linux Issues

#### Issue: Permission denied errors

**Symptoms:**

- Cannot write to directories
- Cannot execute files

**Solutions:**

```bash
# Fix permissions
chmod +x snatch
chmod -R 755 /path/to/snatch

# Add user to appropriate groups
sudo usermod -a -G audio,video $USER

# Use sudo for system-wide installation
sudo pip install -r requirements.txt
```

#### Issue: Missing system dependencies

**Symptoms:**

- Compilation errors during pip install
- Missing header files

**Solutions:**

```bash
# Ubuntu/Debian
sudo apt-get install python3-dev python3-pip
sudo apt-get install build-essential
sudo apt-get install libffi-dev libssl-dev

# CentOS/RHEL
sudo yum install python3-devel python3-pip
sudo yum groupinstall "Development Tools"

# Arch Linux
sudo pacman -S python python-pip base-devel
```

### macOS Issues

#### Issue: Gatekeeper blocking execution

**Symptoms:**

- "App can't be opened" errors
- Security warnings

**Solutions:**

```bash
# Remove quarantine attribute
xattr -d com.apple.quarantine /path/to/snatch

# Allow in System Preferences
# System Preferences → Security & Privacy → Allow anyway
```

#### Issue: Homebrew conflicts

**Symptoms:**

- Multiple Python versions
- Package conflicts

**Solutions:**

```bash
# Use specific Homebrew Python
/usr/local/bin/python3 -m pip install snatch

# Or create isolated environment
brew install pyenv
pyenv install 3.8.10
pyenv local 3.8.10
```

## Debug Mode and Logging

### Enabling Debug Mode

#### Comprehensive debugging

```bash
# Enable full debug output
snatch download "URL" --debug --verbose

# Save debug output to file
snatch download "URL" --debug > debug.log 2>&1

# Network-specific debugging
snatch download "URL" --debug-network

# FFmpeg debugging
snatch download "URL" --debug-ffmpeg
```

### Log Analysis

#### Understanding log patterns

```bash
# Search for specific errors
grep -i "error" snatch.log
grep -i "warning" snatch.log
grep -i "failed" snatch.log

# Check network issues
grep -i "connection\|timeout\|network" snatch.log

# Find performance issues
grep -i "slow\|memory\|cpu" snatch.log
```

### Log Configuration

#### Custom logging setup

```python
# In config file or script
import logging

# Set up detailed logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('snatch_debug.log'),
        logging.StreamHandler()
    ]
)
```

## Advanced Troubleshooting

### Network Troubleshooting

#### Packet capture analysis

```bash
# Capture network traffic (Linux)
sudo tcpdump -i any -w snatch_traffic.pcap host youtube.com

# Analyze with Wireshark
wireshark snatch_traffic.pcap
```

#### DNS troubleshooting

```bash
# Test DNS resolution
nslookup youtube.com
dig youtube.com

# Try different DNS servers
nslookup youtube.com 8.8.8.8
nslookup youtube.com 1.1.1.1
```

### Process Debugging

#### System call tracing

```bash
# Linux: strace
strace -f -o snatch_trace.log python -m snatch download "URL"

# macOS: dtruss
sudo dtruss -f python -m snatch download "URL"

# Windows: Process Monitor (ProcMon)
```

#### Memory debugging

```python
# Add to code for memory profiling
import tracemalloc

tracemalloc.start()

# Your code here

current, peak = tracemalloc.get_traced_memory()
print(f"Current memory usage: {current / 1024 / 1024:.1f} MB")
print(f"Peak memory usage: {peak / 1024 / 1024:.1f} MB")
tracemalloc.stop()
```

### Performance Profiling

#### CPU profiling

```python
import cProfile
import pstats

# Profile the download process
cProfile.run('your_download_function()', 'profile_stats')

# Analyze results
stats = pstats.Stats('profile_stats')
stats.sort_stats('cumulative')
stats.print_stats(10)  # Top 10 functions
```

#### I/O profiling

```bash
# Linux: iotop
sudo iotop -o

# Monitor disk usage
iostat -x 1

# Check file descriptors
lsof -p $(pgrep snatch)
```

## Getting Help

### Information to Include

When reporting issues, include:

1. **System Information:**

   ```bash
   snatch info
   python --version
   pip list | grep -E "(snatch|yt-dlp|ffmpeg)"
   ```

2. **Error Details:**
   - Complete error message
   - Stack trace (if available)
   - Steps to reproduce

3. **Environment:**
   - Operating system and version
   - Python version
   - Virtual environment status
   - Network configuration

4. **Debug Output:**

   ```bash
   snatch download "URL" --debug > debug.log 2>&1
   ```

### Support Channels

- **GitHub Issues**: <https://github.com/your-username/snatch/issues>
- **Documentation**: <https://snatch.readthedocs.io/>
- **Community Forum**: <https://community.snatch.dev/>
- **Discord**: <https://discord.gg/snatch-community>

### Emergency Recovery

#### Complete reinstallation

```bash
# Backup important data
cp -r ./downloads ./downloads_backup
cp config.json config_backup.json

# Remove everything
rm -rf .venv snatch_cache
pip uninstall snatch -y

# Fresh installation
git pull origin main
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pip install -e .

# Restore configuration
cp config_backup.json config.json
```

#### Factory reset

```bash
# Reset to default configuration
snatch --reset-config

# Clear all caches
snatch --clear-all-data

# Rebuild dependencies
pip install --force-reinstall -r requirements.txt
```

Remember: When in doubt, start with the basic diagnostics and work your way up to more advanced troubleshooting techniques. Most issues can be resolved with the solutions provided in this guide.
