from chassis.web import configure_logging as _configure_logging


def configure_logging(level: str | None = None) -> None:
    """Delegates to chassis so every service logs one line per record tagged
    with the request id; kept here so callers do not depend on the library."""
    _configure_logging(level)
