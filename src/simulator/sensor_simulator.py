"""
Simulador de sensores para el proyecto de verificación de integridad en IoT.

Este módulo genera lecturas sintéticas de temperatura y humedad y las publica
en un broker MQTT para su posterior procesamiento. Representa la Capa 1 de la
arquitectura propuesta de cuatro capas, correspondiente a la fuente simulada
de datos IoT.
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import random
import sys
import time
from datetime import datetime, timezone

import paho.mqtt.client as mqtt
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)

TEMP_MIN = 15.0
TEMP_MAX = 35.0
HUMIDITY_MIN = 30.0
HUMIDITY_MAX = 80.0


def generate_sensor_data(sensor_id: str) -> dict:
    """Genera una lectura sintética de sensor con un identificador de sensor,una marca temporal UTC 
    en formato ISO 8601  y valores de temperatura y humedad redondeados a un decimal."""
    return {
        "sensor_id": sensor_id,
        "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "temperature": round(random.uniform(TEMP_MIN, TEMP_MAX), 1),
        "humidity": round(random.uniform(HUMIDITY_MIN, HUMIDITY_MAX), 1),
    }


def _on_connect(client, userdata, flags, reason_code, properties=None):
    if reason_code == 0:
        logger.info("Connected to MQTT broker")
    else:
        logger.error("Failed to connect to MQTT broker (reason: %s)", reason_code)


def _on_disconnect(client, userdata, flags, reason_code, properties=None):
    if reason_code != 0:
        logger.warning("Unexpected disconnection (reason: %s)", reason_code)
    else:
        logger.info("Disconnected from MQTT broker")


def _build_client() -> mqtt.Client:
    client = mqtt.Client(callback_api_version=mqtt.CallbackAPIVersion.VERSION2)
    client.on_connect = _on_connect
    client.on_disconnect = _on_disconnect
    return client


def publish_loop(
    sensor_id: str, interval_seconds: float,
    broker_host: str, broker_port: int, topic: str,
    max_messages: int | None = None,
) -> int:
    """Publica continuamente datos sintéticos de sensores en el broker MQTT."""
    client = _build_client()
    client.connect(broker_host, broker_port, keepalive=60)
    client.loop_start()
    sent = 0
    try:
        while max_messages is None or sent < max_messages:
            data = generate_sensor_data(sensor_id)
            payload = json.dumps(data)
            result = client.publish(topic, payload, qos=1)
            result.wait_for_publish(timeout=5)
            if result.rc == mqtt.MQTT_ERR_SUCCESS:
                logger.info("Published: %s", payload)
                sent += 1
            else:
                logger.error("Publish failed (rc: %s)", result.rc)
            time.sleep(interval_seconds)
    except KeyboardInterrupt:
        logger.info("Simulator stopped by user (Ctrl+C)")
    finally:
        client.loop_stop()
        client.disconnect()
    logger.info("Simulator exited after publishing %d message(s)", sent)
    return sent


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="IoT sensor simulator that publishes synthetic data over MQTT."
    )
    parser.add_argument("--sensor-id", default="sensor_01")
    parser.add_argument("--interval", type=float, default=2.0)
    parser.add_argument("--max-messages", type=int, default=None)
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
    logger.info(
        "Iniciando simulador:  sensor_id=%s, interval=%.1fs, broker=%s:%d, topic=%s",
        args.sensor_id, args.interval, broker_host, broker_port, topic,
    )
    publish_loop(args.sensor_id, args.interval, broker_host, broker_port,
                 topic, args.max_messages)
    return 0


if __name__ == "__main__":
    sys.exit(main())
