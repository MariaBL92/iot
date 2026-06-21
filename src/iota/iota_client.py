"""
Wrapper ligero sobre iota-sdk para centralizar la configuración del nodo, las funciones auxiliares 
de codificación y las importaciones perezosas (lazy imports), de modo que las pruebas unitarias 
puedan ejecutarse sin tener el SDK instalado.

El paquete Python iota-sdk compila bindings nativos de Rust durante la instalación con pip, 
lo cual lo convierte en una dependencia pesada. Al importarlo de forma perezosa dentro de las 
funciones, se mantiene el resto del código importable en entornos donde iota-sdk no está disponible, 
por ejemplo, contenedores de CI o laptops de colaboradores sin Rust.
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

        Lanza una excepción ImportError con un mensaje informativo si iota-sdkno está instalado.   
    """
    try:
        from iota_sdk import Client
    except ImportError as exc:
        raise ImportError(
            "iota-sdk no está instalado. Ejecute `pip install iota-sdk==1.1.3` "
            "(requiere que Rust esté instalado en el sistema para compilar los bindings)."
        ) from exc

    node_url = os.getenv("IOTA_NODE_URL", "https://api.testnet.iota.cafe")
    logger.info("Initializing IOTA client (node: %s)", node_url)
    return Client(nodes=[node_url])


def get_iota_client():
    """Devuelve el cliente IOTA a nivel de módulo, creándolo una única vez durante la primera llamada."""
    global _client
    if _client is None:
        _client = _build_client()
    return _client


def reset_client() -> None:
    """Reinicia la instancia única (singleton). Se utiliza en pruebas que sustituyen dinámicamente distintas implementaciones."""
    global _client
    _client = None


# ---------------------------------------------------------------------------
# Encoding helpers
# ---------------------------------------------------------------------------

def utf8_to_hex(s: str) -> str:
    """Codifica una cadena UTF-8 como una cadena hexadecimal con prefijo '0x'.

iota-sdk 1.1.3 requiere cadenas hexadecimales para tag y data con el
prefijo canónico '0x'; pasar hexadecimal sin prefijo lanza el error
'Invalid hex prefix: expected `0x`'.
    """
    return "0x" + s.encode("utf-8").hex()


def hex_to_utf8(h: str) -> str:
    """Decodifica una cadena hexadecimal y la convierte nuevamente a texto UTF-8."""
    # iota-sdk a veces devuelve cadenas hexadecimales con el prefijo '0x'; elimínelo si está presente.
    if h.startswith("0x"):
        h = h[2:]
    return bytes.fromhex(h).decode("utf-8")


def dict_to_payload_hex(payload: dict) -> str:
    """Serializa un diccionario a JSON canónico y luego a hexadecimal para su almacenamiento en el Tangle."""
    return utf8_to_hex(json.dumps(payload, separators=(",", ":")))


def payload_hex_to_dict(payload_hex: str) -> dict:
    """Operación inversa de dict_to_payload_hex: hexadecimal -> JSON UTF-8 -> diccionario."""
    return json.loads(hex_to_utf8(payload_hex))


# ---------------------------------------------------------------------------
# Tag  (constante para todo el proyecto; almacenada en caché al importar el módulo).
# ---------------------------------------------------------------------------

def get_tag() -> str:
    """Devuelve la etiqueta (tag) de IOTA en formato UTF-8 (obtenida desde una variable de entorno o usando el valor predeterminado).."""
    return os.getenv("IOTA_TAG", "IOT-INTEGRITY")


def get_tag_hex() -> str:
    """Devuelve la etiqueta (tag) de IOTA codificada en hexadecimal para su uso con el SDK."""
    return utf8_to_hex(get_tag())
