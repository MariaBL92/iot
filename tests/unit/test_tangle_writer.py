"""
Unit tests for tangle_writer.

The IOTA client is mocked, so these tests run without iota-sdk installed
and without any network access.
"""
from __future__ import annotations
import pytest
from unittest.mock import MagicMock

from src.iota.tangle_writer import (
    TangleWriteError,
    fetch_block_data,
    register_in_tangle,
)
from src.iota.iota_client import dict_to_payload_hex


@pytest.fixture(autouse=True)
def fast_retries(monkeypatch):
    """Make retries instantaneous so tests don't sleep 13 seconds on failures."""
    monkeypatch.setattr("src.iota.tangle_writer.RETRY_DELAYS_SECONDS", (0, 0, 0))


@pytest.fixture
def payload():
    return {
        "hash":      "a" * 64,
        "sensor_id": "sensor_01",
        "timestamp": "2026-04-20T10:30:00Z",
    }


# ---------------------------------------------------------------------------
# register_in_tangle
# ---------------------------------------------------------------------------

class TestRegisterInTangle:
    def test_returns_block_id_on_success(self, payload):
        mock_client = MagicMock()
        mock_client.build_and_post_block.return_value = ("block_abc_123", None)
        result = register_in_tangle(payload, client=mock_client)
        assert result == "block_abc_123"

    def test_handles_string_return(self, payload):
        """Some iota-sdk variants return just the block_id as a string."""
        mock_client = MagicMock()
        mock_client.build_and_post_block.return_value = "block_xyz"
        result = register_in_tangle(payload, client=mock_client)
        assert result == "block_xyz"

    def test_handles_list_return(self, payload):
        """iota-sdk on private tangle returns a list [block_id, Block(...)]."""
        mock_client = MagicMock()
        mock_client.build_and_post_block.return_value = ["0xblock_list_id", MagicMock()]
        result = register_in_tangle(payload, client=mock_client)
        assert result == "0xblock_list_id"

    def test_handles_object_return(self, payload):
        """Some iota-sdk variants return an object with .block_id attribute."""
        ret = MagicMock(); ret.block_id = "block_obj"
        mock_client = MagicMock()
        # Override isinstance(tuple) and isinstance(str) checks: pass an object
        mock_client.build_and_post_block.return_value = ret
        result = register_in_tangle(payload, client=mock_client)
        assert result == "block_obj"

    def test_retries_on_failure(self, payload):
        mock_client = MagicMock()
        # First two attempts fail; the third succeeds
        mock_client.build_and_post_block.side_effect = [
            ConnectionError("fail 1"),
            ConnectionError("fail 2"),
            ("block_ok", None),
        ]
        assert register_in_tangle(payload, client=mock_client) == "block_ok"
        assert mock_client.build_and_post_block.call_count == 3

    def test_raises_after_all_retries(self, payload):
        mock_client = MagicMock()
        mock_client.build_and_post_block.side_effect = ConnectionError("boom")
        with pytest.raises(TangleWriteError, match="Failed to publish"):
            register_in_tangle(payload, client=mock_client)
        # 1 initial + 3 retries = 4 attempts
        assert mock_client.build_and_post_block.call_count == 4

    def test_payload_serialized_correctly(self, payload):
        mock_client = MagicMock()
        mock_client.build_and_post_block.return_value = ("block", None)
        register_in_tangle(payload, client=mock_client)
        call = mock_client.build_and_post_block.call_args

        # Tag and data must both be 0x-prefixed hex (iota-sdk 1.1.3 requirement)
        assert call.kwargs["tag"].startswith("0x")
        assert call.kwargs["data"].startswith("0x")

        # Tag should decode to "IOT-INTEGRITY"
        tag_bytes = bytes.fromhex(call.kwargs["tag"][2:])
        assert tag_bytes.decode("utf-8") == "IOT-INTEGRITY"

        # Data should match the canonical encoded payload
        assert call.kwargs["data"] == dict_to_payload_hex(payload)


# ---------------------------------------------------------------------------
# fetch_block_data
# ---------------------------------------------------------------------------

class TestFetchBlockData:
    def test_returns_dict_from_block_payload(self, payload):
        # Build a fake block whose payload.data is the hex-encoded payload
        data_hex = dict_to_payload_hex(payload)
        fake_payload = MagicMock()
        fake_payload.data = data_hex
        fake_block = MagicMock()
        fake_block.payload = fake_payload

        mock_client = MagicMock()
        mock_client.get_block_data.return_value = fake_block

        result = fetch_block_data("block_abc", client=mock_client)
        assert result == payload

    def test_raises_when_block_fetch_fails(self):
        mock_client = MagicMock()
        mock_client.get_block_data.side_effect = ConnectionError("unreachable")
        with pytest.raises(TangleWriteError, match="Could not fetch"):
            fetch_block_data("block_abc", client=mock_client)

    def test_raises_when_payload_missing(self):
        fake_block = MagicMock(); fake_block.payload = None
        mock_client = MagicMock(); mock_client.get_block_data.return_value = fake_block
        with pytest.raises(TangleWriteError, match="no payload"):
            fetch_block_data("block_abc", client=mock_client)

    def test_handles_dict_style_block(self, payload):
        """Some SDK variants return a dict instead of an object."""
        data_hex = dict_to_payload_hex(payload)
        fake_block = {"payload": {"data": data_hex}}
        mock_client = MagicMock(); mock_client.get_block_data.return_value = fake_block
        assert fetch_block_data("block_abc", client=mock_client) == payload