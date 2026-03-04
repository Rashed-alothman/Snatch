#!/usr/bin/env python3
"""Network diagnostics and speed testing module for Snatch.

This module provides comprehensive network diagnostics, including:
- Internet connectivity testing
- Speed testing with detailed metrics
- Server latency measurement
- Connection stability analysis
- NAT type detection
- Network interface enumeration
- Bandwidth throttling capabilities
"""

import asyncio
import json
import logging
import os
import re
import time
import socket
import ipaddress
import platform
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union, Set
import aiohttp
import aiofiles
import netifaces
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TimeElapsedColumn, TextColumn
from rich.table import Table
from rich.panel import Panel
from rich.layout import Layout
from rich.text import Text
from rich import box  # Added for box styles
from colorama import Fore, Style

from .defaults import CACHE_DIR, speedtestresult
from .progress import SpinnerAnimation
from .common_utils import ensure_dir, format_size

# Configure logging
logger = logging.getLogger(__name__)
console = Console()

@dataclass
class SpeedTestResult:
    """Represents a network speed test result with enhanced metrics"""
    download_mbps: float
    upload_mbps: float 
    ping_ms: float
    timestamp: float = field(default_factory=time.time)
    server_id: Optional[str] = None
    server_name: Optional[str] = None
    jitter_ms: Optional[float] = None
    packet_loss: Optional[float] = None
    isp: Optional[str] = None
    latencies: Optional[Dict[str, float]] = None
    
    @property
    def is_good_for_streaming(self) -> bool:
        """Check if connection is suitable for HD streaming"""
        return (
            self.download_mbps >= 5.0 
            and self.ping_ms < 100 
            and (self.packet_loss is None or self.packet_loss < 2.0)
        )
    
    @property
    def is_good_for_video_calls(self) -> bool:
        """Check if connection is suitable for video calls"""
        return (
            self.download_mbps >= 1.5 
            and self.upload_mbps >= 1.5
            and self.ping_ms < 150
            and (self.jitter_ms is None or self.jitter_ms < 30)
        )
    
    def get_quality_rating(self) -> int:
        """Get connection quality rating from 1-5"""
        if self.download_mbps < 1.0:
            return 1
        elif self.download_mbps < 5.0:
            return 2
        elif self.download_mbps < 15.0:
            return 3
        elif self.download_mbps < 50.0:
            return 4
        else:
            return 5

@dataclass
class NetworkInterface:
    """Information about a network interface"""
    name: str
    ip_addresses: List[str]
    mac_address: Optional[str] = None
    is_up: bool = True
    mtu: Optional[int] = None
    speed_mbps: Optional[int] = None
    is_loopback: bool = False
    is_wireless: bool = False
    
    @property
    def primary_ip(self) -> Optional[str]:
        """Get primary IP address (first non-loopback)"""
        for ip in self.ip_addresses:
            if not ip.startswith("127."):
                return ip
        return self.ip_addresses[0] if self.ip_addresses else None
        
