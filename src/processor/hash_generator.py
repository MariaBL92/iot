"""
Generación de hash SHA-256 con serialización JSON canónica.

CONTRATO CRÍTICO: todo diccionario que sea hasheado DEBE serializarse mediante
canonical_json para garantizar que payloads semánticamente equivalentes produzcan
hashes idénticos. Las llamadas directas a json.dumps están prohibidas en las zonas de hash.
"""
from __future__ import annotations

import hashlib
import json


def canonical_json(data: dict) -> str:
    ""Serializa un diccionario a JSON en forma canónica(sort_keys, compact).""
    return json.dumps(data, sort_keys=True, separators=(",", ":"))


def generate_hash(data: dict) -> str:
    ""Calcula el hash SHA-256 de un diccionario en forma canónica.""
    return hashlib.sha256(canonical_json(data).encode("utf-8")).hexdigest()
