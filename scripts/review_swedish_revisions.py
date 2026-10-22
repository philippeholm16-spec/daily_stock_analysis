"""Review analyst target direction, distinct fair values and consensus EPS data.

Read-only reproducible historical report, deliberately not a BUY signal.
Example:
python -m scripts.review_swedish_revisions \
  --file data/elekta_analyst_revisions_2026_10_22.json \
  --as-of 2026-10-22T12:40:00Z
"""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path

from src.swedish_revision_quality import inspect_analyst_revisions


def review(path, *, now=None):
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("invalid_revision_record_file")
    return inspect_analyst_revisions(
        data["records"], isin=data["isin"], now=now,
        short_interest=data.get("short_interest"),
        earnings_consensus_snapshots=data.get("earnings_consensus_snapshots")
    )


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--file", type=Path, required=True)
    p.add_argument("--as-of", default=None,
                   help="As-of timestamp only for reproducing a historical review")
    p.add_argument("--output", type=Path, default=None)
    args = p.parse_args()
    now = (datetime.fromisoformat(args.as_of.replace("Z", "+00:00"))
           if args.as_of is not None else datetime.now(timezone.utc))
    if now.tzinfo is None:
        p.error("--as-of must include an explicit timezone")
    result = json.dumps(review(args.file, now=now), ensure_ascii=False, indent=2) + "\n"
    if args.output is not None:
        args.output.write_text(result, encoding="utf-8")
    print(result)


if __name__ == "__main__":
    main()
