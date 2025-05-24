#!/usr/bin/env python3
"""
cyberpunk_ui.py - Cyberpunk/Neon-styled UI Components

Advanced cyberpunk-styled UI components with neon effects, matrix-style animations,
and holographic elements for the Snatch Media Downloader.
"""

from rich.panel import Panel
from rich.text import Text
from rich.console import Console, RenderableType
from rich.table import Table
from rich.progress import Progress, BarColumn, TextColumn, TimeRemainingColumn
from rich.layout import Layout
from rich.align import Align
from rich.columns import Columns
from textual.widgets import Static
from textual.reactive import reactive
from typing import Dict, Any, List
import time
import random

# Cyberpunk color schemes
NEON_COLORS = {
    "electric_blue": "#00FFFF",
    "hot_pink": "#FF1493", 
    "neon_green": "#39FF14",
    "laser_red": "#FF073A",
    "cyber_yellow": "#FFFF00",
    "plasma_purple": "#9D00FF",
    "matrix_green": "#00FF41",
    "terminal_orange": "#FF8C00"
}

CYBERPUNK_THEMES = {
    "dark_city": {
        "primary": NEON_COLORS["electric_blue"],
        "secondary": NEON_COLORS["hot_pink"],
        "accent": NEON_COLORS["neon_green"],
        "warning": NEON_COLORS["cyber_yellow"],
        "error": NEON_COLORS["laser_red"]
    },
    "matrix": {
        "primary": NEON_COLORS["matrix_green"],
        "secondary": NEON_COLORS["electric_blue"],
        "accent": NEON_COLORS["plasma_purple"],
        "warning": NEON_COLORS["cyber_yellow"],
        "error": NEON_COLORS["laser_red"]
    },
    "synthwave": {
        "primary": NEON_COLORS["hot_pink"],
        "secondary": NEON_COLORS["plasma_purple"],
        "accent": NEON_COLORS["electric_blue"],
        "warning": NEON_COLORS["cyber_yellow"],
        "error": NEON_COLORS["laser_red"]
    }
}

class CyberpunkBanner:
    """Creates cyberpunk-styled banner with ASCII art and neon effects"""
    
    def __init__(self, theme: str = "dark_city"):
        self.theme = CYBERPUNK_THEMES.get(theme, CYBERPUNK_THEMES["dark_city"])
        
    def create_banner(self) -> Panel:
        """Create an animated cyberpunk banner"""
        ascii_art = f"""
[{self.theme['primary']}]╔══════════════════════════════════════════════════════════════╗[/]
[{self.theme['primary']}]║[/] [{self.theme['accent']}]███████[/] [{self.theme['secondary']}]███[/] [{self.theme['accent']}]████[/] [{self.theme['secondary']}]███████[/] [{self.theme['accent']}]██[/] [{self.theme['secondary']}]██[/]  [{self.theme['accent']}]███████[/] [{self.theme['secondary']}]██[/]    [{self.theme['accent']}]██[/] [{self.theme['primary']}]║[/]
[{self.theme['primary']}]║[/] [{self.theme['accent']}]██[/]      [{self.theme['secondary']}]████[/]  [{self.theme['accent']}]██[/] [{self.theme['secondary']}]██[/]   [{self.theme['accent']}]██[/] [{self.theme['secondary']}]██[/] [{self.theme['accent']}]██[/]  [{self.theme['secondary']}]██[/]      [{self.theme['accent']}]██[/]    [{self.theme['secondary']}]██[/] [{self.theme['primary']}]║[/]
[{self.theme['primary']}]║[/] [{self.theme['accent']}]███████[/] [{self.theme['secondary']}]██[/] [{self.theme['accent']}]██[/] [{self.theme['secondary']}]██[/] [{self.theme['accent']}]██████[/]  [{self.theme['secondary']}]██████[/]   [{self.theme['accent']}]██[/]      [{self.theme['secondary']}]███████[/] [{self.theme['primary']}]║[/]
[{self.theme['primary']}]║[/]      [{self.theme['accent']}]██[/] [{self.theme['secondary']}]██[/]  [{self.theme['accent']}]████[/] [{self.theme['secondary']}]██[/]   [{self.theme['accent']}]██[/] [{self.theme['secondary']}]██[/]  [{self.theme['accent']}]██[/]  [{self.theme['secondary']}]██[/]      [{self.theme['accent']}]██[/]    [{self.theme['secondary']}]██[/] [{self.theme['primary']}]║[/]
[{self.theme['primary']}]║[/] [{self.theme['accent']}]███████[/] [{self.theme['secondary']}]██[/]   [{self.theme['accent']}]███[/] [{self.theme['secondary']}]███████[/] [{self.theme['accent']}]██[/]   [{self.theme['secondary']}]██[/]  [{self.theme['accent']}]███████[/] [{self.theme['secondary']}]██[/]    [{self.theme['accent']}]██[/] [{self.theme['primary']}]║[/]
[{self.theme['primary']}]╚══════════════════════════════════════════════════════════════╝[/]

[{self.theme['secondary']}]▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓[/]
[{self.theme['accent']}]✦ MEDIA DOWNLOADER V2.0 - CYBERPUNK EDITION ✦[/]
[{self.theme['secondary']}]▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓[/]
"""
        
        subtitle = Text()
        subtitle.append("◢◤", style=self.theme['primary'])
        subtitle.append(" NEURAL NETWORK ENHANCED ", style=f"bold {self.theme['accent']}")
        subtitle.append("◥◣", style=self.theme['primary'])
        subtitle.append("\n")
        subtitle.append("🔮 AI-Powered Downloads", style=self.theme['secondary'])
        subtitle.append(" • ")
        subtitle.append("⚡ P2P Neural Networks", style=self.theme['accent'])
        subtitle.append(" • ")
        subtitle.append("🎵 7.1 Surround Matrix", style=self.theme['primary'])
        
        content = Text()
        content.append(ascii_art)
        content.append("\n")
        content.append(subtitle)
        
        return Panel(
            content,
            title=f"[{self.theme['warning']}]◦ INITIALIZING NEURAL INTERFACE ◦[/]",
            border_style=self.theme['primary'],
            padding=(1, 2)
        )

