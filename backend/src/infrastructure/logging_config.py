import logging
import os
import sys


def configure_logging(level: str | None = None) -> None:
    """Send everything to stdout in a single line per record, which is what a
    container log collector expects."""
    logging.basicConfig(
        level=(level or os.getenv("LOG_LEVEL", "INFO")).upper(),
        format="%(asctime)s %(levelname)-8s %(name)s %(message)s",
        stream=sys.stdout,
        force=True,
    )
