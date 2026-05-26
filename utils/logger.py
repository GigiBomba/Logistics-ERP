import logging
import os


def get_logger(name, level=logging.INFO):
    """Create or reuse a logger. Route-specific debug logs go to 'logs/route_debug.log'.

    The function is intentionally simple: it ensures logs directory exists and
    writes route debug information to a dedicated file for easier diagnosis.
    """
    logger = logging.getLogger(name)
    if not logger.handlers:
        os.makedirs("logs", exist_ok=True)

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
