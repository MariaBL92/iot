"""
Verificación de integridad: dado un block_id y un diccionario de datos
candidato, determina si los datos permanecen íntegros.

El verificador cierra el ciclo de la arquitectura: recupera el bloque desde el Tangle, 
extrae el hash que fue almacenado durante el registro, recalcula el hash de los datos 
candidatos utilizando exactamente el mismo proceso de JSON canónico + SHA-256 empleado 
por el procesador en la Capa 2 y compara ambos valores.

La salida es un diccionario estructurado que contiene ambos hashes junto
con un veredicto, de modo que el llamador pueda registrar, mostrar o
almacenar la evidencia con fines de auditoría.
"""
from __future__ import annotations

import logging
from typing import Optional

from src.processor.hash_generator import generate_hash

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
#  Constantes utilizadas para el veredicto de integridad
# ---------------------------------------------------------------------------

INTEGRO = "INTEGRO"
ALTERADO = "ALTERADO"
NO_ENCONTRADO = "ERROR_CONTROLADO"
ERROR = "ERROR"


class VerificationError(RuntimeError):
    """Se lanza cuando la verificación no puede llevarse a cabo (por ejemplo, si falla la recuperación 
    del bloque, el payload está mal formado, etc.). Se diferencia del veredicto ALTERADO, que indica que la 
    verificación se completó correctamente y detectó una discrepancia."""


# ---------------------------------------------------------------------------
# Core verification
# ---------------------------------------------------------------------------

def verify_integrity(
    block_id: str,
    data: dict,
    fetch_fn=None,
) -> dict:
    """
   Verifica si `data` coincide con el hash almacenado en `block_id` dentro del Tangle.

Args:
    block_id: El block_id del Tangle donde se registró el hash.
    data: Los datos candidatos a verificar. El hash se recalcula sobre este 
        diccionario exacto y se compara con el valor almacenado en la cadena.
    fetch_fn: Función opcional callable(block_id) -> dict que devuelve
              el payload originalmente registrado. Si es None, se utiliza
              fetch_block_data() de tangle_writer contra la red real.

Returns:
    Un diccionario con las siguientes claves:
        status (str):      "INTEGRO" o "ALTERADO"
        stored (str):      hash recuperado del Tangle
        computed (str):    hash recalculado a partir de `data`
        match (bool):      True si y solo si status == "INTEGRO"
        block_id (str):    block_id devuelto para trazabilidad
        sensor_id (str):   recuperado del payload almacenado en el Tangle
        timestamp (str):   recuperado del payload almacenado en el Tangle

Raises:
    VerificationError: Si el bloque no puede recuperarse o si su payload
                       está mal formado. Nótese que un veredicto
                       ALTERADO NO es un error; representa una detección
                       exitosa de una discrepancia.
    """
    if fetch_fn is None:
        from src.iota.tangle_writer import fetch_block_data
        fetch_fn = fetch_block_data

    try:
        tangle_payload = fetch_fn(block_id)
    except Exception as exc:
        raise VerificationError(
            f"Could not fetch block {block_id} from the Tangle: {exc}"
        ) from exc

    # Análisis defensivo del payload recuperado.
    if not isinstance(tangle_payload, dict):
        raise VerificationError(
            f"Tangle payload is not a dict (got {type(tangle_payload).__name__})"
        )
    stored_hash = tangle_payload.get("hash")
    if not stored_hash:
        raise VerificationError(
            f"Tangle payload of block {block_id} has no 'hash' field"
        )

    # Recalcular el hash de los datos candidatos. Este es el mismo proceso
    # utilizado por el procesador en la Capa 2; la consistencia está garantizada
    # porque ambos componentes utilizan generate_hash() de hash_generator.py.
    computed_hash = generate_hash(data)

    match = (stored_hash == computed_hash)
    verdict = {
        "status":    INTEGRO if match else ALTERADO,
        "stored":    stored_hash,
        "computed":  computed_hash,
        "match":     match,
        "block_id":  block_id,
        "sensor_id": tangle_payload.get("sensor_id"),
        "timestamp": tangle_payload.get("timestamp"),
    }
    logger.info(
        "Verification of block %s: %s (sensor=%s)",
        block_id, verdict["status"], verdict["sensor_id"],
    )
    return verdict


# ---------------------------------------------------------------------------
#Función auxiliar: verifica utilizando el registro local.
# ---------------------------------------------------------------------------

def verify_from_registry(
    block_id: str,
    registry,
    fetch_fn=None,
) -> dict:
    """
   Recupera los datos originales (raw_data) desde el registro local a partir del block_id y, posteriormente, 
   verifica su integridad contra el Tangle. Resulta útil para auditorías rutinarias de integridad.

Args:
    block_id: El block_id del Tangle que se desea verificar.
    registry: Una instancia de LocalRegistry.
    fetch_fn: Función opcional, igual que en verify_integrity().

Returns:
    El mismo diccionario de veredicto que devuelve verify_integrity(), o un diccionario con 
    status=NO_ENCONTRADO si el block_id no existe en el registro local.
    """
    entry = registry.find_by_block_id(block_id)
    if entry is None:
        return {
            "status": NO_ENCONTRADO,
            "block_id": block_id,
            "match": False,
            "message": f"block_id {block_id} not present in local registry",
        }
    return verify_integrity(block_id, entry["raw_data"], fetch_fn=fetch_fn)
