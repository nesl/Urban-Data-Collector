"""Archive completed collection days and enforce local retention safely."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import date, datetime
import os
from pathlib import Path
import shutil
import tarfile
import tempfile

from utilities.util import get_config


DATE_FORMAT = "%Y%m%d"


class CleanupError(RuntimeError):
    """Raised when cleanup cannot prove that deletion is safe."""


@dataclass(frozen=True)
class SourcePlan:
    source: str
    completed_days: tuple[Path, ...]
    days_to_delete: tuple[Path, ...]


def _is_date_directory(path: Path) -> bool:
    if not path.is_dir():
        return False
    try:
        datetime.strptime(path.name, DATE_FORMAT)
    except ValueError:
        return False
    return True


def build_cleanup_plan(save_folder: Path, max_days: int, today: date) -> list[SourcePlan]:
    """Build a per-source plan using completed YYYYMMDD directories only."""
    if max_days < 0:
        raise ValueError("max_days must be zero or greater")
    if not save_folder.is_dir():
        raise CleanupError(f"Data directory does not exist: {save_folder}")

    today_name = today.strftime(DATE_FORMAT)
    plans = []
    for source_dir in sorted(path for path in save_folder.iterdir() if path.is_dir()):
        completed = tuple(
            sorted(
                path
                for path in source_dir.iterdir()
                if _is_date_directory(path) and path.name < today_name
            )
        )
        delete_count = max(0, len(completed) - max_days)
        plans.append(
            SourcePlan(
                source=source_dir.name,
                completed_days=completed,
                days_to_delete=completed[:delete_count],
            )
        )
    return plans


def archive_path(backup_folder: Path, source: str, day: str) -> Path:
    return backup_folder / "raw" / source / f"{day}.tar"


def validate_archive(path: Path, expected_day: str) -> None:
    """Require a readable, nonempty tar whose members are rooted at the day."""
    if not path.is_file() or path.stat().st_size == 0:
        raise CleanupError(f"Archive is missing or empty: {path}")
    try:
        with tarfile.open(path, "r") as archive:
            members = archive.getmembers()
    except (tarfile.TarError, OSError) as exc:
        raise CleanupError(f"Archive is unreadable: {path}: {exc}") from exc
    if not members:
        raise CleanupError(f"Archive has no members: {path}")
    if any(Path(member.name).parts[0] != expected_day for member in members):
        raise CleanupError(f"Archive contains an unexpected root: {path}")


def create_archive_atomic(day_folder: Path, destination: Path) -> None:
    """Create, validate, and atomically publish one tar archive."""
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists():
        validate_archive(destination, day_folder.name)
        return

    temporary_path = None
    try:
        with tempfile.NamedTemporaryFile(
            dir=destination.parent,
            prefix=f".{day_folder.name}.",
            suffix=".tar.tmp",
            delete=False,
        ) as temporary:
            temporary_path = Path(temporary.name)

        with tarfile.open(temporary_path, "w") as archive:
            archive.add(day_folder, arcname=day_folder.name)
        validate_archive(temporary_path, day_folder.name)
        os.replace(temporary_path, destination)
        temporary_path = None
        validate_archive(destination, day_folder.name)
    finally:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)


def execute_cleanup(
    save_folder: Path,
    backup_folder: Path,
    *,
    max_days: int = 30,
    today: date | None = None,
    dry_run: bool = False,
) -> dict[str, int]:
    """Archive all completed days, then remove safely archived expired days.

    Archiving is a global first phase. If any archive fails validation, this
    function raises before deleting anything from any source.
    """
    effective_today = today or date.today()
    plans = build_cleanup_plan(save_folder, max_days, effective_today)
    archives_needed = 0

    for plan in plans:
        for day_folder in plan.completed_days:
            destination = archive_path(backup_folder, plan.source, day_folder.name)
            if not destination.exists():
                archives_needed += 1
            if dry_run:
                if destination.exists():
                    validate_archive(destination, day_folder.name)
                action = "verified" if destination.exists() else "would archive"
                print(f"DRY RUN: {action} {day_folder} -> {destination}")
            else:
                create_archive_atomic(day_folder, destination)

    delete_count = sum(len(plan.days_to_delete) for plan in plans)
    for plan in plans:
        for day_folder in plan.days_to_delete:
            destination = archive_path(backup_folder, plan.source, day_folder.name)
            if dry_run:
                print(f"DRY RUN: delete {day_folder} after archive validation")
                continue
            validate_archive(destination, day_folder.name)
            shutil.rmtree(day_folder)
            print(f"Deleted archived data: {day_folder}")

    summary = {
        "sources": len(plans),
        "completed_days": sum(len(plan.completed_days) for plan in plans),
        "archives_needed": archives_needed,
        "days_deleted": 0 if dry_run else delete_count,
        "days_would_delete": delete_count,
    }
    print(
        "Cleanup summary: "
        + ", ".join(f"{key}={value}" for key, value in summary.items())
    )
    return summary


def delete_old_data(
    chosen_sensors=None,
    exclude_sensors=None,
    *,
    max_days: int | None = None,
    dry_run: bool = False,
):
    """Scheduler-compatible cleanup entry point.

    The scheduler supplies include/exclude lists to every job. Cleanup does not
    use sensor selection, but accepts those arguments to share that interface.
    """
    del chosen_sensors, exclude_sensors
    config = get_config()
    retention_days = config.get("retention_days", 30) if max_days is None else max_days
    return execute_cleanup(
        Path(config["save_folder"]),
        Path(config["backup_folder"]),
        max_days=retention_days,
        dry_run=dry_run,
    )


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="Archive completed collection days and enforce retention"
    )
    parser.add_argument(
        "--max-days",
        type=int,
        default=None,
        help="override config.json retention_days (default: 30)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="print archive/deletion actions without changing files",
    )
    args = parser.parse_args(argv)
    try:
        delete_old_data(max_days=args.max_days, dry_run=args.dry_run)
    except (CleanupError, OSError, ValueError) as exc:
        print(f"Cleanup failed; no unverified data was deleted: {exc}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