class NetworkManager:
    """Handles all network-related operations for the application"""
    
    def __init__(self, config: Dict[str, Any]):
        """Initialize the network manager"""
        self.config = config
        self.cache_dir = config.get('cache_directory', CACHE_DIR)
        self.speed_test_cache = os.path.join(self.cache_dir, "speedtest_results.json")
        self.last_speed_test = None
        self.connection_status = False
        self.last_connection_check = 0
        self.connection_check_interval = 60  # seconds
        
        # Advanced configuration
        self.test_servers = config.get('speedtest_servers', [])
        self.timeout = config.get('network_timeout', 10)
        self.retry_count = config.get('network_retries', 3)
        self.packet_count = config.get('ping_packet_count', 5)
        self.bandwidth_limit = config.get('bandwidth_limit_mbps', None)
        
        # Initialize the cache directory
        ensure_dir(self.cache_dir)
        
        # Load previous speed test results
        self._load_speed_test_cache()
    
    def _load_speed_test_cache(self) -> None:
        """Load cached speed test results"""
        if os.path.exists(self.speed_test_cache):
            try:
                with open(self.speed_test_cache, 'r') as f:
                    data = json.load(f)
                    self.last_speed_test = SpeedTestResult(
                        download_mbps=data.get('download_mbps', 0),
                        upload_mbps=data.get('upload_mbps', 0),
                        ping_ms=data.get('ping_ms', 0),
                        timestamp=data.get('timestamp', 0),
                        server_id=data.get('server_id'),
                        server_name=data.get('server_name'),
                        jitter_ms=data.get('jitter_ms'),
                        packet_loss=data.get('packet_loss'),
                        isp=data.get('isp'),
                        latencies=data.get('latencies')
                    )
                    logger.debug("Loaded cached speed test results")
            except Exception as e:
                logger.warning(f"Failed to load speed test cache: {e}")
    
    async def _save_speed_test_cache(self) -> None:
        """Save speed test results to cache using async file I/O"""
        if self.last_speed_test:
            try:
                data = {
                    'download_mbps': self.last_speed_test.download_mbps,
                    'upload_mbps': self.last_speed_test.upload_mbps,
                    'ping_ms': self.last_speed_test.ping_ms,
                    'timestamp': self.last_speed_test.timestamp,
                    'server_id': self.last_speed_test.server_id,
                    'server_name': self.last_speed_test.server_name,
                    'jitter_ms': self.last_speed_test.jitter_ms,
                    'packet_loss': self.last_speed_test.packet_loss,
                    'isp': self.last_speed_test.isp,
                    'latencies': self.last_speed_test.latencies
                }
                
                # Ensure directory exists
                os.makedirs(os.path.dirname(self.speed_test_cache), exist_ok=True)
                
                # Use async file I/O for better performance
                async with aiofiles.open(self.speed_test_cache, 'w') as f:
                    await f.write(json.dumps(data, indent=2))
                logger.debug("Saved speed test results to cache")
            except Exception as e:
                logger.warning(f"Failed to save speed test cache: {e}")
    
    async def check_connection(self) -> bool:
        """Check if internet connection is available with caching"""
        # Use cached result if recent
        current_time = time.time()
        if current_time - self.last_connection_check < self.connection_check_interval:
            return self.connection_status
            
        self.connection_status = await self._perform_connection_check()
        self.last_connection_check = current_time
        return self.connection_status
        
    async def _perform_connection_check(self) -> bool:
        """Perform actual connection check"""
        # Check multiple reliable endpoints
        test_endpoints = [
            "https://www.google.com",
            "https://www.cloudflare.com",
            "https://www.microsoft.com",
            "https://www.apple.com"
        ]
        
        # Try to connect to each with a short timeout
        timeout = aiohttp.ClientTimeout(total=3)
        for endpoint in test_endpoints:
            try:
                async with aiohttp.ClientSession(timeout=timeout) as session:
                    async with session.head(endpoint) as response:
                        if response.status < 400:
                            return True
            except Exception as e:
                # Just try the next endpoint
                logger.debug(f"Connection check failed for {endpoint}: {e}")
                continue
                
        return False
    
    async def get_connection_info(self) -> Dict[str, Any]:
        """Get detailed connection information"""
        is_connected = await self.check_connection()
        
        # Build info dictionary
        info = {
            "connected": is_connected,
            "interfaces": await self.get_network_interfaces(),
            "last_speed_test": self.last_speed_test.__dict__ if self.last_speed_test else None,
            "gateway_ip": await self.get_default_gateway(),
            "dns_servers": await self.get_dns_servers(),
            "public_ip": await self.get_public_ip() if is_connected else None,
            "hostname": socket.gethostname(),
            "platform": platform.system()
        }
        
        return info
    
    async def get_network_interfaces(self) -> List[NetworkInterface]:
        """Get information about network interfaces"""
        interfaces = []
        
        try:
            # Get interface info using netifaces
            for iface_name in netifaces.interfaces():
                addresses = netifaces.ifaddresses(iface_name)
                
                # Skip interfaces with no IPv4 address
                if netifaces.AF_INET not in addresses:
                    continue
                
                # Get IPv4 addresses
                ip_addresses = [addr['addr'] for addr in addresses[netifaces.AF_INET]]
                
                # Get MAC address if available
                mac_address = None
                if netifaces.AF_LINK in addresses and addresses[netifaces.AF_LINK]:
                    mac_address = addresses[netifaces.AF_LINK][0].get('addr')
                
                # Determine if interface is up
                is_up = True  # Assume up if it has addresses
                
                # Try to determine if wireless (platform-specific)
                is_wireless = self._is_wireless_interface(iface_name)
                
                # Determine if loopback
                is_loopback = all(ip.startswith("127.") for ip in ip_addresses)
                
                interface = NetworkInterface(
                    name=iface_name,
                    ip_addresses=ip_addresses,
                    mac_address=mac_address,
                    is_up=is_up,
                    is_loopback=is_loopback,
                    is_wireless=is_wireless
                )
                
                interfaces.append(interface)
                
        except Exception as e:
            logger.error(f"Failed to get network interfaces: {e}")
            
        return interfaces
    
    def _is_wireless_interface(self, iface_name: str) -> bool:
        """Determine if an interface is wireless based on platform-specific rules"""
        if platform.system() == "Windows":
            return "wi-fi" in iface_name.lower() or "wireless" in iface_name.lower()
        elif platform.system() == "Linux":
            return iface_name.startswith("wl")
        elif platform.system() == "Darwin":  # macOS
            return iface_name.startswith("en") and not iface_name.startswith("en0")
        return False
        
    async def get_default_gateway(self) -> Optional[str]:
        """Get default gateway IP address"""
        try:
            gateways = netifaces.gateways()
            default_gateway = gateways.get('default')
            if default_gateway and netifaces.AF_INET in default_gateway:
                return default_gateway[netifaces.AF_INET][0]
        except Exception as e:
            logger.error(f"Failed to get default gateway: {e}")
            
        return None
        
    async def get_dns_servers(self) -> List[str]:
        """Get list of DNS servers"""
        dns_servers = []
        
        try:
            # Get DNS servers based on platform
            if platform.system() == "Windows":
                dns_servers = self._get_windows_dns_servers()
            else:
                dns_servers = self._get_unix_dns_servers()
        except Exception as e:
            logger.error(f"Failed to get DNS servers: {e}")
            
        return dns_servers
    
    def _get_windows_dns_servers(self) -> List[str]:
        """Get DNS servers on Windows"""
        dns_servers = []
        output = os.popen("ipconfig /all").read()
        for line in output.splitlines():
            if "DNS Servers" in line:
                dns_server = line.split(":")[-1].strip()
                if dns_server and not dns_server.startswith("fec0"):
                    dns_servers.append(dns_server)
        return dns_servers
    
    def _get_unix_dns_servers(self) -> List[str]:
        """Get DNS servers on Unix/Linux/macOS"""
        dns_servers = []
        # Read /etc/resolv.conf on Unix/Linux
        if os.path.exists("/etc/resolv.conf"):
            with open("/etc/resolv.conf", "r") as f:
                for line in f:
                    if line.startswith("nameserver"):
                        dns_server = line.split()[1].strip()
                        dns_servers.append(dns_server)
        return dns_servers
    
    async def get_public_ip(self) -> Optional[str]:
        """Get public IP address"""
        # Try multiple IP detection services
        services = [
            "https://api.ipify.org",
            "https://ifconfig.me/ip",
            "https://icanhazip.com"
        ]
        
        for service in services:
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.get(service, timeout=5) as response:
                        if response.status == 200:
                            ip = await response.text()
                            return ip.strip()
            except Exception as e:
                logger.debug(f"IP detection failed for {service}: {e}")
                continue
                
        logger.error("Failed to get public IP from any service")
        return None
    
    async def run_speed_test(self, console: Optional[Console] = None, detailed: bool = True) -> Optional[SpeedTestResult]:
        """Run a network speed test with progress reporting
        
        Args:
            console: Rich console for output
            detailed: Whether to run a detailed test
            
        Returns:
            SpeedTestResult object or None on failure
        """
        # Check for connection first
        if not await self.check_connection():
            if console:
                console.print("[bold red]No internet connection available[/]")
            return None
            
        if console:
            console.print("[bold cyan]Starting network speed test...[/]")
            
        # Create progress display
        progress = Progress(
            SpinnerColumn(),
            TextColumn("[bold blue]{task.description}"),
            TimeElapsedColumn(),
            console=console or Console()
        )
        
        download_mbps = 0
        upload_mbps = 0
        ping_ms = 0
        jitter_ms = 0
        packet_loss = 0
        
        try:
            with progress:
                # Test ping first
                ping_task = progress.add_task("[cyan]Testing ping latency...", total=None)
                ping_ms, jitter_ms = await self._test_ping(["8.8.8.8", "1.1.1.1"])
                progress.update(ping_task, completed=True)
                
                # Test download speed
                download_task = progress.add_task("[green]Testing download speed...", total=None)
                download_mbps = await self._test_download_speed()
                progress.update(download_task, completed=True)
                
                # Test upload speed
                upload_task = progress.add_task("[yellow]Testing upload speed...", total=None)
                upload_mbps = await self._test_upload_speed()
                progress.update(upload_task, completed=True)
                
                if detailed:
                    # Test packet loss
                    packet_task = progress.add_task("[magenta]Testing packet loss...", total=None)
                    packet_loss = await self._test_packet_loss()
                    progress.update(packet_task, completed=True)
        
            # Create result object
            result = SpeedTestResult(
                download_mbps=download_mbps,
                upload_mbps=upload_mbps,
                ping_ms=ping_ms,
                jitter_ms=jitter_ms,
                packet_loss=packet_loss,
                timestamp=time.time()
            )
            
            # Cache the result
            self.last_speed_test = result
            await self._save_speed_test_cache()
            
            # Display results if console provided
            if console:
                self._display_speed_test_results(result, console)
                
            return result
            
        except Exception as e:
            logger.error(f"Speed test failed: {e}")
            if console:
                console.print(f"[bold red]Speed test failed:[/] {str(e)}")
            return None
    
    async def _test_ping(self, hosts: List[str], count: int = 5) -> Tuple[float, float]:
        """Test ping latency to multiple hosts"""
        ping_times = []
        
        for host in hosts:
            # Create platform-specific ping command
            cmd = self._create_ping_command(host, count)
            
            try:
                # Execute ping and parse results
                ping_times.extend(await self._execute_ping(cmd))
            except Exception as e:
                logger.debug(f"Ping failed for {host}: {e}")
                continue
                
        # Calculate average and jitter
        if ping_times:
            avg_ping = sum(ping_times) / len(ping_times)
            # Jitter is the average deviation from the mean
            jitter = sum(abs(p - avg_ping) for p in ping_times) / len(ping_times)
            return avg_ping, jitter
        
        return 0, 0
    
    def _create_ping_command(self, host: str, count: int) -> str:
        """Create platform-specific ping command"""
        if platform.system().lower() == "windows":
            return f"ping -n {count} {host}"
        else:
            return f"ping -c {count} {host}"
    async def _execute_ping(self, cmd: str) -> List[float]:
        """Execute ping command and parse results"""
        ping_times = []
        try:
            # Add timeout to prevent hanging
            proc = await asyncio.wait_for(
                asyncio.create_subprocess_shell(
                    cmd,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                ),
                timeout=15.0  # 15 second timeout
            )
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=15.0)
            output = stdout.decode(errors='ignore')
            
            # Parse ping times from output with improved regex
            import re
            if platform.system().lower() == "windows":
                # Windows ping format: "time=XXXms" or "time<1ms"
                pattern = r'time[<=](\d+(?:\.\d+)?)ms'
            else:
                # Unix/Linux ping format: "time=XXX ms"
                pattern = r'time=(\d+(?:\.\d+)?)\s*ms'
                
            matches = re.findall(pattern, output, re.IGNORECASE)
            for match in matches:
                try:
                    ping_times.append(float(match))
                except ValueError:
                    continue
                    
        except asyncio.TimeoutError:
            logger.warning(f"Ping command timed out: {cmd}")
        except Exception as e:
            logger.warning(f"Ping execution failed: {e}")
                    
        return ping_times
    async def _test_download_speed(self) -> float:
        """Test download speed using HTTP"""
        # List of test file URLs with known sizes
        test_files = self._get_speed_test_urls()
        download_speeds = []
        for url, expected_size in test_files:
            try:
                speed = await self._measure_download_speed(url, expected_size)
                if speed > 0:
                    download_speeds.append(speed)
            except Exception as e:
                logger.debug(f"Download speed test failed for {url}: {e}")
        
        if download_speeds:
            # Return average speed
            return sum(download_speeds) / len(download_speeds)
        
        return 0
    
    def _get_speed_test_urls(self) -> List[Tuple[str, int]]:
        """Get URLs for speed testing - Optimized for high-speed connections (500+ Mbps)"""
        return [
            # URL, size in bytes - use larger files for high-speed connections            ("https://speed.cloudflare.com/__down?bytes=104857600", 100 * 1024 * 1024),  # 100MB Cloudflare
            ("https://speedtest.tele2.net/100MB.zip", 100 * 1024 * 1024),  # 100MB Tele2
            ("https://proof.ovh.net/files/100Mb.dat", 100 * 1024 * 1024),  # 100MB OVH
            ("https://speed.hetzner.de/100MB.bin", 100 * 1024 * 1024),  # 100MB Hetzner
            ("https://bouygues.testdebit.info/100M.iso", 100 * 1024 * 1024),  # 100MB Bouygues
            # Fallback to smaller files if needed
            ("https://speed.cloudflare.com/__down?bytes=52428800", 50 * 1024 * 1024),  # 50MB Cloudflare
            ("https://speedtest.tele2.net/50MB.zip", 50 * 1024 * 1024),  # 50MB Tele2
        ]
        
    async def _measure_download_speed(self, url: str, expected_size: int = None) -> float:
        """Measure download speed for a specific URL - Optimized for high-speed connections (500+ Mbps)"""
        timeout = aiohttp.ClientTimeout(total=30)  # 30 second timeout for high-speed
        downloaded_bytes = 0
        
        try:
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get(url) as response:
                    if response.status != 200:
                        logger.debug(f"HTTP {response.status} for {url}")
                        return 0
                        
                    # Get actual start time after connection is established
                    start_time = time.time()
                    
                    # Use even larger chunks for high-speed connections (1MB chunks)
                    chunk_size = 1024 * 1024  # 1MB chunks for maximum throughput
                    
                    # Download with precise timing - optimized for high speeds
                    while True:
                        chunk = await response.content.read(chunk_size)
                        if not chunk:
                            break
                        downloaded_bytes += len(chunk)
                        
                        # Dynamic stopping criteria optimized for high-speed connections
                        current_time = time.time()
                        duration_so_far = current_time - start_time
                        
                        # For high-speed connections, download more data for accurate measurement
                        # Minimum 20MB for speeds over 100 Mbps, 50MB for expected high speeds
                        min_bytes = 50 * 1024 * 1024  # 50MB minimum for high-speed accuracy
                        if expected_size and expected_size >= 50 * 1024 * 1024:
                            min_bytes = expected_size  # Use full file size if large enough
                            
                        if downloaded_bytes >= min_bytes:
                            break
                            
                        # Stop if we've been downloading for too long 
                        # Allow longer time for high-speed measurements
                        max_duration = 15  # Maximum 15 seconds for speed test
                        if duration_so_far > max_duration:
                            break
                            
        except Exception as e:
            logger.debug(f"Download speed test error for {url}: {e}")
            return 0
                            
        end_time = time.time()
        duration = end_time - start_time
        
        # Require minimum duration and data for accurate high-speed measurement
        if duration > 0.5 and downloaded_bytes > 1024 * 1024:  # Minimum 0.5s and 1MB
            # Calculate speed in Mbps with high precision
            # Convert bytes to bits (*8), then to Mbps (/1,000,000)
            speed_mbps = (downloaded_bytes * 8) / (duration * 1_000_000)
            logger.debug(f"Downloaded {downloaded_bytes:,} bytes in {duration:.3f}s = {speed_mbps:.2f} Mbps from {url}")
            return speed_mbps
        
        logger.debug(f"Download test invalid: {duration:.3f}s, {downloaded_bytes:,} bytes")
        return 0
    
    async def _test_upload_speed(self) -> float:
        """Test upload speed using HTTP POST"""
        # List of upload test endpoints
        upload_endpoints = [
            "https://speed.cloudflare.com/__up",
            "https://speedtest.tele2.net/upload.php"
        ]
        
        upload_speeds = []
        
        # Create test data (1MB)
        data_size = 1 * 1024 * 1024
        test_data = b'0' * data_size
        
        for url in upload_endpoints:
            try:
                speed = await self._measure_upload_speed(url, test_data)
                if speed > 0:
                    upload_speeds.append(speed)
            except Exception as e:
                logger.debug(f"Upload speed test failed for {url}: {e}")
                
        if upload_speeds:
            # Return average speed
            return sum(upload_speeds) / len(upload_speeds)
        
        return 0
    
    async def _measure_upload_speed(self, url: str, data: bytes) -> float:
        """Measure upload speed for a specific URL"""
        timeout = aiohttp.ClientTimeout(total=20)  # 20 second timeout
        start_time = time.time()
        
        try:
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.post(url, data=data) as response:
                    if response.status not in (200, 201, 202):
                        logger.debug(f"Upload HTTP {response.status} for {url}")
                        return 0
                    
                    # Wait for response to complete
                    await response.read()
                        
            end_time = time.time()
            duration = end_time - start_time
            if duration > 0:
                # Calculate speed in Mbps - Fixed calculation
                # Convert bytes to bits (multiply by 8), then to Mbps (divide by 1,000,000)
                speed_mbps = (len(data) * 8) / (duration * 1_000_000)
                logger.debug(f"Uploaded {len(data)} bytes in {duration:.2f}s = {speed_mbps:.2f} Mbps")
                return speed_mbps
                        
        except Exception as e:
            logger.debug(f"Upload speed test error for {url}: {e}")
            return 0
        
        return 0
    
    async def _test_packet_loss(self, host: str = "8.8.8.8", count: int = 20) -> float:
        """Test packet loss percentage"""
        cmd = self._create_ping_command(host, count)
            
        try:
            # Create subprocess and capture output
            proc = await asyncio.create_subprocess_shell(
                cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, _ = await proc.communicate()
            output = stdout.decode()
            
            # Parse packet loss from output based on platform
            return self._parse_packet_loss_output(output)
            
        except Exception as e:
            logger.error(f"Packet loss test failed: {e}")
            
        return 0
    def _parse_packet_loss_output(self, output: str) -> float:
        """Parse packet loss percentage from ping output"""
        # Platform-specific packet loss parsing
        if platform.system().lower() == "windows":
            # Windows format: "(X% loss)"
            pattern = r'\((\d+(?:\.\d+)?)% loss\)'
        else:
            # Unix/Linux format: "X% packet loss"
            pattern = r'(\d+(?:\.\d+)?)% packet loss'
        
        matches = re.findall(pattern, output, re.IGNORECASE)
        if matches:
            try:
                return float(matches[0])
            except ValueError:
                pass
        
        # Fallback to original method if regex fails
        for line in output.splitlines():
            if "loss" in line and "%" in line:
                try:
                    # Extract percentage value
                    loss_str = line.split("%")[0].split()[-1].strip()
                    return float(loss_str)
                except (IndexError, ValueError):
                    pass
        
        return 0
    
    def _display_speed_test_results(self, result: SpeedTestResult, console: Console) -> None:
        """Display speed test results in a formatted table"""
        table = Table(title="Network Speed Test Results", box=box.ROUNDED)
        
        table.add_column("Metric", style="cyan")
        table.add_column("Value", style="green")
        table.add_column("Rating", style="yellow")
        
        # Download speed
        download_rating = "⭐" * result.get_quality_rating()
        table.add_row("Download Speed", f"{result.download_mbps:.2f} Mbps", download_rating)
        
        # Upload speed - Fix nested conditional
        upload_quality = min(5, max(1, int(result.upload_mbps / 2) + 1))
        upload_rating = "⭐" * upload_quality
        table.add_row("Upload Speed", f"{result.upload_mbps:.2f} Mbps", upload_rating)
        
        # Ping - Fix nested conditional
        ping_quality = self._calculate_ping_quality(result.ping_ms)
        ping_rating = "⭐" * ping_quality
        table.add_row("Ping Latency", f"{result.ping_ms:.1f} ms", ping_rating)
        
        # Additional metrics if available
        if result.jitter_ms is not None:
            jitter_quality = self._calculate_jitter_quality(result.jitter_ms)
            jitter_rating = "⭐" * jitter_quality
            table.add_row("Jitter", f"{result.jitter_ms:.1f} ms", jitter_rating)
            
        if result.packet_loss is not None:
            loss_quality = self._calculate_loss_quality(result.packet_loss)
            loss_rating = "⭐" * loss_quality
            table.add_row("Packet Loss", f"{result.packet_loss:.2f}%", loss_rating)
            
        # Streaming suitability - Fix nested conditional
        streaming_quality = self._get_streaming_quality(result.download_mbps)
        table.add_row("Streaming Quality", streaming_quality, "")
        
        console.print(table)
        
        # Add summary based on speed
        self._print_speed_summary(console, result.download_mbps)
    
    def _calculate_ping_quality(self, ping_ms: float) -> int:
        """Calculate ping quality rating from 1-5"""
        if ping_ms < 20:
            return 5
        elif ping_ms < 50:
            return 4
        elif ping_ms < 100:
            return 3
        elif ping_ms < 200:
            return 2
        else:
            return 1
    
    def _calculate_jitter_quality(self, jitter_ms: float) -> int:
        """Calculate jitter quality rating from 1-5"""
        if jitter_ms < 5:
            return 5
        elif jitter_ms < 10:
            return 4
        elif jitter_ms < 20:
            return 3
        elif jitter_ms < 40:
            return 2
        else:
            return 1
    
    def _calculate_loss_quality(self, packet_loss: float) -> int:
        """Calculate packet loss quality rating from 1-5"""
        if packet_loss < 0.1:
            return 5
        elif packet_loss < 0.5:
            return 4
        elif packet_loss < 1:
            return 3
        elif packet_loss < 5:
            return 2
        else:
            return 1
    
    def _get_streaming_quality(self, download_mbps: float) -> str:
        """Get streaming quality description based on download speed"""
        if download_mbps > 25:
            return "Good for HD/4K"
        elif download_mbps > 5:
            return "Good for HD"
        elif download_mbps > 2:
            return "Good for SD"
        else:
            return "Poor for streaming"
    
    def _print_speed_summary(self, console: Console, download_mbps: float) -> None:
        """Print summary of connection quality"""
        if download_mbps > 100:
            console.print("[bold green]Excellent connection! Perfect for all online activities.[/]")
        elif download_mbps > 25:
            console.print("[bold green]Great connection! Suitable for most online activities.[/]")
        elif download_mbps > 5:
            console.print("[yellow]Decent connection. Good for basic streaming and browsing.[/]")
        else:
            console.print("[red]Limited connection. May struggle with high-quality streaming.[/]")


# Module-level function for simple connection checking
async def check_internet_connection() -> Tuple[bool, str]:
    """Check if internet connection is available
    
    Returns:
        Tuple of (connected, reason)
    """
    test_endpoints = [
        "https://www.google.com",
        "https://www.cloudflare.com",
        "https://www.microsoft.com",
        "https://www.apple.com"
    ]
    
    # Try to connect to each with a short timeout
    timeout = aiohttp.ClientTimeout(total=3)
    
    for endpoint in test_endpoints:
        try:
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.head(endpoint) as response:
                    if response.status < 400:
                        return True, "Connection successful"
        except aiohttp.ClientConnectorError:
            continue
        except aiohttp.ServerTimeoutError:
            continue
        except Exception as e:
            logger.debug(f"Connection check error: {str(e)}")
            continue
    
    # Try basic DNS resolution
    try:
        socket.gethostbyname("google.com")
        return False, "DNS working but HTTP connections failed"
    except socket.gaierror:
        return False, "DNS resolution failed"
    except Exception:
        return False, "Unknown connection error"

# Simplified speed test for quick checks
async def run_speedtest(detailed: bool = False, use_cache: bool = True, console: Optional[Console] = None) -> SpeedTestResult:
    """Run an enhanced speed test with improved features
    
    Args:
        detailed: Whether to run a detailed test with packet loss and jitter
        use_cache: Whether to use cached results if available and recent
        console: Rich console for output (optional)
        
    Returns:
        SpeedTestResult object with comprehensive metrics
    """
    try:
        # Create a network manager with enhanced configuration
        config = {
            "cache_directory": CACHE_DIR,
            "connection_timeout": 10,
            "speed_test_timeout": 30
        }
        manager = NetworkManager(config)
        
        # Check if we should use cached results
        if use_cache and manager.last_speed_test:
            cache_age = time.time() - manager.last_speed_test.timestamp
            # Use cache if less than 5 minutes old
            if cache_age < 300:
                if console:
                    console.print(f"[yellow]Using cached speed test results ({cache_age:.0f}s old)[/]")
                return manager.last_speed_test
        
        # Run the speed test with progress reporting
        if console:
            console.print("[bold cyan]🚀 Running enhanced network speed test...[/]")
        
        result = await manager.run_speed_test(console=console, detailed=detailed)
        
        if result:
            # Add enhanced analysis
            if console:
                _display_enhanced_results(result, console)
            return result
        else:
            # Return fallback result with basic connectivity check
            if console:
                console.print("[yellow]⚠️ Speed test failed, running basic connectivity test...[/]")
            
            basic_result = await _run_basic_connectivity_test()
            if console:
                console.print(f"[green]✅ Basic connectivity: {'Online' if basic_result.download_mbps > 0 else 'Offline'}[/]")
            
            return basic_result
            
    except Exception as e:
        logger.error(f"Enhanced speed test failed: {e}")
        if console:
            console.print(f"[red]❌ Speed test error: {e}[/]")
        
        # Return minimal fallback result
        return SpeedTestResult(0, 0, 999, timestamp=time.time())


async def _run_basic_connectivity_test() -> SpeedTestResult:
    """Run a basic connectivity test as fallback"""
    try:
        # Simple HTTP request to test basic connectivity
        timeout = aiohttp.ClientTimeout(total=5)
        start_time = time.time()
        
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get("https://www.google.com") as response:
                if response.status == 200:
                    end_time = time.time()
                    ping_ms = (end_time - start_time) * 1000
                    # Estimate basic speed (very rough)
                    return SpeedTestResult(
                        download_mbps=1.0,  # Basic estimate
                        upload_mbps=0.5,    # Basic estimate
                        ping_ms=ping_ms,
                        timestamp=time.time()
                    )
    except Exception:
        pass
    
    # Return offline result
    return SpeedTestResult(0, 0, 999, timestamp=time.time())


def _display_enhanced_results(result: SpeedTestResult, console: Console) -> None:
    """Display enhanced speed test results with recommendations"""
    from rich.panel import Panel
    from rich.columns import Columns
    
    # Create main results table
    table = Table(title="🌐 Enhanced Network Speed Test Results", box=box.ROUNDED)
    table.add_column("Metric", style="cyan", width=20)
    table.add_column("Value", style="green", width=15)
    table.add_column("Rating", style="yellow", width=10)
    table.add_column("Status", style="magenta", width=15)
    
    # Download speed analysis
    download_rating = "⭐" * result.get_quality_rating()
    download_status = _get_speed_status(result.download_mbps, "download")
    table.add_row("Download Speed", f"{result.download_mbps:.2f} Mbps", download_rating, download_status)
    
    # Upload speed analysis  
    upload_rating = "⭐" * min(5, max(1, int(result.upload_mbps / 2) + 1))
    upload_status = _get_speed_status(result.upload_mbps, "upload")
    table.add_row("Upload Speed", f"{result.upload_mbps:.2f} Mbps", upload_rating, upload_status)
    
    # Ping analysis
    ping_rating = "⭐" * (5 - min(4, max(0, int(result.ping_ms / 50))))
    ping_status = _get_ping_status(result.ping_ms)
    table.add_row("Ping Latency", f"{result.ping_ms:.1f} ms", ping_rating, ping_status)
    
    # Additional metrics if available
    if result.jitter_ms is not None:
        jitter_rating = "⭐" * (5 - min(4, max(0, int(result.jitter_ms / 10))))
        jitter_status = "Excellent" if result.jitter_ms < 5 else "Good" if result.jitter_ms < 20 else "Poor"
        table.add_row("Jitter", f"{result.jitter_ms:.1f} ms", jitter_rating, jitter_status)
        
    if result.packet_loss is not None:
        loss_rating = "⭐" * (5 - min(4, max(0, int(result.packet_loss * 2))))
        loss_status = "Excellent" if result.packet_loss < 1 else "Good" if result.packet_loss < 3 else "Poor"
        table.add_row("Packet Loss", f"{result.packet_loss:.2f}%", loss_rating, loss_status)
    
    console.print(table)
    
    # Activity recommendations
    recommendations = _get_activity_recommendations(result)
    if recommendations:
        rec_panel = Panel(
            recommendations,
            title="🎯 Activity Recommendations",
            border_style="blue"
        )
        console.print(rec_panel)
    
    # Performance tips
    tips = _get_performance_tips(result)
    if tips:
        tips_panel = Panel(
            tips,
            title="💡 Performance Tips",
            border_style="yellow"
        )
        console.print(tips_panel)


def _get_speed_status(speed_mbps: float, type_str: str) -> str:
    """Get speed status description"""
    if type_str == "download":
        if speed_mbps >= 100:
            return "🚀 Excellent"
        elif speed_mbps >= 25:
            return "✅ Very Good"
        elif speed_mbps >= 5:
            return "👍 Good"
        elif speed_mbps >= 1:
            return "⚠️ Fair"
        else:
            return "❌ Poor"
    else:  # upload
        if speed_mbps >= 20:
            return "🚀 Excellent"
        elif speed_mbps >= 5:
            return "✅ Very Good"
        elif speed_mbps >= 1:
            return "👍 Good"
        elif speed_mbps >= 0.5:
            return "⚠️ Fair"
        else:
            return "❌ Poor"


def _get_ping_status(ping_ms: float) -> str:
    """Get ping status description"""
    if ping_ms < 20:
        return "🚀 Excellent"
    elif ping_ms < 50:
        return "✅ Very Good"
    elif ping_ms < 100:
        return "👍 Good"
    elif ping_ms < 200:
        return "⚠️ Fair"
    else:
        return "❌ Poor"


def _get_activity_recommendations(result: SpeedTestResult) -> str:
    """Get activity recommendations based on speed test results"""
    recommendations = []
    
    # Streaming recommendations
    if result.download_mbps >= 25:
        recommendations.append("✅ 4K Ultra HD streaming")
    elif result.download_mbps >= 15:
        recommendations.append("✅ 1080p HD streaming")
    elif result.download_mbps >= 5:
        recommendations.append("✅ 720p HD streaming")
    elif result.download_mbps >= 1.5:
        recommendations.append("⚠️ 480p SD streaming")
    else:
        recommendations.append("❌ Streaming may be problematic")
    
    # Gaming recommendations
    if result.ping_ms < 50 and result.download_mbps >= 3:
        recommendations.append("✅ Online gaming (excellent)")
    elif result.ping_ms < 100 and result.download_mbps >= 1:
        recommendations.append("👍 Online gaming (good)")
    else:
        recommendations.append("❌ Online gaming may lag")
    
    # Video calling
    if result.download_mbps >= 1.5 and result.upload_mbps >= 1.5 and result.ping_ms < 150:
        recommendations.append("✅ HD video calling")
    elif result.download_mbps >= 0.5 and result.upload_mbps >= 0.5:
        recommendations.append("👍 Standard video calling")
    else:
        recommendations.append("❌ Video calling may be poor")
    
    # File downloads
    if result.download_mbps >= 50:
        recommendations.append("✅ Large file downloads (fast)")
    elif result.download_mbps >= 10:
        recommendations.append("👍 Medium file downloads")
    else:
        recommendations.append("⚠️ File downloads will be slow")
    
    return "\n".join(recommendations)


def _get_performance_tips(result: SpeedTestResult) -> str:
    """Get performance improvement tips"""
    tips = []
    
    # Speed-based tips
    if result.download_mbps < 10:
        tips.append("• Consider upgrading your internet plan")
        tips.append("• Check for background applications using bandwidth")
        tips.append("• Try connecting via Ethernet instead of WiFi")
    
    # Ping-based tips
    if result.ping_ms > 100:
        tips.append("• Use a wired connection for gaming")
        tips.append("• Choose servers closer to your location")
        tips.append("• Close unnecessary network applications")
    
    # General tips
    if result.jitter_ms and result.jitter_ms > 20:
        tips.append("• Check for network congestion")
        tips.append("• Consider QoS settings on your router")
    
    if result.packet_loss and result.packet_loss > 2:
        tips.append("• Check network cables and connections")
        tips.append("• Contact your ISP about line quality")
    
    # Always include some general tips
    if not tips:
        tips.extend([
            "• Restart your router periodically",
            "• Keep your router firmware updated",
            "• Position router in a central location"
        ])
    
    return "\n".join(tips)
