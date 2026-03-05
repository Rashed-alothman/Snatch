from .constants import VERSION

__version__ = VERSION

from .manager import DownloadManager
from .config import load_config

__all__ = ["DownloadManager", "load_config", "__version__"]