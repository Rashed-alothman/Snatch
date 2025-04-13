#!/usr/bin/env python
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import os
import sys
import threading
import time
import shutil
import re
import logging

# Try importing required packages
try:
    from colorama import Fore, Style, init

    init(autoreset=True)
except ImportError:
    # Create simple color functions if colorama isn't available
    class DummyFore:
        def __getattr__(self, _):
            return ""

    class DummyStyle:
        def __getattr__(self, _):
            return ""

    Fore = DummyFore()
    Style = DummyStyle()

# Try to import psutil for system stats
try:
    import psutil
except ImportError:
    psutil = None

# Try to import requests for update checks
try:
    import requests
except ImportError:
    requests = None


class CommandHistory:
    """Maintains command history with persistence and search capability"""

    def __init__(self, max_size: int = 100, history_file: str = ".snatch_history"):
        self.history = []
        self.max_size = max_size
        self.history_file = os.path.join(str(Path.home()), history_file)
        self.position = 0
        self.load_history()

    def add(self, command: str) -> None:
        """Add command to history, avoiding duplicates"""
        if not command or not command.strip():
            return

        # Remove command if already in history to avoid duplicates
        if command in self.history:
            self.history.remove(command)

        # Add command to end of history
        self.history.append(command)

        # Trim history if too long
        if len(self.history) > self.max_size:
            self.history = self.history[-self.max_size :]

        # Reset position to end
        self.position = len(self.history)

        # Save updated history
        self.save_history()

    def get_previous(self, current_input: str = "") -> str:
        """Get previous command from history"""
        if not self.history:
            return current_input

        if self.position > 0:
            self.position -= 1

        if self.position < len(self.history):
            return self.history[self.position]
        return current_input

    def get_next(self, current_input: str = "") -> str:
        """Get next command from history"""
        if not self.history:
            return current_input

        if self.position < len(self.history) - 1:
            self.position += 1
            return self.history[self.position]
        else:
            self.position = len(self.history)
            return current_input

    def search(self, prefix: str) -> Optional[str]:
        """Search history for command starting with prefix"""
        if not prefix:
            return None

        # Search from current position backward
        for i in range(len(self.history) - 1, -1, -1):
            if self.history[i].startswith(prefix):
                return self.history[i]
        return None

    def load_history(self) -> None:
        """Load history from file"""
        try:
            if os.path.exists(self.history_file):
                with open(self.history_file, "r") as f:
                    self.history = [line.strip() for line in f.readlines()]
                self.position = len(self.history)
        except Exception:
            # If loading fails, start with empty history
            self.history = []
            self.position = 0

    def save_history(self) -> None:
        """Save history to file"""
        try:
            with open(self.history_file, "w") as f:
                for cmd in self.history:
                    f.write(f"{cmd}\n")
        except Exception:
            pass

    def show_history(self, limit: int = 0) -> None:
        """Display command history"""
        if not self.history:
            print(f"{Fore.YELLOW}No command history available{Style.RESET_ALL}")
            return

        history_to_show = self.history
        if limit > 0:
            history_to_show = self.history[-limit:]

        print(f"\n{Fore.CYAN}Command History:{Style.RESET_ALL}")
        for i, hist_cmd in enumerate(history_to_show, 1):
            print(f"{i}. {hist_cmd}")


