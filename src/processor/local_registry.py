"""
Registro local: almacenamiento persistente de lecturas de sensores y sus hashes.

Formato del archivo: un arreglo JSON de entradas. Cada entrada tiene la forma
    {
        "block_id":       Optional[str],
        "hash":           str,
        "timestamp":      str,
        "raw_data":       dict,
        "tangle_payload": dict,
        "status":         "pending" | "registered" | "failed"
    }

El suscriptor es el único escritor, por lo que las escrituras atómicas simples 
(temp file + os.replace) son suficientes sin bloqueo de archivo.
"""
from __future__ import annotations

import json
import logging
import os
import tempfile
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


class LocalRegistry:
    def __init__(self, path: str | Path):
        self.path = Path(path)

    def _load(self) -> list[dict]:
        if not self.path.exists():
            return []
        try:
            with self.path.open("r", encoding="utf-8") as f:
                data = json.load(f)
            if not isinstance(data, list):
                raise ValueError(f"Registry file {self.path} is not a JSON array")
            return data
        except json.JSONDecodeError as exc:
            raise ValueError(f"Registry file {self.path} is corrupted: {exc}") from exc

    def _save(self, entries: list[dict]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp_fd, tmp_path = tempfile.mkstemp(
            prefix=".registry-", suffix=".tmp", dir=self.path.parent
        )
        try:
            with os.fdopen(tmp_fd, "w", encoding="utf-8") as f:
                json.dump(entries, f, indent=2, ensure_ascii=False)
            os.replace(tmp_path, self.path)
        except Exception:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)
            raise

    def append(self, entry: dict) -> None:
        required = {"hash", "timestamp", "raw_data", "status"}
        missing = required - set(entry.keys())
        if missing:
            raise KeyError(f"Entry is missing required keys: {missing}")
        entries = self._load()
        entries.append(entry)
        self._save(entries)
        logger.debug("Appended entry with hash=%s", entry["hash"][:16])

    def all_entries(self) -> list[dict]:
        return self._load()

    def find_by_hash(self, hash_value: str) -> Optional[dict]:
        for entry in self._load():
            if entry.get("hash") == hash_value:
                return entry
        return None

    def find_by_block_id(self, block_id: str) -> Optional[dict]:
        if block_id is None:
            return None
        for entry in self._load():
            if entry.get("block_id") == block_id:
                return entry
        return None

    def update_block_id(self, hash_value: str, block_id: Optional[str],
                        status: str = "registered") -> bool:
        """Actualiza el block_id y el estado de la entrada coincidente más reciente.."""
        entries = self._load()
        for entry in reversed(entries):
            if entry.get("hash") == hash_value:
                entry["block_id"] = block_id
                entry["status"] = status
                self._save(entries)
                return True
        return False

    def count(self) -> int:
        return len(self._load())
