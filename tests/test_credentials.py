from pathlib import Path


def test_pems_http_debugging_is_disabled():
    source = Path("extractor_modules/pems/pems_extract.py").read_text(encoding="utf-8")
    assert "debug=True" not in source
