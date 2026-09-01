import json

from extractor_modules.common.config import get_config


def test_container_paths_override_host_paths(tmp_path, monkeypatch):
    config_path = tmp_path / "config.json"
    config_path.write_text(
        json.dumps({
            "save_folder": "./data",
            "backup_folder": "archives",
            "pem_password": "secret",
        }),
        encoding="utf-8",
    )
    monkeypatch.setenv("URBAN_SAVE_FOLDER", "/data")
    monkeypatch.setenv("URBAN_BACKUP_FOLDER", "/backups")

    config = get_config(config_path)

    assert config["save_folder"] == "/data"
    assert config["backup_folder"] == "/backups"
    assert config["pem_password"] == "secret"



def test_inventory_paths_are_application_owned(tmp_path, monkeypatch):
    config_path = tmp_path / "config.json"
    config_path.write_text(
        json.dumps({
            "save_folder": "collected",
            "owm_locations": "wrong-weather.txt",
            "purpleair_sensors": "wrong-air.csv",
        }),
        encoding="utf-8",
    )
    monkeypatch.delenv("URBAN_OWM_LOCATIONS", raising=False)
    monkeypatch.delenv("URBAN_PURPLEAIR_SENSORS", raising=False)
    monkeypatch.delenv("URBAN_SAVE_FOLDER", raising=False)
    monkeypatch.delenv("URBAN_BACKUP_FOLDER", raising=False)

    config = get_config(config_path)

    assert config["owm_locations"].endswith("extractor_modules/weather/owm_locations.txt")
    assert config["purpleair_sensors"].endswith(
        "extractor_modules/air/nearby_purpleair_sensors.csv"
    )
