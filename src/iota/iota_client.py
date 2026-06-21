"""
Wraooer ligero sobre iota-sdk para centralizar la configuración del nodo, funciones auxiliares
de codificación, y las importaciones perezosas (lazy imports), de modo que las pruebas unitarias
puedan ejecutarsesin tener el SDK instalado.

El paquete Python iota-sdk compila bindings nativos de Rust al hacer pip install,
lo cual es una dependencia pesada. Al importarlo de forma perezosa dentro de las funciones,
mantenemos el resto del código importable en entornos donde iota-sdk
no está disponible (por ejemplo, contenedores de CI, laptops de colaboradores sin Rust)
"""
from __future__ import annotations

import json
import logging
import os
from typing import Optional

from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)


# Module-level singleton: created on first use and reused thereafter.
_client = None


def _build_client():
    """Lazy import + construct the iota-sdk Client.

    Raises ImportError with a helpful message if iota-sdk is not installed.
    """
    try:
        from iota_sdk import Client
    except ImportError as exc:
        raise ImportError(
            "iota-sdk is not installed. Run `pip install iota-sdk==1.1.3` "
            "(requires Rust to be present on the system to compile bindings)."
        ) from exc

    node_url = os.getenv("IOTA_NODE_URL", "https://api.testnet.iota.cafe")
    logger.info("Initializing IOTA client (node: %s)", node_url)
    return Client(nodes=[node_url])


def get_iota_client():
    """Return the module-level IOTA client, building it once on first call."""
    global _client
    if _client is None:
        _client = _build_client()
    return _client


def reset_client() -> None:
    """Reset the singleton. Used by tests that swap implementations in/out."""
    global _client
    _client = None


# ---------------------------------------------------------------------------
# Encoding helpers
# ---------------------------------------------------------------------------

def utf8_to_hex(s: str) -> str:
    """Encode a UTF-8 string to a '0x'-prefixed hex string.

    iota-sdk 1.1.3 requires hex strings for tag and data to carry the
    canonical '0x' prefix; passing bare hex raises
    'Invalid hex prefix: expected `0x`'.
    """
    return "0x" + s.encode("utf-8").hex()


def hex_to_utf8(h: str) -> str:
    """Decode a hex string back to UTF-8 text."""
    # iota-sdk sometimes returns '0x'-prefixed hex; strip it if present.
    if h.startswith("0x"):
        h = h[2:]
    return bytes.fromhex(h).decode("utf-8")


def dict_to_payload_hex(payload: dict) -> str:
    """Serialize a dict to canonical JSON, then to hex for Tangle storage."""
    return utf8_to_hex(json.dumps(payload, separators=(",", ":")))


def payload_hex_to_dict(payload_hex: str) -> dict:
    """Inverse of dict_to_payload_hex: hex -> UTF-8 JSON -> dict."""
    return json.loads(hex_to_utf8(payload_hex))


# ---------------------------------------------------------------------------
# Tag (constant per project; cached at module import)
# ---------------------------------------------------------------------------

def get_tag() -> str:
    """Return the IOTA tag in UTF-8 form (from env or default)."""
    return os.getenv("IOTA_TAG", "IOT-INTEGRITY")


def get_tag_hex() -> str:
    """Return the IOTA tag hex-encoded for the SDK."""
    return utf8_to_hex(get_tag())
