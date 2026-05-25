"""Small logging helper for future scrapers."""

import logging


def log_scraper_event(scraper_name: str, status: str, message: str) -> None:
    """Log a normalized scraper event."""
    logger = logging.getLogger(scraper_name)
    normalized_status = (status or "info").lower()
    text = "[%s] %s", normalized_status.upper(), message

    if normalized_status in {"error", "failed", "failure"}:
        logger.error(*text)
    elif normalized_status in {"warning", "warn"}:
        logger.warning(*text)
    else:
        logger.info(*text)
