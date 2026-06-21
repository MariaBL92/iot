"""
Suscriptor MQTT que ingesta lecturas de sensores, calcula sus hashes,
las publica en el Tangle de IOTA y las persiste localmente.

Flujo por mensaje:
    1. Analizar el JSON recibido desde el payload MQTT.
    2. Calcular el hash SHA-256 de los datos del sensor.
    3. Construir el payload para el Tangle {hash, sensor_id, timestamp}.
    4. Añadir una entrada con status="pending" al registro local.
    5. Intentar publicar en el Tangle (con reintentos dentro de register_in_tangle).
    6a. Si tiene éxito: actualizar la entrada con block_id y status="registered".
    6b. Si falla: actualizar la entrada con status="failed" (block_id permanece en None).

La publicación en el Tangle puede desactivarse en tiempo de ejecución mediante
la bandera --no-tangle, lo cual es útil para pruebas únicamente locales sin
conectividad de red, por ejemplo durante el desarrollo de las Capas 1 y 2.
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from typing import Callable, Optional

import paho.mqtt.client as mqtt
from dotenv import load_dotenv

from src.processor.hash_generator import generate_hash
from src.processor.local_registry import LocalRegistry
from src.processor.payload_builder import build_tangle_payload

load_dotenv()
logger = logging.getLogger(__name__)


# Alias de tipo para el gancho de escritura en el Tangle (permite que las pruebas inyecten una implementación simulada o mock).
# Firma: callable(payload: dict) -> str(devuelve un block_id o lanza una excepción en caso de error).
TangleWriteFn = Callable[[dict], str]


# ---------------------------------------------------------------------------
#Procesamiento de mensajes casi puro (se puede probar sin MQTT y sin Tangle).
# ---------------------------------------------------------------------------

def process_message(
    payload_bytes: bytes,
    registry: LocalRegistry,
    tangle_write_fn: Optional[TangleWriteFn] = None,
) -> dict:
    """
    Procesa un único payload MQTT y persiste la entrada resultante.

Args:
    payload_bytes: Cuerpo bruto del mensaje MQTT JSON codificado en UTF-8.
    registry: Registro local donde se añadirá la nueva entrada.
    tangle_write_fn: Función opcional que publica en el Tangle y devuelve
        el block_id. Si es None, la entrada permanece en estado "pending".

Returns:
    La entrada tal como quedó almacenada en el registro, con el estado
    actualizado según el resultado de la escritura en el Tangle.
    """
    sensor_data = json.loads(payload_bytes.decode("utf-8"))
    sensor_hash = generate_hash(sensor_data)
    tangle_payload = build_tangle_payload(sensor_data)

    entry = {
        "block_id": None,
        "hash": sensor_hash,
        "timestamp": sensor_data["timestamp"],
        "raw_data": sensor_data,
        "tangle_payload": tangle_payload,
        "status": "pending",
    }
    registry.append(entry)

    if tangle_write_fn is None:
        return entry

    # Attempt to register the hash in the Tangle.
    try:
        block_id = tangle_write_fn(tangle_payload)
        registry.update_block_id(sensor_hash, block_id, status="registered")
        entry["block_id"] = block_id
        entry["status"] = "registered"
        logger.info(
            "Registered in Tangle: sensor=%s hash=%s... block_id=%s",
            sensor_data["sensor_id"], sensor_hash[:16], block_id,
        )
    except Exception as exc:
        registry.update_block_id(sensor_hash, None, status="failed")
        entry["status"] = "failed"
        logger.error(
            "Tangle registration failed for hash=%s...: %s",
            sensor_hash[:16], exc,
        )

    return entry


# ---------------------------------------------------------------------------
# MQTT callbacks
# ---------------------------------------------------------------------------

def _on_connect(client, userdata, flags, reason_code, properties=None):
    if reason_code == 0:
        client.subscribe(userdata["topic"], qos=1)
        logger.info("Connected and subscribed to %s", userdata["topic"])
    else:
        logger.error("Failed to connect to MQTT broker (reason: %s)", reason_code)


def _on_disconnect(client, userdata, flags, reason_code, properties=None):
    if reason_code != 0:
        logger.warning("Unexpected disconnection (reason: %s)", reason_code)


def _on_message(client, userdata, msg):
    registry: LocalRegistry = userdata["registry"]
    tangle_fn: Optional[TangleWriteFn] = userdata.get("tangle_write_fn")
    try:
        entry = process_message(msg.payload, registry, tangle_fn)
        logger.debug("Processed: hash=%s... status=%s",
                     entry["hash"][:16], entry["status"])
    except json.JSONDecodeError:
        logger.exception("Received invalid JSON on topic %s", msg.topic)
    except KeyError as exc:
        logger.error("Payload missing required field: %s", exc)
    except Exception:
        logger.exception("Unexpected error while processing message")


# ---------------------------------------------------------------------------
# Ciclo de vida del Subscriber 
# ---------------------------------------------------------------------------

def run_subscriber(
    broker_host: str, broker_port: int, topic: str,
    registry_path: str, tangle_enabled: bool = True,
) -> None:
    """Connect to the broker and block while processing incoming messages."""
    registry = LocalRegistry(registry_path)

    tangle_fn: Optional[TangleWriteFn] = None
    if tangle_enabled:
        # Lazy import evita que iota-sdk forme parte de las dependencias obligatorias para los usuarios que únicamente
        # desean ejecutar las Capas 1 y 2.
        from src.iota.tangle_writer import register_in_tangle
        tangle_fn = register_in_tangle
        logger.info("Tangle registration ENABLED")
    else:
        logger.warning("Tangle registration DISABLED (--no-tangle). "
                       "Entries will stay in 'pending' state.")

    userdata = {
        "registry": registry,
        "topic": topic,
        "tangle_write_fn": tangle_fn,
    }
    client = mqtt.Client(
        callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
        userdata=userdata,
    )
    client.on_connect = _on_connect
    client.on_disconnect = _on_disconnect
    client.on_message = _on_message
    client.connect(broker_host, broker_port, keepalive=60)
    logger.info(
        "Subscriber started: broker=%s:%d, topic=%s, registry=%s",
        broker_host, broker_port, topic, registry_path,
    )
    try:
        client.loop_forever()
    except KeyboardInterrupt:
        logger.info("Subscriber stopped by user (Ctrl+C)")
    finally:
        client.disconnect()


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="MQTT subscriber that hashes sensor data, persists it "
                    "locally, and registers it in the IOTA Tangle.",
    )
    parser.add_argument("--registry-path", default=None)
    parser.add_argument(
        "--no-tangle", action="store_true",
        help="Disable Tangle registration; entries stay pending. "
             "Useful for development without IOTA connectivity.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    args = _parse_args(argv)
    broker_host = os.getenv("MQTT_BROKER", "localhost")
    broker_port = int(os.getenv("MQTT_PORT", "1883"))
    topic = os.getenv("MQTT_TOPIC", "iot/sensors")
    registry_path = args.registry_path or os.getenv(
        "LOCAL_REGISTRY_PATH", "data/local_registry.json"
    )
    run_subscriber(broker_host, broker_port, topic, registry_path,
                   tangle_enabled=not args.no_tangle)
    return 0


if __name__ == "__main__":
    sys.exit(main())
