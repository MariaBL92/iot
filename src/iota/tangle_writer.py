"""
Tangle writer: publica payloads en la Tangle de IOTA como Bloques de Datos Etiquetados (Tagged Data Blocks)
y retorna el block_id resultante.
Implementa reintentos con retroceso exponencial debido a que las publicaciones en Tangle fallan más
a menudo de lo que uno esperaría. El fallo después de todos los reintentos lanza TangleWriteError,
el cual los llamadores pueden capturar para marcar la entrada correspondiente del registro como
"failed" (fallida) sin hacer que el subscriber colapse.
"""
from __future__ import annotations

import logging
import time
from typing import Optional

from src.iota.iota_client import (
    dict_to_payload_hex,
    get_iota_client,
    get_tag_hex,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Constantes de configuración
# ---------------------------------------------------------------------------

RETRY_DELAYS_SECONDS = (1.0, 3.0, 9.0)  # eretroceso exponencial: 1 s, 3 s, 9 s
PUBLISH_TIMEOUT_SECONDS = 30.0          # informativo; el SDK tiene su propio tiempo de espera


class TangleWriteError(RuntimeError):
    """Se lanza cuando un payload no puede publicarse en el Tangle después de agotar todos los reintentos."""


# ---------------------------------------------------------------------------
#OPERACION PRINCIPAL
# ---------------------------------------------------------------------------

def register_in_tangle(payload: dict, client=None) -> str:
    """
    Publica un payload en la Tangle como un Bloque de Datos Etiquetado (Tagged Data Block).

Args: payload: Un diccionario con las claves {hash, sensor_id, timestamp}. El diccionario es
serializado a JSON canónico, codificado en hexadecimal y almacenado como el
campo de datos del Bloque. client:  Cliente de IOTA opcional a utilizar. Por defecto usa el singleton a nivel
de módulo; las pruebas pasan un mock aquí.

Returns:
El block_id de la Tangle (cadena hexadecimal) del bloque publicado.

Raises:
TangleWriteError: si se agotan todos los reintentos sin éxito.
    """
    if client is None:
        client = get_iota_client()

    tag_hex = get_tag_hex()
    data_hex = dict_to_payload_hex(payload)

    last_exception: Optional[Exception] = None
    for attempt, delay in enumerate(_attempt_delays(), start=1):
        try:
            logger.debug("Tangle write attempt %d", attempt)
            block_id = _do_post(client, tag_hex, data_hex)
            logger.info("Block accepted by Tangle (block_id=%s)", block_id)
            return block_id
        except Exception as exc:
            last_exception = exc
            logger.warning(
                "Tangle write attempt %d failed: %s. Retrying in %.1fs",
                attempt, exc, delay,
            )
            if delay > 0:
                time.sleep(delay)

    raise TangleWriteError(
        f"Failed to publish payload after {len(RETRY_DELAYS_SECONDS) + 1} "
        f"attempts: {last_exception}"
    ) from last_exception


def _attempt_delays():
    """Genera los tiempos de espera (delay) para la secuencia de intentos.

El primer intento no tiene espera previa (se devuelve como 0). Los
intentos posteriores utilizan los tiempos de reintento configurados.
    """
    yield 0.0
    for d in RETRY_DELAYS_SECONDS:
        yield d


def _do_post(client, tag_hex: str, data_hex: str) -> str:
    """Ejecuta una única publicación en el Tangle y devuelve el block_id resultante.

Se encuentra aislada como una función independiente para que las pruebas puedan simular la llamada 
de red mediante mocks, sin necesidad de modificar(monkey-patching) los componentes internos de iota-sdk.
    """
    # iota-sdk 1.1.3 devuelve (block_id, block) para build_and_post_block.
    # El bloque puede contener un payload tagged_data dependiendo de los datos de entrada.
    result = client.build_and_post_block(tag=tag_hex, data=data_hex)

    # Análisis defensivo: manejar tanto valores de retorno tipo tupla como valores de retorno similares a diccionarios.
    if isinstance(result, (tuple, list)) and len(result) >= 1:
        block_id = result[0]
    elif isinstance(result, str):
        block_id = result
    else:
        block_id = getattr(result, "block_id", None) or getattr(result, "id", None)
    if not block_id:
        raise RuntimeError(f"Unexpected return from build_and_post_block: {result!r}")

    return str(block_id)


# ---------------------------------------------------------------------------
#Opcional: recuperar un bloque publicado previamente (utilizado por el verificador).
# ---------------------------------------------------------------------------

def fetch_block_data(block_id: str, client=None) -> dict:
    """
    Recupera un bloque del Tangle y devuelve su payload como un diccionario.
Args:
    block_id: El block_id devuelto por register_in_tangle().
    client:   Cliente IOTA opcional (por defecto se utiliza la instancia singleton).

Returns:
    El diccionario que fue registrado originalmente
    ({hash, sensor_id, timestamp}).

Raises:
    TangleWriteError: Si el bloque no puede recuperarse o si su payload
                      no puede decodificarse como el JSON esperado.
    """
    if client is None:
        client = get_iota_client()

    from src.iota.iota_client import payload_hex_to_dict

    try:
        block = client.get_block_data(block_id)
    except Exception as exc:
        raise TangleWriteError(f"Could not fetch block {block_id}: {exc}") from exc

    # Extract the data hex from the block. iota-sdk Block objects can expose
    # the payload as either an attribute or as a dict-like; cover both.
    data_hex = _extract_payload_data(block)
    try:
        return payload_hex_to_dict(data_hex)
    except Exception as exc:
        raise TangleWriteError(
            f"Could not decode payload of block {block_id}: {exc}"
        ) from exc


def _extract_payload_data(block) -> str:
    """Extrae, en la medida de lo posible (best-effort), los datos del payload codificados en hexadecimal desde un bloque."""
    # Attribute style: block.payload.data
    payload = getattr(block, "payload", None) or (
        block.get("payload") if isinstance(block, dict) else None
    )
    if payload is None:
        raise TangleWriteError("Block has no payload")
    data = getattr(payload, "data", None)
    if data is None and isinstance(payload, dict):
        data = payload.get("data")
    if data is None:
        raise TangleWriteError("Block payload has no data field")
    return data
