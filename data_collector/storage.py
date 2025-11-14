from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Protocol, Union


def _utcnow_iso() -> str:
    return datetime.utcnow().isoformat() + "Z"


@dataclass
class SnapshotRecord:
    exchange: str
    product: str
    kind: str
    recorded_at: str
    payload: Dict[str, Any]
    metadata: Dict[str, Any] = field(default_factory=dict)


class StorageClient(Protocol):
    def persist(self, record: SnapshotRecord) -> None:
        """Persist a normalized snapshot."""
        ...


class FileStorageAdapter:
    """Simple JSONL storage for snapshots."""

    def __init__(self, directory: Union[str, Path]) -> None:
        self.base_dir = Path(directory).expanduser()
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def _path(self, kind: str) -> Path:
        filename = f"snapshot-{kind}.jsonl"
        return self.base_dir / filename

    def persist(self, record: SnapshotRecord) -> None:
        path = self._path(record.kind)
        payload = asdict(record)
        payload.setdefault("metadata", {})
        payload_line = json.dumps(payload, ensure_ascii=False)
        path.open("a", encoding="utf-8").write(payload_line + "\n")

    def persist_snapshot(
        self, exchange: str, product: str, kind: str, payload: Dict[str, Any]
    ) -> None:
        record = SnapshotRecord(
            exchange=exchange,
            product=product,
            kind=kind,
            recorded_at=_utcnow_iso(),
            payload=payload,
        )
        self.persist(record)
