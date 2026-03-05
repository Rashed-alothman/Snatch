"""
Theme sub-package for Snatch interactive interfaces.
"""

try:
    from .modern_interactive import run_modern_interactive, ModernSnatchApp
except ImportError:
    run_modern_interactive = None
    ModernSnatchApp = None

__all__ = [
    'run_modern_interactive',
    'ModernSnatchApp',
]