class HolographicProgress:
    """Creates holographic-style progress displays"""
    
    def __init__(self, theme: str = "dark_city"):
        self.theme = CYBERPUNK_THEMES.get(theme, CYBERPUNK_THEMES["dark_city"])
        
    def create_download_progress(self, filename: str, progress: float, speed: str, eta: str) -> Panel:
        """Create a holographic download progress display"""
        
        # Create progress bar with neon effect
        bar_length = 40
        filled_length = int(bar_length * (progress / 100))
        
        bar = Text()
        bar.append("▓" * filled_length, style=self.theme['accent'])
        bar.append("░" * (bar_length - filled_length), style=f"dim {self.theme['primary']}")
        
        # Holographic border effect
        border_chars = ["◢", "◤", "◥", "◣"]
        border = "".join(random.choice(border_chars) for _ in range(20))
        
        content = Text()
        content.append(f"⟫ DOWNLOADING: {filename}\n", style=f"bold {self.theme['secondary']}")
        content.append("▬" * 50 + "\n", style=self.theme['primary'])
        content.append("║ ", style=self.theme['primary'])
        content.append(bar)
        content.append(f" ║ {progress:.1f}%\n", style=self.theme['primary'])
        content.append("▬" * 50 + "\n", style=self.theme['primary'])
        content.append(f"⟫ SPEED: {speed} ", style=self.theme['accent'])
        content.append(f"⟫ ETA: {eta}\n", style=self.theme['warning'])
        content.append(border, style=f"dim {self.theme['primary']}")
        
        return Panel(
            content,
            title=f"[{self.theme['accent']}]◦ NEURAL TRANSFER PROTOCOL ◦[/]",
            border_style=self.theme['primary']
        )

