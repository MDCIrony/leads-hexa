import os


def database_url() -> str:
    """The only variable a maintenance command needs: no broker, no signing keys."""
    url = os.getenv("DATABASE_URL")
    if not url:
        raise SystemExit("DATABASE_URL is required")
    return url
