import re
import os
import psutil
import time
import shutil
import platform
import logging
import tempfile
import hashlib
import json
import concurrent.futures
from pathlib import Path
from typing import Dict, Any, Optional, List, Union, Callable, Iterator, Tuple
from colorama import Fore, Style
from contextlib import contextmanager

logger = logging.getLogger(__name__)

# Performance monitoring
@contextmanager
def measure_time(operation_name: str, log_level: int = logging.DEBUG) -> Iterator[None]:
    """Context manager to measure execution time of operations.
    
    Args:
        operation_name: Name of the operation being measured
        log_level: Logging level to use for the timing message
        
    Yields:
        None
    """
    start_time = time.time()
    try:
        yield
    finally:
        end_time = time.time()
        elapsed = end_time - start_time
        logger.log(log_level, f"{operation_name} completed in {elapsed:.3f} seconds")

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

def _parse_sites_file(sites_file: Path) -> Tuple[List[str], int]:
    """Helper function to parse the supported sites file.
    
    Args:
        sites_file: Path to the sites file
        
    Returns:
        Tuple[List[str], int]: List of site lines and total sites count
    """
    try:
        with sites_file.open("r", encoding="utf-8") as f:
            lines = [line.strip() for line in f if line.strip()]
    except Exception as e:
        print(f"{Fore.RED}Error reading Supported-sites.txt: {e}{Style.RESET_ALL}")
        return [], 0

    # Skip header lines if they start with "below is a list"
    header_end = 0
    for i, line in enumerate(lines):
        if line.lower().startswith("below is a list"):
            header_end = i + 1
            break
            
    return lines[header_end:], 0

def _build_category_line(line: str, current_category: Optional[str], border: str) -> Tuple[List[str], str, int]:
    """Helper function to handle a category line in sites output.
    
    Args:
        line: Current line from sites data
        current_category: Current category being processed
        border: Formatted border string
        
    Returns:
        Tuple[List[str], str, int]: List of output lines, updated category, and sites count
    """
    output_lines = []
    total_sites = 0
    
    # Skip comment lines
    if line.startswith('"'):
        return output_lines, current_category, total_sites
        
    # Process category:site format
    if ":" in line:
        category, site = map(str.strip, line.split(":", 1))
        cat_upper = category.upper()
        
        # Add category separator if changed
        if current_category != cat_upper:
            if current_category is not None:
                output_lines.append(f"\n{border}\n")
            current_category = cat_upper
            output_lines.append(f"{Fore.MAGENTA}{current_category:^60}{Style.RESET_ALL}")
        
        # Add site if present
        if site:
            output_lines.append(f"{Fore.YELLOW} • {site}{Style.RESET_ALL}")
            total_sites = 1
    else:
        # Handle lines without categories
        output_lines.append(f"{Fore.YELLOW} • {line}{Style.RESET_ALL}")
        total_sites = 1
        
    return output_lines, current_category, total_sites

def _format_sites_output(sites: List[str]) -> Tuple[str, int]:
    """Format the sites list for display.
    
    Args:
        sites: List of site lines from the sites file
        
    Returns:
        Tuple[str, int]: Formatted output string and total sites count
    """
    output_lines = []
    border = f"{Fore.CYAN}{'═' * 60}{Style.RESET_ALL}"
    title = f"{Fore.GREEN}{'SUPPORTED SITES':^60}{Style.RESET_ALL}"
    
    # Add header
    output_lines.append(border)
    output_lines.append(title)
    output_lines.append(border)
    output_lines.append("")

    total_sites = 0
    current_category = None
    
    # Process each line
    for line in sites:
        new_lines, current_category, sites_count = _build_category_line(
            line, current_category, border)
        output_lines.extend(new_lines)
        total_sites += sites_count

    # Add footer
    output_lines.append("")
    output_lines.append(f"{Fore.CYAN}Total supported sites: {total_sites}{Style.RESET_ALL}")
    output_lines.append(border)

    return "\n".join(output_lines), total_sites
    
