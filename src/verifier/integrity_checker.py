"""
Integrity verification: given a block_id and a candidate data dict,
determine whether the data is intact.

The verifier closes the loop of the architecture: it fetches the block
from the Tangle, extracts the hash that was stored there at registration
time, recomputes the hash of the candidate data using the exact same
canonical-JSON + SHA-256 path used by the processor in Layer 2, and
compares the two.

The output is a structured dict with both hashes plus a verdict, so the
caller can log, display, or persist the evidence for audit.
"""
from __future__ import annotations

import logging
from typing import Optional

from src.processor.hash_generator import generate_hash

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Verdict constants
# ---------------------------------------------------------------------------

INTEGRO = "INTEGRO"
ALTERADO = "ALTERADO"
NO_ENCONTRADO = "NO_ENCONTRADO"
ERROR = "ERROR"


class VerificationError(RuntimeError):
    """Raised when verification cannot be carried out (block fetch failed,
    payload malformed, etc.). Distinct from the ALTERADO verdict, which
    means verification completed and detected a mismatch."""


# ---------------------------------------------------------------------------
# Core verification
# ---------------------------------------------------------------------------

def verify_integrity(
    block_id: str,
    data: dict,
    fetch_fn=None,
) -> dict:
    """
    Verify whether `data` matches the hash stored at `block_id` on the Tangle.

    Args:
        block_id: The Tangle block_id where the hash was registered.
        data: The candidate data to verify. The hash is recomputed over
              this exact dict and compared to what's stored on-chain.
        fetch_fn: Optional callable(block_id) -> dict that returns the
                  payload originally written. If None, uses tangle_writer's
                  fetch_block_data() against the real network.

    Returns:
        A dict with the keys:
            status (str):     "INTEGRO" or "ALTERADO"
            stored (str):     hash recovered from the Tangle
            computed (str):   hash recomputed from `data`
            match (bool):     True iff status == "INTEGRO"
            block_id (str):   echoed back for trace
            sensor_id (str):  recovered from the Tangle payload
            timestamp (str):  recovered from the Tangle payload

    Raises:
        VerificationError: if the block cannot be fetched or its payload
                           is malformed. Note: an ALTERADO verdict is NOT
                           an error; it is a successful detection.
    """
    if fetch_fn is None:
        from src.iota.tangle_writer import fetch_block_data
        fetch_fn = fetch_block_data

    try:
        tangle_payload = fetch_fn(block_id)
    except Exception as exc:
        raise VerificationError(
            f"Could not fetch block {block_id} from the Tangle: {exc}"
        ) from exc

    # Defensive parsing of the recovered payload.
    if not isinstance(tangle_payload, dict):
        raise VerificationError(
            f"Tangle payload is not a dict (got {type(tangle_payload).__name__})"
        )
    stored_hash = tangle_payload.get("hash")
    if not stored_hash:
        raise VerificationError(
            f"Tangle payload of block {block_id} has no 'hash' field"
        )

    # Recompute the hash of the candidate data. This is the same path used
    # by the processor in Layer 2; consistency is guaranteed by both sides
    # using generate_hash() from hash_generator.py.
    computed_hash = generate_hash(data)

    match = (stored_hash == computed_hash)
    verdict = {
        "status":    INTEGRO if match else ALTERADO,
        "stored":    stored_hash,
        "computed":  computed_hash,
        "match":     match,
        "block_id":  block_id,
        "sensor_id": tangle_payload.get("sensor_id"),
        "timestamp": tangle_payload.get("timestamp"),
    }
    logger.info(
        "Verification of block %s: %s (sensor=%s)",
        block_id, verdict["status"], verdict["sensor_id"],
    )
    return verdict


# ---------------------------------------------------------------------------
# Convenience wrapper: verify against the local registry
# ---------------------------------------------------------------------------

def verify_from_registry(
    block_id: str,
    registry,
    fetch_fn=None,
) -> dict:
    """
    Recover the original raw_data from the local registry by block_id, then
    verify against the Tangle. Useful for routine integrity audits.

    Args:
        block_id: The Tangle block_id to verify.
        registry: A LocalRegistry instance.
        fetch_fn: Optional callable, as in verify_integrity().

    Returns:
        Same verdict dict as verify_integrity(), or a dict with
        status=NO_ENCONTRADO if the block_id is not in the registry.
    """
    entry = registry.find_by_block_id(block_id)
    if entry is None:
        return {
            "status": NO_ENCONTRADO,
            "block_id": block_id,
            "match": False,
            "message": f"block_id {block_id} not present in local registry",
        }
    return verify_integrity(block_id, entry["raw_data"], fetch_fn=fetch_fn)
