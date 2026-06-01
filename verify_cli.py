"""
Command-line interface for the integrity verifier.

Examples:
    # Verify a block_id against the data recorded in the local registry
    python verify_cli.py --block-id 0x123abc...

    # Verify a block_id against an external data file (e.g. to test
    # the ALTERADO branch by editing a copy of raw_data and pointing here)
    python verify_cli.py --block-id 0x123abc... --data-file /tmp/altered.json

The exit code is 0 when the verdict is INTEGRO, 1 when ALTERADO, and 2
on any error.
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

from src.processor.local_registry import LocalRegistry
from src.verifier.integrity_checker import (
    ALTERADO,
    ERROR,
    INTEGRO,
    NO_ENCONTRADO,
    VerificationError,
    verify_from_registry,
    verify_integrity,
)

load_dotenv()
logger = logging.getLogger(__name__)


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Verify the integrity of a block stored on the IOTA Tangle.",
    )
    parser.add_argument(
        "--block-id", required=True,
        help="Tangle block_id to verify."
    )
    parser.add_argument(
        "--data-file", default=None,
        help="Path to a JSON file containing the candidate data. If omitted, "
             "raw_data is taken from the local registry."
    )
    parser.add_argument(
        "--registry-path", default=None,
        help="Path to the local registry JSON file. Defaults to "
             "LOCAL_REGISTRY_PATH from .env."
    )
    return parser.parse_args(argv)


def _print_verdict(verdict: dict) -> None:
    """Render a human-readable verdict block to stdout."""
    status = verdict.get("status", "?")
    sep = "=" * 64
    print(sep)
    print(f"  VERDICTO: {status}")
    print(sep)
    print(f"  block_id:  {verdict.get('block_id')}")
    print(f"  sensor_id: {verdict.get('sensor_id')}")
    print(f"  timestamp: {verdict.get('timestamp')}")
    print(f"  stored:    {verdict.get('stored')}")
    print(f"  computed:  {verdict.get('computed')}")
    print(f"  match:     {verdict.get('match')}")
    if "message" in verdict:
        print(f"  message:   {verdict['message']}")
    print(sep)


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    args = _parse_args(argv)

    registry_path = args.registry_path or os.getenv(
        "LOCAL_REGISTRY_PATH", "data/local_registry.json"
    )
    registry = LocalRegistry(registry_path)

    try:
        if args.data_file:
            # External data file: verify directly against the Tangle.
            data = json.loads(Path(args.data_file).read_text(encoding="utf-8"))
            verdict = verify_integrity(args.block_id, data)
        else:
            # Use raw_data recorded in the local registry.
            verdict = verify_from_registry(args.block_id, registry)
    except VerificationError as exc:
        logger.error("Verification failed: %s", exc)
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    except FileNotFoundError as exc:
        logger.error("Data file not found: %s", exc)
        return 2

    _print_verdict(verdict)

    status = verdict.get("status")
    if status == INTEGRO:
        return 0
    if status == ALTERADO:
        return 1
    return 2  # NO_ENCONTRADO or any other non-success


if __name__ == "__main__":
    sys.exit(main())
