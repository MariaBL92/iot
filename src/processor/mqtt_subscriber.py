"""
MQTT subscriber that ingests sensor readings, computes their hashes,
publishes them to the IOTA Tangle, and persists them locally.

Flow per message:
    1. Parse JSON from MQTT payload.
    2. Compute SHA-256 hash of the sensor data.
    3. Build the Tangle payload {hash, sensor_id, timestamp}.
    4. Append an entry with status="pending" to the local registry.
    5. Attempt to publish to Tangle (with retries inside register_in_tangle).
    6a. On success: update the entry with block_id and status="registered".
    6b. On failure: update the entry with status="failed" (block_id stays None).

The Tangle publication can be disabled at runtime via the
--no-tangle flag, which is useful for local-only testing without
network connectivity (e.g. during development of Layers 1 and 2).
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from typing import Callable, Optional

import paho.mqtt.client as mqtt
from dotenv import load_dotenv

from src.processor.hash_generator import generate_hash
from src.processor.local_registry import LocalRegistry
from src.processor.payload_builder import build_tangle_payload

load_dotenv()
logger = logging.getLogger(__name__)


# Type alias for the Tangle-write hook (so tests can inject a mock).
# Signature: callable(payload: dict) -> str  (returns block_id) or raises.
TangleWriteFn = Callable[[dict], str]


# ---------------------------------------------------------------------------
# Pure-ish message processing (testable without MQTT and without Tangle)
# ---------------------------------------------------------------------------

def process_message(
    payload_bytes: bytes,
    registry: LocalRegistry,
    tangle_write_fn: Optional[TangleWriteFn] = None,
) -> dict:
    """
    Process a single MQTT payload and persist the resulting entry.

    Args:
        payload_bytes: Raw MQTT message body (UTF-8 encoded JSON).
        registry: Local registry where the new entry will be appended.
        tangle_write_fn: Optional callable that publishes to the Tangle and
            returns the block_id. If None, the entry stays in "pending" state.

    Returns:
        The entry as it ended up in the registry (with status reflecting
        the outcome of the Tangle write).
    """
    sensor_data = json.loads(payload_bytes.decode("utf-8"))
    sensor_hash = generate_hash(sensor_data)
    tangle_payload = build_tangle_payload(sensor_data)

    entry = {
        "block_id": None,
        "hash": sensor_hash,
        "timestamp": sensor_data["timestamp"],
        "raw_data": sensor_data,
        "tangle_payload": tangle_payload,
        "status": "pending",
    }
    registry.append(entry)

    if tangle_write_fn is None:
        return entry

    # Attempt to register the hash in the Tangle.
    try:
        block_id = tangle_write_fn(tangle_payload)
        registry.update_block_id(sensor_hash, block_id, status="registered")
        entry["block_id"] = block_id
        entry["status"] = "registered"
        logger.info(
            "Registered in Tangle: sensor=%s hash=%s... block_id=%s",
            sensor_data["sensor_id"], sensor_hash[:16], block_id,
        )
    except Exception as exc:
        registry.update_block_id(sensor_hash, None, status="failed")
        entry["status"] = "failed"
        logger.error(
            "Tangle registration failed for hash=%s...: %s",
            sensor_hash[:16], exc,
        )

    return entry


# ---------------------------------------------------------------------------
# MQTT callbacks
# ---------------------------------------------------------------------------

def _on_connect(client, userdata, flags, reason_code, properties=None):
    if reason_code == 0:
        client.subscribe(userdata["topic"], qos=1)
        logger.info("Connected and subscribed to %s", userdata["topic"])
    else:
        logger.error("Failed to connect to MQTT broker (reason: %s)", reason_code)


def _on_disconnect(client, userdata, flags, reason_code, properties=None):
    if reason_code != 0:
        logger.warning("Unexpected disconnection (reason: %s)", reason_code)


def _on_message(client, userdata, msg):
    registry: LocalRegistry = userdata["registry"]
    tangle_fn: Optional[TangleWriteFn] = userdata.get("tangle_write_fn")
    try:
        entry = process_message(msg.payload, registry, tangle_fn)
        logger.debug("Processed: hash=%s... status=%s",
                     entry["hash"][:16], entry["status"])
    except json.JSONDecodeError:
        logger.exception("Received invalid JSON on topic %s", msg.topic)
    except KeyError as exc:
        logger.error("Payload missing required field: %s", exc)
    except Exception:
        logger.exception("Unexpected error while processing message")


# ---------------------------------------------------------------------------
# Subscriber lifecycle
# ---------------------------------------------------------------------------

def run_subscriber(
    broker_host: str, broker_port: int, topic: str,
    registry_path: str, tangle_enabled: bool = True,
) -> None:
    """Connect to the broker and block while processing incoming messages."""
    registry = LocalRegistry(registry_path)

    tangle_fn: Optional[TangleWriteFn] = None
    if tangle_enabled:
        # Lazy import keeps iota-sdk out of the dependency graph for users
        # who only want to run Layers 1 and 2.
        from src.iota.tangle_writer import register_in_tangle
        tangle_fn = register_in_tangle
        logger.info("Tangle registration ENABLED")
    else:
        logger.warning("Tangle registration DISABLED (--no-tangle). "
                       "Entries will stay in 'pending' state.")

    userdata = {
        "registry": registry,
        "topic": topic,
        "tangle_write_fn": tangle_fn,
    }
    client = mqtt.Client(
        callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
        userdata=userdata,
    )
    client.on_connect = _on_connect
    client.on_disconnect = _on_disconnect
    client.on_message = _on_message
    client.connect(broker_host, broker_port, keepalive=60)
    logger.info(
        "Subscriber started: broker=%s:%d, topic=%s, registry=%s",
        broker_host, broker_port, topic, registry_path,
    )
    try:
        client.loop_forever()
    except KeyboardInterrupt:
        logger.info("Subscriber stopped by user (Ctrl+C)")
    finally:
        client.disconnect()


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="MQTT subscriber that hashes sensor data, persists it "
                    "locally, and registers it in the IOTA Tangle.",
    )
    parser.add_argument("--registry-path", default=None)
    parser.add_argument(
        "--no-tangle", action="store_true",
        help="Disable Tangle registration; entries stay pending. "
             "Useful for development without IOTA connectivity.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    args = _parse_args(argv)
    broker_host = os.getenv("MQTT_BROKER", "localhost")
    broker_port = int(os.getenv("MQTT_PORT", "1883"))
    topic = os.getenv("MQTT_TOPIC", "iot/sensors")
    registry_path = args.registry_path or os.getenv(
        "LOCAL_REGISTRY_PATH", "data/local_registry.json"
    )
    run_subscriber(broker_host, broker_port, topic, registry_path,
                   tangle_enabled=not args.no_tangle)
    return 0


if __name__ == "__main__":
    sys.exit(main())
