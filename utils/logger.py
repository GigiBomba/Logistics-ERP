import logging
import os

# Ensure logs directory exists once at module level
os.makedirs("logs", exist_ok=True)

# Track which loggers have been configured to prevent handler accumulation
_configured_loggers: set = set()


def get_logger(name, level=logging.INFO):
    """Create or reuse a logger. Route-specific debug logs go to 'logs/route_debug.log'.

    The function is intentionally simple: it writes route debug information to
    a dedicated file for easier diagnosis. Handlers are added only once per
    logger name to avoid accumulation.
    """
    logger = logging.getLogger(name)
    if name not in _configured_loggers:
        _configured_loggers.add(name)

        logger.propagate = False

        if name == "route_debug":
            handler = logging.FileHandler("logs/route_debug.log")
            handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
            logger.addHandler(handler)
            logger.setLevel(logging.DEBUG)
        else:
            handler = logging.FileHandler("logs/app.log")
            handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
            logger.addHandler(handler)
            logger.setLevel(level)

    return logger
