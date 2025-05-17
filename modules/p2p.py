"""
Enhanced P2P implementation with NAT traversal and encryption.
Provides secure file sharing with progress tracking and integrity verification.
"""

import asyncio
import hashlib
import json
import logging
import socket
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Dict, Any, List, Tuple
from urllib.parse import urlparse, parse_qs

from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.backends import default_backend
from pyp2p.net import Net
from pyp2p.dht_msg import DHT
from pyp2p.unl import UNL
from twisted.internet import reactor, task
import netifaces
import miniupnpc

from rich.progress import Progress

from .utils import sanitize_filename
from .progress import ColorProgressBar, HolographicProgress
from .logging_config import setup_logging

# Configure logging
setup_logging()
logger = logging.getLogger(__name__)

# Constants
CHUNK_SIZE = 1024 * 1024  # 1MB chunks
DEFAULT_PORT = 0  # Let system choose port
PROTOCOL_VERSION = 1
DHT_TIMEOUT = 30  # seconds
STUN_SERVERS = ['stun.l.google.com:19302', 'stun1.l.google.com:19302']

@dataclass
class ShareConfig:
    """Configuration for file sharing"""
    upnp: bool = True
    stun_servers: Optional[List[str]] = None
    encryption: bool = True
    chunk_size: int = CHUNK_SIZE
    dht_enabled: bool = True
    
    def __post_init__(self):
        if self.stun_servers is None:
            self.stun_servers = STUN_SERVERS.copy()

class P2PError(Exception):
    """Base class for P2P errors"""
    pass

class PeerRefusedError(P2PError):
    """Raised when peer refuses connection"""
    pass

class IntegrityError(P2PError):
    """Raised when file integrity check fails"""
    pass

class P2PConnection:
    """Wrapper for P2P connections with keepalive support."""
    
    def __init__(self, net: Net):
        self.net = net
        self.active = True
        self._setup_keepalive()
        
    def _setup_keepalive(self, interval: int = 30):
        """Setup connection keepalive."""
        def ping_peers():
            try:
                if not self.active:
                    return
                # Send ping to all connected peers
                for peer in self.net.get_connections():
                    try:
                        if peer.connected:
                            peer.send(b"ping")
                    except Exception as e:
                        logger.debug(f"Peer ping failed: {e}")
            except Exception as e:
                logger.debug(f"Keepalive ping failed: {e}")
        
        loop = task.LoopingCall(ping_peers)
        loop.start(interval)
        
    def close(self):
        """Close connection and stop keepalive."""
        self.active = False
        if self.net:
            self.net.stop()
class NATTraversal:
    async def hole_punch(self, peer_addr: Tuple[str, int]) -> bool:
        """Improved NAT hole punching using simultaneous TCP connections"""
        try:
            # Create simultaneous outbound connections
            connector = asyncio.open_connection(peer_addr[0], peer_addr[1])
            listener = await asyncio.start_server(lambda r,w: None, port=0)
            await asyncio.wait_for(connector, timeout=5)
            return True
        except Exception as e:
            logger.error(f"Hole punching failed: {e}")
            return False