def list_supported_sites() -> bool:
    """Display a clean, organized list of supported sites with fallback for systems without pager."""
    from pathlib import Path
    import sys

    sites_file = Path("Supported-sites.txt")
    if not sites_file.exists():
        print(f"{Fore.RED}Supported-sites.txt not found. Cannot list supported sites.{Style.RESET_ALL}")
        return False

    # Parse the sites file
    sites, _ = _parse_sites_file(sites_file)
    if not sites:
        return False
        
    # Format the output
    final_output, _ = _format_sites_output(sites)
    
    # Try to use system pager, fall back to print if not available
    try:
        import pydoc
        pydoc.pager(final_output)
    except Exception:  # Specific exception class
        print(final_output)
        
    return True

def sanitize_filename(filename: str) -> str:
    """Sanitize filename by removing invalid characters for all platforms.
    
    Args:
        filename: The filename to sanitize
        
    Returns:
        Sanitized filename suitable for all platforms
    """
    # Remove invalid characters for all platforms
    invalid_chars = r'[<>:"/\\|?*\x00-\x1F]'
    filename = re.sub(invalid_chars, '', filename)
    
    # Replace additional problematic characters
    filename = filename.replace('\t', ' ').replace('\n', ' ').replace('\r', ' ')
    
    # Trim leading/trailing spaces and dots which can cause issues on Windows
    filename = filename.strip(' .')
    
    # Ensure filename is not empty or a reserved name on Windows
    if not filename or filename.lower() in [
        'con', 'prn', 'aux', 'nul', 
        'com1', 'com2', 'com3', 'com4', 'com5', 'com6', 'com7', 'com8', 'com9',
        'lpt1', 'lpt2', 'lpt3', 'lpt4', 'lpt5', 'lpt6', 'lpt7', 'lpt8', 'lpt9'
    ]:
        filename = "download"
    
    # Limit filename length (Windows has a 255 char limit)
    if len(filename) > 240:
        filename = filename[:240]
        
    return filename

def format_size(bytes_value: float, precision: int = 2) -> str:
    """
    Format a size in bytes to a human-readable string.
    
    Args:
        bytes_value: Size in bytes
        precision: Number of decimal places to include
        
    Returns:
        Human-readable size string
    """
    if bytes_value <= 0:
        return "0 B"
    
    suffixes = ['B', 'KB', 'MB', 'GB', 'TB', 'PB', 'EB', 'ZB', 'YB']
    index = 0
    while bytes_value >= 1024 and index < len(suffixes) - 1:
        bytes_value /= 1024
        index += 1
    
    return f"{bytes_value:.{precision}f} {suffixes[index]}"

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
        logger.error(f"Error creating directory {path}: {e}")
        return False

def is_windows() -> bool:
    """Check if running on Windows."""
    return platform.system().lower() == "windows"

def get_platform_specific_path(path: str) -> str:
    """Convert a path to be platform-specific.
    
    Args:
        path: The path to convert
        
    Returns:
        str: A platform-specific path
    """
    return str(Path(path))

def compute_file_hash(filepath: str, algorithm: str = 'sha256', blocksize: int = 65536) -> Optional[str]:
    """
    Compute hash of a file using specified algorithm.
    
    Args:
        filepath: Path to the file
        algorithm: Hash algorithm to use ('md5', 'sha1', 'sha256', etc.)
        blocksize: Size of blocks to read for hashing
        
    Returns:
        Hex digest of the file hash or None if error
    """
    try:
        if not os.path.isfile(filepath):
            return None
            
        hasher = getattr(hashlib, algorithm)()
        with open(filepath, 'rb') as f:
            buf = f.read(blocksize)
            while buf:
                hasher.update(buf)
                buf = f.read(blocksize)
        return hasher.hexdigest()
    except (IOError, OSError, AttributeError) as e:
        logger.error(f"Error computing {algorithm} hash for {filepath}: {e}")
        return None

def _prepare_directory(filepath: str) -> bool:
    """Create the parent directory for a file if it doesn't exist.
    
    Args:
        filepath: Path to the file
        
    Returns:
        bool: True if successful, False otherwise
    """
    directory = os.path.dirname(filepath)
    if not directory:
        return True
        
    if not os.path.exists(directory):
        try:
            os.makedirs(directory, exist_ok=True)
            return True
        except OSError as e:
            logger.error(f"Cannot create directory {directory}: {e}")
            return False
    return True

