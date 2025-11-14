from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable


def read_jsonl(path: Path) -> Iterable[dict]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                yield json.loads(line)
            except json.JSONDecodeError:
                continue


def main() -> None:
    base_dir = Path("storage_snapshots")
    target = base_dir / "snapshot-spread_opportunity.jsonl"
    if not target.exists():
        print(f"No opportunity file found at {target}")
        return
    print(f"Reading {target}")
    for entry in read_jsonl(target):
        payload = entry.get("payload", {})
        print(
            f"{entry.get('recorded_at')}: "
            f"{payload.get('buy_exchange')} -> {payload.get('sell_exchange')} "
            f"net={payload.get('net_spread')}"
        )


if __name__ == "__main__":
    main()
