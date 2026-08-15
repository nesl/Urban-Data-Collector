import unittest
import json
import os
import tempfile
from pathlib import Path

from observation_contract import REPORT_SCHEMA_VERSION, ReportValidationError, normalize_report
from utilities.util import get_config


class ReportContractTest(unittest.TestCase):
    def test_normalizes_valid_report(self):
        report = normalize_report({
            "report_id": "r-1",
            "report_date": "2026-08-15T12:00:00+00:00",
            "sensor_id": "station-1",
            "sensor_type": "air_data",
            "location": {"latitude": 34.0, "longitude": -118.2},
            "data": {"pm25": 12.5},
        })
        self.assertEqual(report["schema_version"], REPORT_SCHEMA_VERSION)

    def test_rejects_invalid_location(self):
        with self.assertRaises(ReportValidationError):
            normalize_report({
                "report_id": "r-2", "report_date": "2026-08-15", "sensor_id": "s",
                "sensor_type": "weather", "location": {"latitude": 100}, "data": {},
            })

    def test_config_path_and_secret_environment_expansion(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "runtime.json"
            path.write_text(json.dumps({"service": {"password": "${TEST_SERVICE_PASSWORD}"}}))
            old_path = os.environ.get("URBAN_SYSTEM_CONFIG")
            old_password = os.environ.get("TEST_SERVICE_PASSWORD")
            try:
                os.environ["URBAN_SYSTEM_CONFIG"] = str(path)
                os.environ["TEST_SERVICE_PASSWORD"] = "test-only-value"
                self.assertEqual(get_config()["service"]["password"], "test-only-value")
            finally:
                if old_path is None:
                    os.environ.pop("URBAN_SYSTEM_CONFIG", None)
                else:
                    os.environ["URBAN_SYSTEM_CONFIG"] = old_path
                if old_password is None:
                    os.environ.pop("TEST_SERVICE_PASSWORD", None)
                else:
                    os.environ["TEST_SERVICE_PASSWORD"] = old_password


if __name__ == "__main__":
    unittest.main()
