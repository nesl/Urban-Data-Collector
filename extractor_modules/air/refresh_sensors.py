"""Regenerate the tracked PurpleAir sensor inventory for a geographic area."""

from __future__ import annotations

import argparse
import asyncio

from aiopurpleair import API

from extractor_modules.air.air_extract import get_nearby_sensors
from extractor_modules.common.config import get_config


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--location",
        nargs=2,
        required=True,
        type=float,
        metavar=("LATITUDE", "LONGITUDE"),
        help="latitude and longitude of the search center",
    )
    parser.add_argument(
        "--radius-km", required=True, type=float, help="positive search radius"
    )
    parser.add_argument(
        "--sensor-count",
        type=int,
        default=50,
        help="maximum geographically distributed sensors to save (default: 50)",
    )
    args = parser.parse_args(argv)

    latitude, longitude = args.location
    if not -90 <= latitude <= 90:
        parser.error("latitude must be between -90 and 90")
    if not -180 <= longitude <= 180:
        parser.error("longitude must be between -180 and 180")
    if args.radius_km <= 0:
        parser.error("--radius-km must be greater than zero")
    if args.sensor_count < 1:
        parser.error("--sensor-count must be at least 1")

    config = get_config()
    output_file = config["purpleair_sensors"]
    api = API(config["purpleair_api_key"])
    asyncio.run(
        get_nearby_sensors(
            api,
            output_file,
            latitude,
            longitude,
            args.radius_km,
            args.sensor_count,
        )
    )
    print(f"PurpleAir sensor inventory written to {output_file}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
