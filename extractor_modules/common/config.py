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
    """Load the selected JSON configuration and apply container path overrides."""
    resolved = Path(filepath or os.environ.get("URBAN_SYSTEM_CONFIG", "./config.json"))
    with resolved.open("r", encoding="utf-8") as handle:
        config = _expand_environment(json.load(handle))

    overrides = {
        "save_folder": "URBAN_SAVE_FOLDER",
        "backup_folder": "URBAN_BACKUP_FOLDER",
        "owm_locations": "URBAN_OWM_LOCATIONS",
        "purpleair_sensors": "URBAN_PURPLEAIR_SENSORS",
        "cctv_locations": "URBAN_CCTV_LOCATIONS",
    }
    for config_key, environment_key in overrides.items():
        if environment_key in os.environ:
            config[config_key] = os.environ[environment_key]
    return config
