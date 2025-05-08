#peer‑to‑peer share/fetch logic (future)

import hashlib
import threading
import time
from urllib.parse import urlparse, parse_qs
from pathlib import Path
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.backends import default_backend
from pyp2p.net import Net
from pyp2p.dht_msg import DHT
from pyp2p.unl import UNL
from modules.manager import DownloadManager
from modules.utils import sanitize_filename
from modules.progress import ColorProgressBar
from modules.logging_config import setup_logging
import logging

setup_logging()
logger = logging.getLogger(__name__)

class PeerRefusedError(Exception):
    pass

class IntegrityError(Exception):
    pass

def share_file(file_path: str) -> str:
    file = Path(file_path)
    if not file.is_file():
        raise FileNotFoundError(f"File {file_path} not found")
    
    # Compute file metadata
    sha256 = hashlib.sha256()
    with open(file, 'rb') as f:
        while chunk := f.read(8192):
            sha256.update(chunk)
    file_hash = sha256.hexdigest()
    file_size = file.stat().st_size
    chunk_size = 1024 * 1024  # 1MB chunks
    chunk_count = (file_size + chunk_size - 1) // chunk_size
    file_id = file_hash

    # Initialize P2P node
    unl = UNL()
    dht = DHT(unl=unl)
    node = Net(unl=unl, dht=dht, passive_port=0)
    node.start()
    node.dht_insert(file_id, node.get_latest_connection_info())

    # Build share code
    share_code = (
        f"snatch://{file_id}@{node.external_ip()}:{node.passive_port}"
        f"?chunks={chunk_count}&size={file_size}&hash={file_hash}"
    )

    # Start server thread
    def server_loop():
        while True:
            for conn in node:
                try:
                    data = conn.recv().decode()
                    if data == file_id:
                        print(f"Accept incoming fetch for {file.name} ({file_size//1024//1024} MB)? [y/N]")
                        response = input().strip().lower()
                        if response == 'y':
                            conn.send(b'ACCEPT')
                            _send_file(conn, file, file_id, chunk_size)
                        else:
                            conn.send(b'REFUSE')
                        conn.close()
                except Exception as e:
                    logger.error(f"Connection error: {e}")

    threading.Thread(target=server_loop, daemon=True).start()
    return share_code

def _send_file(conn, file: Path, file_id: str, chunk_size: int):
    key = hashlib.sha256(file_id.encode() + b"secret").digest()[:32]
    with open(file, 'rb') as f:
        while chunk := f.read(chunk_size):
            nonce = hashlib.sha256(str(time.time()).encode()).digest()[:12]
            cipher = Cipher(algorithms.AES(key), modes.GCM(nonce), backend=default_backend())
            encryptor = cipher.encryptor()
            ciphertext = encryptor.update(chunk) + encryptor.finalize()
            conn.send(nonce + ciphertext + encryptor.tag)

def fetch_file(share_code: str, output_dir: str = '.'):
    parsed = urlparse(share_code)
    if parsed.scheme != 'snatch':
        raise ValueError("Invalid share code")
    file_id = parsed.username
    peer_addr = (parsed.hostname, parsed.port)
    query = parse_qs(parsed.query)
    chunk_count = int(query['chunks'][0])
    file_size = int(query['size'][0])
    expected_hash = query['hash'][0]

    # Connect to peer
    unl = UNL()
    node = Net(unl=unl, dht=DHT(unl=unl))
    node.start()
    conn = node.connect(peer_addr)
    if not conn:
        raise ConnectionError("Connection failed")

    conn.send(file_id.encode())
    response = conn.recv().decode()
    if response == 'REFUSE':
        raise PeerRefusedError()
    elif response != 'ACCEPT':
        raise Exception("Peer error")

    # Prepare download
    key = hashlib.sha256(file_id.encode() + b"secret").digest()[:32]
    output_path = Path(output_dir) / sanitize_filename(Path(parsed.path).name)
    manager = DownloadManager(str(output_path), expected_hash=expected_hash)
    progress = ColorProgressBar(total=file_size)

    with open(output_path, 'wb') as f:
        for _ in range(chunk_count):
            data = conn.recv()
            nonce, tag = data[:12], data[-16:]
            cipher = Cipher(algorithms.AES(key), modes.GCM(nonce, tag), backend=default_backend())
            decryptor = cipher.decryptor()
            chunk = decryptor.update(data[12:-16]) + decryptor.finalize()
            manager.write_chunk(chunk)
            progress.update(len(chunk))

    if not manager.verify_hash(expected_hash):
        output_path.unlink()
        raise IntegrityError("Hash mismatch")
    progress.close()