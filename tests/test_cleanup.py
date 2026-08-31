from datetime import date
from pathlib import Path
import tarfile

import pytest

from extractor_modules.operations import archive as cleanup


TODAY = date(2026, 8, 15)


def make_day(root: Path, source: str, day: str, filename: str = "value:00.csv") -> Path:
    folder = root / source / day
    folder.mkdir(parents=True)
    (folder / filename).write_text(day, encoding="utf-8")
    return folder


def test_cleanup_archives_completed_days_and_retains_exact_limit(tmp_path):
    raw = tmp_path / "raw"
    backup = tmp_path / "backup"
    days = [f"202608{number:02d}" for number in range(10, 16)]
    for day in days:
        make_day(raw, "weather_data", day)
    (raw / "weather_data" / "metadata").mkdir()
    (raw / "README.txt").write_text("ignored", encoding="utf-8")

    result = cleanup.execute_cleanup(raw, backup, max_days=3, today=TODAY)

    # Three calendar days including today are retained.
    assert sorted(path.name for path in (raw / "weather_data").iterdir()) == [
        "20260813",
        "20260814",
        "20260815",
        "metadata",
    ]
    assert result["days_deleted"] == 3
    assert result["completed_days"] == 5
    assert len(list((backup / "raw" / "weather_data").glob("*.tar"))) == 5

    # Archiving must not sanitize or rename the source tree before deletion.
    assert (raw / "weather_data" / "20260814" / "value:00.csv").exists()
    with tarfile.open(backup / "raw" / "weather_data" / "20260814.tar") as archive:
        assert "20260814/value:00.csv" in archive.getnames()


def test_corrupt_archive_aborts_before_any_deletion(tmp_path):
    raw = tmp_path / "raw"
    backup = tmp_path / "backup"
    for source in ("a", "b"):
        for day in ("20260810", "20260811"):
            make_day(raw, source, day, "data.txt")
    corrupt = backup / "raw" / "b" / "20260810.tar"
    corrupt.parent.mkdir(parents=True)
    corrupt.write_text("not a tar", encoding="utf-8")

    with pytest.raises(cleanup.CleanupError, match="unreadable"):
        cleanup.execute_cleanup(raw, backup, max_days=1, today=TODAY)

    assert (raw / "a" / "20260810").exists()
    assert (raw / "b" / "20260810").exists()


def test_dry_run_does_not_create_backup_or_delete(tmp_path):
    raw = tmp_path / "raw"
    backup = tmp_path / "backup"
    make_day(raw, "gkg", "20260810", "data.csv")
    make_day(raw, "gkg", "20260811", "data.csv")

    result = cleanup.execute_cleanup(
        raw, backup, max_days=1, today=TODAY, dry_run=True
    )

    assert result["days_deleted"] == 0
    assert result["days_would_delete"] == 2
    assert not backup.exists()
    assert (raw / "gkg" / "20260810").exists()


def test_scheduler_arguments_are_accepted(monkeypatch, tmp_path):
    raw = tmp_path / "raw"
    backup = tmp_path / "backup"
    raw.mkdir()
    monkeypatch.setattr(
        cleanup,
        "get_config",
        lambda: {"save_folder": str(raw), "backup_folder": str(backup)},
    )

    result = cleanup.delete_old_data([], [], max_days=30, dry_run=True)

    assert result["sources"] == 0


def test_configured_retention_is_used(monkeypatch, tmp_path):
    raw = tmp_path / "raw"
    backup = tmp_path / "backup"
    for day in ("20260810", "20260811"):
        make_day(raw, "gkg", day, "data.csv")
    monkeypatch.setattr(
        cleanup,
        "get_config",
        lambda: {
            "save_folder": str(raw),
            "backup_folder": str(backup),
            "retention_days": 1,
        },
    )

    result = cleanup.delete_old_data([], [], dry_run=True)

    assert result["days_would_delete"] == 2


def test_zero_retention_is_rejected(tmp_path):
    raw = tmp_path / "raw"
    raw.mkdir()
    with pytest.raises(ValueError, match="at least 1"):
        cleanup.build_cleanup_plan(raw, 0, TODAY)
