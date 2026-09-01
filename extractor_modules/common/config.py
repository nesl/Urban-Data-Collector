"""Runtime configuration loading for collectors and operational jobs."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any


def _expand_environment(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: _expand_environment(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_expand_environment(item) for item in value]
    if isinstance(value, str) and value.startswith("${") and value.endswith("}"):
        name = value[2:-1]
        if not name:
            raise ValueError("Empty environment-variable placeholder in configuration")
        try:
            return os.environ[name]
        except KeyError as exc:
            raise RuntimeError(
                f"Required configuration environment variable is not set: {name}"
            ) from exc
    return value


def get_config(filepath: str | os.PathLike[str] | None = None) -> dict[str, Any]:
    """Load operator settings and add application-owned inventory paths."""
    resolved = Path(filepath or os.environ.get("URBAN_SYSTEM_CONFIG", "./config.json"))
    with resolved.open("r", encoding="utf-8") as handle:
        config = _expand_environment(json.load(handle))

    overrides = {
        "save_folder": "URBAN_SAVE_FOLDER",
        "backup_folder": "URBAN_BACKUP_FOLDER",
    }
    for config_key, environment_key in overrides.items():
        if environment_key in os.environ:
            config[config_key] = os.environ[environment_key]

    # These are application resources, not operator/account configuration.
    # Environment overrides let the container use its stable mount locations.
    package_root = Path(__file__).resolve().parents[1]
    config["owm_locations"] = os.environ.get(
        "URBAN_OWM_LOCATIONS", str(package_root / "weather" / "owm_locations.txt")
    )
    config["purpleair_sensors"] = os.environ.get(
        "URBAN_PURPLEAIR_SENSORS",
        str(package_root / "air" / "nearby_purpleair_sensors.csv"),
    )
    return config
