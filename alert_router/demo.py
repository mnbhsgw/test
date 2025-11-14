from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable, List

from alert_router.router import AlertRouter, AlertRule, ConsoleChannel, OpportunityAlert, SlackChannelStub


def load_opportunities(path: Path) -> List[OpportunityAlert]:
    alerts: List[OpportunityAlert] = []
    if not path.exists():
        return alerts
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                continue
            payload = entry.get("payload", {})
            try:
                alert = OpportunityAlert(
                    buy_exchange=payload["buy_exchange"],
                    sell_exchange=payload["sell_exchange"],
                    product=payload["product"],
                    net_spread=float(payload["net_spread"]),
                    gross_spread=float(payload.get("gross_spread", 0)),
                    available_volume=float(payload.get("available_volume", 0)),
                    recorded_at=entry.get("recorded_at", ""),
                    metadata=payload.get("metadata", {}),
                )
            except KeyError:
                continue
            alerts.append(alert)
    return alerts


def main() -> None:
    path = Path("storage_snapshots/snapshot-spread_opportunity.jsonl")
    alerts = load_opportunities(path)
    if not alerts:
        print("No stored spread opportunities yet.")
        return
    router = AlertRouter(
        rule=AlertRule(min_net_spread=1000.0, min_volume=0.01, cooldown_seconds=180),
        channels=[ConsoleChannel(), SlackChannelStub("#arb-alerts")],
    )
    for alert in alerts:
        router.handle(alert)


if __name__ == "__main__":
    main()
