from .constants import VERSION

__version__ = VERSION

from .cli import main as main_app
from .manager import DownloadManager
from .config import load_config

__all__ = ["main_app", "DownloadManager", "load_config", "__version__"]