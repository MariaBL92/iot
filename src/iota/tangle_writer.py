"""
Tangle writer: publishes payloads to the IOTA Tangle as Tagged Data Blocks
and returns the resulting block_id.

Implements retry with exponential backoff because Testnet posts fail more
often than one expects. Failure after all retries raises TangleWriteError,
which callers can catch to mark the corresponding registry entry as
"failed" without crashing the subscriber.
"""
from __future__ import annotations

import logging
import time
from typing import Optional

from src.iota.iota_client import (
    dict_to_payload_hex,
    get_iota_client,
    get_tag_hex,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Configuration constants
# ---------------------------------------------------------------------------

RETRY_DELAYS_SECONDS = (1.0, 3.0, 9.0)  # exponential backoff: 1s, 3s, 9s
PUBLISH_TIMEOUT_SECONDS = 30.0          # informational; the SDK has its own


class TangleWriteError(RuntimeError):
    """Raised when a payload cannot be published to the Tangle after retries."""


# ---------------------------------------------------------------------------
# Core operation
# ---------------------------------------------------------------------------

def register_in_tangle(payload: dict, client=None) -> str:
    """
    Publish a payload to the Tangle as a Tagged Data Block.

    Args:
        payload: A dict with keys {hash, sensor_id, timestamp}. The dict is
                 serialized to canonical JSON, hex-encoded and stored as the
                 Block's data field.
        client:  Optional IOTA client to use. Defaults to the module-level
                 singleton; tests pass a mock here.

    Returns:
        The Tangle block_id (hex string) of the published block.

    Raises:
        TangleWriteError: if all retries are exhausted without success.
    """
    if client is None:
        client = get_iota_client()

    tag_hex = get_tag_hex()
    data_hex = dict_to_payload_hex(payload)

    last_exception: Optional[Exception] = None
    for attempt, delay in enumerate(_attempt_delays(), start=1):
        try:
            logger.debug("Tangle write attempt %d", attempt)
            block_id = _do_post(client, tag_hex, data_hex)
            logger.info("Block accepted by Tangle (block_id=%s)", block_id)
            return block_id
        except Exception as exc:
            last_exception = exc
            logger.warning(
                "Tangle write attempt %d failed: %s. Retrying in %.1fs",
                attempt, exc, delay,
            )
            if delay > 0:
                time.sleep(delay)

    raise TangleWriteError(
        f"Failed to publish payload after {len(RETRY_DELAYS_SECONDS) + 1} "
        f"attempts: {last_exception}"
    ) from last_exception


def _attempt_delays():
    """Yield (delay) values for the attempt sequence.

    The first attempt has no preceding delay (yielded as 0). Subsequent
    attempts use the configured retry delays.
    """
    yield 0.0
    for d in RETRY_DELAYS_SECONDS:
        yield d


def _do_post(client, tag_hex: str, data_hex: str) -> str:
    """Execute a single Tangle post and return the resulting block_id.

    Isolated as a separate function so that tests can mock the network call
    without monkey-patching iota-sdk internals.
    """
    # iota-sdk 1.1.3 returns (block_id, block) for build_and_post_block.
    # The Block may have a tagged_data payload depending on inputs.
    result = client.build_and_post_block(tag=tag_hex, data=data_hex)

    # Defensive parsing: handle both tuple and dict-like returns.
    if isinstance(result, (tuple, list)) and len(result) >= 1:
        block_id = result[0]
    elif isinstance(result, str):
        block_id = result
    else:
        block_id = getattr(result, "block_id", None) or getattr(result, "id", None)
    if not block_id:
        raise RuntimeError(f"Unexpected return from build_and_post_block: {result!r}")

    return str(block_id)


# ---------------------------------------------------------------------------
# Optional: fetch a previously-posted block (used by the verifier)
# ---------------------------------------------------------------------------

def fetch_block_data(block_id: str, client=None) -> dict:
    """
    Retrieve a block from the Tangle and return its payload as a dict.

    Args:
        block_id: The block_id returned by register_in_tangle().
        client:   Optional IOTA client (defaults to singleton).

    Returns:
        The dict that was originally registered ({hash, sensor_id, timestamp}).

    Raises:
        TangleWriteError: if the block cannot be retrieved or its payload
                          cannot be decoded as the expected JSON.
    """
    if client is None:
        client = get_iota_client()

    from src.iota.iota_client import payload_hex_to_dict

    try:
        block = client.get_block_data(block_id)
    except Exception as exc:
        raise TangleWriteError(f"Could not fetch block {block_id}: {exc}") from exc

    # Extract the data hex from the block. iota-sdk Block objects can expose
    # the payload as either an attribute or as a dict-like; cover both.
    data_hex = _extract_payload_data(block)
    try:
        return payload_hex_to_dict(data_hex)
    except Exception as exc:
        raise TangleWriteError(
            f"Could not decode payload of block {block_id}: {exc}"
        ) from exc


def _extract_payload_data(block) -> str:
    """Best-effort extraction of the hex-encoded payload data from a block."""
    # Attribute style: block.payload.data
    payload = getattr(block, "payload", None) or (
        block.get("payload") if isinstance(block, dict) else None
    )
    if payload is None:
        raise TangleWriteError("Block has no payload")
    data = getattr(payload, "data", None)
    if data is None and isinstance(payload, dict):
        data = payload.get("data")
    if data is None:
        raise TangleWriteError("Block payload has no data field")
    return data
