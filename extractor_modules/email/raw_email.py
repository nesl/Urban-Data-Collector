"""Versioned, acquisition-only storage for email-backed observations."""

from __future__ import annotations

import csv
import os
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Mapping


SCHEMA_VERSION = "email_raw.v1"
FIELDNAMES = [
    "schema_version",
    "source",
    "imap_uid",
    "message_id",
    "received_at",
    "sender",
    "subject",
    "body",
    "ingested_at",
]


def normalize_email(email: Mapping[str, object], source: str) -> dict[str, str]:
    """Convert one fetched IMAP message into the stable raw contract."""
    return {
        "schema_version": SCHEMA_VERSION,
        "source": source,
        "imap_uid": str(email.get("id", "")),
        "message_id": str(email.get("message_id", "")),
        "received_at": str(email.get("date", "")),
        "sender": str(email.get("sender", "")),
        "subject": str(email.get("subject", "")),
        "body": str(email.get("body", "")),
        "ingested_at": datetime.now(timezone.utc).isoformat(),
    }


def write_raw_batch(records: Iterable[Mapping[str, object]], output_dir: str | Path) -> Path | None:
    """Atomically write one batch, returning only after it is durable.

    A new file is used for every batch, which makes retry/idempotency checks
    possible from the stable ``imap_uid`` and ``message_id`` fields.
    """
    rows = [dict(record) for record in records]
    if not rows:
        return None

    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    destination = output / f"{time.time_ns()}.csv"
    fd, temporary_name = tempfile.mkstemp(prefix=".email-", suffix=".tmp", dir=output)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=FIELDNAMES, extrasaction="ignore")
            writer.writeheader()
            writer.writerows(rows)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary_name, destination)
        return destination
    except Exception:
        try:
            os.unlink(temporary_name)
        except FileNotFoundError:
            pass
        raise
