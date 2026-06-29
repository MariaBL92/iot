"""
Escenarios de validación funcional E1–E6, repetidos N veces cada uno para obtener significancia estadística.
Cada repetición registra una lectura sintética NUEVA de sensor en el Tangle y luego la verifica bajo cada uno de los 6 tipos de mutación (E1–E6), 
con el fin de evaluar la capacidad de detección del sistema. La salida es un archivo CSV con una fila por cada par (repetición, escenario), 
indicando si el veredicto obtenido coincidió con el veredicto esperado.

Escenarios:
E1 - Íntegro:                 datos sin modificar, se espera INTEGRO
E2 - Alteración numérica:     temperatura modificada, se espera ALTERADO
E3 - Alteración timestamp:    timestamp modificado, se espera ALTERADO
E4 - Alteración sensor_id:    sensor_id modificado, se espera ALTERADO
E5 - Bloque inexistente:      verificación contra un block_id inválido
E6 - Manipulación de campo:   humedad modificada, se espera ALTERADO

Uso:
python -m benchmarks.run_scenarios --n 100
python -m benchmarks.run_scenarios --n 50 --output docs/results/scenarios_n50.csv
El CSV, por defecto en docs/results/scenarios.csv, contiene las columnas:
repetition, scenario_id, description, expected, actual, passed, block_id
"""
from __future__ import annotations

import argparse
import copy
import csv
import logging
import sys
from pathlib import Path

from dotenv import load_dotenv

from src.processor.payload_builder import build_tangle_payload
from src.simulator.sensor_simulator import generate_sensor_data

load_dotenv()
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Definición de los escenarios (mutaciones)
# ---------------------------------------------------------------------------

def _mutations() -> list[dict]:
    """Devuelve las especificaciones de las seis mutaciones, independientes de cualquier lectura base."""
    return [
        {
            "id": "E1",
            "description": "Dato íntegro (sin modificación)",
            "data_mutation": lambda d: d,
            "expected": "INTEGRO",
            "use_invalid_block_id": False,
        },
        {
            "id": "E2",
            "description": "Alteración del valor de temperatura",
            "data_mutation": lambda d: {**d, "temperature": d["temperature"] + 1.0},
            "expected": "ALTERADO",
            "use_invalid_block_id": False,
        },
        {
            "id": "E3",
            "description": "Alteración del timestamp",
            "data_mutation": lambda d: {**d, "timestamp": "2099-01-01T00:00:00Z"},
            "expected": "ALTERADO",
            "use_invalid_block_id": False,
        },
        {
            "id": "E4",
            "description": "Alteración del sensor_id",
            "data_mutation": lambda d: {**d, "sensor_id": d["sensor_id"] + "_FAKE"},
            "expected": "ALTERADO",
            "use_invalid_block_id": False,
        },
        {
            "id": "E5",
            "description": "Bloque inexistente (block_id inválido)",
            "data_mutation": lambda d: d,
            "expected": "ERROR_HANDLED",
            "use_invalid_block_id": True,
        },
        {
            "id": "E6",
            "description": "Alteración del valor de humedad",
            "data_mutation": lambda d: {**d, "humidity": d["humidity"] + 5.0},
            "expected": "ALTERADO",
            "use_invalid_block_id": False,
        },
    ]


# ---------------------------------------------------------------------------
# Ejecución
# ---------------------------------------------------------------------------

