"""Offline completeness check for mcp_server/router_policy.py.

Runs the same validate_against_openapi() logic mcp_server/server.py runs at
real startup (against a live-fetched schema), but against the committed
fixture snapshot instead - so it works without a running backend/DB, for
fast local iteration and to keep this check runnable in this project's
existing test suite. The live check at startup is still the one that
actually gates the server for any schema drift since the snapshot was taken.
"""

import json
from pathlib import Path

from mcp_server.router_policy import validate_against_openapi

_FIXTURE = Path(__file__).parent / "fixtures" / "openapi_snapshot.json"


def test_policy_has_no_unclassified_operations():
    with open(_FIXTURE, encoding="utf-8") as f:
        spec = json.load(f)

    problems = validate_against_openapi(spec)
    assert not problems, "router_policy.py is missing classifications:\n" + "\n".join(problems)
