from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Dict, List, Protocol

from observability.metrics import record_alert


@dataclass
class AlertRule:
    min_net_spread: float
    min_volume: float = 0.01
    cooldown_seconds: int = 60


@dataclass
class OpportunityAlert:
    buy_exchange: str
    sell_exchange: str
    product: str
    net_spread: float
    gross_spread: float
    available_volume: float
    recorded_at: str
    metadata: Dict[str, Any] = field(default_factory=dict)


class NotificationChannel(Protocol):
    def send(self, alert: OpportunityAlert) -> None:
        ...


class ConsoleChannel:
    def __init__(self, prefix: str = "[ALERT]") -> None:
        self.prefix = prefix

    def send(self, alert: OpportunityAlert) -> None:
        message = (
            f"{self.prefix} {alert.buy_exchange}->{alert.sell_exchange} "
            f"{alert.product} net={alert.net_spread:.2f} volume={alert.available_volume}"
        )
        print(message)


class SlackChannelStub:
    def __init__(self, channel: str = "#alerts") -> None:
        self.channel = channel

    def send(self, alert: OpportunityAlert) -> None:
        payload = {
            "channel": self.channel,
            "text": (
                f":rotating_light: {alert.product} {alert.buy_exchange}->{alert.sell_exchange} "
                f"net={alert.net_spread:.2f} gross={alert.gross_spread:.2f} "
                f"volume={alert.available_volume}"
            ),
            "metadata": alert.metadata,
        }
        print(f"[SLACK] {json.dumps(payload, ensure_ascii=False)}")


class AlertRouter:
    def __init__(self, rule: AlertRule, channels: List[NotificationChannel]) -> None:
        self.rule = rule
        self.channels = channels
        self.last_sent: Dict[str, datetime] = {}

    @staticmethod
    def _key(alert: OpportunityAlert) -> str:
        return f"{alert.product}:{alert.buy_exchange}->{alert.sell_exchange}"

    def _passes_threshold(self, alert: OpportunityAlert) -> bool:
        if alert.net_spread < self.rule.min_net_spread:
            return False
        if alert.available_volume < self.rule.min_volume:
            return False
        return True

    def _under_cooldown(self, key: str) -> bool:
        last = self.last_sent.get(key)
        if not last:
            return False
        return (datetime.utcnow() - last) < timedelta(seconds=self.rule.cooldown_seconds)

    def handle(self, alert: OpportunityAlert) -> bool:
        if not self._passes_threshold(alert):
            return False
        key = self._key(alert)
        if self._under_cooldown(key):
            return False
        for channel in self.channels:
            channel.send(alert)
            record_alert(channel.__class__.__name__)
        self.last_sent[key] = datetime.utcnow()
        return True
