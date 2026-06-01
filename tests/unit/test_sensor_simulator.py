"""Unit tests for the sensor_simulator module."""
from __future__ import annotations
import re
from datetime import datetime
import pytest

from src.simulator.sensor_simulator import (
    HUMIDITY_MAX, HUMIDITY_MIN, TEMP_MAX, TEMP_MIN, generate_sensor_data,
)

ISO_8601_Z_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")


class TestGenerateSensorData:
    def test_returns_dict_with_required_keys(self):
        data = generate_sensor_data("sensor_01")
        assert set(data.keys()) == {"sensor_id", "timestamp", "temperature", "humidity"}

    def test_sensor_id_is_preserved(self):
        assert generate_sensor_data("sensor_42")["sensor_id"] == "sensor_42"

    def test_temperature_within_expected_range(self):
        for _ in range(200):
            d = generate_sensor_data("s")
            assert TEMP_MIN <= d["temperature"] <= TEMP_MAX

    def test_humidity_within_expected_range(self):
        for _ in range(200):
            d = generate_sensor_data("s")
            assert HUMIDITY_MIN <= d["humidity"] <= HUMIDITY_MAX

    def test_temperature_has_one_decimal_place(self):
        for _ in range(50):
            t10 = generate_sensor_data("s")["temperature"] * 10
            assert abs(t10 - round(t10)) < 1e-9

    def test_humidity_has_one_decimal_place(self):
        for _ in range(50):
            h10 = generate_sensor_data("s")["humidity"] * 10
            assert abs(h10 - round(h10)) < 1e-9

    def test_temperature_is_float(self):
        assert isinstance(generate_sensor_data("s")["temperature"], float)

    def test_timestamp_is_iso_8601_with_z_suffix(self):
        assert ISO_8601_Z_PATTERN.match(generate_sensor_data("s")["timestamp"])

    def test_timestamp_is_parseable(self):
        ts = generate_sensor_data("s")["timestamp"].replace("Z", "+00:00")
        assert datetime.fromisoformat(ts).tzinfo is not None

    def test_returns_different_values_on_consecutive_calls(self):
        values = [generate_sensor_data("s") for _ in range(50)]
        assert len({d["temperature"] for d in values}) > 1
        assert len({d["humidity"] for d in values}) > 1

    @pytest.mark.parametrize("sensor_id", ["sensor_01", "balcony_01", "x"])
    def test_accepts_various_sensor_id_formats(self, sensor_id):
        assert generate_sensor_data(sensor_id)["sensor_id"] == sensor_id
