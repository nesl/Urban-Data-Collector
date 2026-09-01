import json
from pathlib import Path
from unittest.mock import Mock

import pandas as pd

from extractor_modules.gdelt import article_download


def test_interval_folder_and_manifest_are_named_from_gkg_csv(tmp_path, monkeypatch):
    frame = pd.DataFrame({4: ["https://example.com/a", "https://example.com/a"]})
    csv_path = tmp_path / "20260805070000.gkg.csv"

    def fake_download(url, output_dir, timeout):
        result = {"url": url, "status": "ok"}
        (output_dir / "fake.json").write_text(json.dumps(result))
        return result

    monkeypatch.setattr(article_download, "download_article", fake_download)
    summary = article_download.download_gkg_articles(frame, csv_path, max_workers=1)

    output_dir = tmp_path / "20260805070000.gkg"
    assert output_dir.is_dir()
    assert summary["unique_urls"] == 1
    assert summary["succeeded"] == 1
    assert json.loads((output_dir / "manifest.json").read_text())["gkg_csv"] == csv_path.name


def test_download_article_saves_html_text_and_metadata(tmp_path, monkeypatch):
    response = Mock(
        status_code=200,
        url="https://example.com/final",
        text="<html><article><h1>Title</h1><p>Body text.</p></article></html>",
        headers={"content-type": "text/html; charset=utf-8"},
    )
    response.raise_for_status.return_value = None
    monkeypatch.setattr(article_download.requests, "get", Mock(return_value=response))

    parsed = Mock(title="Title", authors=["Author"], publish_date=None, text="Body text.")
    monkeypatch.setattr(article_download, "Article", Mock(return_value=parsed))
    result = article_download.download_article("https://example.com/a", tmp_path)

    assert result["status"] == "ok"
    assert (tmp_path / f"{result['article_id']}.html").exists()
    assert (tmp_path / f"{result['article_id']}.txt").read_text() == "Body text.\n"
    assert json.loads((tmp_path / f"{result['article_id']}.json").read_text())["title"] == "Title"
