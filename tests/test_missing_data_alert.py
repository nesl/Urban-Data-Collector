from datetime import date
from pathlib import Path

from extractor_modules.operations import missing_data_alert as alert


TODAY = date(2026, 8, 31)


def test_presence_can_be_local_or_archived(tmp_path: Path):
    raw = tmp_path / "raw"
    backup = tmp_path / "backup"
    (raw / "weather_data" / "20260830").mkdir(parents=True)
    archive = backup / "raw" / "air_data" / "20260830.tar"
    archive.parent.mkdir(parents=True)
    archive.write_bytes(b"archive")

    missing = alert.find_missing_days(
        raw,
        backup,
        {"weather_data": 1, "air_data": 1},
        TODAY,
    )

    assert missing == []


def test_pems_can_have_an_extra_day_of_grace(tmp_path: Path):
    raw = tmp_path / "raw"
    backup = tmp_path / "backup"
    (raw / "pem_data_station_5min" / "20260829").mkdir(parents=True)

    missing = alert.find_missing_days(
        raw,
        backup,
        {"pem_data_station_5min": 2, "weather_data": 1},
        TODAY,
    )

    assert missing == [alert.MissingDay("weather_data", date(2026, 8, 30))]


def test_message_targets_separate_recipient():
    missing = [alert.MissingDay("air_data", date(2026, 8, 30))]

    message = alert.build_message("collector@example.com", "ops@example.com", missing, TODAY)

    assert message["From"] == "collector@example.com"
    assert message["To"] == "ops@example.com"
    assert "air_data" in message.get_content()
