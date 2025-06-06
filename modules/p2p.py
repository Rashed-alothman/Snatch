"""
Enhanced P2P implementation with NAT traversal and encryption.
Provides secure file sharing with progress tracking and integrity verification.

Features:
- NAT traversal using STUN/TURN protocols
- End-to-end encryption with key exchange
- Peer discovery via DHT
- Resumable transfers
- Automatic port mapping using UPnP
- Connection resilience with keepalive support
- Integrity verification using SHA-256
"""

import asyncio
import hashlib
import json
import logging
import socket
import threading
import time
import os
import random
import ipaddress
import binascii
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, Dict, Any, List, Tuple, Set, Union, Callable
from urllib.parse import urlparse, parse_qs

# Cryptography imports
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from cryptography.hazmat.primitives import hashes, padding
from cryptography.hazmat.primitives.asymmetric import rsa, padding as asym_padding
from cryptography.hazmat.backends import default_backend

# Third-party library imports
import miniupnpc
import netifaces
import aiohttp
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TimeElapsedColumn
from rich.console import Console

# Local imports
from .common_utils import sanitize_filename, ensure_dir
from .progress import ColorProgressBar, HolographicProgress
from .logging_config import setup_logging
from .constants import DEFAULT_TIMEOUT, DEFAULT_CHUNK_SIZE
from .session import SessionManager

# Configure logging
logger = logging.getLogger(__name__)

# Constants
CHUNK_SIZE = DEFAULT_CHUNK_SIZE  # Use constant from constants.py
DEFAULT_PORT_RANGE = (49152, 65535)  # Dynamic/private port range
PROTOCOL_VERSION = 2  # Increment protocol version
DHT_TIMEOUT = 30  # seconds
STUN_SERVERS = [
    'stun.l.google.com:19302',
    'stun1.l.google.com:19302',
    'stun.stunprotocol.org:3478',
    'stun.voip.blackberry.com:3478'
]
TURN_SERVERS = [
    # Format: 'server:port:username:password'
    'turn.snatch-app.org:3478:snatch:s3cur3p@ss',
]
P2P_ID_PREFIX = "snatch-"
NAT_TYPES = {
    "OPEN": 0,
    "FULL_CONE": 1,
    "RESTRICTED_CONE": 2,
    "PORT_RESTRICTED": 3,
    "SYMMETRIC": 4,
    "UNKNOWN": 5
}

# P2P Protocol Message Types
MSG_TYPE = {
    "HANDSHAKE": 0x01,
    "REQUEST": 0x02,
    "RESPONSE": 0x03,
    "DATA": 0x04,
    "ACK": 0x05,
    "COMPLETE": 0x06,
    "ERROR": 0x07,
    "PING": 0x08,
    "PONG": 0x09,
    "KEY_EXCHANGE": 0x0A,
    "NAT_INFO": 0x0B
}

# New P2P Library Sharing System
@dataclass
class SharedLibrary:
    """Represents a shared download library"""
    library_id: str
    name: str
    description: str
    owner_peer_id: str
    created_at: float
    last_updated: float
    files: Dict[str, 'LibraryFile'] = field(default_factory=dict)
    subscribers: Set[str] = field(default_factory=set)  # peer_ids
    auto_sync: bool = True
    public: bool = False
    tags: List[str] = field(default_factory=list)

@dataclass
class LibraryFile:
    """File entry in a shared library"""
    file_id: str
    name: str
    size: int
    checksum: str
    download_url: Optional[str]
    metadata: Dict[str, Any] = field(default_factory=dict)
    added_at: float = field(default_factory=time.time)
    category: str = "general"  # video, audio, document, etc.
    quality: Optional[str] = None
    format: Optional[str] = None

@dataclass
class SyncUpdate:
    """Represents a library synchronization update"""
    library_id: str
    update_type: str  # "file_added", "file_removed", "library_updated"
    data: Dict[str, Any]
    timestamp: float
    from_peer: str

class P2PError(Exception):
    """Base class for P2P errors"""
    pass

class PeerConnectionError(P2PError):
    """Raised when peer connection fails"""
    pass

class PeerAuthenticationError(P2PError):
    """Raised when peer authentication fails"""
    pass

class EncryptionError(P2PError):
    """Raised when encryption/decryption fails"""
    pass

class FileTransferError(P2PError):
    """Raised when file transfer fails"""
    pass

class IntegrityError(P2PError):
    """Raised when file integrity check fails"""
    pass

class NATTraversalError(P2PError):
    """Raised when NAT traversal fails"""
    pass

@dataclass
class PeerInfo:
    """Information about a connected peer"""
    peer_id: str
    ip: str
    port: int
    public_key: Optional[Any] = None
    symmetric_key: Optional[bytes] = None
    nat_type: int = field(default=NAT_TYPES["UNKNOWN"])
    connected: bool = False
    last_seen: float = field(default_factory=time.time)
    capabilities: List[str] = field(default_factory=list)
    version: int = PROTOCOL_VERSION

@dataclass
class FileInfo:
    """Information about a shared file"""
    file_id: str
    file_name: str
    file_path: str
    file_size: int
    hash: str
    chunks: int
    chunk_hashes: List[str] = field(default_factory=list)
    mime_type: str = "application/octet-stream"
    created_at: float = field(default_factory=time.time)
    shared_at: float = field(default_factory=time.time)

    @property
    def name(self) -> str:
        """Alias for file_name for backward compatibility"""
        return self.file_name
    
    @property
    def size(self) -> int:
        """Alias for file_size for backward compatibility"""
        return self.file_size
    
    @property
    def path(self) -> str:
        """Alias for file_path for backward compatibility"""
        return self.file_path

@dataclass
class TransferProgress:
    """Progress tracking for file transfers"""
    transfer_id: str
    file_id: str
    peer_id: str
    total_bytes: int
    bytes_transferred: int = 0
    chunks_completed: int = 0
    total_chunks: int = 0
    speed_bps: float = 0.0
    eta_seconds: float = 0.0
    status: str = "pending"  # pending, active, paused, completed, failed
    start_time: float = field(default_factory=time.time)
    last_update: float = field(default_factory=time.time)
    error_message: Optional[str] = None

    @property
    def progress_percent(self) -> float:
        """Calculate progress percentage"""
        if self.total_bytes <= 0:
            return 0.0
        return min(100.0, (self.bytes_transferred / self.total_bytes) * 100)

@dataclass
class ShareConfig:
    """Configuration for P2P sharing"""
    upnp: bool = True
    encryption: bool = True
    compression: bool = True
    chunk_size: int = CHUNK_SIZE
    dht_enabled: bool = True
    max_peers: int = 10
    timeout: int = DEFAULT_TIMEOUT
    auto_retry: bool = True
    retry_attempts: int = 3
    port_range: Tuple[int, int] = DEFAULT_PORT_RANGE
    stun_servers: List[str] = field(default_factory=lambda: STUN_SERVERS.copy())

