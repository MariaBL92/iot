"""
SHA-256 hash generation with canonical JSON serialization.

CRITICAL CONTRACT: every dict that is hashed MUST be serialized through
canonical_json to guarantee that semantically equal payloads produce
identical hashes. Direct calls to json.dumps are forbidden in hash zones.
"""
from __future__ import annotations

import hashlib
import json


def canonical_json(data: dict) -> str:
    """Serialize a dict to JSON in canonical form (sort_keys, compact)."""
    return json.dumps(data, sort_keys=True, separators=(",", ":"))


def generate_hash(data: dict) -> str:
    """Compute the SHA-256 hash of a dict, in canonical form."""
    return hashlib.sha256(canonical_json(data).encode("utf-8")).hexdigest()
