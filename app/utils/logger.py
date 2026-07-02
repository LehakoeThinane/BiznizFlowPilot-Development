"""Logging configuration."""

import logging
import sys

from app.core.config import settings

# Create logger
logger = logging.getLogger("biznizflowpilot")
logger.setLevel(getattr(logging, settings.log_level))

# Create console handler
handler = logging.StreamHandler(sys.stdout)
handler.setLevel(getattr(logging, settings.log_level))

# Create formatter
formatter = logging.Formatter(
    "[%(asctime)s] %(name)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
handler.setFormatter(formatter)

# Add handler to logger
logger.addHandler(handler)


def get_logger(name: str = "biznizflowpilot") -> logging.Logger:
    """Get a logger that inherits the configured console handler.

    Returns a child of the "biznizflowpilot" logger so callers passing
    their module's __name__ (e.g. "app.services.email") still propagate
    up to the one handler configured above, instead of silently going
    nowhere (the root logger has no handler of its own).
    """
    if name in ("", "biznizflowpilot"):
        return logger
    if name.startswith("biznizflowpilot."):
        return logging.getLogger(name)
    return logging.getLogger(f"biznizflowpilot.{name}")