class CommandCompleter:
    """Provides tab completion for commands"""

    def __init__(self):
        self.commands = [
            "download",
            "dl",
            "audio",
            "video",
            "help",
            "?",
            "exit",
            "quit",
            "q",
            "flac",
            "mp3",
            "wav",
            "m4a",
            "opus",
            "list",
            "sites",
            "clear",
            "cls",
            "history",
            "version",
            "stats",
            "system-stats",
            "config",
            "speedtest",
            "test",
        ]

        self.options = [
            "--audio-only",
            "--resolution",
            "--format-id",
            "--filename",
            "--audio-format",
            "--output-dir",
            "--resume",
            "--stats",
            "--system-stats",
            "--no-cache",
            "--no-retry",
            "--throttle",
            "--aria2c",
            "--verbose",
            "--organize",
            "--no-organize",
            "--audio-channels",
        ]

        # Common website domains for URL autocompletion
        self.common_domains = [
            "youtube.com/watch?v=",
            "youtu.be/",
            "soundcloud.com/",
            "bandcamp.com/",
            "vimeo.com/",
            "dailymotion.com/video/",
            "twitch.tv/videos/",
            "spotify.com/track/",
            "open.spotify.com/track/",
        ]

    def complete(self, text: str) -> List[str]:
        """Return list of completions for the given text"""
        if not text:
            return []

        # If text starts with "http", try to complete a URL
        if text.lower().startswith("http"):
            return [d for d in self.common_domains if d.startswith(text[7:])]

        # Command at beginning of line
        if " " not in text:
            return [cmd for cmd in self.commands if cmd.startswith(text)]

        # Option after a command
        parts = text.split()
        if len(parts) > 1 and parts[-1].startswith("--"):
            return [opt for opt in self.options if opt.startswith(parts[-1])]

        return []


class SpinnerAnimation:
    """
    Animated spinner for displaying loading states.
    This is a simplified version for interactive mode.
    """

    def __init__(
        self, message: str = "Processing", style: str = "dots", color: str = "cyan"
    ):
        self.message = message
        self.running = False
        self.spinner_thread = None

        # Define spinner characters
        spinner_styles = {
            "dots": ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"],
            "line": ["|", "/", "-", "\\"],
            "aesthetic": ["⣾", "⣽", "⣻", "⢿", "⡿", "⣟", "⣯", "⣷"],
        }

        # Get color function from colorama
        self.color_func = getattr(Fore, color.upper(), Fore.CYAN)

        # Get spinner characters
        self.spinner_chars = spinner_styles.get(style, spinner_styles["dots"])

    def _get_color(self, text):
        """Apply color to text"""
        return f"{self.color_func}{text}{Style.RESET_ALL}"

    def spin(self):
        """Display spinner animation"""
        i = 0
        while self.running:
            char = self.spinner_chars[i % len(self.spinner_chars)]
            sys.stdout.write(f"\r{self._get_color(char)} {self.message} ")
            sys.stdout.flush()
            time.sleep(0.1)
            i += 1
            if not self.running:
                break
        sys.stdout.write("\r" + " " * (len(self.message) + 10) + "\r")
        sys.stdout.flush()

    def start(self):
        """Start spinner animation in a separate thread"""
        self.running = True
        self.spinner_thread = threading.Thread(target=self.spin)
        self.spinner_thread.daemon = True
        self.spinner_thread.start()

    def stop(self, clear=True):
        """Stop spinner animation"""
        self.running = False
        if self.spinner_thread:
            self.spinner_thread.join(0.2)
        if clear:
            sys.stdout.write("\r" + " " * (len(self.message) + 10) + "\r")
            sys.stdout.flush()

    def update_status(self, message):
        """Update the spinner message while running"""
        self.message = message