class MatrixDataTable:
    """Creates matrix-style data tables with scrolling effects"""
    
    def __init__(self, theme: str = "matrix"):
        self.theme = CYBERPUNK_THEMES.get(theme, CYBERPUNK_THEMES["matrix"])
        
    def create_format_table(self, formats: List[Dict[str, Any]]) -> Table:
        """Create a matrix-style format selection table"""
        
        table = self._create_base_table()
        self._populate_table_rows(table, formats)
        
        return table
    
    def _create_base_table(self) -> Table:
        """Create the base table structure"""
        table = Table(
            title=f"[{self.theme['accent']}]◦ FORMAT MATRIX ◦[/]",
            border_style=self.theme['primary'],
            header_style=f"bold {self.theme['secondary']}",
            show_lines=True
        )
        
        # Add columns with neon styling
        table.add_column("🔸 ID", style=self.theme['accent'], width=8)
        table.add_column("📄 FORMAT", style=self.theme['primary'], width=10)
        table.add_column("🖥️ RESOLUTION", style=self.theme['secondary'], width=12)
        table.add_column("⚙️ CODEC", style=self.theme['accent'], width=12)
        table.add_column("💾 SIZE", style=self.theme['warning'], width=10)
        table.add_column("🎵 AUDIO", style=self.theme['primary'], width=10)
        table.add_column("🎬 FPS", style=self.theme['secondary'], width=8)
        
        return table
    
    def _populate_table_rows(self, table: Table, formats: List[Dict[str, Any]]) -> None:
        """Populate table with format data"""
        for i, fmt in enumerate(formats[:15]):  # Limit to 15 rows
            row_style = self.theme['accent'] if i % 2 == 0 else self.theme['primary']
            row_data = self._create_row_data(fmt, row_style)
            table.add_row(*row_data)
    
    def _create_row_data(self, fmt: Dict[str, Any], row_style: str) -> tuple:
        """Create formatted row data for a single format"""
        format_id = str(fmt.get('format_id', 'N/A'))
        ext = fmt.get('ext', 'N/A').upper()
        resolution = self._format_resolution(fmt)
        codec = self._format_codec(fmt)
        size = self._format_size(fmt)
        audio = self._format_audio(fmt)
        fps = self._format_fps(fmt)
        
        return (
            f"[{row_style}]{format_id}[/]",
            f"[bold {row_style}]{ext}[/]",
            f"[{row_style}]{resolution}[/]",
            f"[{row_style}]{codec}[/]",
            f"[{row_style}]{size}[/]",
            f"[{row_style}]{audio}[/]",
            f"[{row_style}]{fps}[/]"
        )
    
    def _format_resolution(self, fmt: Dict[str, Any]) -> str:
        """Format resolution with quality indicator"""
        if fmt.get('width') and fmt.get('height'):
            resolution = f"{fmt['width']}x{fmt['height']}"
            if fmt['height'] >= 1080:
                resolution += " ✦"
            elif fmt['height'] >= 720:
                resolution += " ◦"
            return resolution
        return 'AUDIO'
    
    def _format_codec(self, fmt: Dict[str, Any]) -> str:
        """Format codec information"""
        codec = fmt.get('vcodec', fmt.get('acodec', 'N/A'))
        if codec == 'none':
            codec = fmt.get('acodec', 'N/A')
        return codec
    
    def _format_size(self, fmt: Dict[str, Any]) -> str:
        """Format file size with neon styling"""
        filesize = fmt.get('filesize') or fmt.get('filesize_approx')
        if filesize:
            if filesize > 1024**3:  # GB
                return f"{filesize/(1024**3):.1f}GB"
            elif filesize > 1024**2:  # MB
                return f"{filesize/(1024**2):.1f}MB"
            else:
                return f"{filesize/1024:.1f}KB"
        return '▒▒▒'
    
    def _format_audio(self, fmt: Dict[str, Any]) -> str:
        """Format audio quality"""
        abr = fmt.get('abr')
        return f"{abr}k" if abr else '▒▒▒'
    
    def _format_fps(self, fmt: Dict[str, Any]) -> str:
        """Format FPS information"""
        return str(fmt.get('fps', '▒▒')) if fmt.get('fps') else '▒▒'

class CyberStatusPanel:
    """Creates cyberpunk-styled status panels"""
    
    def __init__(self, theme: str = "synthwave"):
        self.theme = CYBERPUNK_THEMES.get(theme, CYBERPUNK_THEMES["synthwave"])
        
    def create_system_status(self, stats: Dict[str, Any]) -> Panel:
        """Create a cyberpunk system status panel"""
        
        # Neural network style metrics
        content = Text()
        content.append("◢◤◢◤◢◤◢◤◢◤◢◤◢◤◢◤◢◤◢◤\n", style=self.theme['primary'])
        content.append("▓▓ NEURAL SYSTEM STATUS ▓▓\n", style=f"bold {self.theme['accent']}")
        content.append("◥◣◥◣◥◣◥◣◥◣◥◣◥◣◥◣◥◣◥◣\n\n", style=self.theme['primary'])
        
        # CPU with visual indicator
        cpu = stats.get('cpu_percent', 0)
        cpu_bar = self._create_meter(cpu, 100)
        
        if cpu > 80:
            cpu_status = "🔴 OVERLOAD"
        elif cpu > 50:
            cpu_status = "🟡 ACTIVE"
        else:
            cpu_status = "🟢 OPTIMAL"
            
        content.append(f"🧠 CPU MATRIX: {cpu:.1f}% {cpu_bar} {cpu_status}\n", style=self.theme['secondary'])
        
        # Memory
        memory = stats.get('memory_percent', 0)
        memory_bar = self._create_meter(memory, 100)
        
        if memory > 85:
            memory_status = "🔴 CRITICAL"
        elif memory > 70:
            memory_status = "🟡 WARNING"
        else:
            memory_status = "🟢 STABLE"
            
        content.append(f"🗄️ MEMORY BANK: {memory:.1f}% {memory_bar} {memory_status}\n", style=self.theme['accent'])
        
        # Network
        network = stats.get('network_mbps', 0)
        network_bar = self._create_meter(network, 100)
        
        if network > 10:
            network_status = "🟢 UPLINK"
        elif network > 1:
            network_status = "🟡 SYNCING"
        else:
            network_status = "🔴 OFFLINE"
            
        content.append(f"📡 NEURAL NET: {network:.1f}Mb/s {network_bar} {network_status}\n", style=self.theme['primary'])
        
        # Downloads
        downloads = stats.get('active_downloads', 0)
        content.append(f"\n⚡ ACTIVE DOWNLOADS: {downloads}\n", style=self.theme['warning'])
        content.append(f"💾 CACHE NODES: {stats.get('cache_size', 0)}\n", style=self.theme['secondary'])
        content.append(f"🔗 P2P LINKS: {stats.get('p2p_connections', 0)}\n", style=self.theme['accent'])
        
        content.append("\n◢◤◢◤◢◤◢◤◢◤◢◤◢◤◢◤◢◤◢◤", style=self.theme['primary'])
        
        return Panel(
            content,
            title=f"[{self.theme['warning']}]◦ CYBERDECK STATUS ◦[/]",
            border_style=self.theme['primary']
        )
    
    def _create_meter(self, value: float, max_value: float) -> str:
        """Create a visual meter with neon blocks"""
        filled = int((value / max_value) * 10)
        return "▓" * filled + "░" * (10 - filled)