class P2PManager:
    """Main P2P management class for secure file sharing
    
    Features:
    - Secure file sharing with encryption
    - NAT traversal for connectivity through firewalls
    - DHT-based peer discovery
    - Resumable transfers with integrity checking
    - UPnP support for automatic port forwarding
    """
    
    def __init__(self, config: Dict[str, Any], session_manager: Optional[SessionManager] = None):
        """Initialize P2P manager
        
        Args:
            config: Application configuration
            session_manager: Optional session manager for persistence
        """
        self.config = config
        self.share_config = ShareConfig(
            upnp=config.get("upnp_enabled", True),
            encryption=config.get("p2p_encryption", True),
            compression=config.get("p2p_compression", True),
            chunk_size=config.get("p2p_chunk_size", CHUNK_SIZE),
            dht_enabled=config.get("dht_enabled", True)
        )
        
        # Set up data directories
        self.data_dir = config.get("p2p_data_dir", os.path.join(os.path.expanduser("~"), ".snatch", "p2p"))
        self.temp_dir = os.path.join(self.data_dir, "temp")
        self.keys_dir = os.path.join(self.data_dir, "keys")
        ensure_dir(self.data_dir)
        ensure_dir(self.temp_dir)
        ensure_dir(self.keys_dir)
        
        # Session management
        self.session_manager = session_manager
        
        # State tracking
        self.peer_id = self._generate_peer_id()
        self.peers: Dict[str, PeerInfo] = {}  # peer_id -> PeerInfo
        self.shared_files: Dict[str, FileInfo] = {}  # file_id -> FileInfo
        self.transfers: Dict[str, TransferProgress] = {}  # transfer_id -> TransferProgress
        self.libraries: Dict[str, SharedLibrary] = {}
        self.subscribed_libraries: Dict[str, SharedLibrary] = {}
        self.friends: Dict[str, PeerInfo] = {}
        self.pending_syncs: List[SyncUpdate] = []
        
        # Keys and encryption
        self.private_key = self._load_or_generate_keys()
        self.public_key = self.private_key.public_key()
        
        # UPnP and NAT traversal
        self.upnp = None
        self.external_ip = None
        self.external_port = None
        self.nat_type = NAT_TYPES["UNKNOWN"]
        
        # Network state
        self.listening = False
        self.server = None
        self.port = self._select_port()
        
        # Event hooks
        self.on_transfer_progress: Optional[Callable[[TransferProgress], None]] = None
        self.on_peer_connected: Optional[Callable[[PeerInfo], None]] = None
        self.on_transfer_complete: Optional[Callable[[str, str], None]] = None
        
        # Initialize UPnP if enabled
        if self.share_config.upnp:
            self._setup_upnp()
            
        # Start background tasks
        self._start_maintenance_tasks()
        
    def _generate_peer_id(self) -> str:
        """Generate a unique peer ID"""
        random_part = binascii.hexlify(os.urandom(8)).decode()
        return f"{P2P_ID_PREFIX}{random_part}"
        
    def _load_or_generate_keys(self) -> rsa.RSAPrivateKey:
        """Load existing or generate new RSA keypair"""
        key_path = os.path.join(self.keys_dir, "private_key.pem")
        
        if os.path.exists(key_path):
            try:
                with open(key_path, "rb") as f:
                    from cryptography.hazmat.primitives.serialization import load_pem_private_key
                    private_key = load_pem_private_key(
                        f.read(),
                        password=None,
                        backend=default_backend()
                    )
                    logger.debug("Loaded existing RSA key")
                    return private_key
            except Exception as e:
                logger.warning(f"Failed to load RSA key: {e}")
                
        # Generate new key
        private_key = rsa.generate_private_key(
            public_exponent=65537,
            key_size=2048,
            backend=default_backend()
        )
        
        # Save the new key
        try:
            from cryptography.hazmat.primitives.serialization import (
                Encoding, PrivateFormat, NoEncryption
            )
            with open(key_path, "wb") as f:
                f.write(private_key.private_bytes(
                    encoding=Encoding.PEM,
                    format=PrivateFormat.PKCS8,
                    encryption_algorithm=NoEncryption()
                ))
            logger.debug("Generated and saved new RSA key")
        except Exception as e:
            logger.warning(f"Failed to save RSA key: {e}")
            
        return private_key
        
    def _select_port(self) -> int:
        """Select an available port in the configured range"""
        min_port, max_port = self.share_config.port_range
        
        for _ in range(10):  # Try 10 times
            port = random.randint(min_port, max_port)
            
            # Check if port is available
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.settimeout(0.5)
                result = s.connect_ex(('127.0.0.1', port))
                if result != 0:  # Port is available
                    return port
                    
        # Fall back to a random port and let the OS pick
        return 0
        
    def _setup_upnp(self) -> bool:
        """Set up UPnP port mapping"""
        try:
            self.upnp = miniupnpc.UPnP()
            self.upnp.discoverdelay = 200  # ms
            
            # Discover UPnP devices
            logger.debug("Discovering UPnP devices...")
            discover_count = self.upnp.discover()
            if discover_count < 1:
                logger.warning("No UPnP devices found")
                return False
                
            logger.debug(f"Found {discover_count} UPnP devices")
            
            # Select first IGD (Internet Gateway Device)
            self.upnp.selectigd()
            
            # Get external IP
            self.external_ip = self.upnp.externalipaddress()
            logger.debug(f"UPnP external IP: {self.external_ip}")
            
            # Add port mapping
            # Note: We'll actually add the mapping later when we know the listening port
            return True
            
        except Exception as e:
            logger.warning(f"UPnP setup failed: {e}")
            return False
            
    def _add_port_mapping(self, port: int) -> bool:
        """Add UPnP port mapping"""
        if not self.upnp:
            return False
        try:
            # Delete any existing mapping first
            try:
                self.upnp.deleteportmapping(port, 'TCP')
            except Exception:
                pass  # Ignore errors here
                
            # Add new mapping
            result = self.upnp.addportmapping(
                port,              # External port
                'TCP',             # Protocol
                self.upnp.lanaddr, # Internal host
                port,              # Internal port
                f'Snatch P2P {self.peer_id}',  # Description
                ''                 # Remote host (empty for any)
            )
            
            if result:
                logger.debug(f"Added UPnP port mapping for port {port}")
                self.external_port = port
                return True
            else:
                logger.warning(f"Failed to add UPnP port mapping for port {port}")
                return False
                
        except Exception as e:
            logger.warning(f"Error adding UPnP port mapping: {e}")
            return False
            
    def _start_maintenance_tasks(self) -> None:
        """Start background maintenance tasks"""
        # Start in a separate thread to avoid blocking
        threading.Thread(target=self._run_maintenance_loop, daemon=True).start()
        
    def _run_maintenance_loop(self) -> None:
        """Background maintenance loop"""
        while True:
            try:
                # Clean up expired peers
                self._cleanup_peers()
                
                # Send keepalive to connected peers
                self._ping_peers()
                
                # Update transfer stats
                self._update_transfer_stats()
                
            except Exception as e:
                logger.error(f"Error in maintenance loop: {e}")
                
            # Sleep for maintenance interval
            time.sleep(30)  # 30 second interval
            
    def _cleanup_peers(self) -> None:
        """Remove expired peer connections"""
        now = time.time()
        expired_peers = []
        
        for peer_id, peer in self.peers.items():
            # Consider peer expired if not seen in 5 minutes
            if now - peer.last_seen > 300:  # 5 minutes
                expired_peers.append(peer_id)
                  # Remove expired peers
        for peer_id in expired_peers:
            logger.debug(f"Removing expired peer: {peer_id}")
            self.peers.pop(peer_id, None)
            
    def _ping_peers(self) -> None:
        """Send keepalive pings to connected peers"""
        for peer_id, peer in self.peers.items():
            if peer.connected:
                try:
                    # Send ping in a non-blocking way
                    threading.Thread(
                        target=self._send_ping,
                        args=(peer,),
                        daemon=True
                    ).start()
                except Exception as e:
                    logger.warning(f"Error sending ping to peer {peer_id}: {e}")
                    
    def _send_ping(self, peer: PeerInfo) -> None:
        """Send ping message to a peer"""
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.settimeout(5)  # Increased timeout for stability
                s.connect((peer.ip, peer.port))
                
                # Create ping message
                message = {
                    "type": MSG_TYPE["PING"],
                    "peer_id": self.peer_id,
                    "timestamp": time.time()
                }
                
                # Send encrypted if we have a symmetric key
                if peer.symmetric_key and self.share_config.encryption:
                    try:
                        message_data = self._encrypt_message(message, peer.symmetric_key)
                    except Exception as encrypt_error:
                        logger.warning(f"Encryption failed for ping to {peer.peer_id}: {encrypt_error}")
                        message_data = json.dumps(message).encode()
                else:
                    message_data = json.dumps(message).encode()
                    
                # Send message with length prefix
                s.sendall(len(message_data).to_bytes(4, byteorder="big"))
                s.sendall(message_data)
                
                # Wait for pong response with increased timeout
                s.settimeout(3)
                try:
                    response_length = s.recv(4)
                    if response_length:
                        length = int.from_bytes(response_length, byteorder="big")
                        if length > 0 and length < 10240:  # Reasonable size limit
                            response_data = s.recv(length)
                            # Successfully received pong
                            peer.last_seen = time.time()
                            logger.debug(f"Ping successful for peer {peer.peer_id}")
                except socket.timeout:
                    logger.debug(f"Ping timeout for peer {peer.peer_id}")
                    
        except Exception as e:
            # If ping fails, mark peer as disconnected
            peer.connected = False
            logger.debug(f"Ping failed for peer {peer.peer_id}: {e}")
            
    def _update_transfer_stats(self) -> None:
        """Update transfer statistics"""
        now = time.time()
        
        for transfer_id, progress in self.transfers.items():
            if progress.status not in ("active", "paused"):
                continue
                
            # Calculate speed
            time_diff = now - progress.last_update
            if time_diff > 0:
                bytes_diff = progress.bytes_transferred - getattr(progress, "_last_bytes", 0)
                progress.speed_bps = bytes_diff / time_diff
                
                # Calculate ETA
                remaining_bytes = progress.total_bytes - progress.bytes_transferred
                if progress.speed_bps > 0:
                    progress.eta_seconds = remaining_bytes / progress.speed_bps
                    
                # Store current bytes for next update
                progress._last_bytes = progress.bytes_transferred
                progress.last_update = now
                
                # Call progress callback if registered
                if self.on_transfer_progress:
                    self.on_transfer_progress(progress)
                    
    async def start_server(self) -> bool:
        """Start P2P server to listen for connections"""
        if self.listening:
            logger.warning("P2P server is already running")
            return True
            
        try:
            # Create server socket
            self.server = await asyncio.start_server(
                self._handle_connection,
                "0.0.0.0",  # Listen on all interfaces
                self.port,
                family=socket.AF_INET
            )
            
            # Get actual listening port (in case we used port 0)
            socket_info = self.server.sockets[0].getsockname()
            self.port = socket_info[1]
            logger.info(f"P2P server listening on port {self.port}")
            
            # Set up UPnP port mapping if enabled
            if self.share_config.upnp and self.upnp:
                self._add_port_mapping(self.port)
                
            # Determine external IP and NAT type
            threading.Thread(
                target=self._detect_nat_type,
                daemon=True
            ).start()
            
            # Mark as listening
            self.listening = True
            
            # Start serving
            asyncio.create_task(self.server.serve_forever())
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to start P2P server: {e}")
            return False
            
    async def stop_server(self) -> None:
        """Stop P2P server"""
        if not self.listening:
            return
            
        # Close server
        if self.server:
            self.server.close()
            await self.server.wait_closed()
            self.server = None
            
        # Remove UPnP port mapping if it was set up
        if self.share_config.upnp and self.upnp and self.external_port:
            try:
                self.upnp.deleteportmapping(self.external_port, 'TCP')
                logger.debug(f"Removed UPnP port mapping for port {self.external_port}")
            except Exception as e:
                logger.warning(f"Error removing UPnP port mapping: {e}")
                self.listening = False
        logger.info("P2P server stopped")
        
    async def _handle_connection(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        """Handle incoming connection"""
        peer_addr = writer.get_extra_info('peername')
        logger.debug(f"New connection from {peer_addr}")
        
        try:
            # Read and validate message
            message, peer = await self._read_and_parse_message(reader, writer, peer_addr)
            if not message:
                return
                
            # Route message to appropriate handler
            await self._route_message(message, reader, writer, peer)
                
        except Exception as e:
            logger.error(f"Error handling connection: {e}")
            
        finally:
            writer.close()
            
    async def _read_and_parse_message(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter, peer_addr) -> Tuple[Optional[Dict[str, Any]], Optional[PeerInfo]]:
        """Read and parse incoming message, handling encryption if needed"""
        # Read message length
        length_bytes = await reader.read(4)
        if not length_bytes:
            logger.warning(f"Empty connection from {peer_addr}")
            writer.close()
            return None, None
            
        message_length = int.from_bytes(length_bytes, byteorder="big")
        
        # Read message data
        message_data = await reader.read(message_length)
        if not message_data:
            logger.warning(f"Failed to read message from {peer_addr}")
            writer.close()
            return None, None
            
        # Parse message with encryption handling
        return await self._parse_message_with_encryption(message_data, peer_addr, writer)
    async def _parse_message_with_encryption(self, message_data: bytes, peer_addr: Tuple[str, int], writer: asyncio.StreamWriter) -> Tuple[Optional[Dict[str, Any]], Optional[PeerInfo]]:
        """Parse message, handling encryption/decryption as needed"""
        # Try unencrypted parsing first
        unencrypted_result = self._try_parse_unencrypted(message_data)
        if unencrypted_result:
            return unencrypted_result, None
            
        # Try encrypted parsing
        return await self._try_parse_encrypted(message_data, peer_addr, writer)

    def _try_parse_unencrypted(self, message_data: bytes) -> Optional[Dict[str, Any]]:
        """Try to parse message as unencrypted JSON"""
        try:
            return json.loads(message_data.decode())
        except (json.JSONDecodeError, UnicodeDecodeError):
            return None

    async def _try_parse_encrypted(self, message_data: bytes, peer_addr: Tuple[str, int], writer: asyncio.StreamWriter) -> Tuple[Optional[Dict[str, Any]], Optional[PeerInfo]]:
        """Try to parse message as encrypted data"""
        peer_ip, _ = peer_addr
        peer = self._find_peer_for_decryption(peer_ip, message_data)
        
        if not peer:
            logger.warning(f"Could not decrypt message from {peer_addr}")
            writer.close()
            return None, None
            
        return self._decrypt_and_parse_message(message_data, peer, peer_addr, writer)

    def _decrypt_and_parse_message(self, message_data: bytes, peer: PeerInfo, peer_addr: Tuple[str, int], writer: asyncio.StreamWriter) -> Tuple[Optional[Dict[str, Any]], Optional[PeerInfo]]:
        """Decrypt message data and parse as JSON"""
        try:
            decrypted = self._decrypt_message(message_data, peer.symmetric_key)
            message = json.loads(decrypted.decode())
            return message, peer
        except Exception as e:
            logger.warning(f"Failed to decrypt message from {peer_addr}: {e}")
            writer.close()
            return None, None
                
    def _find_peer_for_decryption(self, peer_ip: str, message_data: bytes) -> Optional[PeerInfo]:
        """Find peer that can decrypt the message"""
        for p in self.peers.values():
            if p.ip == peer_ip and p.symmetric_key:
                try:
                    # Try to decrypt with this peer's key
                    self._decrypt_message(message_data, p.symmetric_key)
                    return p            
                except Exception as e:
                    logger.debug(f"Failed to decrypt with peer {p.peer_id} key: {e}")
                    continue
        return None
    async def _route_message(self, message: Dict[str, Any], reader: asyncio.StreamReader, writer: asyncio.StreamWriter, peer: Optional[PeerInfo]) -> None:
        """Route message to appropriate handler based on type"""
        message_type = message.get("type")
        
        if message_type == MSG_TYPE["HANDSHAKE"]:
            await self._handle_handshake(message, writer)
        elif message_type == MSG_TYPE["REQUEST"]:
            await self._handle_request(message, reader, writer, peer)
        elif message_type == MSG_TYPE["DATA"]:
            await self._handle_data(message, reader, writer, peer)
        elif message_type == MSG_TYPE["PING"]:
            await self._handle_ping(message, writer, peer)
        elif message_type == MSG_TYPE["KEY_EXCHANGE"]:
            await self._handle_key_exchange(message, reader, writer)
        elif message_type == MSG_TYPE["LIBRARY_UPDATE"]:
            await self._handle_library_update(message, reader, writer, peer)
        elif message_type == MSG_TYPE["FRIEND_REQUEST"]:
            await self._handle_friend_request(message, reader, writer, peer)
        elif message_type == MSG_TYPE["FRIEND_RESPONSE"]:
            await self._handle_friend_response(message, reader, writer, peer)
        else:
            logger.warning(f"Unknown message type: {message_type}")
            
    async def _handle_handshake(self, message: Dict[str, Any], writer: asyncio.StreamWriter) -> None:
        """Handle handshake message"""
        peer_addr = writer.get_extra_info('peername')
        peer_id = message.get("peer_id")
        
        if not peer_id:
            logger.warning(f"Invalid handshake from {peer_addr}: missing peer_id")
            return
            
        # Create or update peer info
        peer = self._create_or_update_peer(peer_id, peer_addr, message)
        
        # Parse public key if provided
        self._parse_peer_public_key(peer, message)
                
        # Send handshake response
        await self._send_handshake_response(writer, peer_id)
        
    def _create_or_update_peer(self, peer_id: str, peer_addr: Tuple[str, int], message: Dict[str, Any]) -> PeerInfo:
        """Create new peer or update existing peer info"""
        peer_ip, peer_port = peer_addr
        
        if peer_id in self.peers:
            # Update existing peer
            peer = self.peers[peer_id]
            peer.ip = peer_ip
            peer.port = peer_port
            peer.last_seen = time.time()
            peer.connected = True
            peer.nat_type = message.get("nat_type", NAT_TYPES["UNKNOWN"])
        else:
            # Create new peer
            peer = PeerInfo(
                peer_id=peer_id,
                ip=peer_ip,
                port=peer_port,
                nat_type=message.get("nat_type", NAT_TYPES["UNKNOWN"]),
                connected=True
            )
            self.peers[peer_id] = peer
            
        return peer
        
    def _parse_peer_public_key(self, peer: PeerInfo, message: Dict[str, Any]) -> None:
        """Parse and store peer's public key if provided"""
        if public_key_data := message.get("public_key"):
            from cryptography.hazmat.primitives.serialization import load_der_public_key
            try:
                peer.public_key = load_der_public_key(
                    binascii.unhexlify(public_key_data),
                    backend=default_backend()
                )
            except Exception as e:
                logger.warning(f"Failed to parse public key: {e}")
                
    async def _send_handshake_response(self, writer: asyncio.StreamWriter, peer_id: str) -> None:
        """Send handshake response to peer"""
        # Create response
        response = {
            "type": MSG_TYPE["HANDSHAKE"],
            "peer_id": self.peer_id,
            "nat_type": self.nat_type,
            "protocol_version": PROTOCOL_VERSION,
            "features": {
                "encryption": self.share_config.encryption,
                "compression": self.share_config.compression
            }
        }
        
        # Include public key if we support encryption
        if self.share_config.encryption:
            from cryptography.hazmat.primitives.serialization import (
                Encoding, PublicFormat
            )
            response["public_key"] = binascii.hexlify(
                self.public_key.public_bytes(
                    encoding=Encoding.DER,
                    format=PublicFormat.SubjectPublicKeyInfo
                )
            ).decode()
            
        # Send response
        response_data = json.dumps(response).encode()
        writer.write(len(response_data).to_bytes(4, byteorder="big"))
        writer.write(response_data)
        await writer.drain()
        
        logger.debug(f"Completed handshake with peer {peer_id}")
        
        # Notify peer connected callback
        if self.on_peer_connected:
            peer = self.peers[peer_id]
            self.on_peer_connected(peer)
    async def _handle_key_exchange(self, message: Dict[str, Any], writer: asyncio.StreamWriter) -> None:
        """Handle key exchange message"""
        peer_id = message.get("peer_id")
        
        if not peer_id or peer_id not in self.peers:
            logger.warning(f"Key exchange from unknown peer: {peer_id}")
            return
            
        peer = self.peers[peer_id]
        
        # Extract encrypted key
        encrypted_key = message.get("encrypted_key")
        if not encrypted_key:
            logger.warning(f"Missing encrypted key in key exchange from {peer_id}")
            return
            
        try:
            # Decrypt symmetric key using our private key
            from cryptography.hazmat.primitives.asymmetric import padding as asym_padding
            from cryptography.hazmat.primitives import hashes
            
            encrypted_key_bytes = binascii.unhexlify(encrypted_key)
            symmetric_key = self.private_key.decrypt(
                encrypted_key_bytes,
                asym_padding.OAEP(
                    mgf=asym_padding.MGF1(algorithm=hashes.SHA256()),
                    algorithm=hashes.SHA256(),
                    label=None
                )
            )
            
            # Store symmetric key for this peer
            peer.symmetric_key = symmetric_key
            logger.debug(f"Completed key exchange with peer {peer_id}")
            
            # Send acknowledgement
            response = {
                "type": MSG_TYPE["ACK"],
                "peer_id": self.peer_id,
                "message_id": message.get("message_id", "")
            }
            
            # Encrypt response
            response_data = self._encrypt_message(response, symmetric_key)
            writer.write(len(response_data).to_bytes(4, byteorder="big"))
            writer.write(response_data)
            await writer.drain()
            
        except Exception as e:
            logger.error(f"Error processing key exchange: {e}")
            
    def _encrypt_message(self, message: Dict[str, Any], key: bytes) -> bytes:
        """Encrypt a message using AES-GCM"""
        try:
            # Convert message to JSON bytes
            message_bytes = json.dumps(message).encode()
            
            # Generate random IV
            iv = os.urandom(12)  # 96 bits for GCM
            
            # Create AES-GCM cipher
            cipher = Cipher(
                algorithms.AES(key),
                modes.GCM(iv),
                backend=default_backend()
            )
            
            # Encrypt
            encryptor = cipher.encryptor()
            ciphertext = encryptor.update(message_bytes) + encryptor.finalize()
            
            # Combine IV, ciphertext, and tag
            result = iv + encryptor.tag + ciphertext
            
            return result
            
        except Exception as e:
            logger.error(f"Encryption error: {e}")
            raise EncryptionError(f"Failed to encrypt message: {e}")
            
    def _decrypt_message(self, data: bytes, key: bytes) -> bytes:
        """Decrypt an AES-GCM encrypted message"""
        try:
            # Extract IV (12 bytes) and tag (16 bytes)
            iv = data[:12]
            tag = data[12:28]
            ciphertext = data[28:]
            
            # Create AES-GCM cipher
            cipher = Cipher(
                algorithms.AES(key),
                modes.GCM(iv, tag),
                backend=default_backend()
            )
            
            # Decrypt
            decryptor = cipher.decryptor()
            plaintext = decryptor.update(ciphertext) + decryptor.finalize()
            
            return plaintext
            
        except Exception as e:
            logger.error(f"Decryption error: {e}")
            raise EncryptionError(f"Failed to decrypt message: {e}")
            
    async def _handle_ping(self, message: Dict[str, Any], writer: asyncio.StreamWriter, peer: Optional[PeerInfo] = None) -> None:
        """Handle ping message"""
        peer_id = message.get("peer_id")
        
        if peer_id and peer_id in self.peers:
            peer = self.peers[peer_id]
            peer.last_seen = time.time()
            
        # Send pong response
        response = {
            "type": MSG_TYPE["PONG"],
            "peer_id": self.peer_id,
            "timestamp": time.time(),
            "echo": message.get("timestamp", 0)
        }
        
        # Encrypt if we have a symmetric key and encryption is enabled
        if peer and peer.symmetric_key and self.share_config.encryption:
            response_data = self._encrypt_message(response, peer.symmetric_key)
        else:
            response_data = json.dumps(response).encode()
            
        # Send response
        writer.write(len(response_data).to_bytes(4, byteorder="big"))
        writer.write(response_data)
        await writer.drain()
        
    async def _handle_request(self, message: Dict[str, Any], reader: asyncio.StreamReader, writer: asyncio.StreamWriter, peer: PeerInfo) -> None:
        """Handle file request message"""
        try:
            file_id = message.get("file_id")
            if not file_id or file_id not in self.shared_files:
                await self._send_error_response(writer, "File not found", peer)
                return
                
            file_info = self.shared_files[file_id]
            
            # Check if file still exists
            if not os.path.exists(file_info.file_path):
                await self._send_error_response(writer, "File no longer available", peer)
                return
                
            # Send file metadata
            response = {
                "type": MSG_TYPE["RESPONSE"],
                "file_id": file_id,
                "file_name": file_info.file_name,
                "file_size": file_info.file_size,
                "chunks": file_info.chunks,
                "chunk_size": self.share_config.chunk_size
            }
            
            # Encrypt response if possible
            if peer.symmetric_key and self.share_config.encryption:
                response_data = self._encrypt_message(response, peer.symmetric_key)
            else:
                response_data = json.dumps(response).encode()
                
            # Send response
            writer.write(len(response_data).to_bytes(4, byteorder="big"))
            writer.write(response_data)
            await writer.drain()
            
            # Handle chunk requests
            await self._handle_chunk_requests(file_info, reader, writer, peer)
            
        except Exception as e:
            logger.error(f"Error handling request: {e}")
            await self._send_error_response(writer, str(e), peer)
    
    async def _send_error_response(self, writer: asyncio.StreamWriter, error_msg: str, peer: Optional[PeerInfo] = None) -> None:
        """Send error response to peer"""
        try:
            response = {
                "type": MSG_TYPE["ERROR"],
                "error": error_msg,
                "timestamp": time.time()
            }
            
            # Encrypt if possible
            if peer and peer.symmetric_key and self.share_config.encryption:
                response_data = self._encrypt_message(response, peer.symmetric_key)
            else:
                response_data = json.dumps(response).encode()
                
            writer.write(len(response_data).to_bytes(4, byteorder="big"))
            writer.write(response_data)
            await writer.drain()
            
        except Exception as e:
            logger.error(f"Error sending error response: {e}")
    async def _handle_chunk_requests(self, file_info: 'FileInfo', reader: asyncio.StreamReader, writer: asyncio.StreamWriter, peer: PeerInfo) -> None:
        """Handle chunk data requests for file transfer"""
        try:
            with open(file_info.file_path, 'rb') as f:
                while True:
                    chunk_request = await self._read_chunk_request(reader, peer)
                    if not chunk_request:
                        break
                        
                    if not self._validate_chunk_request(chunk_request, file_info):
                        continue
                        
                    chunk_index = chunk_request["chunk_index"]
                    chunk_data = self._read_file_chunk(f, chunk_index)
                    
                    await self._send_chunk_response(writer, chunk_index, chunk_data, peer)
                    
        except Exception as e:
            logger.error(f"Error handling chunk requests: {e}")
            await self._send_error_response(writer, str(e), peer)

    async def _read_chunk_request(self, reader: asyncio.StreamReader, peer: PeerInfo) -> Optional[Dict[str, Any]]:
        """Read and parse a chunk request from the stream"""
        try:
            length_bytes = await reader.read(4)
            if not length_bytes:
                return None
                
            message_length = int.from_bytes(length_bytes, byteorder="big")
            message_data = await reader.read(message_length)
            
            if peer.symmetric_key and self.share_config.encryption:
                chunk_request = json.loads(self._decrypt_message(message_data, peer.symmetric_key).decode())
            else:
                chunk_request = json.loads(message_data.decode())
                
            return chunk_request
        except Exception as e:
            logger.error(f"Error reading chunk request: {e}")
            return None

    def _validate_chunk_request(self, chunk_request: Dict[str, Any], file_info: 'FileInfo') -> bool:
        """Validate that the chunk request is valid"""
        if chunk_request.get("type") != MSG_TYPE["CHUNK_REQUEST"]:
            return False
            
        chunk_index = chunk_request.get("chunk_index")
        if chunk_index is None or chunk_index >= file_info.chunks:
            return False
            
        return True

    def _read_file_chunk(self, file_handle, chunk_index: int) -> bytes:
        """Read a specific chunk from the file"""
        file_handle.seek(chunk_index * self.share_config.chunk_size)
        return file_handle.read(self.share_config.chunk_size)

    async def _send_chunk_response(self, writer: asyncio.StreamWriter, chunk_index: int, 
                                   chunk_data: bytes, peer: PeerInfo) -> None:
        """Send a chunk response to the peer"""
        response = {
            "type": MSG_TYPE["CHUNK_DATA"],
            "chunk_index": chunk_index,
            "data": chunk_data.hex(),  # Send as hex string
            "size": len(chunk_data)
        }
        
        if peer.symmetric_key and self.share_config.encryption:
            response_data = self._encrypt_message(response, peer.symmetric_key)
        else:
            response_data = json.dumps(response).encode()
            
        writer.write(len(response_data).to_bytes(4, byteorder="big"))
        writer.write(response_data)
        await writer.drain()
            
    async def _handle_request_legacy(self, message: Dict[str, Any], writer: asyncio.StreamWriter, peer: PeerInfo) -> None:
        """Handle file request message"""
        file_id = message.get("file_id")
        
        if not file_id or file_id not in self.shared_files:
            # Send error response
            response = {
                "type": MSG_TYPE["ERROR"],
                "peer_id": self.peer_id,
                "error_code": 404,
                "error_message": f"File not found: {file_id}"
            }
        else:
            # Get file info
            file_info = self.shared_files[file_id]
            
            # Send file info response
            response = {
                "type": MSG_TYPE["RESPONSE"],
                "peer_id": self.peer_id,
                "file_id": file_id,
                "file_info": {
                    "name": file_info.name,
                    "size": file_info.size,
                    "hash": file_info.hash,
                    "chunk_count": len(file_info.chunk_hashes),
                    "mime_type": file_info.mime_type
                }
            }
            
        # Encrypt response if possible
        if peer.symmetric_key and self.share_config.encryption:
            response_data = self._encrypt_message(response, peer.symmetric_key)
        else:
            response_data = json.dumps(response).encode()
            
        # Send response
        writer.write(len(response_data).to_bytes(4, byteorder="big"))
        writer.write(response_data)
        await writer.drain()
        
    async def _handle_data(self, message: Dict[str, Any], reader: asyncio.StreamReader, writer: asyncio.StreamWriter, peer: PeerInfo) -> None:
        """Handle data request message (file chunk request)"""
        file_id = message.get("file_id")
        chunk_index = message.get("chunk_index")
        
        if not file_id or file_id not in self.shared_files:
            # Send error response
            response = {
                "type": MSG_TYPE["ERROR"],
                "peer_id": self.peer_id,
                "error_code": 404,
                "error_message": f"File not found: {file_id}"
            }
            
            # Encrypt response if possible
            if peer.symmetric_key and self.share_config.encryption:
                response_data = self._encrypt_message(response, peer.symmetric_key)
            else:
                response_data = json.dumps(response).encode()
                
            # Send response
            writer.write(len(response_data).to_bytes(4, byteorder="big"))
            writer.write(response_data)
            await writer.drain()
            return
            
        # Get file info
        file_info = self.shared_files[file_id]
        
        try:
            # Open file and read requested chunk
            with open(file_info.file_path, "rb") as f:
                chunk_size = self.share_config.chunk_size
                f.seek(chunk_index * chunk_size)
                chunk_data = f.read(chunk_size)
                
            # Calculate chunk hash
            chunk_hash = hashlib.sha256(chunk_data).hexdigest()
            
            # Build response
            response = {
                "type": MSG_TYPE["DATA"],
                "peer_id": self.peer_id,
                "file_id": file_id,
                "chunk_index": chunk_index,
                "chunk_hash": chunk_hash,
                "final_chunk": chunk_index == len(file_info.chunks) - 1
            }
            
            # Encrypt response header if possible
            if peer.symmetric_key and self.share_config.encryption:
                response_data = self._encrypt_message(response, peer.symmetric_key)
            else:
                response_data = json.dumps(response).encode()
                
            # Send response header
            writer.write(len(response_data).to_bytes(4, byteorder="big"))
            writer.write(response_data)
            
            # Send chunk data length
            writer.write(len(chunk_data).to_bytes(4, byteorder="big"))
            
            # Send chunk data
            writer.write(chunk_data)
            await writer.drain()
            
        except Exception as e:
            logger.error(f"Error sending file chunk: {e}")
            
            # Send error response
            response = {
                "type": MSG_TYPE["ERROR"],
                "peer_id": self.peer_id,
                "error_code": 500,
                "error_message": f"Error reading file chunk: {str(e)}"
            }
            
            # Encrypt response if possible
            if peer.symmetric_key and self.share_config.encryption:
                response_data = self._encrypt_message(response, peer.symmetric_key)
            else:
                response_data = json.dumps(response).encode()
                
            # Send response
            writer.write(len(response_data).to_bytes(4, byteorder="big"))
            writer.write(response_data)
            await writer.drain()

    def _detect_nat_type(self) -> None:
        """Detect NAT type using STUN"""
        try:
            # Try multiple STUN servers to detect NAT type
            results = []
            for server in self.share_config.stun_servers:
                result = self._try_stun_server(server)
                if result:
                    results.append(result)
                    break
            
            if results:
                # Process first successful result
                self._process_stun_result(results[0])
            else:
                logger.warning("Failed to contact any STUN servers")
                self.nat_type = NAT_TYPES["UNKNOWN"]
                
        except Exception as e:
            logger.error(f"NAT type detection failed: {e}")
            self.nat_type = NAT_TYPES["UNKNOWN"]

    def _try_stun_server(self, server: str) -> Optional[Tuple[str, int]]:
        """Try to get mapped address from a single STUN server"""
        try:
            host, port_str = server.split(":")
            port = int(port_str)
            
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
                s.settimeout(3)
                
                # Send STUN binding request
                transaction_id = os.urandom(12)
                binding_request = self._create_stun_request(transaction_id)
                s.sendto(binding_request, (host, port))
                
                # Receive and parse response
                response, addr = s.recvfrom(1024)
                return self._parse_stun_response(response)
                
        except Exception as e:
            logger.debug(f"STUN error with server {server}: {e}")
            return None

    def _create_stun_request(self, transaction_id: bytes) -> bytes:
        """Create STUN binding request packet"""
        return (bytes([0x00, 0x01]) + bytes([0x00, 0x00]) + 
                bytes([0x21, 0x12, 0xA4, 0x42]) + transaction_id)

    def _parse_stun_response(self, response: bytes) -> Optional[Tuple[str, int]]:
        """Parse STUN response to extract mapped address"""
        try:
            if len(response) < 20:
                return None
            
            # Check STUN header
            msg_type = int.from_bytes(response[0:2], byteorder='big')
            msg_length = int.from_bytes(response[2:4], byteorder='big')
            
            if msg_type != 0x0101:  # Binding Response
                return None
            
            # Parse attributes
            offset = 20
            while offset < len(response):
                if offset + 4 > len(response):
                    break
                    
                attr_type = int.from_bytes(response[offset:offset+2], byteorder='big')
                attr_length = int.from_bytes(response[offset+2:offset+4], byteorder='big')
                
                if attr_type == 0x0001:  # MAPPED-ADDRESS
                    return self._extract_mapped_address(response, offset + 4)
                    
                # Move to next attribute
                offset += 4 + attr_length
                
        except Exception as e:
            logger.debug(f"Error parsing STUN response: {e}")
        
        return None

    def _extract_mapped_address(self, response: bytes, offset: int) -> Optional[Tuple[str, int]]:
        """Extract IP and port from MAPPED-ADDRESS attribute"""
        try:
            if offset + 8 > len(response):
                return None
            
            # Skip reserved byte
            family = response[offset + 1]
            if family != 0x01:  # IPv4
                return None
            
            # Extract port and IP
            port = int.from_bytes(response[offset+2:offset+4], byteorder='big')
            ip_bytes = response[offset+4:offset+8]
            ip = ".".join(str(b) for b in ip_bytes)
            
            return (ip, port)
            
        except Exception as e:
            logger.debug(f"Error extracting mapped address: {e}")
            return None

    def _process_stun_result(self, mapped_addr: Tuple[str, int]) -> None:
        """Process STUN result to determine NAT type"""
        self.external_ip, self.external_port = mapped_addr
        
        # Simple NAT type detection
        local_ip = self._get_local_ip()
        if self.external_ip == local_ip:
            self.nat_type = NAT_TYPES["OPEN"]
        else:
            # Assume restricted cone NAT for now
            self.nat_type = NAT_TYPES["RESTRICTED_CONE"]
        
        logger.debug(f"Detected NAT type: {self.nat_type}, External: {self.external_ip}:{self.external_port}")

    def _get_local_ip(self) -> str:
        """Get local IP address of the default interface"""
        try:
            # Create a socket to determine local IP
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
                s.connect(("8.8.8.8", 80))
                return s.getsockname()[0]
        except Exception:
            return "127.0.0.1"
            
    async def connect_to_peer(self, address: str) -> Optional[PeerInfo]:
        """Connect to a peer and perform handshake
        
        Args:
            address: Peer address in format "ip:port"
            
        Returns:
            PeerInfo if connection successful, None otherwise
        """
        try:
            # Parse address
            ip, port_str = address.split(":")
            port = int(port_str)
            
            # Connect to peer
            reader, writer = await asyncio.open_connection(
                ip, port, family=socket.AF_INET
            )
            
            # Prepare handshake message
            handshake = {
                "type": MSG_TYPE["HANDSHAKE"],
                "peer_id": self.peer_id,
                "protocol_version": PROTOCOL_VERSION,
                "nat_type": self.nat_type,
                "features": {
                    "encryption": self.share_config.encryption,
                    "compression": self.share_config.compression
                }
            }
            
            # Include public key if we support encryption
            if self.share_config.encryption:
                from cryptography.hazmat.primitives.serialization import (
                    Encoding, PublicFormat
                )
                handshake["public_key"] = binascii.hexlify(
                    self.public_key.public_bytes(
                        encoding=Encoding.DER,
                        format=PublicFormat.SubjectPublicKeyInfo
                    )
                ).decode()
                
            # Send handshake
            handshake_data = json.dumps(handshake).encode()
            writer.write(len(handshake_data).to_bytes(4, byteorder="big"))
            writer.write(handshake_data)
            await writer.drain()
            
            # Read response length
            try:
                length_bytes = await asyncio.wait_for(reader.read(4), 5.0)
                if not length_bytes:
                    logger.warning(f"Empty response from {address}")
                    writer.close()
                    return None
                    
                message_length = int.from_bytes(length_bytes, byteorder="big")
                
                # Read response data
                message_data = await asyncio.wait_for(reader.read(message_length), 5.0)
                if not message_data:
                    logger.warning(f"Failed to read response from {address}")
                    writer.close()
                    return None
                    
                # Parse response
                response = json.loads(message_data.decode())
                
                # Check if it's a handshake response
                if response.get("type") != MSG_TYPE["HANDSHAKE"]:
                    logger.warning(f"Expected handshake response, got {response.get('type')}")
                    writer.close()
                    return None
                    
                # Extract peer ID
                peer_id = response.get("peer_id")
                if not peer_id:
                    logger.warning("Missing peer ID in handshake response")
                    writer.close()
                    return None
                    
                # Create or update peer info
                if peer_id in self.peers:
                    # Update existing peer
                    peer = self.peers[peer_id]
                    peer.ip = ip
                    peer.port = port
                    peer.last_seen = time.time()
                    peer.connected = True
                    peer.nat_type = response.get("nat_type", NAT_TYPES["UNKNOWN"])
                else:
                    # Create new peer
                    peer = PeerInfo(
                        peer_id=peer_id,
                        ip=ip,
                        port=port,
                        nat_type=response.get("nat_type", NAT_TYPES["UNKNOWN"]),
                        connected=True
                    )
                    self.peers[peer_id] = peer
                    
                # Parse public key if provided
                if public_key_data := response.get("public_key"):
                    from cryptography.hazmat.primitives.serialization import load_der_public_key
                    try:
                        peer.public_key = load_der_public_key(
                            binascii.unhexlify(public_key_data),
                            backend=default_backend()
                        )
                    except Exception as e:
                        logger.warning(f"Failed to parse public key: {e}")
                        
                # If we support encryption and have the peer's public key, establish a symmetric key
                if self.share_config.encryption and peer.public_key:
                    await self._establish_symmetric_key(peer, writer)
                    
                logger.debug(f"Connected to peer {peer_id} at {address}")
                
                # Notify peer connected callback
                if self.on_peer_connected:
                    self.on_peer_connected(peer)
                    
                writer.close()
                return peer
                
            except asyncio.TimeoutError:
                logger.warning(f"Timeout waiting for handshake response from {address}")
                writer.close()
                return None
                
        except Exception as e:
            logger.error(f"Error connecting to peer {address}: {e}")
            return None
            
    async def _establish_symmetric_key(self, peer: PeerInfo, writer: asyncio.StreamWriter) -> bool:
        """Establish a symmetric encryption key with a peer"""
        try:
            # Generate a random symmetric key
            symmetric_key = os.urandom(32)  # 256-bit AES key
            
            # Encrypt the symmetric key with the peer's public key
            from cryptography.hazmat.primitives.asymmetric import padding as asym_padding
            from cryptography.hazmat.primitives import hashes
            
            encrypted_key = peer.public_key.encrypt(
                symmetric_key,
                asym_padding.OAEP(
                    mgf=asym_padding.MGF1(algorithm=hashes.SHA256()),
                    algorithm=hashes.SHA256(),
                    label=None
                )
            )
            
            # Create key exchange message
            message = {
                "type": MSG_TYPE["KEY_EXCHANGE"],
                "peer_id": self.peer_id,
                "message_id": binascii.hexlify(os.urandom(8)).decode(),
                "encrypted_key": binascii.hexlify(encrypted_key).decode()
            }
            
            # Send message
            message_data = json.dumps(message).encode()
            writer.write(len(message_data).to_bytes(4, byteorder="big"))
            writer.write(message_data)
            await writer.drain()
            
            # Store symmetric key
            peer.symmetric_key = symmetric_key
            logger.debug(f"Established symmetric key with peer {peer.peer_id}")
            
            return True
            
        except Exception as e:
            logger.error(f"Error establishing symmetric key: {e}")
            return False
        
    async def _handle_library_update(self, message: Dict[str, Any], reader: asyncio.StreamReader, writer: asyncio.StreamWriter, peer: Optional[PeerInfo]) -> None:
        """Handle library update notification"""
        library_id = message.get("library_id")
        update_type = message.get("update_type")
        data = message.get("data")
        
        if update_type == "file_added":
            # New file added to library
            file_info = data.get("file_info")
            if file_info:
                await self._add_file_to_library(library_id, file_info, peer)
                
        elif update_type == "file_removed":
            # File removed from library
            file_id = data.get("file_id")
            if file_id:
                await self._remove_file_from_library(library_id, file_id, peer)
                
        elif update_type == "library_updated":
            # Library metadata updated
            await self._update_library_metadata(library_id, data, peer)
            
    async def _add_file_to_library(self, library_id: str, file_info: Dict[str, Any], peer: Optional[PeerInfo]) -> None:
        """Add a file to a shared library (on receiving notification from peer)"""
        if library_id not in self.libraries:
            logger.warning(f"Library not found: {library_id}")
            return
        
        library = self.libraries[library_id]
        
        # Check if we already have this file
        file_id = file_info.get("file_id")
        if file_id in library.files:
            logger.info(f"File already exists in library: {file_id}")
            return
        
        # Add file to library
        library.files[file_id] = LibraryFile(**file_info)
        library.last_updated = time.time()
        
        self._save_library(library)
        
        logger.info(f"Added new file to library {library.name}: {file_info.get('name')}")
        
    async def _remove_file_from_library(self, library_id: str, file_id: str, peer: Optional[PeerInfo]) -> None:
        """Remove a file from a shared library (on receiving notification from peer)"""
        if library_id not in self.libraries:
            logger.warning(f"Library not found: {library_id}")
            return
        
        library = self.libraries[library_id]
        
        if file_id in library.files:
            # Remove file
            del library.files[file_id]
            library.last_updated = time.time()
            
            self._save_library(library)
            
            logger.info(f"Removed file from library {library.name}: {file_id}")
        else:
            logger.info(f"File not found in library: {file_id}")
            
    async def _update_library_metadata(self, library_id: str, metadata: Dict[str, Any], peer: Optional[PeerInfo]) -> None:
        """Update metadata of a shared library (on receiving notification from peer)"""
        if library_id not in self.libraries:
            logger.warning(f"Library not found: {library_id}")
            return
        
        library = self.libraries[library_id]
        
        # Update library attributes
        library.name = metadata.get("name", library.name)
        library.description = metadata.get("description", library.description)
        library.public = metadata.get("public", library.public)
        library.auto_sync = metadata.get("auto_sync", library.auto_sync)
        library.tags = metadata.get("tags", library.tags)
        library.last_updated = time.time()
        
        self._save_library(library)
        
        logger.info(f"Updated library metadata: {library_id}")
    
    async def _request_library_subscription(self, library_id: str, owner_peer_id: str) -> None:
        """Request subscription to a friend's library"""
        if owner_peer_id not in self.friends:
            logger.warning(f"Peer not found in friends list: {owner_peer_id}")
            return
        
        friend = self.friends[owner_peer_id]
        
        # Send subscription request
        request = {
            "type": MSG_TYPE["LIBRARY_SUBSCRIBE"],
            "library_id": library_id,
            "peer_id": self.peer_id
        }
        
        try:
            await self._send_message_to_peer(friend, request)
            logger.info(f"Sent library subscription request to {owner_peer_id}")
        except Exception as e:
            logger.error(f"Error sending subscription request: {e}")
            
    async def _notify_friendship(self, friend_peer_id: str) -> None:
        """Notify a peer that they have been added as a friend"""
        if friend_peer_id not in self.friends:
            return
        
        friend = self.friends[friend_peer_id]
        
        # Send friend notification
        notification = {
            "type": MSG_TYPE["FRIEND_RESPONSE"],
            "peer_id": self.peer_id,
            "friend_id": friend_peer_id,
            "status": "accepted"
        }
        
        try:
            await self._send_message_to_peer(friend, notification)
            logger.info(f"Notified {friend_peer_id} of friendship acceptance")
        except Exception as e:
            logger.error(f"Error notifying friendship: {e}")
            
    async def _handle_friend_request(self, message: Dict[str, Any], reader: asyncio.StreamReader, writer: asyncio.StreamWriter, peer: Optional[PeerInfo]) -> None:
        """Handle incoming friend request"""
        requester_id = message.get("peer_id")
        
        if not requester_id:
            logger.warning(f"Invalid friend request from {peer.peer_id}: missing peer_id")
            return
        
        # Automatically accept friend requests from known peers
        if requester_id in self.peers:
            await self.add_friend(requester_id, self.peers[requester_id])
            
            # Send response
            response = {
                "type": MSG_TYPE["FRIEND_RESPONSE"],
                "peer_id": self.peer_id,
                "friend_id": requester_id,
                "status": "accepted"
            }
            
            # Encrypt if we have a symmetric key
            if peer.symmetric_key and self.share_config.encryption:
                response_data = self._encrypt_message(response, peer.symmetric_key)
            else:
                response_data = json.dumps(response).encode()
                
            writer.write(len(response_data).to_bytes(4, byteorder="big"))
            writer.write(response_data)
            await writer.drain()
            
            logger.info(f"Automatically accepted friend request from {requester_id}")
        else:
            logger.info(f"Received friend request from {requester_id}, awaiting acceptance")
            
    async def _handle_friend_response(self, message: Dict[str, Any], reader: asyncio.StreamReader, writer: asyncio.StreamWriter, peer: Optional[PeerInfo]) -> None:
        """Handle response to friend request"""
        friend_id = message.get("friend_id")
        status = message.get("status")
        
        if status == "accepted":
            if friend_id and friend_id not in self.friends:
                # Add new friend
                await self.add_friend(friend_id, peer)
                
                logger.info(f"Friend {friend_id} accepted")
            else:
                logger.info(f"Friend {friend_id} already in list")
        else:
            logger.info(f"Friend request from {friend_id} declined")
            
    async def add_friend(self, peer_id: str, peer_info: PeerInfo) -> bool:
        """Add a peer as a friend for library sharing"""
        self.friends[peer_id] = peer_info
        self._save_friends()
        
        logger.info(f"Added friend: {peer_id}")
        
        # Notify friend of friendship
        asyncio.create_task(self._notify_friendship(peer_id))
        return True
    
    def share_library_with_friend(self, library_id: str, friend_peer_id: str) -> bool:
        """Share a library with a specific friend"""
        if library_id not in self.libraries:
            return False
            
        if friend_peer_id not in self.friends:
            return False
            
        library = self.libraries[library_id]
        library.subscribers.add(friend_peer_id)
        library.last_updated = time.time()
        
        self._save_library(library)
        
        # Send library info to friend
        asyncio.create_task(self._share_library_with_peer(library, friend_peer_id))
        return True
    
    def get_library_files(self, library_id: str) -> List[LibraryFile]:
        """Get all files in a library"""
        if library_id in self.libraries:
            return list(self.libraries[library_id].files.values())
        elif library_id in self.subscribed_libraries:
            return list(self.subscribed_libraries[library_id].files.values())
        return []
    
    def search_libraries(self, query: str, category: str = None) -> List[Tuple[str, LibraryFile]]:
        """Search for files across all accessible libraries"""
        results = []
        
        # Search own libraries
        for lib_id, library in self.libraries.items():
            for file_id, file_info in library.files.items():
                if self._file_matches_query(file_info, query, category):
                    results.append((lib_id, file_info))
        
        # Search subscribed libraries
        for lib_id, library in self.subscribed_libraries.items():
            for file_id, file_info in library.files.items():
                if self._file_matches_query(file_info, query, category):
                    results.append((lib_id, file_info))
        
        return results
    
    async def download_from_library(self, library_id: str, file_id: str, output_path: str) -> bool:
        """Download a file from a library (own or subscribed)"""
        library = None
        
        if library_id in self.libraries:
            library = self.libraries[library_id]
        elif library_id in self.subscribed_libraries:
            library = self.subscribed_libraries[library_id]
        else:
            logger.error(f"Library not found: {library_id}")
            return False
            
        if file_id not in library.files:
            logger.error(f"File not found in library: {file_id}")
            return False
            
        file_info = library.files[file_id]
        
        # If it's our own library, copy directly
        if library.owner_peer_id == self.p2p_manager.peer_id:
            return await self._copy_local_file(file_info, output_path)
        
        # If it's a subscribed library, request from owner
        return await self._download_from_peer(library.owner_peer_id, file_info, output_path)
    
    # Private helper methods
    def _calculate_checksum(self, file_path: str) -> bytes:
        """Calculate SHA-256 checksum of a file"""
        hash_sha256 = hashlib.sha256()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_sha256.update(chunk)
        return hash_sha256.digest()
    
    def _determine_category(self, file_ext: str) -> str:
        """Determine file category based on extension"""
        video_exts = {'.mp4', '.avi', '.mkv', '.mov', '.wmv', '.flv', '.webm', '.m4v'}
        audio_exts = {'.mp3', '.flac', '.wav', '.aac', '.ogg', '.m4a', '.wma'}
        document_exts = {'.pdf', '.doc', '.docx', '.txt', '.epub', '.mobi'}
        
        if file_ext in video_exts:
            return "video"
        elif file_ext in audio_exts:
            return "audio"
        elif file_ext in document_exts:
            return "document"
        else:
            return "general"
    
    def _file_matches_query(self, file_info: LibraryFile, query: str, category: str = None) -> bool:
        """Check if a file matches search criteria"""
        if category and file_info.category != category:
            return False
            
        query_lower = query.lower()
        return (query_lower in file_info.name.lower() or 
                any(query_lower in tag.lower() for tag in file_info.metadata.get('tags', [])))
    
    def _save_library(self, library: SharedLibrary) -> None:
        """Save library to disk"""
        library_file = os.path.join(self.library_dir, f"{library.library_id}.json")
        try:
            with open(library_file, 'w') as f:
                # Convert to dict for JSON serialization
                library_dict = {
                    'library_id': library.library_id,
                    'name': library.name,
                    'description': library.description,
                    'owner_peer_id': library.owner_peer_id,
                    'created_at': library.created_at,
                    'last_updated': library.last_updated,
                    'files': {fid: file.__dict__ for fid, file in library.files.items()},
                    'subscribers': list(library.subscribers),
                    'auto_sync': library.auto_sync,
                    'public': library.public,
                    'tags': library.tags
                }
                json.dump(library_dict, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save library {library.library_id}: {e}")
    
    def _load_libraries(self) -> None:
        """Load libraries from disk"""
        if not os.path.exists(self.library_dir):
            return
            
        for filename in os.listdir(self.library_dir):
            if filename.endswith('.json'):
                library_file = os.path.join(self.library_dir, filename)
                try:
                    with open(library_file, 'r') as f:
                        library_dict = json.load(f)
                        
                    # Convert back to objects
                    library = SharedLibrary(**{k: v for k, v in library_dict.items() if k != 'files'})
                    library.subscribers = set(library_dict.get('subscribers', []))
                    
                    # Convert files
                    for fid, file_dict in library_dict.get('files', {}).items():
                        library.files[fid] = LibraryFile(**file_dict)
                    
                    self.libraries[library.library_id] = library
                    
                    # Subscribe to library if auto-sync is enabled
                    if library.library_id not in self.subscribed_libraries and library.auto_sync:
                        self.subscribed_libraries[library.library_id] = library
                        logger.info(f"Subscribed to library {library.name} ({library.library_id})")
                    
                except Exception as e:
                    logger.error(f"Failed to load library {filename}: {e}")
    
    def _save_friends(self) -> None:
        """Save friends list to disk"""
        try:
            friends_data = {}
            for peer_id, peer_info in self.friends.items():
                friends_data[peer_id] = {
                    'peer_id': peer_info.peer_id,
                    'ip': peer_info.ip,
                    'port': peer_info.port,
                    'last_seen': peer_info.last_seen,
                    'nat_type': peer_info.nat_type
                }
            
            with open(self.friends_file, 'w') as f:
                json.dump(friends_data, f, indent=2)
                
        except Exception as e:
            logger.error(f"Failed to save friends: {e}")
    
    def _load_friends(self) -> None:
        """Load friends list from disk"""
        if not os.path.exists(self.friends_file):
            return
            
        try:
            with open(self.friends_file, 'r') as f:
                friends_data = json.load(f)
                
            for peer_id, peer_dict in friends_data.items():
                peer_info = PeerInfo(**peer_dict)
                self.friends[peer_id] = peer_info
                
        except Exception as e:
            logger.error(f"Failed to load friends: {e}")
    
    def _start_sync_worker(self) -> None:
        """Start background synchronization worker"""
        threading.Thread(target=self._sync_worker_loop, daemon=True).start()
    
    def _sync_worker_loop(self) -> None:
        """Background worker for library synchronization"""
        while True:
            try:
                # Process pending sync updates
                if self.pending_syncs:
                    sync_update = self.pending_syncs.pop(0)
                    asyncio.create_task(self._process_sync_update(sync_update))
                
                # Check for library updates from friends
                for library_id, library in self.subscribed_libraries.items():
                    if library.auto_sync:
                        asyncio.create_task(self._check_library_updates(library_id))
                
                time.sleep(30)  # Check every 30 seconds
                
            except Exception as e:
                logger.error(f"Error in sync worker: {e}")
                time.sleep(60)  # Wait longer on error
    
    async def _notify_library_update(self, library_id: str, update_type: str, data: Dict[str, Any]) -> None:
        """Notify subscribers of library updates"""
        if library_id not in self.libraries:
            return
            
        library = self.libraries[library_id]
        
        update_message = {
            "type": MSG_TYPE["LIBRARY_UPDATE"],
            "library_id": library_id,
            "update_type": update_type,
            "data": data,
            "timestamp": time.time(),
            "from_peer": self.p2p_manager.peer_id
        }
        
        # Send to all subscribers
        for subscriber_id in library.subscribers:
            if subscriber_id in self.friends:
                friend = self.friends[subscriber_id]
                try:
                    await self._send_message_to_peer(friend, update_message)
                except Exception as e:
                    logger.warning(f"Failed to notify subscriber {subscriber_id}: {e}")
    
    async def _send_message_to_peer(self, peer: PeerInfo, message: Dict[str, Any]) -> None:
        """Send a message to a specific peer"""
        try:
            reader, writer = await asyncio.open_connection(peer.ip, peer.port)
            
            # Encrypt if we have a symmetric key
            if peer.symmetric_key and self.p2p_manager.share_config.encryption:
                message_data = self.p2p_manager._encrypt_message(message, peer.symmetric_key)
            else:
                message_data = json.dumps(message).encode()
                  # Send with length prefix
            writer.write(len(message_data).to_bytes(4, byteorder="big"))
            writer.write(message_data)
            await writer.drain()
            
            writer.close()
            await writer.wait_closed()
            
        except Exception as e:
            logger.error(f"Error sending message to peer {peer.peer_id}: {e}")
            raise

    # PUBLIC API METHODS - Core P2P functionality
    async def start(self) -> bool:
        """Start P2P service and begin listening for connections"""
        try:
            logger.info("Starting P2P service...")
            
            # Start the P2P server
            if not await self.start_server():
                logger.error("Failed to start P2P server")
                return False
                
            # Load existing friends and libraries
            self._load_friends()
            self._load_libraries()
            
            # Start background sync worker
            self._start_sync_worker()
            
            logger.info(f"P2P service started successfully on port {self.port}")
            logger.info(f"Peer ID: {self.peer_id}")
            if self.external_ip:
                logger.info(f"External address: {self.external_ip}:{self.external_port}")
            return True
        except Exception as e:
            logger.error(f"Failed to start P2P service: {e}")
            return False    
    async def stop(self) -> None:
        """Stop P2P service and cleanup connections"""
        try:
            logger.info("Stopping P2P service...")
            
            # Stop listening
            if self.server:
                self.server.close()
                await self.server.wait_closed()
                self.listening = False
                
            # Close all peer connections
            for peer in self.peers.values():
                peer.connected = False
                
            # Remove UPnP port mapping
            if self.upnp and self.external_port:
                try:
                    self.upnp.deleteportmapping(self.external_port, 'TCP')
                    logger.debug("Removed UPnP port mapping")
                except Exception as e:
                    logger.warning(f"Failed to remove UPnP mapping: {e}")

            # Save state
            self._save_friends()
            self._save_libraries()
            
            # Clear state
            self.peers.clear()
            self.transfers.clear()
            
            logger.info("P2P service stopped")
        except Exception as e:
            logger.error(f"Error stopping P2P service: {e}")

    async def share_file(self, file_path: str, max_peers: int = 10, encryption: bool = True) -> Optional[str]:    
        
        """Share a file via P2P network and return share code
        
        Args:
            file_path: Path to file to share
            max_peers: Maximum concurrent connections (default: 10)
            encryption: Enable end-to-end encryption (default: True)
            
        Returns:
            Share code for other peers, or None if sharing failed
        """
        try:
            if not os.path.exists(file_path):
                logger.error(f"File not found: {file_path}")
                return None
                
            # Generate file ID and info
            file_id = binascii.hexlify(os.urandom(16)).decode()
            file_stat = os.stat(file_path)
            
            # Calculate file hash for integrity verification
            file_hash = self._calculate_checksum(file_path)
            
            # Create file info
            file_info = FileInfo(
                file_id=file_id,
                file_path=file_path,
                file_name=os.path.basename(file_path),
                file_size=file_stat.st_size,
                hash=file_hash.hex(),
                chunk_size=self.share_config.chunk_size,
                chunks=[]  # Will be calculated if needed
            )
            
            # Calculate chunks if file is large
            if file_stat.st_size > self.share_config.chunk_size:
                file_info.chunks = self._calculate_file_chunks(file_path)
            
            # Store in shared files
            self.shared_files[file_id] = file_info
            
            # Generate share code (format: peer_id:file_id:port)
            share_code = f"{self.peer_id}:{file_id}:{self.port}"
            
            # If we have external IP, use that in share code
            if self.external_ip and self.external_port:
                share_code = f"{self.peer_id}:{file_id}:{self.external_ip}:{self.external_port}"
                
            logger.info(f"File shared successfully: {file_path}")
            logger.info(f"Share code: {share_code}")
            
            return share_code
        except Exception as e:
            logger.error(f"Failed to share file {file_path}: {e}")            
            return None

    async def fetch_file(self, share_code: str, output_path: str) -> bool:
    
        """
        Download file using share code
        Args:
            share_code: Code received from file sharer
            output_path: Directory to save downloaded file
        Returns:
            True if download successful, False otherwise
        """
        try:
            # Parse share code
            parts = share_code.split(":")
            if len(parts) < 3:
                logger.error(f"Invalid share code format: {share_code}")
                return False

            peer_id = parts[0]
            file_id = parts[1]

            # Determine peer address
            if len(parts) == 4:  # peer_id:file_id:ip:port
                peer_ip = parts[2]
                peer_port = int(parts[3])
            else:  # peer_id:file_id:port (local network)
                peer_ip = "127.0.0.1"  # Assume local for now
                peer_port = int(parts[2])

            # Connect to peer
            peer_address = f"{peer_ip}:{peer_port}"
            peer = await self.connect_to_peer(peer_address)

            if not peer:
                logger.error(f"Failed to connect to peer: {peer_address}")
                return False

            # Request file
            request = {
                "type": MSG_TYPE["REQUEST"],
                "peer_id": self.peer_id,
                "file_id": file_id
            }            # Send request to peer and handle download
            success = await self._request_and_download_file(peer, request, output_path)
            
            if success:
                logger.info(f"File downloaded successfully to: {output_path}")
            else:
                logger.error("File download failed")
            
            return success
        except Exception as e:
            logger.error(f"Failed to fetch file with code {share_code}: {e}")
            return False

    async def discover_peers(self, query: Optional[str] = None) -> List[PeerInfo]:
        """Discover peers on the network
        
        Args:
            query: Optional search query for specific content
            
        Returns:
            List of discovered peers
        """
        try:
            discovered_peers = []
            
            # Method 1: Local network broadcast discovery
            local_peers = await self._discover_local_peers()
            discovered_peers.extend(local_peers)
            
            # Method 2: DHT-based discovery (if enabled)
            if self.share_config.dht_enabled:
                dht_peers = await self._discover_dht_peers(query)
                discovered_peers.extend(dht_peers)
            
            # Method 3: Friend network discovery
            friend_peers = await self._discover_friend_peers()
            discovered_peers.extend(friend_peers)
            
            # Remove duplicates
            unique_peers = {}
            for peer in discovered_peers:
                if peer.peer_id not in unique_peers:
                    unique_peers[peer.peer_id] = peer
                    
            logger.info(f"Discovered {len(unique_peers)} peers")
            return list(unique_peers.values())
        except Exception as e:
            logger.error(f"Peer discovery failed: {e}")
            return []

    async def is_content_available(self, content_hash: str) -> bool:
        """Check if content is available via P2P network
        
        Args:
            content_hash: Hash of the content to check
            
        Returns:
            True if content is available from peers
        """
        try:
            # Check connected peers for content availability
            for peer in self.peers.values():
                if peer.connected:
                    if await self._query_peer_for_content(peer, content_hash):
                        return True
                        
            # If not found in connected peers, try discovery
            peers = await self.discover_peers(content_hash)
            for peer in peers:
                if await self._query_peer_for_content(peer, content_hash):
                    return True
                    
            return False
        except Exception as e:
            logger.warning(f"Content availability check failed: {e}")
            return False

    def get_peer_info(self) -> Dict[str, Any]:
        """Get local peer information and network status
        
        Returns:
            Dictionary containing peer details and network status
        """
        try:
            return {
                "peer_id": self.peer_id,
                "listening": self.listening,
                "port": self.port,
                "external_ip": self.external_ip,
                "external_port": self.external_port,
                "nat_type": self.nat_type,
                "connected_peers": len([p for p in self.peers.values() if p.connected]),
                "total_peers": len(self.peers),
                "shared_files": len(self.shared_files),
                "active_transfers": len([t for t in self.transfers.values() if t.status == "active"]),
                "libraries": len(self.libraries),
                "subscribed_libraries": len(self.subscribed_libraries),
                "friends": len(self.friends),
                "upnp_enabled": self.upnp is not None,
                "encryption_enabled": self.share_config.encryption
            }
        except Exception as e:
            logger.error(f"Error getting peer info: {e}")            
            return {}

# HELPER METHODS FOR PUBLIC API

    def _calculate_file_chunks(self, file_path: str) -> List[str]:
        """Calculate chunk hashes for a file"""
        chunks = []
        try:
            with open(file_path, 'rb') as f:
                while True:
                    chunk = f.read(self.share_config.chunk_size)
                    if not chunk:
                        break
                    chunk_hash = hashlib.sha256(chunk).hexdigest()
                    chunks.append(chunk_hash)
            return chunks
        except Exception as e:
            logger.error(f"Error calculating file chunks: {e}")
            return []

    async def _request_and_download_file(self, peer: PeerInfo, request: Dict[str, Any], output_path: str) -> bool:
        """Request and download file from peer"""
        try:
            # Connect and send request
            reader, writer = await asyncio.open_connection(peer.ip, peer.port)
            
            # Encrypt request if we have symmetric key
            if peer.symmetric_key and self.share_config.encryption:
                request_data = self._encrypt_message(request, peer.symmetric_key)
            else:
                request_data = json.dumps(request).encode()
                
            # Send request
            writer.write(len(request_data).to_bytes(4, byteorder="big"))
            writer.write(request_data)
            await writer.drain()
            
            # Read response
            response_length = await reader.read(4)
            if not response_length:
                writer.close()
                return False
                
            response_data = await reader.read(int.from_bytes(response_length, byteorder="big"))
            
            # Decrypt if needed
            if peer.symmetric_key and self.share_config.encryption:
                response = json.loads(self._decrypt_message(response_data, peer.symmetric_key).decode())
            else:
                response = json.loads(response_data.decode())
                
            # Check for error
            if response.get("type") == MSG_TYPE["ERROR"]:
                logger.error(f"Peer error: {response.get('error_message')}")
                writer.close()
                return False
                
            # Download file chunks
            file_name = response.get("file_name", "downloaded_file")
            output_file_path = os.path.join(output_path, file_name)
            
            success = await self._download_file_chunks(reader, writer, response, output_file_path, peer)
            
            writer.close()
            return success
            
        except Exception as e:
            logger.error(f"Error downloading file from peer: {e}")
            return False
    
    async def _discover_local_peers(self) -> List[PeerInfo]:
        """Discover peers on local network via broadcast"""
        try:
            discovered = []
            
            # Get local network interfaces
            interfaces = netifaces.interfaces()
            
            for interface in interfaces:
                try:
                    addrs = netifaces.ifaddresses(interface)
                    if netifaces.AF_INET in addrs:
                        for addr_info in addrs[netifaces.AF_INET]:
                            addr = addr_info.get('addr')
                            netmask = addr_info.get('netmask')
                            
                            if addr and netmask and not addr.startswith('127.'):
                                # Calculate network range
                                network = ipaddress.IPv4Network(f"{addr}/{netmask}", strict=False)
                                
                                # Send broadcast discovery
                                peers = await self._broadcast_discovery(str(network.network_address), str(network.broadcast_address))
                                discovered.extend(peers)
                                
                except Exception as e:
                    logger.debug(f"Error processing interface {interface}: {e}")
                    continue
            
            logger.debug(f"Local discovery found {len(discovered)} peers")
            return discovered
            
        except Exception as e:
            logger.debug(f"Local peer discovery error: {e}")
            return []
    
    async def _discover_dht_peers(self, query: Optional[str] = None) -> List[PeerInfo]:
        """Discover peers via DHT network"""
        try:
            discovered = []
            
            # Implement a simple DHT-like discovery using known bootstrap nodes
            bootstrap_nodes = [
                ("dht.snatch.network", 8080),  # Hypothetical bootstrap node
                ("bootstrap.p2p.example.com", 6881),  # Example DHT node
            ]
            
            for node_host, node_port in bootstrap_nodes:
                try:
                    # Try to connect to bootstrap node and request peer list
                    peers = await self._query_dht_node(node_host, node_port, query)
                    discovered.extend(peers)
                    
                except Exception as e:
                    logger.debug(f"DHT node {node_host}:{node_port} query failed: {e}")
                    continue
            
            # Also check if any current peers know about other peers
            for peer in self.peers.values():
                if peer.connected:
                    try:
                        peer_discoveries = await self._query_peer_for_peers(peer)
                        discovered.extend(peer_discoveries)
                    except Exception as e:
                        logger.debug(f"Peer discovery from {peer.peer_id} failed: {e}")
            
            logger.debug(f"DHT discovery found {len(discovered)} peers")
            return discovered
            
        except Exception as e:
            logger.debug(f"DHT peer discovery error: {e}")
            return []
    
    async def _discover_friend_peers(self) -> List[PeerInfo]:
        """Discover peers from friends list"""
        try:
            # Return currently known friends as potential peers
            return list(self.friends.values())
        except Exception as e:
            logger.debug(f"Friend peer discovery error: {e}")
            return []
    
    async def _query_peer_for_content(self, peer: PeerInfo, content_hash: str) -> bool:
        """Query a peer to see if they have specific content"""
        try:
            # Send a content availability query
            query = {
                "type": MSG_TYPE["REQUEST"],
                "peer_id": self.peer_id,
                "content_hash": content_hash,
                "query_only": True  # Just checking availability
            }
            
            # Connect to peer and send query
            try:
                reader, writer = await asyncio.wait_for(
                    asyncio.open_connection(peer.ip, peer.port), 
                    timeout=5.0
                )
                
                # Encrypt query if we have symmetric key
                if peer.symmetric_key and self.share_config.encryption:
                    query_data = self._encrypt_message(query, peer.symmetric_key)
                else:
                    query_data = json.dumps(query).encode()
                
                # Send query
                writer.write(len(query_data).to_bytes(4, byteorder="big"))
                writer.write(query_data)
                await writer.drain()
                
                # Read response
                length_bytes = await asyncio.wait_for(reader.read(4), timeout=3.0)
                if not length_bytes:
                    return False
                    
                message_length = int.from_bytes(length_bytes, byteorder="big")
                response_data = await asyncio.wait_for(reader.read(message_length), timeout=3.0)
                
                if not response_data:
                    return False
                
                # Parse response
                if peer.symmetric_key and self.share_config.encryption:
                    response_json = self._decrypt_message(response_data, peer.symmetric_key)
                    response = json.loads(response_json)
                else:
                    response = json.loads(response_data.decode())
                
                # Check if content is available
                return response.get("available", False)
                
            except asyncio.TimeoutError:
                logger.debug(f"Timeout querying peer {peer.peer_id} for content")
                return False
            except Exception as e:
                logger.debug(f"Error querying peer {peer.peer_id}: {e}")
                return False
            finally:
                if 'writer' in locals():
                    writer.close()
                    
        except Exception as e:
            logger.debug(f"Content query error: {e}")
            return False
    
    async def _download_file_chunks(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter, 
                                       file_info: Dict[str, Any], output_path: str, peer: PeerInfo) -> bool:
        """Download file data in chunks"""
        try:
            file_size = file_info.get("file_size", 0)
            chunks = file_info.get("chunks", [])
            
            with open(output_path, 'wb') as f:
                if chunks:
                    # Download chunk by chunk for large files
                    for i, chunk_hash in enumerate(chunks):
                        chunk_request = {
                            "type": MSG_TYPE["DATA"],
                            "chunk_index": i,
                            "chunk_hash": chunk_hash
                        }
                        
                        # Send chunk request
                        if peer.symmetric_key and self.share_config.encryption:
                            request_data = self._encrypt_message(chunk_request, peer.symmetric_key)
                        else:
                            request_data = json.dumps(chunk_request).encode()
                            
                        writer.write(len(request_data).to_bytes(4, byteorder="big"))
                        writer.write(request_data)
                        await writer.drain()
                        
                        # Read chunk response
                        chunk_length = await reader.read(4)
                        if not chunk_length:
                            return False
                            
                        chunk_data = await reader.read(int.from_bytes(chunk_length, byteorder="big"))
                        
                        # Decrypt if needed
                        if peer.symmetric_key and self.share_config.encryption:
                            chunk_data = self._decrypt_message(chunk_data, peer.symmetric_key)
                            
                        f.write(chunk_data)
                else:
                    # Download as single chunk for small files
                    data_length = await reader.read(4)
                    if data_length:
                        file_data = await reader.read(int.from_bytes(data_length, byteorder="big"))
                        
                        # Decrypt if needed
                        if peer.symmetric_key and self.share_config.encryption:
                            file_data = self._decrypt_message(file_data, peer.symmetric_key)
                            
                        f.write(file_data)
                        
            return True
            
        except Exception as e:
            logger.error(f"Error downloading file chunks: {e}")
            return False

    def _load_libraries(self) -> None:
        """Load libraries from disk"""
        try:
            libraries_file = os.path.join(self.data_dir, "libraries.json")
            if os.path.exists(libraries_file):
                with open(libraries_file, 'r') as f:
                    libraries_data = json.load(f)
                    
                for lib_id, lib_data in libraries_data.items():
                    # Convert files dict back to LibraryFile objects
                    files = {}
                    for file_id, file_data in lib_data.get("files", {}).items():
                        files[file_id] = LibraryFile(**file_data)
                    
                    lib_data["files"] = files
                    self.libraries[lib_id] = SharedLibrary(**lib_data)
                    
        except Exception as e:
            logger.error(f"Failed to load libraries: {e}")
            
    def _save_libraries(self) -> None:
        """Save libraries to disk"""
        try:
            libraries_file = os.path.join(self.data_dir, "libraries.json")
            libraries_data = {}
            
            for lib_id, library in self.libraries.items():
                # Convert LibraryFile objects to dicts for JSON serialization
                files = {}
                for file_id, file_obj in library.files.items():
                    files[file_id] = {
                        "file_id": file_obj.file_id,
                        "name": file_obj.name,
                        "size": file_obj.size,
                        "checksum": file_obj.checksum,
                        "download_url": file_obj.download_url,
                        "metadata": file_obj.metadata,
                        "added_at": file_obj.added_at,
                        "category": file_obj.category,
                        "quality": file_obj.quality,
                        "format": file_obj.format
                    }
                
                libraries_data[lib_id] = {
                    "library_id": library.library_id,
                    "name": library.name,
                    "description": library.description,
                    "owner_peer_id": library.owner_peer_id,
                    "created_at": library.created_at,
                    "last_updated": library.last_updated,
                    "files": files,
                    "subscribers": list(library.subscribers),
                    "auto_sync": library.auto_sync,
                    "public": library.public,
                    "tags": library.tags
                }
                
            with open(libraries_file, 'w') as f:
                json.dump(libraries_data, f, indent=2)
                
        except Exception as e:
            logger.error(f"Failed to save libraries: {e}")

    async def _broadcast_discovery(self, network_addr: str, broadcast_addr: str) -> List[PeerInfo]:
        """Perform UDP broadcast discovery on a network segment"""
        discovered = []
        try:
            # Create UDP socket for broadcast
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
            sock.settimeout(2.0)  # 2 second timeout
            
            # Prepare discovery message
            discovery_msg = {
                "type": MSG_TYPE["PING"],
                "peer_id": self.peer_id,
                "port": self.port,
                "discovery": True
            }
            message_data = json.dumps(discovery_msg).encode()
            
            # Broadcast on default P2P discovery port
            discovery_port = 58264  # Custom P2P discovery port
            
            try:
                sock.sendto(message_data, (broadcast_addr, discovery_port))
                
                # Listen for responses for a short time
                start_time = time.time()
                while time.time() - start_time < 2.0:
                    try:
                        response, addr = sock.recvfrom(1024)
                        response_data = json.loads(response.decode())
                        
                        if response_data.get("type") == MSG_TYPE["PONG"]:
                            peer_id = response_data.get("peer_id")
                            peer_port = response_data.get("port")
                            
                            if peer_id and peer_id != self.peer_id:
                                peer = PeerInfo(
                                    peer_id=peer_id,
                                    ip=addr[0],
                                    port=peer_port,
                                    connected=False
                                )
                                discovered.append(peer)
                                
                    except socket.timeout:
                        break
                    except Exception as e:
                        logger.debug(f"Error processing broadcast response: {e}")
                        break
                        
            except Exception as e:
                logger.debug(f"Broadcast send error: {e}")
                
        except Exception as e:
            logger.debug(f"Broadcast discovery error: {e}")
        finally:
            try:
                sock.close()
            except:
                pass
                
        return discovered
    
    async def _query_dht_node(self, host: str, port: int, query: Optional[str] = None) -> List[PeerInfo]:
        """Query a DHT bootstrap node for peer information"""
        try:
            # This is a simplified DHT query - in a real implementation
            # you would use the BitTorrent DHT protocol or similar
            
            # For now, we'll simulate a simple peer list request
            dht_query = {
                "type": "dht_find_peers",
                "query": query or "general",
                "max_peers": 20
            }
            
            # Try to connect and query (simplified)
            try:
                reader, writer = await asyncio.wait_for(
                    asyncio.open_connection(host, port),
                    timeout=5.0
                )
                
                query_data = json.dumps(dht_query).encode()
                writer.write(len(query_data).to_bytes(4, byteorder="big"))
                writer.write(query_data)
                await writer.drain()
                
                # Read response (simplified)
                length_bytes = await asyncio.wait_for(reader.read(4), timeout=3.0)
                if length_bytes:
                    message_length = int.from_bytes(length_bytes, byteorder="big")
                    response_data = await asyncio.wait_for(reader.read(message_length), timeout=3.0)
                    
                    if response_data:
                        response = json.loads(response_data.decode())
                        peers_data = response.get("peers", [])
                        
                        discovered = []
                        for peer_data in peers_data:
                            peer = PeerInfo(
                                peer_id=peer_data.get("peer_id", ""),
                                ip=peer_data.get("ip", ""),
                                port=peer_data.get("port", 0),
                                connected=False
                            )
                            discovered.append(peer)
                        
                        return discovered
                        
            except Exception as e:
                logger.debug(f"DHT query connection error: {e}")
                
        except Exception as e:
            logger.debug(f"DHT node query error: {e}")
            
        return []
    
    async def _query_peer_for_peers(self, peer: PeerInfo) -> List[PeerInfo]:
        """Ask a connected peer for other peers they know about"""
        try:
            # Send peer list request
            peer_query = {
                "type": MSG_TYPE["REQUEST"],
                "peer_id": self.peer_id,
                "request_type": "peer_list",
                "max_peers": 10
            }
            
            # Connect and send query
            try:
                reader, writer = await asyncio.wait_for(
                    asyncio.open_connection(peer.ip, peer.port),
                    timeout=5.0
                )
                
                # Encrypt if possible
                if peer.symmetric_key and self.share_config.encryption:
                    query_data = self._encrypt_message(peer_query, peer.symmetric_key)
                else:
                    query_data = json.dumps(peer_query).encode()
                
                # Send query
                writer.write(len(query_data).to_bytes(4, byteorder="big"))
                writer.write(query_data)
                await writer.drain()
                
                # Read response
                length_bytes = await asyncio.wait_for(reader.read(4), timeout=3.0)
                if not length_bytes:
                    return []
                    
                message_length = int.from_bytes(length_bytes, byteorder="big")
                response_data = await asyncio.wait_for(reader.read(message_length), timeout=3.0)
                
                if not response_data:
                    return []
                
                # Parse response
                if peer.symmetric_key and self.share_config.encryption:
                    response_json = self._decrypt_message(response_data, peer.symmetric_key)
                    response = json.loads(response_json)
                else:
                    response = json.loads(response_data.decode())
                
                # Extract peer list
                peers_data = response.get("peers", [])
                discovered = []
                
                for peer_data in peers_data:
                    if peer_data.get("peer_id") != self.peer_id:  # Don't add ourselves
                        new_peer = PeerInfo(
                            peer_id=peer_data.get("peer_id", ""),
                            ip=peer_data.get("ip", ""),
                            port=peer_data.get("port", 0),
                            connected=False
                        )
                        discovered.append(new_peer)
                
                return discovered
                
            except asyncio.TimeoutError:
                logger.debug(f"Timeout querying peer {peer.peer_id} for peer list")
                return []
            except Exception as e:
                logger.debug(f"Error querying peer {peer.peer_id} for peers: {e}")
                return []
            finally:
                if 'writer' in locals():
                    writer.close()
                    
        except Exception as e:
            logger.debug(f"Peer query error: {e}")
            return []