def _cleanup_temp_file(temp_path: str) -> None:
    """Clean up a temporary file if it exists.
    
    Args:
        temp_path: Path to the temporary file
    """
    if os.path.exists(temp_path):
        try:
            os.unlink(temp_path)
        except OSError as e:
            logger.error(f"Failed to remove temporary file {temp_path}: {e}")

def safe_file_write(filepath: str, content: Union[str, bytes], mode: str = 'w') -> bool:
    """
    Write to a file safely using a temporary file and atomic rename.
    
    Args:
        filepath: Path to the target file
        content: Content to write (string or bytes)
        mode: File mode ('w' for text, 'wb' for binary)
        
    Returns:
        bool: True if successful, False otherwise
    """
    # Ensure binary mode if content is bytes
    if 'b' not in mode and isinstance(content, bytes):
        mode += 'b'
    
    # Prepare the directory
    if not _prepare_directory(filepath):
        return False
    
    try:
        # Create a temporary file in the same directory
        directory = os.path.dirname(filepath)
        fd, temp_path = tempfile.mkstemp(dir=directory or None)
        
        # Write content to the temporary file
        with os.fdopen(fd, mode) as f:
            f.write(content)
        
        # On Windows, remove existing target if it exists
        if is_windows() and os.path.exists(filepath):
            try:
                os.unlink(filepath)
            except OSError as e:
                logger.error(f"Failed to remove existing file {filepath}: {e}")
                _cleanup_temp_file(temp_path)
                return False
                
        # Atomic rename
        os.replace(temp_path, filepath)
        return True
    except Exception as e:
        logger.error(f"Error writing to {filepath}: {e}")
        # Clean up temp file if it exists
        if 'temp_path' in locals():
            _cleanup_temp_file(temp_path)
        return False

def parallel_process(items: List[Any], process_func: Callable, max_workers: Optional[int] = None) -> List[Any]:
    """
    Process items in parallel using a thread pool.
    
    Args:
        items: List of items to process
        process_func: Function to apply to each item
        max_workers: Maximum number of worker threads (default: CPU count)
        
    Returns:
        List of results in the same order as input items
    """
    if not items:
        return []
        
    if max_workers is None:
        max_workers = min(32, (os.cpu_count() or 4) + 4)
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        # Submit all tasks and create a future-to-index mapping
        future_to_index = {executor.submit(process_func, item): i for i, item in enumerate(items)}
        results = [None] * len(items)
        
        # Process results as they complete
        for future in concurrent.futures.as_completed(future_to_index):
            index = future_to_index[future]
            try:
                results[index] = future.result()
            except Exception as e:
                logger.error(f"Error processing item {index}: {e}")
                results[index] = None
                
    return results

def get_free_space(path: str) -> int:
    """
    Get free space in bytes for the drive containing the specified path.
    
    Args:
        path: Path to check free space for
        
    Returns:
        int: Free space in bytes
    """
    try:
        if not os.path.exists(path):
            # If path doesn't exist, check its parent directory
            path = os.path.dirname(path)
            # If that still doesn't exist, use current directory
            if not path or not os.path.exists(path):
                path = '.'
                
        return shutil.disk_usage(path).free
    except Exception as e:
        logger.error(f"Error getting free space for {path}: {e}")
        return 0

def create_dir_with_mode(path: str, mode: int = 0o755) -> bool:
    """
    Create a directory with specific permissions.
    
    Args:
        path: Directory path to create
        mode: Directory permissions mode
        
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        os.makedirs(path, mode=mode, exist_ok=True)
        return True
    except Exception as e:
        logger.error(f"Error creating directory {path} with mode {mode:o}: {e}")
        return False

def safe_json_read(filepath: str, default: Any = None) -> Any:
    """
    Safely read a JSON file with error handling and backup creation if corrupted.
    
    Args:
        filepath: Path to the JSON file
        default: Default value to return if file is missing or corrupted
        
    Returns:
        Parsed JSON data or default value if error
    """
    if not os.path.exists(filepath):
        return default
        
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError, UnicodeDecodeError) as e:
        logger.error(f"Error reading JSON file {filepath}: {e}")
        
        # Create backup of corrupted file
        try:
            backup_path = f"{filepath}.corrupted"
            shutil.copy2(filepath, backup_path)
            logger.info(f"Created backup of corrupted file at {backup_path}")
        except Exception as be:
            logger.error(f"Error creating backup of corrupted file: {be}")
            
        return default