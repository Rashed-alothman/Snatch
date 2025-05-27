# Snatch-DL Fixes

This directory contains various scripts to fix critical issues in the Snatch-DL media downloader.

## Quick Fix Guide

To apply all fixes at once, run:

```bash
python apply_all_fixes.py
```

This script will:

1. Fix the interactive mode's `RowDoesNotExist` error
2. Fix the download command with proper asyncio event loop handling
3. Ensure proper configuration with automatic directory creation

## Individual Fix Scripts

If you prefer to apply fixes individually:

- **direct_fix.py** - Applies direct patches to fix the most critical issues:

  ```bash
  python direct_fix.py
  ```

- **fix_interactive_mode.py** - Specifically fixes interactive mode issues:

  ```bash
  python fix_interactive_mode.py
  ```

- **ensure_config.py** - Validates and creates the configuration file:

  ```bash
  python ensure_config.py
  ```

## Testing Your Installation

After applying the fixes, you can test if they worked correctly:

```bash
python test_audio_and_resolution.py
```

This will test various download options including audio-only and resolution-specific downloads.

## Usage After Fixes

Once the fixes are applied, you can use these commands:

1. Download a video:

   ```bash
   snatch download <URL>
   ```

2. Download audio only:

   ```bash
   snatch download <URL> --audio-only
   ```

3. Download at specific resolution:

   ```bash
   snatch download <URL> --resolution 720
   ```

4. Use interactive mode:

   ```bash
   snatch interactive
   ```

## Detailed Fix Information

For detailed technical information about the fixes, please see the [FIXES_SUMMARY.md](./FIXES_SUMMARY.md) file.
