
"""
ModelLedger Evidence Engine CLI bridge.

Used by the Next.js application to request an EvidenceRecord
from the Python evidence engine.

This module does not make authenticity or AI-generation decisions.
It only collects evidence and emits the EvidenceRecord as JSON.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def load_record_module():
    """
    Load the evidence package even when evidence-engine is not installed
    as a normal Python package.
    """
    root = Path(__file__).resolve().parent

    if str(root) not in sys.path:
        sys.path.insert(0, str(root.parent))

    import importlib.util
    import types

    package_name = "modelledger_evidence"

    if package_name not in sys.modules:
        package = types.ModuleType(package_name)
        package.__path__ = [str(root)]
        sys.modules[package_name] = package

    import modelledger_evidence.record as record

    return record


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Collect ModelLedger evidence for an asset."
    )

    parser.add_argument(
        "path",
        help="Path to the asset to inspect.",
    )

    parser.add_argument(
        "--no-metadata",
        action="store_true",
        help="Skip ExifTool metadata collection.",
    )

    args = parser.parse_args()

    asset_path = Path(args.path).resolve()

    if not asset_path.is_file():
        print(
            json.dumps(
                {
                    "error": f"Asset does not exist: {asset_path}",
                }
            ),
            file=sys.stderr,
        )
        return 2

    try:
        record_module = load_record_module()

        record = record_module.build_record(
            asset_path,
            collect_metadata=not args.no_metadata,
        )

        if hasattr(record, "to_dict"):
            output = record.to_dict()
        else:
            from dataclasses import asdict

            output = asdict(record)

        print(
            json.dumps(
                output,
                indent=2,
                default=str,
            )
        )

        return 0

    except Exception as exc:
        print(
            json.dumps(
                {
                    "error": type(exc).__name__,
                    "message": str(exc),
                }
            ),
            file=sys.stderr,
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