def run(n: int, output: Path, sensor_id_prefix: str = "scenario_sensor") -> None:
    from src.iota.tangle_writer import (
        TangleWriteError,
        fetch_block_data,
        register_in_tangle,
    )
    from src.verifier.integrity_checker import (
        VerificationError,
        verify_integrity,
    )

    output.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = ["repetition", "scenario_id", "description", "expected",
                  "actual", "passed", "block_id"]

    mutations = _mutations()
    rows = []

    for rep in range(1, n + 1):
        sensor_id = f"{sensor_id_prefix}_{rep}"

        # Fresh base reading per repetition, registered once on the Tangle.
        base_data = generate_sensor_data(sensor_id)
        payload = build_tangle_payload(base_data)
        try:
            block_id = register_in_tangle(payload)
        except TangleWriteError as exc:
            logger.error("Rep %d: could not register base reading: %s. Skipping.",
                         rep, exc)
            continue

        for m in mutations:
            scenario_id = m["id"]
            description = m["description"]
            expected = m["expected"]
            block_to_check = "INVALID_BLOCK_ID_123" if m["use_invalid_block_id"] else block_id
            candidate = m["data_mutation"](copy.deepcopy(base_data))

            try:
                verdict = verify_integrity(block_to_check, candidate, fetch_fn=fetch_block_data)
                actual = verdict["status"]
            except VerificationError:
                actual = "ERROR_HANDLED"
            except Exception as exc:
                logger.exception("Unexpected exception in rep %d, scenario %s",
                                 rep, scenario_id)
                actual = f"EXCEPTION: {exc}"

            passed = (actual == expected)
            rows.append({
                "repetition":  rep,
                "scenario_id": scenario_id,
                "description": description,
                "expected":    expected,
                "actual":      actual,
                "passed":      "YES" if passed else "NO",
                "block_id":    block_to_check,
            })
            logger.info("[rep %d/%d] %s | expected=%s actual=%s | %s",
                        rep, n, scenario_id, expected, actual,
                        "PASS" if passed else "FAIL")

    #Generación del archivo CSV
    with output.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    # --- Summary: overall + per scenario type ---
    total = len(rows)
    passed_total = sum(1 for r in rows if r["passed"] == "YES")
    logger.info("=" * 64)
    logger.info("OVERALL: %d/%d PASSED (%.1f%%)", passed_total, total,
                100.0 * passed_total / total if total else 0.0)

    by_scenario: dict[str, list[dict]] = {}
    for r in rows:
        by_scenario.setdefault(r["scenario_id"], []).append(r)

    for scenario_id, scenario_rows in sorted(by_scenario.items()):
        p = sum(1 for r in scenario_rows if r["passed"] == "YES")
        t = len(scenario_rows)
        logger.info("  %s: %d/%d (%.1f%%) - %s",
                    scenario_id, p, t, 100.0 * p / t if t else 0.0,
                    scenario_rows[0]["description"])

# Tasa de detección considerando únicamente las alteraciones reales
# (excluye E1 y E5, ya que no representan "alteraciones", sino un caso
# de control y un caso de error, respectivamente).
    alteration_ids = {"E2", "E3", "E4", "E6"}
    alteration_rows = [r for r in rows if r["scenario_id"] in alteration_ids]
    alteration_passed = sum(1 for r in alteration_rows if r["passed"] == "YES")
    n_alt = len(alteration_rows)
    logger.info("=" * 64)
    logger.info("Tasa de detección de alteraciones (E2,E3,E4,E6): %d/%d (%.2f%%)",
                alteration_passed, n_alt,
                100.0 * alteration_passed / n_alt if n_alt else 0.0)
    logger.info("Output written to: %s", output)


def _parse_args(argv=None):
    parser = argparse.ArgumentParser(
        description="Run functional validation scenarios E1-E6 against the "
                    "Tangle, repeated N times for statistical significance.",
    )
    parser.add_argument("--n", type=int, default=100,
                        help="Number of repetitions (default: 100)")
    parser.add_argument("--output", type=Path,
                        default=Path("docs/results/scenarios.csv"))
    parser.add_argument("--sensor-id-prefix", default="scenario_sensor")
    return parser.parse_args(argv)


def main(argv=None) -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    args = _parse_args(argv)
    run(args.n, args.output, args.sensor_id_prefix)
    return 0


if __name__ == "__main__":
    sys.exit(main())
