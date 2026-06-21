"""
Constructor de payload para el Tangle.  
Materializa el límite de privacidad: únicamente {hash, sensor_id, timestamp} salen del entorno local.  
Los valores crudos de los sensores permanecen en el registro local..
"""
from __future__ import annotations

from src.processor.hash_generator import generate_hash


def build_tangle_payload(sensor_data: dict) -> dict:
    """Construye el diccionario que será registrado en el Tangle.

    Args:
        sensor_data: Debe contener 'sensor_id' y 'timestamp'.

    Returns:
        Un diccionario con las claves 'hash', 'sensor_id', 'timestamp'.

    Raises:
        KeyError: si faltan 'sensor_id' o 'timestamp'.
    """
    if "sensor_id" not in sensor_data:
        raise KeyError("sensor_data must contain 'sensor_id'")
    if "timestamp" not in sensor_data:
        raise KeyError("sensor_data must contain 'timestamp'")
    return {
        "hash": generate_hash(sensor_data),
        "sensor_id": sensor_data["sensor_id"],
        "timestamp": sensor_data["timestamp"],
    }
