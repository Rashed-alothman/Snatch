# Universal Downloader

A powerful Python script that can download videos and audio from hundreds of websites (YouTube, Vimeo, Twitter, TikTok, Instagram, Twitch, and more) using yt-dlp.

## Prerequisites

- Python 3.7 or higher
- FFmpeg installed on your system
- Required Python packages (yt-dlp)

## Installation

1. Clone this repository:

```bash
git clone https://github.com/Rashed-alothman/universal-downloader.git
cd universal-downloader
```

2. Install the required Python packages:

```bash
pip install -r requirements.txt
```

## Usage Examples

There are two ways to provide URLs: using the `--url` flag or directly as an argument.

### Method 1: Using --url flag

#### Bash Commands

To download a video, run the following command:

```bash
python UniversalDownloader.py --url "VIDEO_URL"
```

To download audio only, run the following command:

```bash
python UniversalDownloader.py --url "VIDEO_URL" --audio-only
```

You can specify the output format using the `--format` option:

```bash
python UniversalDownloader.py --url "VIDEO_URL" --format "mp4"
```

For more options, run:

```bash
python UniversalDownloader.py --help
```

#### Windows Command Prompt

To download a video, run the following command:

```cmd
python UniversalDownloader.py --url "VIDEO_URL"
```

To download audio only, run the following command:

```cmd
python UniversalDownloader.py --url "VIDEO_URL" --audio-only
```

You can specify the output format using the `--format` option:

```cmd
python UniversalDownloader.py --url "VIDEO_URL" --format "mp4"
```

For more options, run:

```cmd
python UniversalDownloader.py --help
```

#### PowerShell

To download a video, run the following command:

```powershell
python UniversalDownloader.py --url "VIDEO_URL"
```

To download audio only, run the following command:

```powershell
python UniversalDownloader.py --url "VIDEO_URL" --audio-only
```

You can specify the output format using the `--format` option:

```powershell
python UniversalDownloader.py --url "VIDEO_URL" --format "mp4"
```

For more options, run:

```powershell
python UniversalDownloader.py --help
```

### Method 2: Direct Argument

#### Bash Commands

To download a video, run the following command:

```bash
python UniversalDownloader.py "VIDEO_URL"
```

To download audio only, run the following command:

```bash
python UniversalDownloader.py "VIDEO_URL" --audio-only
```

You can specify the output format using the `--format` option:

```bash
python UniversalDownloader.py "VIDEO_URL" --format "mp4"
```

For more options, run:

```bash
python UniversalDownloader.py --help
```

#### Windows Command Prompt

To download a video, run the following command:

```cmd
python UniversalDownloader.py "VIDEO_URL"
```

To download audio only, run the following command:

```cmd
python UniversalDownloader.py "VIDEO_URL" --audio-only
```

You can specify the output format using the `--format` option:

```cmd
python UniversalDownloader.py "VIDEO_URL" --format "mp4"
```

For more options, run:

```cmd
python UniversalDownloader.py --help
```

#### PowerShell

To download a video, run the following command:

```powershell
python UniversalDownloader.py "VIDEO_URL"
```

To download audio only, run the following command:

```powershell
python UniversalDownloader.py "VIDEO_URL" --audio-only
```

You can specify the output format using the `--format` option:

```powershell
python UniversalDownloader.py "VIDEO_URL" --format "mp4"
```

For more options, run:

```powershell
python UniversalDownloader.py --help
```

## Command Line Help

Get detailed help information by running:
