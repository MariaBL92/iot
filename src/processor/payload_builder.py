"""
Tangle payload builder. Materializes the privacy boundary: only {hash,
sensor_id, timestamp} ever leaves the local environment. Raw sensor
values stay in the local registry.
"""
from __future__ import annotations

from src.processor.hash_generator import generate_hash


def build_tangle_payload(sensor_data: dict) -> dict:
    """Build the dict to be registered on the Tangle.

    Args:
        sensor_data: Must contain 'sensor_id' and 'timestamp'.

    Returns:
        A dict with the keys 'hash', 'sensor_id', 'timestamp'.

    Raises:
        KeyError: if 'sensor_id' or 'timestamp' are missing.
    """
    if "sensor_id" not in sensor_data:
        raise KeyError("sensor_data must contain 'sensor_id'")
    if "timestamp" not in sensor_data:
        raise KeyError("sensor_data must contain 'timestamp'")
    return {
        "hash": generate_hash(sensor_data),
        "sensor_id": sensor_data["sensor_id"],
        "timestamp": sensor_data["timestamp"],
    }