class NeonMenu:
    """Creates neon-styled menu systems"""
    
    def __init__(self, theme: str = "dark_city"):
        self.theme = CYBERPUNK_THEMES.get(theme, CYBERPUNK_THEMES["dark_city"])
        
    def create_main_menu(self) -> Panel:
        """Create the main cyberpunk menu"""
        
        menu_items = [
            ("🔗", "NEURAL DOWNLOAD", "Initialize media transfer protocols"),
            ("🎵", "AUDIO MATRIX", "Process audio with 7.1 surround enhancement"),
            ("🎬", "VIDEO NEXUS", "Transform video with neural filters"),
            ("📡", "P2P NETWORK", "Connect to distributed neural nodes"),
            ("⚙️", "CYBER CONFIG", "Modify system parameters"),
            ("📊", "DATA STREAM", "Monitor neural network activity"),
            ("❓", "HELP MATRIX", "Access knowledge database"),
            ("🚪", "JACK OUT", "Disconnect from the matrix")
        ]
        
        content = Text()
        content.append("╔═══════════════════════════════════════╗\n", style=self.theme['primary'])
        content.append("║ ", style=self.theme['primary'])
        content.append("CYBERPUNK COMMAND INTERFACE", style=f"bold {self.theme['accent']}")
        content.append(" ║\n", style=self.theme['primary'])
        content.append("╠═══════════════════════════════════════╣\n", style=self.theme['primary'])
        
        for i, (icon, name, desc) in enumerate(menu_items, 1):
            content.append("║ ", style=self.theme['primary'])
            content.append(f"[{i}] {icon} ", style=self.theme['secondary'])
            content.append(f"{name:<20}", style=f"bold {self.theme['accent']}")
            content.append(" ║\n", style=self.theme['primary'])
            content.append("║ ", style=self.theme['primary'])
            content.append(f"    {desc:<31}", style=f"dim {self.theme['secondary']}")
            content.append(" ║\n", style=self.theme['primary'])
            
            if i < len(menu_items):
                content.append("╠───────────────────────────────────────╣\n", style=f"dim {self.theme['primary']}")
        
        content.append("╚═══════════════════════════════════════╝", style=self.theme['primary'])
        
        return Panel(
            content,
            title=f"[{self.theme['warning']}]◦ NEURAL INTERFACE ACTIVE ◦[/]",
            border_style=self.theme['primary']
        )

def create_cyberpunk_layout() -> Layout:
    """Create a complete cyberpunk layout"""
    layout = Layout()
    
    layout.split_column(
        Layout(name="header", size=12),
        Layout(name="body"),
        Layout(name="footer", size=3)
    )
    
    layout["body"].split_row(
        Layout(name="left", ratio=2),
        Layout(name="right", ratio=3)
    )
    
    layout["left"].split_column(
        Layout(name="menu"),
        Layout(name="status")
    )
    
    layout["right"].split_column(
        Layout(name="main"),
        Layout(name="progress")
    )
    
    return layout
