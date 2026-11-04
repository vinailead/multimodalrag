"""Tamper-evident, SHA-256 hash-chained JSONL audit trail."""

from __future__ import annotations

import hashlib
import json
import threading
from datetime import UTC, datetime
from pathlib import Path

from insurance_mmrag.schemas import AuditLogEntry

GENESIS_HASH = "0" * 64


def _canonical(obj: object) -> str:
    return json.dumps(obj, sort_keys=True, ensure_ascii=False, separators=(",", ":"), default=str)


class AuditLogger:
    """Append-only log. Each record hashes its content plus the previous record's hash."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._last_hash = self._load_last_hash()

    def _load_last_hash(self) -> str:
        if not self.path.exists():
            return GENESIS_HASH
        last = GENESIS_HASH
        with self.path.open(encoding="utf-8") as fh:
            for line in fh:
                if line.strip():
                    last = str(json.loads(line)["record_hash"])
        return last

    def log(self, event_type: str, payload: dict[str, object]) -> AuditLogEntry:
        with self._lock:
            timestamp = datetime.now(UTC).isoformat()
            body = {
                "timestamp": timestamp,
                "event_type": event_type,
                "payload": payload,
                "prev_hash": self._last_hash,
            }
            record_hash = hashlib.sha256(_canonical(body).encode("utf-8")).hexdigest()
            entry = AuditLogEntry(
                timestamp=timestamp,
                event_type=event_type,
                payload=payload,
                prev_hash=self._last_hash,
                record_hash=record_hash,
            )
            with self.path.open("a", encoding="utf-8") as fh:
                fh.write(_canonical(entry.model_dump(mode="json")) + "\n")
            self._last_hash = record_hash
            return entry

    def read(self, limit: int = 50) -> list[AuditLogEntry]:
        if not self.path.exists():
            return []
        lines = [ln for ln in self.path.read_text(encoding="utf-8").splitlines() if ln.strip()]
        return [AuditLogEntry.model_validate_json(ln) for ln in lines[-limit:]]

    def verify_chain(self) -> bool:
        """Recompute every hash; returns False if any record was altered, removed or reordered."""
        prev = GENESIS_HASH
        for entry in self.read(limit=10**9):
            body = {
                "timestamp": entry.timestamp,
                "event_type": entry.event_type,
                "payload": entry.payload,
                "prev_hash": entry.prev_hash,
            }
            expected = hashlib.sha256(_canonical(body).encode("utf-8")).hexdigest()
            if entry.prev_hash != prev or entry.record_hash != expected:
                return False
            prev = entry.record_hash
        return True
