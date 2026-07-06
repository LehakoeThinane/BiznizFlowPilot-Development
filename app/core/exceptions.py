"""Shared application-level exceptions not tied to a single domain."""


class ConcurrencyConflictError(Exception):
    """Raised when an optimistic-concurrency (version) check fails.

    Signals that the row being updated was changed by someone else since it
    was loaded - the caller should reload and retry, not blindly overwrite.
    API routes map this to HTTP 409 Conflict.
    """
