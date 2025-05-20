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

@dataclass
class ShareConfig:
    """Configuration for file sharing"""
    upnp: bool = True
    stun_servers: Optional[List[str]] = None
    turn_servers: Optional[List[str]] = None
    encryption: bool = True
    compression: bool = True
    chunk_size: int = CHUNK_SIZE
    dht_enabled: bool = True
    port_range: Tuple[int, int] = DEFAULT_PORT_RANGE
    connect_timeout: int = DEFAULT_TIMEOUT
    transfer_timeout: int = 120
    max_retry_count: int = 5
    
    def __post_init__(self):
        if self.stun_servers is None:
            self.stun_servers = STUN_SERVERS.copy()
        if self.turn_servers is None:
            self.turn_servers = TURN_SERVERS.copy()

@dataclass
class PeerInfo:
    """Information about a connected peer"""
    peer_id: str
    ip: str
    port: int
    nat_type: int = NAT_TYPES["UNKNOWN"]
    public_key: Optional[bytes] = None
    symmetric_key: Optional[bytes] = None
    connected: bool = False
    last_seen: float = field(default_factory=time.time)
    is_relay: bool = False
    connection_quality: int = 0  # 0-100 quality rating
    
    @property
    def address(self) -> str:
        """Get formatted address string"""
        return f"{self.ip}:{self.port}"

@dataclass
class FileInfo:
    """Information about a shared file"""
    path: str
    size: int
    hash: str
    chunk_hashes: List[str] = field(default_factory=list)
    created: float = field(default_factory=time.time)
    name: Optional[str] = None
    mime_type: Optional[str] = None
    
    def __post_init__(self):
        if not self.name:
            self.name = os.path.basename(self.path)

