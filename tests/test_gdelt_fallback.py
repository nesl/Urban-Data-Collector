from unittest.mock import Mock

import pandas as pd
import requests

from extractor_modules.gdelt import gdelt_extract


def test_latest_available_file_walks_back_after_404(monkeypatch):
    calls = []

    def fake_get_df(url, file_type):
        calls.append((url, file_type))
        if len(calls) < 3:
            response = Mock(status_code=404)
            raise requests.HTTPError(response=response)
        return pd.DataFrame([["available"]])

    monkeypatch.setattr(gdelt_extract, "get_df", fake_get_df)
    url, dataframe = gdelt_extract.get_latest_available_df(
        "http://example/20260831230000.gkg.csv.zip", "zip"
    )

    assert url.endswith("20260831221500.gkg.csv.zip")
    assert dataframe.iloc[0, 0] == "available"


def test_get_df_raises_for_http_failure(monkeypatch):
    response = Mock(content=b"", status_code=404)
    response.raise_for_status.side_effect = requests.HTTPError(response=response)
    monkeypatch.setattr(gdelt_extract.requests, "get", Mock(return_value=response))

    try:
        gdelt_extract.get_df("http://example/missing.zip", "zip")
    except requests.HTTPError as exc:
        assert exc.response.status_code == 404
    else:
        raise AssertionError("expected an HTTPError")
