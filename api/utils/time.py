"""
Utility for UTC timestamps.
"""
from datetime import datetime, timezone


def utcnow() -> datetime:
    """Return current UTC datetime with timezone info."""
    return datetime.now(timezone.utc)


def utcnow_iso() -> str:
    """Return current UTC datetime as ISO 8601 string."""
    return utcnow().isoformat()
