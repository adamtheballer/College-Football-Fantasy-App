from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any


def stable_snapshot_hash(payload: dict[str, Any]) -> str:
    encoded = json.dumps(payload, sort_keys=True, default=str, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()
