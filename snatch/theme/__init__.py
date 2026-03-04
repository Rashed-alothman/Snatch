"""
Theme sub-package for Snatch interactive interfaces.

Contains modern and enhanced interactive interfaces using Textual framework.
"""

try:
    from .modern_interactive import run_modern_interactive, ModernSnatchApp
except ImportError:
    run_modern_interactive = None
    ModernSnatchApp = None

try:
    from .textual_interface import start_textual_interface
except ImportError:
    start_textual_interface = None

__all__ = [
    'run_modern_interactive',
    'ModernSnatchApp',
    'start_textual_interface',
]