class P2PManager:
    """Enhanced P2P manager with NAT traversal support"""
    
    def __init__(self, config: Optional[ShareConfig] = None):
        self.config = config or ShareConfig()
        self.node = None
        self.dht = None
        self.unl = None
        self._active = False
        self._port = DEFAULT_PORT
        self._lock = threading.Lock()

    async def connect_peer(self, peer_info: Dict) -> Optional[P2PConnection]:
        """Enhanced connection handling with fallback strategies"""
        for attempt in range(3):
            try:
                if await self.nat_traversal.hole_punch((peer_info['ip'], peer_info['port'])):
                    return await self._establish_secure_channel(peer_info)
            except Exception as e:
                logger.warning(f"Connection attempt {attempt+1} failed: {e}")
                await asyncio.sleep(2**attempt)  # Exponential backoff
        return None

    def _get_stun_address(self) -> Tuple[str, int]:
        """Get external address using STUN"""
        for stun_server in self.config.stun_servers:
            try:
                host, port = stun_server.split(':')
                with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
                    s.settimeout(2)
                    s.sendto(b'', (host, int(port)))
                    _, addr = s.recvfrom(1024)
                    return addr[0], self._port
            except Exception as e:
                logger.debug(f"STUN query failed for {stun_server}: {e}")
                continue
        
        return self._get_local_address()

    def _get_local_address(self) -> Tuple[str, int]:
        """Get local network address"""
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            s.connect(('8.8.8.8', 80))
            return s.getsockname()[0], self._port
        except Exception:
            return '127.0.0.1', self._port
        finally:
            s.close()

    def start(self) -> None:
        """Start P2P node"""
        if self._active:
            return

        try:
            # Initialize P2P components
            self.unl = UNL()
            self.dht = DHT(unl=self.unl)
            self.node = Net(
                unl=self.unl,
                dht=self.dht,
                passive_port=self._port
            )
            self.node.start()
            self._port = self.node.passive_port
            
            # Get external address
            ext_ip, ext_port = self._get_stun_address()
            logger.info(f"P2P node started at {ext_ip}:{ext_port}")
            self._active = True

        except Exception as e:
            logger.error(f"Failed to start P2P node: {e}")
            raise P2PError(f"Node startup failed: {str(e)}")

    def stop(self) -> None:
        """Stop P2P node"""
        if not self._active:
            return

        try:
            if self.node:
                self.node.stop()
            self._active = False
            logger.info("P2P node stopped")

        except Exception as e:
            logger.error(f"Error stopping P2P node: {e}")

    def handle_incoming_connection(self, conn, file: Path, metadata: Dict[str, Any]) -> None:
        """Handle incoming file request"""
        try:
            data = conn.recv().decode()
            if data == metadata['id']:
                # Get user confirmation
                print(f"\nAccept fetch for {file.name} ({metadata['size']//1024//1024} MB)? [y/N] ", end='')
                if input().strip().lower() == 'y':
                    conn.send(b'ACCEPT')
                    self._send_file(conn, file, metadata)
                else:
                    conn.send(b'REFUSE')
            conn.close()
        except Exception as e:
            logger.error(f"Connection error: {e}")

    def _run_server(self, file: Path, metadata: Dict[str, Any]) -> None:
        """Server loop for handling requests"""
        while self._active:
            for conn in self.node:
                self.handle_incoming_connection(conn, file, metadata)

    def _start_server_thread(self, file: Path, metadata: Dict[str, Any]) -> None:
        """Start server thread"""
        thread = threading.Thread(
            target=self._run_server,
            args=(file, metadata),
            daemon=True
        )
        thread.start()

    async def share_file(self, file_path: str) -> str:
        """Share a file with encryption and DHT announcements"""
        if not self._active:
            self.start()

        file = Path(file_path)
        if not file.is_file():
            raise FileNotFoundError(f"File {file_path} not found")

        try:
            # Generate file metadata
            metadata = self._generate_file_metadata(file)
            
            # Announce on DHT if enabled
            if self.config.dht_enabled:
                self.node.dht_insert(
                    metadata['id'],
                    self.node.get_latest_connection_info()
                )

            # Start server thread
            self._start_server_thread(file, metadata)
            
            # Return share code
            return self._generate_share_code(metadata)

        except Exception as e:
            logger.error(f"Failed to share file: {e}")
            raise P2PError(f"Share failed: {str(e)}")

    def _send_file(self, conn, file: Path, metadata: Dict[str, Any]) -> None:
        """Send file with optional encryption"""
        try:
            key = self._derive_key(metadata['id']) if metadata['encryption'] else None
            
            with open(file, 'rb') as f:
                while data := f.read(metadata['chunk_size']):
                    if key:
                        nonce = hashlib.sha256(str(time.time()).encode()).digest()[:12]
                        cipher = Cipher(algorithms.AES(key), modes.GCM(nonce), backend=default_backend())
                        encryptor = cipher.encryptor()
                        data = nonce + encryptor.update(data) + encryptor.finalize() + encryptor.tag
                    conn.send(data)
                    
        except Exception as e:
            logger.error(f"Error sending file: {e}")
            raise P2PError(f"Send failed: {str(e)}")

    def _generate_file_metadata(self, file: Path) -> Dict[str, Any]:
        """Generate file metadata"""
        sha256 = hashlib.sha256()
        size = 0
        
        with open(file, 'rb') as f:
            while chunk := f.read(self.config.chunk_size):
                sha256.update(chunk)
                size += len(chunk)

        file_hash = sha256.hexdigest()
        return {
            'id': file_hash,
            'name': file.name,
            'size': size,
            'hash': file_hash,
            'chunk_size': self.config.chunk_size,
            'chunks': (size + self.config.chunk_size - 1) // self.config.chunk_size,
            'version': PROTOCOL_VERSION,
            'encryption': self.config.encryption
        }

    def _generate_share_code(self, metadata: Dict[str, Any]) -> str:
        """Generate share code"""
        return (
            f"snatch://{metadata['id']}@{self.node.external_ip()}:{self.node.passive_port}"
            f"?chunks={metadata['chunks']}&size={metadata['size']}&hash={metadata['hash']}"
            f"&v={metadata['version']}&e={1 if metadata['encryption'] else 0}"
        )

    async def fetch_file(self, share_code: str, output_dir: str = ".",
                         progress: Optional[Progress] = None,
                         task_id: Optional[str] = None) -> Path:
        """Fetch a shared file with progress tracking."""
        if not self._active:
            self.start()
            
        try:
            metadata = self._parse_share_code(share_code)
            output_path = Path(output_dir) / sanitize_filename(metadata.get('name', 'downloaded_file'))
            
            # Start progress tracking if enabled
            prog_task_id = None
            if progress and not task_id:
                prog_task_id = progress.add_task(
                    f"Downloading {metadata.get('name', 'file')}",
                    total=metadata['size']
                )
            elif task_id:
                prog_task_id = task_id

            # Download file with progress updates            
            await self._download_file(metadata, output_path, progress, prog_task_id)
            
            # Verify integrity
            if not self._verify_integrity(output_path, metadata['hash']):
                output_path.unlink()
                raise IntegrityError("File integrity check failed")
                
            return output_path
            
        except Exception as e:
            logger.error(f"Download failed: {e}")
            raise P2PError(f"Download failed: {str(e)}")

    async def _download_file(self, metadata: Dict[str, Any], output_path: Path,
                             progress: Optional[Progress], task_id: Optional[str]) -> None:
        """Download file with progress tracking."""
        total_size = int(metadata['size'])
        chunk_size = int(metadata.get('chunk_size', 1024 * 1024))
        received = 0

        try:
            temp_path = output_path.with_suffix('.part')
            
            async with self._net.connect(metadata['peer']) as conn:
                with temp_path.open('wb') as f:
                    while received < total_size:
                        data = await conn.receive(chunk_size)
                        if not data:
                            break
                            
                        # Write data and update progress
                        f.write(data)
                        received += len(data)
                        
                        # Update progress if tracking enabled
                        if progress and task_id:
                            progress.update(task_id, completed=received,
                                            total=total_size,
                                            description=f"{received/total_size:.1%}")

            # Move temp file to final location
            temp_path.rename(output_path)
            
        except Exception as e:
            if temp_path.exists():
                temp_path.unlink()
            raise P2PError(f"Download error: {str(e)}")

    def _parse_share_code(self, share_code: str) -> Dict[str, Any]:
        """Parse share code"""
        try:
            parsed = urlparse(share_code)
            if parsed.scheme != 'snatch':
                raise ValueError("Invalid protocol")

            query = parse_qs(parsed.query)
            return {
                'id': parsed.username,
                'host': parsed.hostname,
                'port': parsed.port,
                'chunks': int(query['chunks'][0]),
                'size': int(query['size'][0]),
                'hash': query['hash'][0],
                'version': int(query.get('v', [PROTOCOL_VERSION])[0]),
                'encryption': query.get('e', ['1'])[0] == '1'
            }
        except Exception as e:
            raise ValueError(f"Invalid share code format: {e}")

    def _derive_key(self, file_id: str) -> bytes:
        """Derive encryption key"""
        hkdf = HKDF(
            algorithm=hashes.SHA256(),
            length=32,
            salt=None,
            info=b'snatch-file-encryption',
            backend=default_backend()
        )
        return hkdf.derive(file_id.encode())

    def _verify_integrity(self, file_path: Path, expected_hash: str) -> bool:
        """Verify file integrity using SHA256."""
        try:
            with file_path.open('rb') as f:
                content = f.read()
                actual_hash = hashlib.sha256(content).hexdigest()
                return actual_hash == expected_hash
        except Exception as e:
            logger.error(f"Integrity check error: {e}")
            return False

# CLI command handlers
def share_file_cmd(file_path: str) -> str:
    """Share file command handler"""
    config = ShareConfig(upnp=True, dht_enabled=True)
    p2p = P2PManager(config)
    return asyncio.run(p2p.share_file(file_path))

def fetch_file_cmd(share_code: str, output_path: str = ".") -> Path:
    """Fetch file command handler"""
    config = ShareConfig(upnp=True, dht_enabled=True)
    p2p = P2PManager(config)
    with HolographicProgress() as progress:
        return asyncio.run(p2p.fetch_file(share_code, output_path, progress))