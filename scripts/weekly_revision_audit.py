"""Render source-auditable 90-day analyst revision research for a selected watchlist.

Never prints an invented consensus EPS delta or a BUY recommendation.
The published 100-point October weekly scores are archived discovery notes;
until full due diligence is complete this command returns no final buy score.

Example:
python -m scripts.weekly_revision_audit \
  --file data/swedish_revision_evidence_2026_w43.json \
  --as-of 2026-10-22T14:40:00+02:00
"""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path

from src.swedish_investment_due_diligence import evaluate_research_comparison


def run(path, *, now=None):
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    if (not isinstance(raw, dict)
            or raw.get("schema_version") != "1.0"
            or not isinstance(raw.get("companies"), list)):
        raise ValueError("unverified_revision_data_document")
    return evaluate_research_comparison(raw["companies"], now=now)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--file", type=Path, required=True)
    parser.add_argument("--as-of", default=None, help="Timezone-aware ISO 8601")
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args()
    now = datetime.fromisoformat(args.as_of.replace("Z", "+00:00")) if args.as_of else datetime.now(timezone.utc)
    if now.tzinfo is None:
        parser.error("--as-of must include timezone offset")
    output = json.dumps(run(args.file, now=now), ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.write_text(output, encoding="utf-8")
    print(output)


if __name__ == "__main__":
    main()
