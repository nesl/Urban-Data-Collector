"""Download and deterministically parse webpages referenced by GDELT GKG rows."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
import hashlib
import json
from pathlib import Path
import re
from typing import Iterable

from newspaper import Article
import requests


URL_COLUMN = 4
USER_AGENT = "urban-observations/0.1 (GDELT research collector)"


def _article_id(url: str) -> str:
    """Return a stable, filesystem-safe identifier without leaking URL details."""
    return hashlib.sha256(url.encode("utf-8")).hexdigest()[:24]


def _write_json(path: Path, value: dict) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


def download_article(url: str, output_dir: Path, timeout: int = 20) -> dict:
    """Save raw HTML, parsed text, and metadata for one URL.

    Network and parsing errors are returned and persisted instead of raised so a
    blocked or malformed publisher page cannot abort the GDELT interval.
    """
    article_id = _article_id(url)
    metadata_path = output_dir / f"{article_id}.json"
    result = {"url": url, "article_id": article_id, "status": "failed"}

    try:
        response = requests.get(
            url,
            headers={"User-Agent": USER_AGENT, "Accept": "text/html,application/xhtml+xml"},
            timeout=timeout,
        )
        result.update(
            http_status=response.status_code,
            final_url=response.url,
            content_type=response.headers.get("content-type", ""),
        )
        response.raise_for_status()
        if "html" not in result["content_type"].lower():
            raise ValueError(f"unsupported content type: {result['content_type'] or 'unknown'}")

        html = response.text
        (output_dir / f"{article_id}.html").write_text(html, encoding="utf-8")

        article = Article(response.url)
        article.download(input_html=html)
        article.parse()
        text = re.sub(r"\n{3,}", "\n\n", article.text).strip()
        if not text:
            raise ValueError("article parser returned no body text")
        (output_dir / f"{article_id}.txt").write_text(text + "\n", encoding="utf-8")
        result.update(
            status="ok",
            title=article.title,
            authors=article.authors,
            publish_date=article.publish_date.isoformat() if article.publish_date else None,
            text_characters=len(text),
        )
    except Exception as exc:  # each URL must leave a durable failure record
        result.update(error_type=type(exc).__name__, error=str(exc))

    _write_json(metadata_path, result)
    return result


def download_gkg_articles(
    dataframe,
    gkg_csv_path: Path,
    *,
    max_workers: int = 4,
    timeout: int = 20,
) -> dict:
    """Download unique GKG document URLs beside an interval CSV.

    For ``20260805070000.gkg.csv`` output is stored under the sibling directory
    ``20260805070000.gkg/``. Existing success records make reruns resumable.
    """
    output_dir = gkg_csv_path.with_suffix("")
    output_dir.mkdir(parents=True, exist_ok=True)
    urls: Iterable[str] = dataframe.get(URL_COLUMN, dataframe.get(str(URL_COLUMN), []))
    unique_urls = sorted({str(url).strip() for url in urls if str(url).startswith(("http://", "https://"))})

    pending = []
    skipped = 0
    for url in unique_urls:
        metadata_path = output_dir / f"{_article_id(url)}.json"
        if metadata_path.exists():
            try:
                if json.loads(metadata_path.read_text(encoding="utf-8")).get("status") == "ok":
                    skipped += 1
                    continue
            except (OSError, json.JSONDecodeError):
                pass
        pending.append(url)

    results = []
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(download_article, url, output_dir, timeout): url for url in pending}
        for future in as_completed(futures):
            results.append(future.result())

    summary = {
        "gkg_csv": gkg_csv_path.name,
        "unique_urls": len(unique_urls),
        "attempted": len(results),
        "succeeded": sum(item["status"] == "ok" for item in results),
        "failed": sum(item["status"] != "ok" for item in results),
        "previously_succeeded": skipped,
    }
    _write_json(output_dir / "manifest.json", summary)
    return summary
