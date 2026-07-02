"""Parse @type:value tokens from user chat input."""

from __future__ import annotations

import re
from dataclasses import dataclass

# Matches @client:Acme  @lead:WebsiteRedesign  @task:Follow_up
# Value ends at whitespace or another @-mention.
_PATTERN = re.compile(r"@(\w+):(\S+)")

SUPPORTED_TYPES = {
    "client",
    "lead",
    "task",
    "user",
    "product",
    "supplier",
    "order",
    "po",
}


@dataclass
class RawMention:
    mention_type: str   # e.g. "client"
    raw_value: str      # e.g. "Acme"
    original: str       # full match e.g. "@client:Acme"


def parse_mentions(text: str) -> list[RawMention]:
    """Extract all @type:value mentions from a message string."""
    results: list[RawMention] = []
    for match in _PATTERN.finditer(text):
        mention_type = match.group(1).lower()
        raw_value = match.group(2).replace("_", " ")
        if mention_type in SUPPORTED_TYPES:
            results.append(
                RawMention(
                    mention_type=mention_type,
                    raw_value=raw_value,
                    original=match.group(0),
                )
            )
    return results
