#setup human vs JSON logging
import logging 
from colorama import Fore, Style
from pythonjsonlogger import jsonlogger  
import argparse
import textwrap
class ColoramaFormatter(logging.Formatter):
    def format(self, record):
        level = record.levelname
        msg = super().format(record)
        if record.levelno >= logging.ERROR:
            return f"{Fore.RED}{msg}{Style.RESET_ALL}"
        if record.levelno >= logging.WARNING:
            return f"{Fore.YELLOW}{msg}{Style.RESET_ALL}"
        return msg

def setup_logging(json_format: bool = False, level: int = logging.INFO):
    """Configure the root logger once for the whole app."""
    root = logging.getLogger()
    root.setLevel(level)
    # remove any default handlers
    for h in list(root.handlers):
        root.removeHandler(h)

    handler = logging.StreamHandler()
    if json_format:
        fmt = jsonlogger.JsonFormatter(
            '%(asctime)s %(name)s %(levelname)s %(message)s'
        )
    else:
        fmt = ColoramaFormatter('%(asctime)s %(levelname)s %(name)s: %(message)s')
    handler.setFormatter(fmt)
    root.addHandler(handler)

class CustomHelpFormatter(argparse.HelpFormatter):
    def _split_lines(self, text, width):
        return textwrap.wrap(text, width)