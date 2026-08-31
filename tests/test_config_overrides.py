import json

from extractor_modules.common.config import get_config


def test_container_paths_can_override_host_paths(tmp_path, monkeypatch):
    config_path = tmp_path / "config.json"
    config_path.write_text(
        json.dumps({"save_folder": "/host/data", "pem_password": "secret"}),
        encoding="utf-8",
    )
    monkeypatch.setenv("URBAN_SAVE_FOLDER", "/data")

    config = get_config(config_path)

    assert config["save_folder"] == "/data"
    assert config["pem_password"] == "secret"