class InteractiveMode:
    """Enhanced interactive command system for Snatch"""

    def __init__(self, snatch_api):
        """
        Initialize interactive mode with references to Snatch functions

        Args:
            snatch_api: Dictionary containing references to Snatch functions and constants
        """
        self.snatch_api = snatch_api
        self.config = snatch_api["load_config"]()
        self.VERSION = snatch_api["VERSION"]
        self.EXAMPLES = snatch_api["EXAMPLES"]
        self.history = CommandHistory()
        self.completer = CommandCompleter()
        self.running = True
        self.display_banner()
        self.terminal_width = shutil.get_terminal_size().columns

        # Store download function reference
        self.download_function = snatch_api["download"]
        self.batch_download_function = snatch_api["batch_download"]

        # Command categories for help menu
        self.command_categories = {
            "Basic": [
                ("URL", "Download media from URL in best quality"),
                ("URL mp3", "Download audio in MP3 format"),
                ("URL flac", "Download audio in FLAC format"),
                ("URL 720|1080|2160", "Download video in specific resolution"),
                ("download <URL>", "Download media from URL (alias: dl)"),
                ("audio <URL>", "Download audio only from URL"),
            ],
            "Utility": [
                ("help, ?", "Show this help menu"),
                ("clear, cls", "Clear the screen"),
                ("history", "Show command history"),
                ("version", "Show version information"),
                ("exit, quit, q", "Exit the program"),
                ("config", "Show current configuration"),
            ],
            "Advanced": [
                ("playlist URL", "Download entire playlist with options"),
                ("batch file.txt", "Process batch file with URLs"),
                ("stats", "Show download statistics"),
                ("system-stats", "Show system resource usage"),
                ("list, sites", "Show supported sites"),
            ],
            "Audio Formats": [
                ("flac <URL>", "Download audio in FLAC format (lossless)"),
                ("mp3 <URL>", "Download audio in MP3 format (320kbps)"),
                ("opus <URL>", "Download audio in Opus format (high quality)"),
                ("wav <URL>", "Download audio in WAV format (uncompressed)"),
                ("m4a <URL>", "Download audio in M4A format (AAC)"),
            ],
        }

        # Added valid_commands attribute for fuzzy matching
        self.valid_commands = (
            "download", "dl", "audio", "video", "help", "?", "exit",
            "quit", "q", "flac", "mp3", "wav", "m4a", "opus", "list", "sites", "clear", "cls"
        )

    def fuzzy_match_command(self, input_cmd: str, valid_commands: tuple) -> str:
        """Fuzzy match user input to valid commands"""
        # Direct match
        if input_cmd in valid_commands:
            return input_cmd
        # Check for command prefix match
        prefix_matches = [cmd for cmd in valid_commands if cmd.startswith(input_cmd)]
        if prefix_matches:
            return prefix_matches[0]
        # Check for close matches using difflib
        from difflib import get_close_matches
        matches = get_close_matches(input_cmd, valid_commands, n=1, cutoff=0.6)
        if matches:
            return matches[0]
        # Check for substring match
        substring_matches = [cmd for cmd in valid_commands if input_cmd in cmd]
        if substring_matches:
            return substring_matches[0]
        return input_cmd

    def display_banner(self):
        """
        Display a colorful welcome banner with a bold block-style ASCII art logo.

        The banner features:
        - A bold, modern block-style ASCII art logo for "SNATCH"
        - Dynamic centering based on terminal width
        - Vibrant color scheme designed for both light and dark backgrounds
        - Version information and GitHub link
        - Basic usage instructions
        - Decorative borders to create a polished look
        """
        # Get current terminal width for dynamic centering
        terminal_width = shutil.get_terminal_size().columns

        # Define the bold ASCII block logo for "SNATCH"
        # Using a custom blocky font style that's professional yet eye-catching
        logo = [
            "  ██████╗ ███╗   ██╗ █████╗ ████████╗ ██████╗██╗  ██╗",
            "  ██╔════╝ ████╗  ██║██╔══██╗╚══██╔══╝██╔════╝██║  ██║",
            "  ███████╗ ██╔██╗ ██║███████║   ██║   ██║     ███████║",
            "  ╚════██║ ██║╚██╗██║██╔══██║   ██║   ██║     ██╔══██║",
            "  ███████║ ██║ ╚████║██║  ██║   ██║   ╚██████╗██║  ██║",
            "  ╚══════╝ ╚═╝  ╚═══╝╚═╝  ╚═╝   ╚═╝    ╚═════╝╚═╝  ╚═╝",
        ]

        # Get the width of the logo content (without ANSI color codes)
        logo_width = max(len(line) for line in logo)

        # Calculate padding for centering the logo and other elements
        logo_padding = max(0, (terminal_width - logo_width) // 2)

        # Define additional information to be displayed
        tagline = "Download Anything, Anywhere, Anytime"
        version_info = f"Version: {self.VERSION}"
        github_link = "GitHub: github.com/Rashed-alothman/Snatch"
        instructions = "Type 'help' or '?' for commands | Press Ctrl+C to exit"

        # Calculate the longest line for border width
        max_content_width = max(
            logo_width,
            len(tagline),
            len(version_info) + len(github_link) + 4,  # +4 for spacing
            len(instructions),
        )

        # Add some padding to the border width for aesthetics
        border_width = max_content_width + 8
        border_width = min(border_width, terminal_width - 2)  # Ensure it fits

        # Calculate padding for centering the border
        border_padding = max(0, (terminal_width - border_width) // 2)

        # Construct the banner with dynamic centering
        banner = []

        # Top border with rounded corners
        banner.append(f"{' ' * border_padding}{Fore.CYAN}╭{'━' * border_width}╮")

        # Empty space for visual breathing room
        banner.append(f"{' ' * border_padding}{Fore.CYAN}│{' ' * border_width}│")

        # Add the logo with dynamic centering and cyan color
        for line in logo:
            # Calculate centering for this specific line
            inner_padding = (border_width - len(line)) // 2
            banner.append(
                f"{' ' * border_padding}{Fore.CYAN}│{' ' * inner_padding}{Fore.CYAN}{Style.BRIGHT}{line}{' ' * (border_width - len(line) - inner_padding)}{Fore.CYAN}│"
            )

        # Empty space after logo
        banner.append(f"{' ' * border_padding}{Fore.CYAN}│{' ' * border_width}│")

        # Add tagline
        tagline_padding = (border_width - len(tagline)) // 2
        banner.append(
            f"{' ' * border_padding}{Fore.CYAN}│{' ' * tagline_padding}{Fore.YELLOW}{tagline}{' ' * (border_width - len(tagline) - tagline_padding)}{Fore.CYAN}│"
        )

        # Empty space as separator
        banner.append(f"{' ' * border_padding}{Fore.CYAN}│{' ' * border_width}│")

        # Add version and GitHub link on the same line
        combined_info = f"{Fore.GREEN}{version_info}   {Fore.BLUE}{github_link}"
        # Remove ANSI codes for length calculation
        clean_combined = f"{version_info}   {github_link}"
        combined_padding = (border_width - len(clean_combined)) // 2
        banner.append(
            f"{' ' * border_padding}{Fore.CYAN}│{' ' * combined_padding}{combined_info}{' ' * (border_width - len(clean_combined) - combined_padding)}{Fore.CYAN}│"
        )

        # Empty space before instructions
        banner.append(f"{' ' * border_padding}{Fore.CYAN}│{' ' * border_width}│")

        # Add user instructions
        instructions_padding = (border_width - len(instructions)) // 2
        banner.append(
            f"{' ' * border_padding}{Fore.CYAN}│{' ' * instructions_padding}{Fore.GREEN}{instructions}{' ' * (border_width - len(instructions) - instructions_padding)}{Fore.CYAN}│"
        )

        # Empty space for visual breathing room
        banner.append(f"{' ' * border_padding}{Fore.CYAN}│{' ' * border_width}│")

        # Bottom border with rounded corners
        banner.append(
            f"{' ' * border_padding}{Fore.CYAN}╰{'━' * border_width}╯{Style.RESET_ALL}"
        )

        # Add some vertical spacing before the banner
        print("\n")

        # Print the complete banner
        for line in banner:
            print(line)

        # Add a bit of space after the banner
        print("\n")

    def display_system_stats(self):
        """Display detailed system resource statistics"""
        if psutil is None:
            print(
                f"{Fore.YELLOW}System stats require psutil module. Install with: pip install psutil{Style.RESET_ALL}"
            )
            return

        print(f"\n{Fore.CYAN}{'=' * 40}")
        print(f"{Fore.GREEN}SYSTEM STATISTICS{Style.RESET_ALL}")
        print(f"{Fore.CYAN}{'=' * 40}{Style.RESET_ALL}\n")

        # CPU information
        cpu_percent = psutil.cpu_percent(interval=1)
        cpu_count = psutil.cpu_count(logical=False)
        cpu_logical = psutil.cpu_count(logical=True)
        print(f"{Fore.YELLOW}CPU Usage:{Style.RESET_ALL} {cpu_percent}%")
        print(
            f"{Fore.YELLOW}CPU Cores:{Style.RESET_ALL} {cpu_count} physical, {cpu_logical} logical"
        )

        # Memory information
        mem = psutil.virtual_memory()
        print(f"\n{Fore.YELLOW}Memory Usage:{Style.RESET_ALL} {mem.percent}%")
        print(
            f"{Fore.YELLOW}Total Memory:{Style.RESET_ALL} {mem.total / (1024**3):.2f} GB"
        )
        print(
            f"{Fore.YELLOW}Available Memory:{Style.RESET_ALL} {mem.available / (1024**3):.2f} GB"
        )
        print(
            f"{Fore.YELLOW}Used Memory:{Style.RESET_ALL} {mem.used / (1024**3):.2f} GB"
        )

        # Disk information
        print(f"\n{Fore.YELLOW}Disk Information:{Style.RESET_ALL}")
        for part in psutil.disk_partitions(all=False):
            if (
                self.snatch_api["is_windows"]() and "cdrom" in part.opts
            ) or part.fstype == "":
                continue
            usage = psutil.disk_usage(part.mountpoint)
            print(f"  {Fore.CYAN}Drive {part.mountpoint}{Style.RESET_ALL}")
            print(f"    Total: {usage.total / (1024**3):.2f} GB")
            print(f"    Used: {usage.used / (1024**3):.2f} GB ({usage.percent}%)")
            print(f"    Free: {usage.free / (1024**3):.2f} GB")

    def show_config(self):
        """Display current configuration settings in a formatted table"""
        width = min(self.terminal_width - 4, 80)

        print(f"\n{Fore.CYAN}╔{'═' * width}╗")
        print(
            f"{Fore.CYAN}║ {Fore.GREEN}SNATCH CONFIGURATION{Fore.CYAN}{' ' * (width - 20)}║"
        )
        print(f"{Fore.CYAN}╠{'═' * width}╣{Style.RESET_ALL}")

        # Display main configuration options
        keys_to_show = [
            "video_output",
            "audio_output",
            "ffmpeg_location",
            "max_concurrent",
            "organize",
        ]
        for key in keys_to_show:
            if key in self.config:
                value = self.config[key]
                if isinstance(value, bool):
                    value = "Enabled" if value else "Disabled"
                print(
                    f"{Fore.CYAN}║ {Fore.YELLOW}{key}: {Fore.WHITE}{value}{' ' * (width - len(key) - len(str(value)) - 3)}{Fore.CYAN}║{Style.RESET_ALL}"
                )

        # Display organization templates if organizing is enabled
        if (
            self.config.get("organize", False)
            and "organization_templates" in self.config
        ):
            print(f"{Fore.CYAN}║{' ' * width}║{Style.RESET_ALL}")
            print(
                f"{Fore.CYAN}║ {Fore.YELLOW}File Organization Templates:{' ' * (width - 28)}{Fore.CYAN}║{Style.RESET_ALL}"
            )

            for type_key, template in self.config["organization_templates"].items():
                print(
                    f"{Fore.CYAN}║ {Fore.GREEN}{type_key}: {Fore.WHITE}{template}{' ' * (width - len(type_key) - len(template) - 3)}{Fore.CYAN}║{Style.RESET_ALL}"
                )

        print(f"{Fore.CYAN}╚{'═' * width}╝{Style.RESET_ALL}")

    def check_update(self) -> Tuple[bool, str, str]:
        """
        Check if a newer version of Snatch is available

        Returns:
            Tuple[bool, str, str]: (has_update, latest_version, message)
        """
        if requests is None:
            return False, "", "Requests module not available"

        spinner = SpinnerAnimation("Checking for updates", style="aesthetic")
        spinner.start()

        try:
            # This URL would be replaced with the actual URL for version checking
            response = requests.get(
                "https://api.github.com/repos/Rashed-alothman/Snatch/releases/latest",
                timeout=5,
            )

            spinner.stop(clear=True)
            if response.status_code == 200:
                latest_version = response.json().get("tag_name", "").lstrip("v")
                current_version = self.VERSION

                if latest_version and latest_version != current_version:
                    message = f"Update available! Version {latest_version} is now available. You have version {current_version}"
                    return True, latest_version, message
                else:
                    message = f"You're running the latest version ({current_version})"
                    return False, current_version, message

            return (
                False,
                "",
                f"Failed to check for updates: HTTP {response.status_code}",
            )
        except Exception as e:
            spinner.stop(clear=True)
            return False, "", f"Failed to check for updates: {str(e)}"

    def run(self):
        # Check for updates in background
        def check_update_bg():
            has_update, latest_version, message = self.check_update()
            if has_update:
                print(f"\n{Fore.GREEN}✨ {message}{Style.RESET_ALL}")
                print(
                    f"{Fore.CYAN}Visit: github.com/Rashed-alothman/Snatch to update{Style.RESET_ALL}\n"
                )
            else:
                if latest_version:  # Only show the message if we got a version
                    print(f"\n{Fore.CYAN}✓ {message}{Style.RESET_ALL}\n")

        # Start background update check
        update_thread = threading.Thread(target=check_update_bg)
        update_thread.daemon = True
        update_thread.start()
        while self.running:
            try:
                # Get input command from user
                command = input(f"\n{Fore.GREEN}snatch> {Style.RESET_ALL}").strip()
                if not command:
                    continue

                # Add command to history
                self.history.add(command)

                # Fuzzy match command to handle typos and similar variations
                command = self.fuzzy_match_command(command.lower(), self.valid_commands)

                # Exit condition
                if command.lower() in ("exit", "quit", "q"):
                    print(f"{Fore.YELLOW}Exiting Snatch. Goodbye!{Style.RESET_ALL}")
                    self.running = False
                    continue

                # Help command
                elif command.lower() in ("help", "?"):
                    self.show_help()
                    continue

                # Speed test command
                elif command.lower() in ("speedtest", "speed", "test"):
                    self.snatch_api["run_speedtest"]()
                    continue

                # Clear screen command
                elif command.lower() in ("clear", "cls"):
                    os.system("cls" if self.snatch_api["is_windows"]() else "clear")
                    self.display_banner()
                    continue

                # List supported sites
                elif command.lower() in ("list", "sites"):
                    self.snatch_api["list_supported_sites"]()
                    continue

                # Show history
                elif command.lower() == "history":
                    self.history.show_history()
                    continue

                # Show version
                elif command.lower() == "version":
                    print(f"{Fore.CYAN}Snatch Version: {self.VERSION}{Style.RESET_ALL}")
                    # Check for updates
                    has_update, latest_version, message = self.check_update()
                    if has_update:
                        print(f"{Fore.GREEN}✨ {message}{Style.RESET_ALL}")
                        print(
                            f"{Fore.CYAN}Visit: github.com/Rashed-alothman/Snatch to update{Style.RESET_ALL}"
                        )
                    elif (
                        latest_version
                    ):  # Only show "latest version" if we got a version
                        print(f"{Fore.CYAN}✓ {message}{Style.RESET_ALL}")
                    continue

                # Show config
                elif command.lower() == "config":
                    self.show_config()
                    continue

                # Show system stats
                elif command.lower() == "system-stats":
                    self.display_system_stats()
                    continue

                # For download commands, detect URLs or download-related commands
                elif command.startswith("http") or any(
                    command.lower().startswith(cmd)
                    for cmd in [
                        "download",
                        "dl",
                        "audio",
                        "video",
                        "playlist",
                        "flac",
                        "mp3",
                        "wav",
                        "m4a",
                        "opus",
                    ]
                ):
                    self.process_download_command(command)
                    continue

                # If we get here, it's an unrecognized command
                print(f"{Fore.YELLOW}Unrecognized command: {command}{Style.RESET_ALL}")
                print(
                    f"{Fore.CYAN}Type 'help' or '?' for available commands{Style.RESET_ALL}"
                )

            except KeyboardInterrupt:
                print(
                    f"\n{Fore.YELLOW}Operation cancelled by user. Exiting interactive mode...{Style.RESET_ALL}"
                )
                self.running = False
            except Exception as e:
                print(f"{Fore.RED}An error occurred: {str(e)}{Style.RESET_ALL}")

    def process_download_command(self, command: str) -> None:
        # Forward the entire command to the backend download processor.
        print(f"{Fore.CYAN}Forwarding download command to backend...{Style.RESET_ALL}")
        try:
            result = self.snatch_api["process_download"](command)
            if result:
                print(f"{Fore.GREEN}Download completed: {result}{Style.RESET_ALL}")
            else:
                print(f"{Fore.RED}Download failed. Check the URL or try again.{Style.RESET_ALL}")
        except Exception as e:
            print(f"{Fore.RED}Error processing download command: {str(e)}{Style.RESET_ALL}")

    def show_help(self):
        """Display organized help information based on command categories"""
        term_width = shutil.get_terminal_size().columns
        width = min(term_width - 4, 80)

        print(f"\n{Fore.CYAN}╔{'═' * width}╗")
        print(f"{Fore.CYAN}║ {Fore.GREEN}SNATCH COMMAND REFERENCE{' ' * (width - 23)}║")
        print(f"{Fore.CYAN}╠{'═' * width}╣{Style.RESET_ALL}")

        for category, commands in self.command_categories.items():
            print(
                f"{Fore.CYAN}║ {Fore.YELLOW}{category} Commands:{' ' * (width - len(category) - 10)}║{Style.RESET_ALL}"
            )

            for command, description in commands:
                cmd_str = f"{Fore.GREEN}{command}{Style.RESET_ALL}"
                desc_str = f"{description}"
                padding = width - len(command) - len(description) - 3
                padding = max(1, padding)
                print(
                    f"{Fore.CYAN}║ {cmd_str} {' ' * padding}{desc_str}{' ' * (width - len(command) - len(description) - padding - 3)}{Fore.CYAN}║{Style.RESET_ALL}"
                )

            print(f"{Fore.CYAN}║{' ' * width}║{Style.RESET_ALL}")

        print(f"{Fore.CYAN}╚{'═' * width}╝{Style.RESET_ALL}")
        print(
            f"\n{Fore.CYAN}For more examples, see the full documentation at:{Style.RESET_ALL}"
        )
        print(
            f"{Fore.GREEN}https://github.com/Rashed-alothman/Snatch{Style.RESET_ALL}\n"
        )


# This function is called by Snatch.py to start the interactive mode
def start_interactive_mode(snatch_api):
    """
    Entry point function to start the interactive mode

    Args:
        snatch_api: Dictionary with references to Snatch functions
    """
    interactive = InteractiveMode(snatch_api)

    interactive.run()


# Prevent direct execution
if __name__ == "__main__":
    print(
        f"{Fore.RED}Error: This module should be imported by Snatch.py, not run directly.{Style.RESET_ALL}"
    )
    print(
        f"{Fore.YELLOW}Please run 'python Snatch.py' or 'python Snatch.py --interactive' instead.{Style.RESET_ALL}"
    )
    sys.exit(1)
