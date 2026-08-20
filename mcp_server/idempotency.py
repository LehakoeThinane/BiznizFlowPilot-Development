"""Client-side dedupe for create-type mutations on invoice/sales-orders/
purchase-orders - the routers where a duplicate write is costly and hard to
unwind (a second invoice or order, not just a second identical task).

BFP's REST API has no server-side Idempotency-Key support today (confirmed:
the concept only exists internally in app/workflow_engine/, never exposed to
API clients) - this is a client-side mitigation, not a substitute for one.
It covers the "httpx timeout, did the create actually apply?" case,
including a retry Claude itself might issue after seeing a timeout error.

Known blind spot, named rather than papered over: this cache is in-memory in
the MCP server process, so it's wiped by exactly the event most likely to
cause an ambiguous retry - a crash or restart mid-request. Not solved here,
same category as the audit-trail gap documented in the plan.
"""

from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass
from threading import Lock
from typing import Any

# Only create-type operations where a duplicate is genuinely costly - not
# every write in these routers (an update/delete retried twice is
# self-correcting or a harmless no-op; a duplicate CREATE is not).
DEDUPED_OPERATIONS: frozenset[tuple[str, str]] = frozenset(
    {
        ("POST", "/api/v1/invoices"),
        ("POST", "/api/v1/sales-orders"),
        ("POST", "/api/v1/purchase-orders"),
    }
)


@dataclass
class _CacheEntry:
    result: Any
    expires_at: float


class IdempotencyCache:
    def __init__(self, window_seconds: int):
        self._window_seconds = window_seconds
        self._entries: dict[str, _CacheEntry] = {}
        self._lock = Lock()

    def is_deduped(self, method: str, path: str) -> bool:
        return (method.upper(), path) in DEDUPED_OPERATIONS

    def get(self, method: str, path: str, args: dict) -> Any | None:
        """Return a cached result for an identical recent call, or None."""
        key = self._key(method, path, args)
        with self._lock:
            entry = self._entries.get(key)
            if entry is None:
                return None
            if entry.expires_at < time.monotonic():
                del self._entries[key]
                return None
            return entry.result

    def put(self, method: str, path: str, args: dict, result: Any) -> None:
        key = self._key(method, path, args)
        with self._lock:
            self._entries[key] = _CacheEntry(result=result, expires_at=time.monotonic() + self._window_seconds)

    @staticmethod
    def _key(method: str, path: str, args: dict) -> str:
        payload = json.dumps({"method": method, "path": path, "args": args}, sort_keys=True, default=str)
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()
