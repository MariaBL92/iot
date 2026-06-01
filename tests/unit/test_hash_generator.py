"""Unit tests for the hash_generator module."""
from __future__ import annotations
import hashlib
import pytest

from src.processor.hash_generator import canonical_json, generate_hash


@pytest.fixture
def sample_sensor_data():
    return {
        "sensor_id": "sensor_01",
        "timestamp": "2026-04-20T10:30:00Z",
        "temperature": 23.5,
        "humidity": 61.2,
    }


class TestCanonicalJson:
    def test_sorts_top_level_keys(self):
        assert canonical_json({"b": 2, "a": 1, "c": 3}) == '{"a":1,"b":2,"c":3}'

    def test_sorts_nested_keys(self):
        d = {"outer": {"z": 1, "a": 2}, "alpha": 3}
        assert canonical_json(d) == '{"alpha":3,"outer":{"a":2,"z":1}}'

    def test_no_unnecessary_whitespace(self):
        r = canonical_json({"a": 1, "b": 2})
        assert " " not in r and "\n" not in r

    def test_returns_string(self):
        assert isinstance(canonical_json({"a": 1}), str)

    def test_handles_empty_dict(self):
        assert canonical_json({}) == "{}"


class TestGenerateHash:
    def test_is_deterministic(self, sample_sensor_data):
        h = generate_hash(sample_sensor_data)
        for _ in range(1000):
            assert generate_hash(sample_sensor_data) == h

    def test_is_invariant_to_key_order_top_level(self):
        a = {"sensor_id": "s1", "timestamp": "t", "temperature": 20.0, "humidity": 50.0}
        b = {"humidity": 50.0, "temperature": 20.0, "timestamp": "t", "sensor_id": "s1"}
        assert generate_hash(a) == generate_hash(b)

    def test_is_invariant_to_key_order_nested(self):
        a = {"outer": {"x": 1, "y": 2}, "id": "a"}
        b = {"id": "a", "outer": {"y": 2, "x": 1}}
        assert generate_hash(a) == generate_hash(b)

    def test_changes_when_value_changes(self, sample_sensor_data):
        h1 = generate_hash(sample_sensor_data)
        m = dict(sample_sensor_data); m["temperature"] = 24.5
        assert h1 != generate_hash(m)

    def test_changes_when_timestamp_changes(self, sample_sensor_data):
        h1 = generate_hash(sample_sensor_data)
        m = dict(sample_sensor_data); m["timestamp"] = "2026-04-20T10:30:01Z"
        assert h1 != generate_hash(m)

    def test_changes_when_sensor_id_changes(self, sample_sensor_data):
        h1 = generate_hash(sample_sensor_data)
        m = dict(sample_sensor_data); m["sensor_id"] = "sensor_02"
        assert h1 != generate_hash(m)

    def test_returns_64_char_hex_string(self, sample_sensor_data):
        h = generate_hash(sample_sensor_data)
        assert isinstance(h, str) and len(h) == 64
        int(h, 16)

    def test_returns_lowercase_hex(self, sample_sensor_data):
        assert generate_hash(sample_sensor_data) == generate_hash(sample_sensor_data).lower()

    def test_known_vector(self):
        d = {"a": 1, "b": 2}
        expected = hashlib.sha256('{"a":1,"b":2}'.encode("utf-8")).hexdigest()
        assert generate_hash(d) == expected
