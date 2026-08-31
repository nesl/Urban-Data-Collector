import csv

from extractor_modules.email.raw_email import FIELDNAMES, SCHEMA_VERSION, normalize_email, write_raw_batch


def test_raw_email_contract_preserves_source_content(tmp_path):
    record = normalize_email({
        "id": "42",
        "message_id": "<example@example.com>",
        "date": "2026-08-31T10:00:00+00:00",
        "sender": "alerts@example.com",
        "subject": "Citizen alert",
        "body": "Original message text",
    }, "citizen")

    path = write_raw_batch([record], tmp_path)
    with path.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))

    assert list(rows[0]) == FIELDNAMES
    assert rows[0]["schema_version"] == SCHEMA_VERSION
    assert rows[0]["imap_uid"] == "42"
    assert rows[0]["body"] == "Original message text"


def test_empty_raw_batch_creates_no_file(tmp_path):
    assert write_raw_batch([], tmp_path) is None
    assert list(tmp_path.iterdir()) == []
