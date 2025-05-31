"""
Theme package for SnatchV2 interactive interfaces.

This package contains modern and enhanced interactive interfaces for SnatchV2.
"""

# Import main interface functions
try:
    from .modern_interactive import run_modern_interactive, ModernSnatchApp
except ImportError:
    run_modern_interactive = None
    ModernSnatchApp = None

try:
    from .textual_interface import start_textual_interface
except ImportError:
    start_textual_interface = None

try:
    from .cyberpunk_interactive import start_cyberpunk_interface
except ImportError:
    start_cyberpunk_interface = None

__all__ = [
    'run_modern_interactive',
    'ModernSnatchApp', 
    'start_textual_interface',
    'start_cyberpunk_interface'
]