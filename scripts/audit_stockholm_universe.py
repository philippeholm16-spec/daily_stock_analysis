"""Audit a supplied authorized Nasdaq Stockholm reference and Avanza mapping.

Usage:
  python -m scripts.audit_stockholm_universe --reference xsto_reference.json \
      --mapping avanza_xsto_mapping.json --output coverage_audit.json

Without BOTH real sources, no 'complete coverage' is claimed. Assertions
must be backed by upstream provider documentation and authorizations.
"""
import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from src.complete_market_coverage import audit_complete_xsto


def run(reference_path, mapping_path):
    reference = json.loads(Path(reference_path).read_text(encoding="utf-8"))
    mapping = json.loads(Path(mapping_path).read_text(encoding="utf-8"))
    if not isinstance(reference, dict) or not isinstance(mapping, dict):
        raise ValueError("invalid_manifest_document")
    result = audit_complete_xsto(reference, mapping)
    report = result.as_dict()
    report.update({
        "audited_at_utc": datetime.now(timezone.utc).isoformat(),
        "claim": "COMPLETE_XSTO_ONLY_WHEN_TRUE" if report["complete"] else "NOT_COMPLETE",
        "no_trading": True,
        "operator_must_verify_license_and_source_provenance": True,
    })
    return report


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--reference", type=Path, required=True)
    parser.add_argument("--mapping", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=Path("coverage_audit.json"))
    args = parser.parse_args()
    report = run(args.reference, args.mapping)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "reference_count": report["reference_count"],
        "mapped_count": report["mapped_count"],
        "missing": len(report["missing_isins"]),
        "mismatched": len(report["mismatched"]),
        "complete": report["complete"],
    }))
    if not report["complete"]:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
