"""Unit tests for the LocalRegistry."""
from __future__ import annotations
import json
import pytest

from src.processor.local_registry import LocalRegistry


@pytest.fixture
def registry(tmp_path):
    return LocalRegistry(tmp_path / "registry.json")


@pytest.fixture
def sample_entry():
    return {
        "block_id": None,
        "hash": "a" * 64,
        "timestamp": "2026-04-20T10:30:00Z",
        "raw_data": {"sensor_id": "s1", "timestamp": "t", "temperature": 1.0, "humidity": 2.0},
        "status": "pending",
    }


class TestLoadAndSave:
    def test_load_on_missing_file(self, registry):
        assert registry.all_entries() == []
        assert registry.count() == 0

    def test_save_creates_file(self, registry, sample_entry):
        registry.append(sample_entry)
        assert registry.path.exists()

    def test_save_creates_parent_dirs(self, tmp_path, sample_entry):
        nested = tmp_path / "a" / "b" / "registry.json"
        LocalRegistry(nested).append(sample_entry)
        assert nested.exists()

    def test_file_is_valid_json(self, registry, sample_entry):
        registry.append(sample_entry)
        assert isinstance(json.load(registry.path.open()), list)


class TestAppend:
    def test_persists_entry(self, registry, sample_entry):
        registry.append(sample_entry)
        assert registry.count() == 1
        assert registry.all_entries()[0] == sample_entry

    def test_multiple_appends_preserve_order(self, registry, sample_entry):
        for i in range(3):
            registry.append(dict(sample_entry, hash=str(i) * 64))
        assert [e["hash"] for e in registry.all_entries()] == ["0" * 64, "1" * 64, "2" * 64]

    def test_raises_on_missing_required_keys(self, registry):
        with pytest.raises(KeyError, match="missing required keys"):
            registry.append({"hash": "x" * 64})


class TestFindOperations:
    def test_find_by_hash(self, registry, sample_entry):
        registry.append(sample_entry)
        assert registry.find_by_hash(sample_entry["hash"]) == sample_entry

    def test_find_by_hash_returns_none_when_missing(self, registry, sample_entry):
        registry.append(sample_entry)
        assert registry.find_by_hash("nope") is None

    def test_find_by_block_id_skips_none(self, registry, sample_entry):
        registry.append(sample_entry)
        assert registry.find_by_block_id(None) is None

    def test_find_by_block_id_matches(self, registry, sample_entry):
        e = dict(sample_entry, block_id="block_xyz", status="registered")
        registry.append(e)
        assert registry.find_by_block_id("block_xyz")["block_id"] == "block_xyz"


class TestUpdateBlockId:
    def test_modifies_entry(self, registry, sample_entry):
        registry.append(sample_entry)
        assert registry.update_block_id(sample_entry["hash"], "block_abc") is True
        updated = registry.find_by_hash(sample_entry["hash"])
        assert updated["block_id"] == "block_abc"
        assert updated["status"] == "registered"

    def test_returns_false_when_not_found(self, registry):
        assert registry.update_block_id("ghost", "block_x") is False

    def test_supports_failed_status(self, registry, sample_entry):
        registry.append(sample_entry)
        registry.update_block_id(sample_entry["hash"], None, status="failed")
        assert registry.find_by_hash(sample_entry["hash"])["status"] == "failed"

    def test_targets_most_recent(self, registry, sample_entry):
        registry.append(sample_entry)
        registry.append(dict(sample_entry))
        registry.update_block_id(sample_entry["hash"], "block_late")
        entries = registry.all_entries()
        assert entries[0]["block_id"] is None
        assert entries[1]["block_id"] == "block_late"


class TestPersistenceAcrossInstances:
    def test_new_instance_sees_writes(self, tmp_path, sample_entry):
        path = tmp_path / "registry.json"
        LocalRegistry(path).append(sample_entry)
        assert LocalRegistry(path).count() == 1


class TestCorruption:
    def test_corrupted_file_raises_clear_error(self, tmp_path):
        path = tmp_path / "registry.json"
        path.write_text("{not valid")
        with pytest.raises(ValueError, match="corrupted"):
            LocalRegistry(path).all_entries()

    def test_non_array_file_raises_clear_error(self, tmp_path):
        path = tmp_path / "registry.json"
        path.write_text('{"a": 1}')
        with pytest.raises(ValueError, match="not a JSON array"):
            LocalRegistry(path).all_entries()


class TestAtomicity:
    def test_no_temp_files_left(self, registry, sample_entry):
        registry.append(sample_entry)
        registry.append(sample_entry)
        assert list(registry.path.parent.glob(".registry-*.tmp")) == []
