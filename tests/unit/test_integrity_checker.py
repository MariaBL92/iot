"""
Unit tests for the integrity_checker.

The Tangle fetch is mocked via the fetch_fn argument, so these tests run
in isolation without any network access.
"""
from __future__ import annotations
import pytest

from src.processor.hash_generator import generate_hash
from src.processor.local_registry import LocalRegistry
from src.processor.payload_builder import build_tangle_payload
from src.verifier.integrity_checker import (
    ALTERADO, INTEGRO, NO_ENCONTRADO,
    VerificationError, verify_from_registry, verify_integrity,
)


@pytest.fixture
def sample_data():
    return {
        "sensor_id": "sensor_01",
        "timestamp": "2026-04-20T10:30:00Z",
        "temperature": 23.5,
        "humidity": 61.2,
    }


@pytest.fixture
def stored_payload(sample_data):
    """The payload that would have been stored on the Tangle for sample_data."""
    return build_tangle_payload(sample_data)


# ---------------------------------------------------------------------------
# verify_integrity: happy path
# ---------------------------------------------------------------------------

class TestVerifyIntegrityIntact:
    def test_integro_on_unmodified_data(self, sample_data, stored_payload):
        fetch_fn = lambda block_id: stored_payload
        verdict = verify_integrity("block_abc", sample_data, fetch_fn=fetch_fn)
        assert verdict["status"] == INTEGRO
        assert verdict["match"] is True

    def test_stored_and_computed_match(self, sample_data, stored_payload):
        fetch_fn = lambda block_id: stored_payload
        v = verify_integrity("block_abc", sample_data, fetch_fn=fetch_fn)
        assert v["stored"] == v["computed"]
        assert v["computed"] == generate_hash(sample_data)

    def test_recovers_sensor_id_and_timestamp(self, sample_data, stored_payload):
        fetch_fn = lambda block_id: stored_payload
        v = verify_integrity("block_abc", sample_data, fetch_fn=fetch_fn)
        assert v["sensor_id"] == sample_data["sensor_id"]
        assert v["timestamp"] == sample_data["timestamp"]


# ---------------------------------------------------------------------------
# verify_integrity: alterations
# ---------------------------------------------------------------------------

class TestVerifyIntegrityAltered:
    def test_alterado_on_temperature_change(self, sample_data, stored_payload):
        fetch_fn = lambda block_id: stored_payload
        altered = {**sample_data, "temperature": 99.9}
        v = verify_integrity("block_abc", altered, fetch_fn=fetch_fn)
        assert v["status"] == ALTERADO
        assert v["match"] is False

    def test_alterado_on_humidity_change(self, sample_data, stored_payload):
        fetch_fn = lambda block_id: stored_payload
        altered = {**sample_data, "humidity": 1.0}
        v = verify_integrity("block_abc", altered, fetch_fn=fetch_fn)
        assert v["status"] == ALTERADO

    def test_alterado_on_timestamp_change(self, sample_data, stored_payload):
        fetch_fn = lambda block_id: stored_payload
        altered = {**sample_data, "timestamp": "2099-01-01T00:00:00Z"}
        assert verify_integrity("b", altered, fetch_fn=fetch_fn)["status"] == ALTERADO

    def test_alterado_on_sensor_id_change(self, sample_data, stored_payload):
        fetch_fn = lambda block_id: stored_payload
        altered = {**sample_data, "sensor_id": "FAKE_SENSOR"}
        assert verify_integrity("b", altered, fetch_fn=fetch_fn)["status"] == ALTERADO

    def test_alterado_on_added_field(self, sample_data, stored_payload):
        fetch_fn = lambda block_id: stored_payload
        altered = {**sample_data, "extra_field": "injected"}
        assert verify_integrity("b", altered, fetch_fn=fetch_fn)["status"] == ALTERADO

    def test_alterado_on_removed_field(self, sample_data, stored_payload):
        fetch_fn = lambda block_id: stored_payload
        altered = {k: v for k, v in sample_data.items() if k != "humidity"}
        assert verify_integrity("b", altered, fetch_fn=fetch_fn)["status"] == ALTERADO


# ---------------------------------------------------------------------------
# verify_integrity: error handling
# ---------------------------------------------------------------------------

class TestVerifyIntegrityErrors:
    def test_raises_when_fetch_fails(self, sample_data):
        def bad_fetch(block_id):
            raise ConnectionError("Tangle unreachable")
        with pytest.raises(VerificationError, match="Could not fetch"):
            verify_integrity("b", sample_data, fetch_fn=bad_fetch)

    def test_raises_when_payload_is_not_dict(self, sample_data):
        fetch_fn = lambda b: "not a dict"
        with pytest.raises(VerificationError, match="not a dict"):
            verify_integrity("b", sample_data, fetch_fn=fetch_fn)

    def test_raises_when_payload_missing_hash(self, sample_data):
        fetch_fn = lambda b: {"sensor_id": "s", "timestamp": "t"}
        with pytest.raises(VerificationError, match="no 'hash' field"):
            verify_integrity("b", sample_data, fetch_fn=fetch_fn)


# ---------------------------------------------------------------------------
# verify_from_registry
# ---------------------------------------------------------------------------

class TestVerifyFromRegistry:
    def test_no_encontrado_when_block_id_unknown(self, tmp_path):
        registry = LocalRegistry(tmp_path / "r.json")
        v = verify_from_registry("ghost_block_id", registry)
        assert v["status"] == NO_ENCONTRADO

    def test_integro_when_data_in_registry(self, tmp_path, sample_data, stored_payload):
        registry = LocalRegistry(tmp_path / "r.json")
        block_id = "block_xyz"
        registry.append({
            "block_id": block_id,
            "hash": stored_payload["hash"],
            "timestamp": sample_data["timestamp"],
            "raw_data": sample_data,
            "status": "registered",
        })
        fetch_fn = lambda b: stored_payload
        v = verify_from_registry(block_id, registry, fetch_fn=fetch_fn)
        assert v["status"] == INTEGRO
