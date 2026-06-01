"""Unit tests for the payload_builder module."""
from __future__ import annotations
import pytest

from src.processor.hash_generator import generate_hash
from src.processor.payload_builder import build_tangle_payload


@pytest.fixture
def sample_sensor_data():
    return {
        "sensor_id": "sensor_01",
        "timestamp": "2026-04-20T10:30:00Z",
        "temperature": 23.5,
        "humidity": 61.2,
    }


class TestBuildTanglePayload:
    def test_has_exactly_three_keys(self, sample_sensor_data):
        p = build_tangle_payload(sample_sensor_data)
        assert set(p.keys()) == {"hash", "sensor_id", "timestamp"}

    def test_hash_matches_independent_computation(self, sample_sensor_data):
        assert build_tangle_payload(sample_sensor_data)["hash"] == generate_hash(sample_sensor_data)

    def test_sensor_id_copied_verbatim(self, sample_sensor_data):
        assert build_tangle_payload(sample_sensor_data)["sensor_id"] == sample_sensor_data["sensor_id"]

    def test_timestamp_copied_verbatim(self, sample_sensor_data):
        assert build_tangle_payload(sample_sensor_data)["timestamp"] == sample_sensor_data["timestamp"]

    def test_excludes_temperature(self, sample_sensor_data):
        assert "temperature" not in build_tangle_payload(sample_sensor_data)

    def test_excludes_humidity(self, sample_sensor_data):
        assert "humidity" not in build_tangle_payload(sample_sensor_data)

    def test_raises_keyerror_when_sensor_id_missing(self):
        with pytest.raises(KeyError, match="sensor_id"):
            build_tangle_payload({"timestamp": "t", "temperature": 1.0})

    def test_raises_keyerror_when_timestamp_missing(self):
        with pytest.raises(KeyError, match="timestamp"):
            build_tangle_payload({"sensor_id": "s", "temperature": 1.0})
