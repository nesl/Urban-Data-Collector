"""Export a compact, deterministic camera snapshot for the offline simulator."""

from __future__ import annotations

import argparse
from datetime import datetime
import hashlib
import json
from pathlib import Path
import shutil
import xml.etree.ElementTree as ET

from PIL import Image, ImageChops, ImageOps

from extractor_modules.common.config import get_config


def _camera_locations(kml: Path) -> dict[str, tuple[float, float]]:
    root = ET.parse(kml).getroot()
    ns = {"kml": "http://www.opengis.net/kml/2.2"}
    result = {}
    for item in root.findall(".//kml:Placemark", ns):
        name = item.find("kml:name", ns)
        coords = item.find(".//kml:coordinates", ns)
        if name is None or coords is None or not name.text or not coords.text:
            continue
        longitude, latitude, *_ = coords.text.strip().split(",")
        result[name.text.strip()] = (float(latitude), float(longitude))
    return result


def _day(source: Path, requested: str | None) -> Path:
    if requested:
        result = source / requested
        if not result.is_dir():
            raise FileNotFoundError(result)
        return result
    folders = sorted(path for path in source.iterdir() if path.is_dir())
    if not folders:
        raise FileNotFoundError(f"no dated folders below {source}")
    return folders[-1]


def _daytime_image(folder: Path) -> Path | None:
    choices = []
    for path in folder.glob("*.jpg"):
        try:
            stamp = datetime.strptime(path.stem[:14], "%Y%m%d%H%M%S")
        except ValueError:
            continue
        if 10 <= stamp.hour < 14:
            choices.append((abs(stamp.hour * 60 + stamp.minute - 720), path.name, path))
    return min(choices)[2] if choices else None


def _same_image(left: Path, right: Path) -> bool:
    try:
        with Image.open(left) as a, Image.open(right) as b:
            a = a.convert("RGB"); b = b.convert("RGB")
            return a.size == b.size and ImageChops.difference(a, b).getbbox() is None
    except Exception:
        return False


def _write_image(source: Path, destination: Path, max_pixels: int, quality: int) -> dict:
    original = source.read_bytes()
    with Image.open(source) as image:
        image = ImageOps.exif_transpose(image).convert("RGB")
        image.thumbnail((max_pixels, max_pixels), Image.Resampling.LANCZOS)
        destination.parent.mkdir(parents=True, exist_ok=True)
        image.save(destination, "JPEG", quality=quality, optimize=True, progressive=True)
        width, height = image.size
    content = destination.read_bytes()
    return {
        "width": width, "height": height, "bytes": len(content),
        "sha256": hashlib.sha256(content).hexdigest(),
        "original_sha256": hashlib.sha256(original).hexdigest(),
    }


def export(data_root: Path, output: Path, *, day: str | None, max_pixels=640, quality=80) -> dict:
    repository = Path(__file__).resolve().parents[2]
    locations = _camera_locations(repository / "extractor_modules" / "cctv" / "cctv.kml")
    unavailable = repository / "extractor_modules" / "cctv" / "unavailable.jpg"
    records = []

    cctv_day = _day(data_root / "cctv", day)
    alert_day = _day(data_root / "alertcalifornia", day)
    for camera_id, (latitude, longitude) in sorted(locations.items()):
        image = _daytime_image(cctv_day / camera_id)
        if image is None or _same_image(unavailable, image):
            continue
        key = hashlib.sha256(f"cctv\0{camera_id}".encode()).hexdigest()[:16]
        relative = Path("images") / "cctv" / f"{key}.jpg"
        metadata = _write_image(image, output / relative, max_pixels, quality)
        records.append({"source": "cctv", "camera_id": camera_id, "latitude": latitude,
                        "longitude": longitude, "direction": None, "file": str(relative),
                        "source_date": cctv_day.name, **metadata})

    for folder in sorted(path for path in alert_day.iterdir() if path.is_dir()):
        image = _daytime_image(folder)
        location = image.with_suffix(".location") if image else None
        if image is None or location is None or not location.is_file():
            continue
        latitude, longitude, angle = map(float, location.read_text().strip().split(",")[:3])
        bearing = (90 - angle) % 360
        directions = ["North", "Northeast", "East", "Southeast", "South", "Southwest", "West", "Northwest"]
        direction = "Facing " + directions[round(bearing / 45) % 8]
        key = hashlib.sha256(f"alertcalifornia\0{folder.name}".encode()).hexdigest()[:16]
        relative = Path("images") / "alertcalifornia" / f"{key}.jpg"
        metadata = _write_image(image, output / relative, max_pixels, quality)
        records.append({"source": "alertcalifornia", "camera_id": folder.name,
                        "latitude": latitude, "longitude": longitude, "direction": direction,
                        "file": str(relative), "source_date": alert_day.name, **metadata})

    manifest = {"schema_version": "simulator-camera-snapshot.v1", "max_pixels": max_pixels,
                "jpeg_quality": quality, "cameras": records}
    output.mkdir(parents=True, exist_ok=True)
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return manifest


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Export one Git-sized daytime reference per camera")
    parser.add_argument("output", type=Path)
    parser.add_argument("--data-root", type=Path)
    parser.add_argument("--day", help="YYYYMMDD; default: newest available date")
    parser.add_argument("--max-pixels", type=int, default=640)
    parser.add_argument("--jpeg-quality", type=int, default=80)
    args = parser.parse_args(argv)
    config = get_config()
    data_root = args.data_root or Path(config["save_folder"])
    manifest = export(data_root.resolve(), args.output.resolve(), day=args.day,
                      max_pixels=args.max_pixels, quality=args.jpeg_quality)
    print(f"exported {len(manifest['cameras'])} camera references to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
