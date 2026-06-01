"""
Unit tests for mqtt_subscriber.process_message.

These tests exercise the orchestrator function without an MQTT broker
and without a live Tangle. The tangle_write_fn parameter is used to
inject mock behavior (success, failure, specific return values).
"""
from __future__ import annotations
import json
import pytest

from src.processor.hash_generator import generate_hash
from src.processor.local_registry import LocalRegistry
from src.processor.mqtt_subscriber import process_message


@pytest.fixture
def registry(tmp_path):
    return LocalRegistry(tmp_path / "registry.json")


@pytest.fixture
def sensor_payload():
    return {
        "sensor_id": "sensor_01",
        "timestamp": "2026-04-20T10:30:00Z",
        "temperature": 23.5,
        "humidity": 61.2,
    }


def to_bytes(d):
    return json.dumps(d).encode("utf-8")


# ---------------------------------------------------------------------------
# Phase 2 behavior: without a Tangle write function, entries stay pending
# ---------------------------------------------------------------------------

class TestProcessMessageNoTangle:
    def test_appends_to_registry(self, registry, sensor_payload):
        process_message(to_bytes(sensor_payload), registry, tangle_write_fn=None)
        assert registry.count() == 1

    def test_entry_starts_pending(self, registry, sensor_payload):
        e = process_message(to_bytes(sensor_payload), registry, tangle_write_fn=None)
        assert e["status"] == "pending"
        assert e["block_id"] is None

    def test_computed_hash_correct(self, registry, sensor_payload):
        e = process_message(to_bytes(sensor_payload), registry, tangle_write_fn=None)
        assert e["hash"] == generate_hash(sensor_payload)

    def test_preserves_raw_data(self, registry, sensor_payload):
        e = process_message(to_bytes(sensor_payload), registry, tangle_write_fn=None)
        assert e["raw_data"] == sensor_payload

    def test_includes_tangle_payload(self, registry, sensor_payload):
        e = process_message(to_bytes(sensor_payload), registry, tangle_write_fn=None)
        assert set(e["tangle_payload"].keys()) == {"hash", "sensor_id", "timestamp"}

    def test_invalid_json_raises(self, registry):
        with pytest.raises(json.JSONDecodeError):
            process_message(b"{not valid", registry, tangle_write_fn=None)
        assert registry.count() == 0

    def test_missing_field_raises(self, registry):
        with pytest.raises(KeyError):
            process_message(to_bytes({"sensor_id": "s"}), registry, tangle_write_fn=None)
        assert registry.count() == 0


# ---------------------------------------------------------------------------
# Phase 3 behavior: with a successful Tangle write function
# ---------------------------------------------------------------------------

class TestProcessMessageTangleOK:
    def test_entry_marked_registered(self, registry, sensor_payload):
        fake_block_id = "block_abc_123"
        write_fn = lambda payload: fake_block_id

        entry = process_message(to_bytes(sensor_payload), registry, write_fn)
        assert entry["status"] == "registered"
        assert entry["block_id"] == fake_block_id

    def test_registry_reflects_status(self, registry, sensor_payload):
        write_fn = lambda payload: "block_xyz"
        process_message(to_bytes(sensor_payload), registry, write_fn)
        stored = registry.all_entries()[0]
        assert stored["status"] == "registered"
        assert stored["block_id"] == "block_xyz"

    def test_write_fn_receives_tangle_payload_only(self, registry, sensor_payload):
        received = []
        def write_fn(payload):
            received.append(payload)
            return "block_id_1"
        process_message(to_bytes(sensor_payload), registry, write_fn)
        assert set(received[0].keys()) == {"hash", "sensor_id", "timestamp"}
        # Privacy boundary preserved: no raw sensor values to the Tangle
        assert "temperature" not in received[0]
        assert "humidity" not in received[0]


# ---------------------------------------------------------------------------
# Phase 3 behavior: Tangle write failure must not crash the subscriber
# ---------------------------------------------------------------------------

class TestProcessMessageTangleFail:
    def test_entry_marked_failed_on_exception(self, registry, sensor_payload):
        def write_fn(payload):
            raise RuntimeError("Testnet unreachable")
        entry = process_message(to_bytes(sensor_payload), registry, write_fn)
        assert entry["status"] == "failed"
        assert entry["block_id"] is None

    def test_registry_reflects_failed_status(self, registry, sensor_payload):
        def write_fn(payload):
            raise ConnectionError("Timeout")
        process_message(to_bytes(sensor_payload), registry, write_fn)
        assert registry.all_entries()[0]["status"] == "failed"
        assert registry.all_entries()[0]["block_id"] is None

    def test_subscriber_keeps_running_after_failure(self, registry, sensor_payload):
        """Multiple failures don't crash, and each appends a failed entry."""
        def write_fn(payload):
            raise RuntimeError("boom")
        for _ in range(3):
            process_message(to_bytes(sensor_payload), registry, write_fn)
        assert registry.count() == 3
        for e in registry.all_entries():
            assert e["status"] == "failed"
