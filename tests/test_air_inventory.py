import csv
from pathlib import Path


def test_tracked_purpleair_inventory_has_runtime_format():
    path = Path("extractor_modules/air/nearby_purpleair_sensors.csv")
    with path.open(newline="", encoding="utf-8") as stream:
        rows = list(csv.reader(stream))

    assert rows
    assert all(len(row) == 3 for row in rows)
    assert all(row[0].isdigit() for row in rows)
    assert all(-90 <= float(row[1]) <= 90 for row in rows)
    assert all(-180 <= float(row[2]) <= 180 for row in rows)
