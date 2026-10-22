"""Reproduce sourced weekly VALUE-opportunity rank, not live daytrading tips.

Example:
python -m scripts.weekly_value_board \
  --file data/swedish_research_2026_w43.json \
  --as-of 2026-10-22T12:00:00+02:00

Score inputs are manually judged, cited facts. A high value score never
authorizes a buy or bypasses the separate 85/100 Stock Analyst technical gate.
"""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path

from src.swedish_fundamental_weekly_score import rank_weekly_watchlist


def run(path, *, now=None):
    document = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(document, dict) or not isinstance(document.get("candidates"), list):
        raise ValueError("invalid_weekly_research_document")
    ranked = rank_weekly_watchlist(document["candidates"], now=now)
    if document.get("week") != ranked["week"]:
        raise ValueError("stored_week_mismatch")
    return ranked


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--file", type=Path, required=True)
    parser.add_argument("--as-of", default=None,
                        help="UTC-aware ISO date for archived backtesting/reproduction")
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args()
    as_of = (datetime.fromisoformat(args.as_of.replace("Z", "+00:00"))
             if args.as_of else datetime.now(timezone.utc))
    if as_of.tzinfo is None:
        parser.error("--as-of needs a timezone offset")
    ranked = run(args.file, now=as_of)
    result = json.dumps(ranked, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.write_text(result, encoding="utf-8")
    print(result)


if __name__ == "__main__":
    main()
