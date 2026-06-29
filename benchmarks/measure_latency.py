"""
Análisis de latencia: mide T_reg (latencia de registro en el Tangle) y T_ver (latencia de verificación de integridad) durante N iteraciones.

En cada iteración se realizan las siguientes acciones:

Se genera una lectura sintética de un sensor.
Se construye la carga útil (payload) que se registrará en el Tangle, compuesta por el hash y los metadatos.
Se mide el tiempo de ejecución de la función register_in_tangle(), obteniendo la latencia de registro (T_reg).
Se mide el tiempo de ejecución de la función verify_integrity(), obteniendo la latencia de verificación (T_ver).
Se añade una nueva fila al archivo CSV con los resultados de la iteración.

El archivo CSV generado (por defecto: docs/results/latencies.csv) contiene las siguientes columnas:

iteration: número de iteración.
sensor_id: identificador del sensor.
T_reg_ms: latencia de registro en el Tangle, expresada en milisegundos.
T_ver_ms: latencia de verificación de integridad, expresada en milisegundos.
status: resultado de la verificación (por ejemplo, íntegro o alterado).
block_id: identificador del bloque o transacción registrado en el Tangle.

Ejemplos de uso:

python -m benchmarks.measure_latency --n 100
python -m benchmarks.measure_latency --n 50 --output /tmp/latencies.csv
"""
from __future__ import annotations

import argparse
import csv
import logging
import os
import sys
import time
from pathlib import Path

from dotenv import load_dotenv

from src.processor.hash_generator import generate_hash
from src.processor.payload_builder import build_tangle_payload
from src.simulator.sensor_simulator import generate_sensor_data

load_dotenv()
logger = logging.getLogger(__name__)


def measure_one(iteration: int, sensor_id: str) -> dict:
    """Ejecuta un ciclo completo de registro y verificación, generando una fila con los resultados de las mediciones."""
    # Lazy imports so that running --help doesn't pull in iota-sdk.
    from src.iota.tangle_writer import (
        TangleWriteError,
        fetch_block_data,
        register_in_tangle,
    )
    from src.verifier.integrity_checker import verify_integrity

    sensor_data = generate_sensor_data(sensor_id)
    payload = build_tangle_payload(sensor_data)

   # T_reg: tiempo transcurrido desde la llamada a register_in_tangle hasta que se devuelve el block_id.
    t0 = time.perf_counter()
    try:
        block_id = register_in_tangle(payload)
        t1 = time.perf_counter()
        t_reg_ms = (t1 - t0) * 1000.0
    except TangleWriteError as exc:
        logger.error("Iteration %d: Tangle write failed: %s", iteration, exc)
        return {
            "iteration": iteration,
            "sensor_id":  sensor_id,
            "T_reg_ms":   "",
            "T_ver_ms":   "",
            "status":     "REGISTER_FAILED",
            "block_id":   "",
        }

    # T_ver: tiempo transcurrido desde la llamada a verify_integrity hasta la obtención del veredicto.
    t2 = time.perf_counter()
    try:
        verdict = verify_integrity(block_id, sensor_data, fetch_fn=fetch_block_data)
        t3 = time.perf_counter()
        t_ver_ms = (t3 - t2) * 1000.0
        status = verdict["status"]
    except Exception as exc:
        logger.error("Iteration %d: verify failed: %s", iteration, exc)
        return {
            "iteration": iteration,
            "sensor_id":  sensor_id,
            "T_reg_ms":   f"{t_reg_ms:.2f}",
            "T_ver_ms":   "",
            "status":     "VERIFY_FAILED",
            "block_id":   block_id,
        }

    return {
        "iteration": iteration,
        "sensor_id":  sensor_id,
        "T_reg_ms":   f"{t_reg_ms:.2f}",
        "T_ver_ms":   f"{t_ver_ms:.2f}",
        "status":     status,
        "block_id":   block_id,
    }


def run(n: int, output: Path, sensor_id: str = "bench_sensor") -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = ["iteration", "sensor_id", "T_reg_ms", "T_ver_ms",
                  "status", "block_id"]

    with output.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for i in range(1, n + 1):
            row = measure_one(i, sensor_id)
            writer.writerow(row)
            f.flush()  # Keep CSV in sync even if interrupted
            logger.info(
                "Iter %d/%d: T_reg=%s ms, T_ver=%s ms, status=%s",
                i, n, row["T_reg_ms"], row["T_ver_ms"], row["status"],
            )

    logger.info("Done. Wrote %d rows to %s", n, output)


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Mide la latencia de registro en el Tangle y la latencia de verificación de la integridad durante N iteraciones.",
    )
    parser.add_argument("--n", type=int, default=100,
                        help="Number of iterations (default: 100)")
    parser.add_argument("--output", type=Path,
                        default=Path("docs/results/latencies.csv"),
                        help="Output CSV path (default: docs/results/latencies.csv)")
    parser.add_argument("--sensor-id", default="bench_sensor",
                        help="sensor_id to use in synthetic readings.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    args = _parse_args(argv)
    run(args.n, args.output, args.sensor_id)
    return 0


if __name__ == "__main__":
    sys.exit(main())
