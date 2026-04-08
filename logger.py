"""
Sentinel-T Structured Logger
Writes both to the console (coloured) and to a rotating log file.
Import this module and call get_logger(__name__) in any module.
"""

import logging
import logging.handlers
import sys
from config import LOG_FILE, LOG_LEVEL

_LEVEL_MAP = {
    "DEBUG":   logging.DEBUG,
    "INFO":    logging.INFO,
    "WARNING": logging.WARNING,
    "ERROR":   logging.ERROR,
}


class _ColourFormatter(logging.Formatter):
    """ANSI-coloured console formatter."""
    _COLOURS = {
        logging.DEBUG:   "\033[94m",   # Blue
        logging.INFO:    "\033[92m",   # Green
        logging.WARNING: "\033[93m",   # Yellow
        logging.ERROR:   "\033[91m",   # Red
    }
    _RESET = "\033[0m"

    def format(self, record: logging.LogRecord) -> str:
        colour = self._COLOURS.get(record.levelno, "")
        record.levelname = f"{colour}{record.levelname}{self._RESET}"
        return super().format(record)


def get_logger(name: str) -> logging.Logger:
    """
    Return a named logger configured with:
    - A coloured StreamHandler (stdout)
    - A RotatingFileHandler writing to LOG_FILE (max 1 MB, 3 backups)
    """
    logger = logging.getLogger(name)

    # Avoid adding duplicate handlers if already configured
    if logger.handlers:
        return logger

    level = _LEVEL_MAP.get(LOG_LEVEL.upper(), logging.INFO)
    logger.setLevel(level)

    fmt = "%(asctime)s [%(name)s] %(levelname)s %(message)s"
    datefmt = "%Y-%m-%dT%H:%M:%S"

    # Console handler
    ch = logging.StreamHandler(sys.stdout)
    ch.setLevel(level)
    ch.setFormatter(_ColourFormatter(fmt, datefmt))
    logger.addHandler(ch)

    # Rotating file handler
    try:
        fh = logging.handlers.RotatingFileHandler(
            LOG_FILE, maxBytes=1_048_576, backupCount=3, encoding="utf-8"
        )
        fh.setLevel(level)
        fh.setFormatter(logging.Formatter(fmt, datefmt))
        logger.addHandler(fh)
    except OSError:
        logger.warning("Could not open log file '%s'; file logging disabled.", LOG_FILE)

    return logger