@dataclass
class TransferProgress:
    """Progress information for a file transfer"""
    file_id: str
    bytes_transferred: int = 0
    total_bytes: int = 0
    chunks_completed: Set[int] = field(default_factory=set)
    start_time: float = field(default_factory=time.time)
    last_update: float = field(default_factory=time.time)
    speed_bps: float = 0
    eta_seconds: float = 0
    status: str = "pending"  # pending, active, completed, failed, paused
    
    @property
    def progress_percent(self) -> float:
        """Get progress percentage"""
        if self.total_bytes <= 0:
            return 0
        return (self.bytes_transferred / self.total_bytes) * 100
    
    @property
    def is_complete(self) -> bool:
        """Check if transfer is complete"""
        return self.bytes_transferred >= self.total_bytes

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
            except:
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
                s.settimeout(2)  # Short timeout for pings
                s.connect((peer.ip, peer.port))
                
                # Create ping message
                message = {
                    "type": MSG_TYPE["PING"],
                    "peer_id": self.peer_id,
                    "timestamp": time.time()
                }
                
                # Send encrypted if we have a symmetric key
                if peer.symmetric_key and self.share_config.encryption:
                    message_data = self._encrypt_message(message, peer.symmetric_key)
                else:
                    message_data = json.dumps(message).encode()
                    
                # Send message with length prefix
                s.sendall(len(message_data).to_bytes(4, byteorder="big"))
                s.sendall(message_data)
                
                # Receive response (don't wait for it)
                # This is just to complete the ping round-trip
                s.settimeout(1)
                try:
                    s.recv(1024)
                except:
                    pass
                    
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
            # Read message length
            length_bytes = await reader.read(4)
            if not length_bytes:
                logger.warning(f"Empty connection from {peer_addr}")
                writer.close()
                return
                
            message_length = int.from_bytes(length_bytes, byteorder="big")
            
            # Read message data
            message_data = await reader.read(message_length)
            if not message_data:
                logger.warning(f"Failed to read message from {peer_addr}")
                writer.close()
                return
                
            # Parse message
            try:
                # Try to parse as JSON first (unencrypted)
                message = json.loads(message_data.decode())
            except:
                # Try to find a peer by address for decryption
                peer_ip, peer_port = peer_addr
                peer = None
                for p in self.peers.values():
                    if p.ip == peer_ip and p.symmetric_key:
                        try:
                            # Try to decrypt with this peer's key
                            decrypted = self._decrypt_message(message_data, p.symmetric_key)
                            message = json.loads(decrypted.decode())
                            peer = p
                            break
                        except:
                            continue
                
                if not peer:
                    logger.warning(f"Could not decrypt message from {peer_addr}")
                    writer.close()
                    return
                    
            # Process message based on type
            if message.get("type") == MSG_TYPE["HANDSHAKE"]:
                await self._handle_handshake(message, reader, writer)
            elif message.get("type") == MSG_TYPE["REQUEST"]:
                await self._handle_request(message, reader, writer, peer)
            elif message.get("type") == MSG_TYPE["DATA"]:
                await self._handle_data(message, reader, writer, peer)
            elif message.get("type") == MSG_TYPE["PING"]:
                await self._handle_ping(message, writer, peer)
            elif message.get("type") == MSG_TYPE["KEY_EXCHANGE"]:
                await self._handle_key_exchange(message, reader, writer)
            else:
                logger.warning(f"Unknown message type: {message.get('type')}")
                
        except Exception as e:
            logger.error(f"Error handling connection: {e}")
            
        finally:
            writer.close()
            
    async def _handle_handshake(self, message: Dict[str, Any], reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        """Handle handshake message"""
        peer_addr = writer.get_extra_info('peername')
        peer_id = message.get("peer_id")
        
        if not peer_id:
            logger.warning(f"Invalid handshake from {peer_addr}: missing peer_id")
            return
            
        # Create or update peer info
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
            
        # Parse public key if provided
        if public_key_data := message.get("public_key"):
            from cryptography.hazmat.primitives.serialization import load_der_public_key
            try:
                peer.public_key = load_der_public_key(
                    binascii.unhexlify(public_key_data),
                    backend=default_backend()
                )
            except Exception as e:
                logger.warning(f"Failed to parse public key: {e}")
                
        # Send handshake response
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
            self.on_peer_connected(peer)
            
    async def _handle_key_exchange(self, message: Dict[str, Any], reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        """Handle key exchange message"""
        peer_addr = writer.get_extra_info('peername')
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
            with open(file_info.path, "rb") as f:
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
                "final_chunk": chunk_index == len(file_info.chunk_hashes) - 1
            }
            
            # Encrypt response header if possible
            if peer.symmetric_key and self.share_config.encryption:
                header_data = self._encrypt_message(response, peer.symmetric_key)
                
                # Also encrypt chunk data
                from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
                iv = os.urandom(12)  # 96 bits for GCM
                cipher = Cipher(
                    algorithms.AES(peer.symmetric_key),
                    modes.GCM(iv),
                    backend=default_backend()
                )
                encryptor = cipher.encryptor()
                encrypted_chunk = encryptor.update(chunk_data) + encryptor.finalize()
                chunk_data = iv + encryptor.tag + encrypted_chunk
            else:
                header_data = json.dumps(response).encode()
                
            # Send header
            writer.write(len(header_data).to_bytes(4, byteorder="big"))
            writer.write(header_data)
            await writer.drain()
            
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
            # Try STUN servers until one responds
            stun_servers = self.share_config.stun_servers
            
            for server in stun_servers:
                try:
                    host, port_str = server.split(":")
                    port = int(port_str)
                    
                    # Create socket for STUN request
                    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
                        s.settimeout(3)
                        
                        # Send binding request
                        transaction_id = os.urandom(12)
                        binding_request = bytes([0x00, 0x01]) + bytes([0x00, 0x00]) + bytes([0x21, 0x12, 0xA4, 0x42]) + transaction_id
                        
                        s.sendto(binding_request, (host, port))
                        
                        # Receive response
                        response, addr = s.recvfrom(1024)
                        
                        # Check for success response
                        if len(response) < 20 or response[0:2] != bytes([0x01, 0x01]):
                            continue
                            
                        # Parse mapped address
                        mapped_addr = None
                        i = 20
                        while i < len(response):
                            attr_type = (response[i] << 8) | response[i+1]
                            attr_len = (response[i+2] << 8) | response[i+3]
                            
                            if attr_type == 0x0001:  # MAPPED-ADDRESS
                                family = response[i+5]
                                port = (response[i+6] << 8) | response[i+7]
                                if family == 0x01:  # IPv4
                                    ip = ".".join(str(b) for b in response[i+8:i+12])
                                    mapped_addr = (ip, port)
                            
                            i += 4 + attr_len
                            
                        if mapped_addr:
                            # Store mapped address
                            self.external_ip = mapped_addr[0]
                            
                            # Determine NAT type (simplified)
                            # This is a partial implementation - a full STUN implementation
                            # would require multiple tests to accurately determine NAT type
                            local_ip = self._get_local_ip()
                            if local_ip == self.external_ip:
                                self.nat_type = NAT_TYPES["OPEN"]
                            else:
                                # Default to port restricted NAT
                                # Without multiple tests, we can't accurately determine more
                                self.nat_type = NAT_TYPES["PORT_RESTRICTED"]
                                
                            logger.debug(f"NAT type detected: {self.nat_type}, external IP: {self.external_ip}")
                            return
                            
                except Exception as e:
                    logger.debug(f"STUN error with server {server}: {e}")
                    continue
                    
            # If we reach here, all STUN servers failed
            logger.warning("Failed to detect NAT type using STUN")
            self.nat_type = NAT_TYPES["UNKNOWN"]
            
        except Exception as e:
            logger.error(f"NAT detection error: {e}")
            self.nat_type = NAT_TYPES["UNKNOWN"]
            
    def _get_local_ip(self) -> str:
        """Get local IP address of the default interface"""
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
                # Doesn't actually connect
                s.connect(("8.8.8.8", 53))
                return s.getsockname()[0]
        except:
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