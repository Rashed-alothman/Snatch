import re
import os
import psutil
from colorama import Fore, Style
import shutil
import platform

def print_banner():
    """Display an enhanced colorful welcome banner with snake logo and performance optimizations"""
    terminal_width = shutil.get_terminal_size().columns
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
║     {Fore.GREEN}■ {Fore.WHITE}Version: {Fore.YELLOW}1.7.0{Fore.WHITE}                                   {Fore.CYAN}  ║
║     {Fore.GREEN}■ {Fore.WHITE}GitHub : {Fore.YELLOW}github.com/Rashed-alothman/Snatch{Fore.WHITE}        {Fore.CYAN} ║
╠{'═' * 58}╣
║  {Fore.YELLOW}Type {Fore.GREEN}help{Fore.YELLOW} or {Fore.GREEN}?{Fore.YELLOW} for commands  {Fore.WHITE}|  {Fore.YELLOW}Press {Fore.GREEN}Ctrl+C{Fore.YELLOW} to cancel  {Fore.CYAN}║
╚{'═' * 58}╝{Style.RESET_ALL}"""

    # Calculate padding for centering
    lines = banner.split("\n")
    max_content_width = max(
        (len(re.sub(r"\x1b\[[0-9;]+m", "", line)) for line in lines if line), default=0
    )
    padding = max(0, (terminal_width - max_content_width) // 2)

    # Print banner with padding
    print("\n" * 2)  # Add some space above banner
    for line in banner.split("\n"):
        if line:
            print(" " * padding + line)
    print("\n")  # Add space below banner

def display_system_stats():
    """Display detailed system resource statistics"""
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
    print(f"{Fore.YELLOW}Total Memory:{Style.RESET_ALL} {mem.total / (1024**3):.2f} GB")
    print(
        f"{Fore.YELLOW}Available Memory:{Style.RESET_ALL} {mem.available / (1024**3):.2f} GB"
    )
    print(f"{Fore.YELLOW}Used Memory:{Style.RESET_ALL} {mem.used / (1024**3):.2f} GB")

    # Disk information
    print(f"\n{Fore.YELLOW}Disk Information:{Style.RESET_ALL}")
    for part in psutil.disk_partitions(all=False):
        if os.name == "nt" and "cdrom" in part.opts or part.fstype == "":
            # Skip CD-ROM drives with no disk or other special drives
            continue
        usage = psutil.disk_usage(part.mountpoint)
        print(f"  {Fore.CYAN}Drive {part.mountpoint}{Style.RESET_ALL}")
        print(f"    Total: {usage.total / (1024**3):.2f} GB")
        print(f"    Used: {usage.used / (1024**3):.2f} GB ({usage.percent}%)")
        print(f"    Free: {usage.free / (1024**3):.2f} GB")

def list_supported_sites() -> bool:
    """Display a clean, organized list of supported sites with fallback for systems without pager."""
    from pathlib import Path
    import sys

    sites_file = Path("Supported-sites.txt")
    if not sites_file.exists():
        print(f"{Fore.RED}Supported-sites.txt not found. Cannot list supported sites.{Style.RESET_ALL}")
        return False

    try:
        with sites_file.open("r", encoding="utf-8") as f:
            lines = [line.strip() for line in f if line.strip()]
    except Exception as e:
        print(f"{Fore.RED}Error reading Supported-sites.txt: {e}{Style.RESET_ALL}")
        return False

    # Skip header lines if they start with "below is a list"
    header_end = 0
    for i, line in enumerate(lines):
        if line.lower().startswith("below is a list"):
            header_end = i + 1
            break
    sites = lines[header_end:]

    output_lines = []
    border = f"{Fore.CYAN}{'═' * 60}{Style.RESET_ALL}"
    title = f"{Fore.GREEN}{'SUPPORTED SITES':^60}{Style.RESET_ALL}"
    output_lines.append(border)
    output_lines.append(title)
    output_lines.append(border)
    output_lines.append("")

    total_sites = 0
    current_category = None
    category_separator = f"\n{border}\n"
    
    for line in sites:
        if line.startswith('"'):
            continue
        if ":" in line:
            category, site = map(str.strip, line.split(":", 1))
            cat_upper = category.upper()
            if current_category != cat_upper:
                if current_category is not None:
                    output_lines.append(category_separator)
                current_category = cat_upper
                output_lines.append(f"{Fore.MAGENTA}{current_category:^60}{Style.RESET_ALL}")
            if site:
                output_lines.append(f"{Fore.YELLOW} • {site}{Style.RESET_ALL}")
                total_sites += 1
        else:
            output_lines.append(f"{Fore.YELLOW} • {line}{Style.RESET_ALL}")
            total_sites += 1

    output_lines.append("")
    output_lines.append(f"{Fore.CYAN}Total supported sites: {total_sites}{Style.RESET_ALL}")
    output_lines.append(border)

    final_output = "\n".join(output_lines)
    
    # Try to use system pager, fall back to print if not available
    try:
        import pydoc
        pydoc.pager(final_output)
    except:
        print(final_output)
        
    return True

def sanitize_filename(filename: str) -> str:
    """Sanitize filename by removing invalid characters"""
    # Remove invalid characters
    invalid_chars = r'[<>:"/\\|?*]'
    filename = re.sub(invalid_chars, '', filename)
    
    # Remove control characters
    filename = "".join(char for char in filename if ord(char) >= 32)
    
    # Ensure filename is not empty
    if not filename:
        filename = "download"
        
    return filename.strip()

def ensure_dir(path: str) -> bool:
    """
    Ensure a directory exists, creating it if necessary.
    
    Args:
        path: The directory path to create
        
    Returns:
        bool: True if directory exists or was created successfully, False otherwise
        
    Raises:
        OSError: If there is an error creating the directory
    """
    try:
        os.makedirs(path, exist_ok=True)
        return True
    except OSError as e:
        print(f"{Fore.RED}Error creating directory {path}: {e}{Style.RESET_ALL}")
        return False

def is_windows() -> bool:
    """Check if running on Windows."""
    return platform.system().lower() == "windows"