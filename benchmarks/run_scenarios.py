"""
Functional validation scenarios E1–E6.

Each scenario registers a known sensor reading on the Tangle, then
verifies it under different mutations to test the detection capability
of the system. The output is a CSV with one row per scenario indicating
whether the actual verdict matched the expected verdict.

Scenarios:
    E1 - Integro:                 unmutated data, expect INTEGRO
    E2 - Alteración numérica:     temperature mutated, expect ALTERADO
    E3 - Alteración timestamp:    timestamp mutated, expect ALTERADO
    E4 - Alteración sensor_id:    sensor_id mutated, expect ALTERADO
    E5 - Bloque inexistente:      verify against an invalid block_id
    E6 - Manipulación de campo:   humidity mutated, expect ALTERADO

The CSV (default: docs/results/scenarios.csv) has the columns:
    scenario_id, description, expected, actual, passed, block_id
"""
from __future__ import annotations

import argparse
import csv
import copy
import logging
import sys
from pathlib import Path

from dotenv import load_dotenv

from src.processor.payload_builder import build_tangle_payload
from src.simulator.sensor_simulator import generate_sensor_data

load_dotenv()
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Scenario definitions
# ---------------------------------------------------------------------------

def _scenarios(base_data: dict) -> list[dict]:
    """Build the list of scenario specifications from a base reading."""
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
# Execution
# ---------------------------------------------------------------------------

def run(output: Path, sensor_id: str = "scenario_sensor") -> None:
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
    fieldnames = ["scenario_id", "description", "expected",
                  "actual", "passed", "block_id"]

    # Generate ONE base reading and register it once on the Tangle. All
    # scenarios except E5 verify against this single block.
    base_data = generate_sensor_data(sensor_id)
    payload = build_tangle_payload(base_data)
    logger.info("Registering base reading on Tangle...")
    try:
        block_id = register_in_tangle(payload)
        logger.info("Base block_id: %s", block_id)
    except TangleWriteError as exc:
        logger.error("Could not register base reading: %s. Aborting scenarios.", exc)
        return

    scenarios = _scenarios(base_data)
    rows = []
    for s in scenarios:
        scenario_id = s["id"]
        description = s["description"]
        expected = s["expected"]
        block_to_check = "INVALID_BLOCK_ID_123" if s["use_invalid_block_id"] else block_id
        candidate = s["data_mutation"](copy.deepcopy(base_data))

        try:
            verdict = verify_integrity(block_to_check, candidate, fetch_fn=fetch_block_data)
            actual = verdict["status"]
        except VerificationError:
            # For E5 this is the expected outcome (graceful error handling).
            actual = "ERROR_HANDLED"
        except Exception as exc:
            logger.exception("Unexpected exception in scenario %s", scenario_id)
            actual = f"EXCEPTION: {exc}"

        passed = (actual == expected)
        rows.append({
            "scenario_id": scenario_id,
            "description": description,
            "expected":    expected,
            "actual":      actual,
            "passed":      "YES" if passed else "NO",
            "block_id":    block_to_check,
        })
        logger.info("%s | %s | expected=%s actual=%s | %s",
                    scenario_id, description, expected, actual,
                    "PASS" if passed else "FAIL")

    # Write CSV
    with output.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    total = len(rows)
    passed = sum(1 for r in rows if r["passed"] == "YES")
    logger.info("Summary: %d/%d scenarios PASSED. Output: %s",
                passed, total, output)


def _parse_args(argv=None):
    parser = argparse.ArgumentParser(
        description="Run functional validation scenarios E1-E6 against the Tangle.",
    )
    parser.add_argument("--output", type=Path,
                        default=Path("docs/results/scenarios.csv"))
    parser.add_argument("--sensor-id", default="scenario_sensor")
    return parser.parse_args(argv)


def main(argv=None) -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    args = _parse_args(argv)
    run(args.output, args.sensor_id)
    return 0


if __name__ == "__main__":
    sys.exit(main())
