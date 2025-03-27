#!/usr/bin/env python
import os
import sys
import re
import time
import shutil
import platform
from pathlib import Path
from typing import List, Dict, Any, Optional

# Try importing required packages
try:
    from colorama import init, Fore, Style
    init(autoreset=True)
except ImportError:
    # Create simple color functions if colorama isn't available
    class DummyFore:
        def __getattr__(self, _): return ""
    class DummyStyle:
        def __getattr__(self, _): return ""
    Fore = DummyFore()
    Style = DummyStyle()

# Import local module if available
try:
    from Snatch import DownloadManager, load_config, EnhancedSpinnerAnimation
except ImportError:
    print("Error: Could not import from Snatch.py. Make sure you're in the correct directory.")
    sys.exit(1)

class InteractiveMode:
    """Enhanced interactive command system for Snatch"""
    
    def __init__(self):
        self.config = load_config()
        self.download_manager = DownloadManager(self.config)
        self.history = []
        self.running = True
        self.terminal_width = shutil.get_terminal_size().columns
        
        # Command categories for help menu
        self.command_categories = {
            "Basic": [
                ("URL", "Download media from URL in best quality"),
                ("URL mp3", "Download audio in MP3 format"),
                ("URL flac", "Download audio in FLAC format"),
                ("URL 720|1080|2160", "Download video in specific resolution")
            ],
            "Utility": [
                ("help", "Show this help menu"),
                ("clear", "Clear the screen"),
                ("history", "Show command history"),
                ("version", "Show version information"),
                ("exit", "Exit the program")
            ],
            "Advanced": [
                ("playlist URL", "Download entire playlist with options"),
                ("batch file.txt", "Process batch file with URLs"),
                ("config", "Show current configuration"),
                ("stats", "Show system statistics")
            ]
        }

    def print_banner(self):
        """Print colorful banner with version information"""
        banner = f"""
{Fore.CYAN}╔{'═' * 58}╗
║  {Fore.GREEN}             ____  {Fore.YELLOW}               _        _      {Fore.CYAN}      ║
║  {Fore.GREEN}    _____  / ___| {Fore.YELLOW}_ __    __ _  | |_   __| |__   {Fore.CYAN}       ║
║  {Fore.GREEN}   |_____| \\___ \\ {Fore.YELLOW}| '_ \\  / _` | | __| / _` / /   {Fore.CYAN}      ║
║  {Fore.GREEN}   |_____| |___) |{Fore.YELLOW}| | | || (_| | | |_ | (_| \\ \\   {Fore.CYAN}      ║
║  {Fore.GREEN}           |____/ {Fore.YELLOW}|_| |_| \\__,_|  \\__| \\__,_/_/   {Fore.CYAN}      ║
║  {Fore.GREEN}    /^ ^\\   ___  {Fore.YELLOW}                                  {Fore.CYAN}     ║
║  {Fore.GREEN}   / 0 0 \\ / _ \\ {Fore.YELLOW}        Download Anything!       {Fore.CYAN}      ║
║  {Fore.GREEN}   V\\ Y /V / (_) |{Fore.YELLOW}                                {Fore.CYAN}      ║
║  {Fore.GREEN}    / - \\  \\___/ {Fore.YELLOW}      ~ Videos & Music ~        {Fore.CYAN}       ║
║  {Fore.GREEN}   /    |         {Fore.YELLOW}                                {Fore.CYAN}      ║
║  {Fore.GREEN}  *___/||         {Fore.YELLOW}                                {Fore.CYAN}      ║
╠{'═' * 58}╣
║     {Fore.GREEN}■ {Fore.WHITE}Version: {Fore.YELLOW}1.2.0{Fore.WHITE}                                   {Fore.CYAN}  ║
║     {Fore.GREEN}■ {Fore.WHITE}Author : {Fore.YELLOW}Rashed Alothman{Fore.WHITE}                           {Fore.CYAN}║
║     {Fore.GREEN}■ {Fore.WHITE}GitHub : {Fore.YELLOW}github.com/Rashed-alothman/Snatch{Fore.WHITE}        {Fore.CYAN} ║
╠{'═' * 58}╣
║  {Fore.YELLOW}Type {Fore.GREEN}help{Fore.YELLOW} for commands  {Fore.WHITE}|  {Fore.YELLOW}Press {Fore.GREEN}Ctrl+C{Fore.YELLOW} to cancel  {Fore.CYAN}║
╚{'═' * 58}╝{Style.RESET_ALL}"""
        
        print('\n' * 1)
        # Center the banner
        for line in banner.split('\n'):
            if line.strip():
                print(line.center(self.terminal_width))
        print()

    def show_help(self):
        """Display organized help menu with command categories"""
        width = min(self.terminal_width - 4, 80)
        
        print(f"\n{Fore.CYAN}╔{'═' * width}╗")
        print(f"{Fore.CYAN}║ {Fore.GREEN}SNATCH INTERACTIVE MODE COMMANDS{Fore.CYAN}{' ' * (width - 30)}║")
        print(f"{Fore.CYAN}╠{'═' * width}╣{Style.RESET_ALL}")
        
        # Print each category
        for category, commands in self.command_categories.items():
            print(f"{Fore.CYAN}║ {Fore.YELLOW}{category} Commands:{' ' * (width - len(category) - 11)}{Fore.CYAN}║{Style.RESET_ALL}")
            print(f"{Fore.CYAN}║{Style.RESET_ALL}")
            
            for cmd, desc in commands:
                # Calculate padding to align descriptions
                cmd_display = f"  {Fore.GREEN}{cmd}{Style.RESET_ALL}"
                padding = 25 - len(cmd)
                
                # Ensure we don't have negative padding
                if padding < 1:
                    padding = 1
                    
                desc_start = f"{' ' * padding}{Fore.WHITE}{desc}"
                
                # Handle long descriptions with wrapping
                if len(cmd) + padding + len(desc) > width - 5:
                    print(f"{Fore.CYAN}║{Style.RESET_ALL} {cmd_display}{' ' * padding}{desc[:width - len(cmd) - padding - 5]}...{Fore.CYAN} ║{Style.RESET_ALL}")
                else:
                    print(f"{Fore.CYAN}║{Style.RESET_ALL} {cmd_display}{' ' * padding}{desc}{' ' * (width - len(cmd) - len(desc) - padding - 2)}{Fore.CYAN}║{Style.RESET_ALL}")
            
            print(f"{Fore.CYAN}║{' ' * width}║{Style.RESET_ALL}")
            
        print(f"{Fore.CYAN}╚{'═' * width}╝{Style.RESET_ALL}")
        print()

    def show_stats(self):
        """Display system stats and app configuration"""
        try:
            import psutil
            # Get system information
            cpu_percent = psutil.cpu_percent(interval=1)
            memory = psutil.virtual_memory()
            disk = psutil.disk_usage('/')
            
            width = min(self.terminal_width - 4, 80)
            
            print(f"\n{Fore.CYAN}╔{'═' * width}╗")
            print(f"{Fore.CYAN}║ {Fore.GREEN}SYSTEM STATISTICS{Fore.CYAN}{' ' * (width - 18)}║")
            print(f"{Fore.CYAN}╠{'═' * width}╣{Style.RESET_ALL}")
            
            # System info
            print(f"{Fore.CYAN}║ {Fore.YELLOW}System Information:{' ' * (width - 20)}{Fore.CYAN}║{Style.RESET_ALL}")
            print(f"{Fore.CYAN}║{Style.RESET_ALL}   {Fore.GREEN}CPU Usage:{Style.RESET_ALL}     {cpu_percent}%{' ' * (width - 18 - len(str(cpu_percent)))}{Fore.CYAN}║{Style.RESET_ALL}")
            print(f"{Fore.CYAN}║{Style.RESET_ALL}   {Fore.GREEN}Memory Usage:{Style.RESET_ALL}  {memory.percent}% ({memory.used // (1024**2)} MB used of {memory.total // (1024**2)} MB){' ' * (width - 53)}{Fore.CYAN}║{Style.RESET_ALL}")
            print(f"{Fore.CYAN}║{Style.RESET_ALL}   {Fore.GREEN}Disk Usage:{Style.RESET_ALL}    {disk.percent}% ({disk.used // (1024**3)} GB used of {disk.total // (1024**3)} GB){' ' * (width - 51)}{Fore.CYAN}║{Style.RESET_ALL}")
            print(f"{Fore.CYAN}║{Style.RESET_ALL}   {Fore.GREEN}Platform:{Style.RESET_ALL}      {platform.system()} {platform.release()}{' ' * (width - 20 - len(platform.system()) - len(platform.release()))}{Fore.CYAN}║{Style.RESET_ALL}")
            print(f"{Fore.CYAN}║{Style.RESET_ALL}   {Fore.GREEN}Python:{Style.RESET_ALL}        {platform.python_version()}{' ' * (width - 17 - len(platform.python_version()))}{Fore.CYAN}║{Style.RESET_ALL}")
            
            # Config info
            print(f"{Fore.CYAN}║{' ' * width}║{Style.RESET_ALL}")
            print(f"{Fore.CYAN}║ {Fore.YELLOW}Configuration:{' ' * (width - 15)}{Fore.CYAN}║{Style.RESET_ALL}")
            print(f"{Fore.CYAN}║{Style.RESET_ALL}   {Fore.GREEN}Video Output:{Style.RESET_ALL}  {self.config['video_output']}{' ' * max(2, width - 17 - len(str(self.config['video_output'])))}{Fore.CYAN}║{Style.RESET_ALL}")
            print(f"{Fore.CYAN}║{Style.RESET_ALL}   {Fore.GREEN}Audio Output:{Style.RESET_ALL}  {self.config['audio_output']}{' ' * max(2, width - 17 - len(str(self.config['audio_output'])))}{Fore.CYAN}║{Style.RESET_ALL}")
            print(f"{Fore.CYAN}║{Style.RESET_ALL}   {Fore.GREEN}FFmpeg Path:{Style.RESET_ALL}   {self.config['ffmpeg_location']}{' ' * max(2, width - 16 - len(str(self.config['ffmpeg_location'])))}{Fore.CYAN}║{Style.RESET_ALL}")
            print(f"{Fore.CYAN}║{Style.RESET_ALL}   {Fore.GREEN}Max Concurrent:{Style.RESET_ALL} {self.config['max_concurrent']}{' ' * (width - 19 - len(str(self.config['max_concurrent'])))}{Fore.CYAN}║{Style.RESET_ALL}")
            
            print(f"{Fore.CYAN}╚{'═' * width}╝{Style.RESET_ALL}")
            
        except ImportError:
            print(f"{Fore.RED}Could not load system statistics. psutil module not found.")
        except Exception as e:
            print(f"{Fore.RED}Error displaying statistics: {str(e)}")

    def process_command(self, command: str) -> bool:
        """Process a user command with enhanced features"""
        if not command.strip():
            return True
            
        # Add to history
        self.history.append(command)
        if len(self.history) > 50:  # Limit history size
            self.history.pop(0)
            
        # Split command into parts
        parts = command.split()
        cmd = parts[0].lower() if parts else ""
        
        # Handle built-in commands
        if cmd in ['exit', 'quit', 'q']:
            print(f"{Fore.YELLOW}Exiting Snatch...{Style.RESET_ALL}")
            return False
            
        elif cmd in ['help', '?']:
            self.show_help()
            return True
            
        elif cmd in ['clear', 'cls']:
            os.system('cls' if platform.system() == 'Windows' else 'clear')
            self.print_banner()
            return True
            
        elif cmd == 'history':
            print(f"\n{Fore.CYAN}Command History:{Style.RESET_ALL}")
            for i, hist_cmd in enumerate(self.history, 1):
                print(f"{i}. {hist_cmd}")
            return True
            
        elif cmd == 'version':
            print(f"{Fore.GREEN}Snatch version 1.2.0{Style.RESET_ALL}")
            return True
            
        elif cmd == 'stats':
            self.show_stats()
            return True
            
        elif cmd == 'config':
            print(f"\n{Fore.CYAN}Current Configuration:{Style.RESET_ALL}")
            for key, value in self.config.items():
                print(f"{key}: {value}")
            return True
            
        # Handle URL downloads
        elif '://' in command:
            # Extract URL - either the whole command or part until the first space
            url_end = command.find(' ')
            if url_end == -1:
                url = command
                options = []
            else:
                url = command[:url_end]
                options = command[url_end+1:].split()
                
            # Process download with spinner
            spinner = EnhancedSpinnerAnimation("Processing download", style="aesthetic")
            spinner.start()
            
            try:
                # Process options
                kwargs = {}
                for option in options:
                    option = option.lower()
                    if option in ['mp3', 'flac', 'wav', 'm4a']:
                        kwargs['audio_only'] = True
                        kwargs['audio_format'] = option
                    elif option in ['720', '1080', '2160', '4k']:
                        kwargs['resolution'] = '2160' if option == '4k' else option
                
                # Start download
                success = self.download_manager.download(url, **kwargs)
                spinner.stop(clear=True)
                
                if success:
                    print(f"\n{Fore.GREEN}✓ Download completed successfully!{Style.RESET_ALL}")
                else:
                    print(f"\n{Fore.RED}✗ Download failed. Check logs for details.{Style.RESET_ALL}")
                    
            except Exception as e:
                spinner.stop(clear=True, success=False)
                print(f"\n{Fore.RED}Error: {str(e)}{Style.RESET_ALL}")
                
            return True
            
        # Handle batch commands
        elif cmd == 'batch' and len(parts) > 1:
            batch_file = parts[1]
            if not os.path.exists(batch_file):
                print(f"{Fore.RED}Error: Batch file '{batch_file}' not found.{Style.RESET_ALL}")
                return True
                
            try:
                with open(batch_file, 'r') as f:
                    urls = []
                    for line in f:
                        line = line.strip()
                        if line and not line.startswith('#') and '://' in line:
                            urls.append(line)
                            
                if not urls:
                    print(f"{Fore.YELLOW}No valid URLs found in batch file.{Style.RESET_ALL}")
                    return True
                    
                print(f"{Fore.CYAN}Found {len(urls)} URLs in batch file.{Style.RESET_ALL}")
                if input(f"Do you want to download all of them? (y/n): ").lower() == 'y':
                    self.download_manager.batch_download(urls)
                    
            except Exception as e:
                print(f"{Fore.RED}Error processing batch file: {str(e)}{Style.RESET_ALL}")
                
            return True
            
        # Handle unknown commands
        else:
            print(f"{Fore.YELLOW}Unknown command: '{command}'{Style.RESET_ALL}")
            print(f"Type {Fore.GREEN}help{Style.RESET_ALL} to see available commands.")
            return True

    def run(self):
        """Run the interactive shell"""
        self.print_banner()
        
        while self.running:
            try:
                # Show enhanced prompt with emoji based on platform
                emoji = "🐍" if platform.system() != "Windows" else ">"
                command = input(f"{Fore.GREEN}{emoji} {Style.RESET_ALL}")
                self.running = self.process_command(command)
                
            except KeyboardInterrupt:
                print(f"\n{Fore.YELLOW}Operation cancelled. Type 'exit' to quit.{Style.RESET_ALL}")
                
            except EOFError:
                print(f"\n{Fore.YELLOW}Exiting Snatch...{Style.RESET_ALL}")
                break
                
            except Exception as e:
                print(f"\n{Fore.RED}Error: {str(e)}{Style.RESET_ALL}")

if __name__ == "__main__":
    interactive = InteractiveMode()
    interactive.run()
