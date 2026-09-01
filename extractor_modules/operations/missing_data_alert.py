"""Email a daily alert when an expected data-day folder/archive is absent."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from email.message import EmailMessage
import os
from pathlib import Path
import smtplib
import socket

from extractor_modules.common.config import get_config


DATE_FORMAT = "%Y%m%d"
DEFAULT_SOURCES = {
    "air_data": 1,
    "alertcalifornia": 1,
    "cctv": 1,
    "gkg": 1,
    "weather_data": 1,
    "pem_data_chp_incidents_day": 2,
    "pem_data_station_5min": 2,
}


@dataclass(frozen=True)
class MissingDay:
    source: str
    expected_day: date


def expected_day_exists(save_folder: Path, backup_folder: Path, source: str, day: date) -> bool:
    day_name = day.strftime(DATE_FORMAT)
    local = save_folder / source / day_name
    archive = backup_folder / "raw" / source / f"{day_name}.tar"
    return local.is_dir() or (archive.is_file() and archive.stat().st_size > 0)


def find_missing_days(save_folder: Path, backup_folder: Path, sources: dict[str, int], today: date) -> list[MissingDay]:
    missing = []
    for source, lag_days in sorted(sources.items()):
        if not isinstance(lag_days, int) or lag_days < 1:
            raise ValueError(f"Lag for {source!r} must be an integer of at least 1")
        expected = today - timedelta(days=lag_days)
        if not expected_day_exists(save_folder, backup_folder, source, expected):
            missing.append(MissingDay(source, expected))
    return missing


def build_message(sender: str, recipient: str, missing: list[MissingDay], today: date) -> EmailMessage:
    message = EmailMessage()
    message["From"] = sender
    message["To"] = recipient
    message["Subject"] = f"[Urban observations alert] {len(missing)} missing daily dataset(s)"
    lines = [
        f"The daily data check on {today.isoformat()} found missing data:",
        "",
        *(f"- {item.source}: expected {item.expected_day.isoformat()}" for item in missing),
        "",
        f"Host: {socket.gethostname()}",
        "A date is present when its local folder or external .tar archive exists.",
    ]
    message.set_content("\n".join(lines))
    return message


def send_alert(config: dict, recipient: str, missing: list[MissingDay], today: date) -> None:
    account = config["email_acc_info"]
    alert_config = config.get("data_quality_alerts", {})
    message = build_message(account["email"], recipient, missing, today)
    with smtplib.SMTP_SSL(
        alert_config.get("smtp_host", "smtp.gmail.com"),
        int(alert_config.get("smtp_port", 465)),
        timeout=30,
    ) as smtp:
        smtp.login(account["email"], account["password"])
        smtp.send_message(message)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--today", help="Override today (YYYY-MM-DD) for testing")
    parser.add_argument("--recipient", help="Override the configured recipient")
    args = parser.parse_args(argv)

    config = get_config()
    alert_config = config.get("data_quality_alerts", {})
    sources = alert_config.get("sources", DEFAULT_SOURCES)
    today = datetime.strptime(args.today, "%Y-%m-%d").date() if args.today else date.today()
    missing = find_missing_days(Path(config["save_folder"]), Path(config["backup_folder"]), sources, today)
    if not missing:
        print(f"Data completeness check passed for {len(sources)} sources")
        return 0

    print("Missing daily data: " + ", ".join(
        f"{item.source}/{item.expected_day.strftime(DATE_FORMAT)}" for item in missing
    ))
    if args.dry_run:
        return 1
    recipient = args.recipient or os.environ.get("DATA_ALERT_RECIPIENT") or alert_config.get("recipient")
    if not recipient:
        print("Alert not sent: configure DATA_ALERT_RECIPIENT or data_quality_alerts.recipient")
        return 2
    try:
        send_alert(config, recipient, missing, today)
    except (OSError, smtplib.SMTPException) as exc:
        print(f"Alert delivery failed: {exc}")
        return 3
    print(f"Alert sent to {recipient}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
