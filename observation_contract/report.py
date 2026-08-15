"""Dependency-free validation for the normalized REPORT JSON interchange format."""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime
from typing import Any, Dict, Mapping

REPORT_SCHEMA_VERSION = "1.0"
REQUIRED_FIELDS = ("report_id", "report_date", "sensor_id", "sensor_type", "location", "data")


class ReportValidationError(ValueError):
    """Raised when a producer emits an incompatible normalized report."""


def _valid_timestamp(value: Any) -> bool:
    if not isinstance(value, str) or not value.strip():
        return False
    candidate = value.strip().replace("Z", "+00:00")
    try:
        datetime.fromisoformat(candidate)
        return True
    except ValueError:
        # Existing source timestamps are not uniformly ISO-8601. They remain
        # accepted in v1 as long as a producer supplies a non-empty string.
        return True


def validate_report(report: Mapping[str, Any]) -> None:
    """Validate the stable fields used by SIGMUS, IncidentLens, and benchmarks."""
    if not isinstance(report, Mapping):
        raise ReportValidationError("REPORT must be a JSON object")
    missing = [name for name in REQUIRED_FIELDS if report.get(name) is None]
    if missing:
        raise ReportValidationError("REPORT is missing required field(s): " + ", ".join(missing))
    if not str(report["report_id"]).strip():
        raise ReportValidationError("report_id must be non-empty")
    if not str(report["sensor_id"]).strip() or not str(report["sensor_type"]).strip():
        raise ReportValidationError("sensor_id and sensor_type must be non-empty")
    if not _valid_timestamp(report["report_date"]):
        raise ReportValidationError("report_date must be a non-empty timestamp string")
    location = report["location"]
    if not isinstance(location, Mapping):
        raise ReportValidationError("location must be an object")
    for name, low, high in (("latitude", -90.0, 90.0), ("longitude", -180.0, 180.0)):
        value = location.get(name)
        if value is None:
            continue
        try:
            numeric = float(value)
        except (TypeError, ValueError) as exc:
            raise ReportValidationError(f"location.{name} must be numeric or null") from exc
        if not low <= numeric <= high:
            raise ReportValidationError(f"location.{name} is outside [{low}, {high}]")
    if not isinstance(report["data"], Mapping):
        raise ReportValidationError("data must be an object")
    if report.get("metadata") is not None and not isinstance(report["metadata"], Mapping):
        raise ReportValidationError("metadata must be an object when provided")


def normalize_report(report: Mapping[str, Any]) -> Dict[str, Any]:
    """Return a validated copy carrying an explicit schema version."""
    normalized = deepcopy(dict(report))
    normalized.setdefault("schema_version", REPORT_SCHEMA_VERSION)
    validate_report(normalized)
    return normalized
