# Urban Observations

Urban Observations collects live and daily data for Los Angeles from public
feeds, authenticated APIs, traffic and wildfire cameras, and email alerts. Raw
observations are written to a configurable data directory for use by SIGMUS,
IncidentLens, or other analysis pipelines.

## Requirements

- Enough storage for camera images and daily archives
- Accounts or API keys for PeMS, OpenWeather, PurpleAir, and Gmail
- Docker Engine with the Compose plugin

## Deployment model

This repository is deployed with Docker Compose only. Each source or operational
job is a long-running container built from the same image. The container runs a
Python APScheduler process, which launches its extractor as a child process at
the five-field schedule declared in `compose.yaml`. There is no cron daemon and
no host crontab to install.

## Installation

Each data source runs as a long-lived service with its own in-container
APScheduler; all services write through the same mounted data and backup
directories.

```bash
cp config.example.json config.json
cp .env.example .env
# Add credentials to .env, then:
docker compose up -d --build
docker compose ps
docker compose logs -f cctv
```

Keep `config.json` and `.env` out of version control and restrict their
permissions because they may contain plaintext credentials:

```bash
chmod 600 config.json .env
```

By default, data is stored in `./pulled_data`, backups in `./backups`, and
scheduled times use `America/Los_Angeles`. Override these without editing
Compose:

```dotenv
TZ=America/Los_Angeles
URBAN_DATA_DIR=/mnt/urban-data/raw
URBAN_BACKUP_DIR=/mnt/urban-backups
URBAN_CONFIG_FILE=./config.json
```

Add those values to `.env` if desired. `URBAN_CONFIG_FILE` may point to an
existing configuration outside this repository. Compose overrides its storage
and inventory paths with the stable container mounts, while leaving credentials
and other settings unchanged. Docker creates the host directories when
the stack starts. For example, a deployment using a shared configuration can be
started without copying its secrets into this repository:

```bash
export URBAN_CONFIG_FILE=/home/user/urban-system/config.json
export URBAN_DATA_DIR=/mnt/urban-data/raw
export URBAN_BACKUP_DIR=/mnt/urban-backups
docker compose up -d --build
```

Schedules are defined only in `compose.yaml`. A job is never run more than once
concurrently within its service; failures are logged and the next scheduled run
still occurs. Inspect all logs with
`docker compose logs -f`, stop with `docker compose down`, and start a subset
with a command such as `docker compose up -d cctv weather`.

The PurpleAir inventory must exist before the scheduled air collector runs.
The Docker example stores it under `/data/.config`, so this one-off command
persists it in the shared data mount:

```bash
docker compose run --rm air python -m extractor_modules.air.air_extract --refresh-sensors
```

After startup, confirm that the schedulers are running and inspect each source
before relying on unattended collection:

```bash
docker compose ps
docker compose logs --tail=50 weather cctv alertcalifornia
find "${URBAN_DATA_DIR:-./pulled_data}" -type f | head
```

The email-backed collectors preserve messages in the ingestion mailbox. Each
stores a stable IMAP UID checkpoint beneath `<save_folder>/.email_state`, so it
processes only mail that arrived after the previous successful run. Test email
credentials using a dedicated mailbox before enabling those services.
`docker compose up -d` enables all services; use an explicit service list for a
staged rollout.

Do not start a second scheduler against the same mounted dataset because that
would duplicate collection and could race on the email mailbox.

## Credentials

Fill in `.env`:

```dotenv
PEMS_USERNAME=your_pems_username
PEMS_PASSWORD=your_pems_password
OPEN_WEATHER_MAP_API_KEY=your_openweather_key
PURPLEAIR_API_KEY=your_purpleair_key
INGEST_EMAIL=collector@example.com
INGEST_EMAIL_PASSWORD=your_gmail_app_password
DATA_ALERT_RECIPIENT=operations@example.com
```

The Gmail password must be an app password, not the normal account password.
The collectors preserve messages and use UID checkpoints to process only new
mail. `DATA_ALERT_RECIPIENT` may be a different address from `INGEST_EMAIL`.

For an interactive run, load the environment and select the configuration:

```bash
set -a
. ./.env
set +a
export URBAN_SYSTEM_CONFIG="$PWD/config.json"
```

`URBAN_SYSTEM_CONFIG` may point to any JSON configuration file. If it is not
set, the code looks for `config.json` in the current directory. Missing
environment variables referenced by the JSON produce an error at startup.

## Provider account setup

### PurpleAir

Create a developer account at [PurpleAir Develop](https://develop.purpleair.com/),
create a read API key, and place it in `.env` as `PURPLEAIR_API_KEY`. The JSON
example resolves this secret at runtime, so the key does not need to be copied
directly into a tracked file. Never commit the key.

With the current 50-sensor hourly inventory, budget approximately 2,500
PurpleAir points per day. A fresh allocation of 1,000,000 free points lasts
about 400 days, or roughly 13 months, at that rate. For the currently deployed
account, set an operational reminder to replace or replenish the account/key in
early May 2027; that date reflects the existing deployment's usage timeline,
not 13 months from a newly created account.

### Caltrans PeMS

[Apply for a PeMS account](https://pems.dot.ca.gov/?dnode=apply), then place the
approved username and password in `PEMS_USERNAME` and `PEMS_PASSWORD`. PeMS
indicates that account applications involve manual review, so allow time for a
person to approve the account before testing the extractor.

### OpenWeather

Create an OpenWeather account, generate an API key, and place it in
`OPEN_WEATHER_MAP_API_KEY`. The free API currently advertises limits of 60 API
calls per minute and 1,000,000 calls per month. The hourly collector makes one
call per predefined coordinate, so keep the number of entries in
`owm_locations` within the account quota. See the
[OpenWeather pricing and limits](https://openweathermap.org/price) before a new
deployment in case the provider changes them.

### IFTTT, X, and Citizen

X and Citizen notification ingestion requires IFTTT Pro for the applets used by
this deployment. Budget approximately $3.49 per month, but verify the current
[IFTTT plan price](https://ifttt.com/plans); pricing and annual-billing discounts
can change.

An IFTTT applet's setup/status screen may continue to display the destination
address captured when the applet was created (for example, an old
`testingemail_...@gmail.com` address). In practice, the Email action sends to
the **Email** field on the current IFTTT account. Check that account field when
changing ingestion mailboxes. It can be different from the address originally
used to sign up for IFTTT.

### Gmail app password

The extractors connect to Gmail through IMAP and the alert monitor sends through
SMTP. Enable 2-Step Verification on the Gmail account, then create a 16-digit
[Google app password](https://support.google.com/mail/answer/185833) and put it
in `INGEST_EMAIL_PASSWORD`. Do not use or store the normal Google account
password. Google may revoke app passwords after the Google account password is
changed, in which case generate a replacement and update `.env`.

### Data-quality alert defaults

Normal installations do not need a `data_quality_alerts` object in
`config.json`. The monitor defaults to Gmail SMTP (`smtp.gmail.com:465`) and the
following expectations:

- A value of `1` means that yesterday's folder/archive must exist.
- A value of `2` means that the folder/archive from two days ago must exist,
  giving the provider one extra publication day.
- Air, ALERTCalifornia, CCTV, GKG, VKG, and weather use `1`.
- Both PeMS products use `2` because PeMS publication is delayed.
- Event-driven X/Citizen and disabled noise/seismic are not checked by default.

Set only `DATA_ALERT_RECIPIENT` for the standard deployment. Advanced users can
override the defaults with an optional configuration object, for example:

```json
{
  "data_quality_alerts": {
    "recipient": "operations@example.com",
    "sources": {"air_data": 1, "pem_data_station_5min": 2}
  }
}
```

When `sources` is supplied it replaces, rather than extends, the built-in source
map. SMTP host and port should be overridden only when using a non-Gmail mail
server.

## Configure notification sources

X and Citizen data arrive through the Gmail account configured above.

### X

Create an IFTTT applet using
[Email new tweets from a specific X user](https://ifttt.com/applets/VFS5xmgc-email-new-tweets-from-a-specific-x-user).
Configure one applet for each X account to monitor and send the messages to the
ingestion mailbox. The extractor recognizes notification senders or subjects
containing `twitter` or `x.com` and stores the original message without
interpreting it. Event and location extraction belongs to downstream ingestion.

### Citizen

Register for the desired location alerts in the Citizen app and have those
alerts delivered to the same ingestion mailbox. The Citizen extractor stores
the original headers and body without parsing them. No Citizen API or OpenAI
credential is required by this repository.

### PurpleAir sensor inventory

PurpleAir observations require a local inventory of sensor IDs and locations.
The tracked file
`extractor_modules/air/nearby_purpleair_sensors.example.csv` contains synthetic
rows that demonstrate the required format:

```text
sensor_index,latitude,longitude
```

The actual file has no header; each row contains a numeric PurpleAir sensor
index followed by its latitude and longitude. The example identifiers and
coordinates are illustrative and must not be used for collection.

Generate it with your own PurpleAir API key before running the air collector:

```bash
python -m extractor_modules.air.air_extract --refresh-sensors
```

This calls PurpleAir's
[Get Sensors API](https://api.purpleair.com/#api-sensors-get-sensors-data),
selects outdoor sensors around Los Angeles, chooses a geographically distributed
subset, and writes the CSV configured by `purpleair_sensors`. API calls consume
PurpleAir points.

The generated CSV is ignored and is not distributed with this repository.
PurpleAir data is subject to its
[Data Licensing requirements](https://www2.purpleair.com/pages/license),
including attribution and distribution restrictions. Each deployment should
obtain the inventory directly from PurpleAir under its own API credentials.

## Data sources and collection schedule

`compose.yaml` contains the production schedules.

| Source | Data access | Frequency | Output beneath `save_folder` |
|---|---|---:|---|
| GDELT Visual KG | `http://data.gdeltproject.org/gdeltv3/vgkg/lastupdate.txt` and the data URL listed there | every minute | `vkg/YYYYMMDD/` |
| GDELT Events/GKG | `http://data.gdeltproject.org/gdeltv2/lastupdate.txt` and the CSV ZIP URLs listed there | every 15 minutes | `gkg/YYYYMMDD/` |
| Caltrans PeMS | Authenticated Clearinghouse downloads from `https://pems.dot.ca.gov`; District 7 `station_5min` and `chp_incidents_day` files | daily at 08:00 | `pem_data_station_5min/YYYYMMDD/`, `pem_data_chp_incidents_day/YYYYMMDD/` |
| Caltrans CCTV | Camera list and streams discovered from `https://cwwp2.dot.ca.gov/vm/streamlist.htm`; LA County cameras | every 15 minutes | `cctv/YYYYMMDD/` |
| ALERTCalifornia | Cameras discovered from `https://cameras.alertcalifornia.org/?pos=33.9639_-118.2898_10`; LA County bounds | every 30 minutes | `alertcalifornia/YYYYMMDD/` |
| OpenWeather | OpenWeather API at the locations listed by `owm_locations`; includes wind speed and direction | hourly | `weather_data/YYYYMMDD/` |
| PurpleAir | PurpleAir API for the outdoor sensors listed by `purpleair_sensors` | hourly | `air_data/YYYYMMDD/` |
| X notifications | IFTTT email notifications read through `imap.gmail.com` | every 5 minutes | `twitter_data/YYYYMMDD/` |
| Citizen notifications | Registered Citizen alert emails read through `imap.gmail.com` | every 30 minutes | `citizen_data/YYYYMMDD/` |
| Cleanup and backup | Local storage maintenance | daily at 08:00 | archives completed days under `backup_folder` |
| Data completeness alert | Local folders and backup archives; email sent with the ingestion Gmail account | daily at 10:00 | no data output; set `DATA_ALERT_RECIPIENT` |

NoiseCapture and SCEDC seismic collector code is included but has no service in
`compose.yaml`, so it is disabled by default. Test it manually and add an
explicit Compose service before enabling it.

The Los Angeles deployment also uses these checked-in inventories:

- `extractor_modules/weather/owm_locations.txt`
- `extractor_modules/air/nearby_purpleair_sensors.example.csv` (synthetic format example)
- `extractor_modules/cctv/cctv.kml`
- `extractor_modules/seismic/seismic_stations.txt`

## Collection scope and operator choices

The collectors do not all discover devices in the same way. Some query a
provider for everything in a geographic area, while others depend on an
operator-maintained inventory or a deliberately selected subset.

| Source | How collection scope is chosen | Manual choice or dynamic query |
|---|---|---|
| PurpleAir | `--refresh-sensors` queries outdoor sensors within 30 km of central Los Angeles, then K-means selects a geographically distributed subset of 50 and writes `purpleair_sensors`. Hourly collection uses only that saved inventory. | Both. Geographic discovery is automatic, but the radius, outdoor-only filter, and 50-sensor limit are deliberate cost controls. Collecting every returned LA-area sensor consumes PurpleAir points too quickly for continuous operation. |
| OpenWeather | Calls the OpenWeather Current Weather API for the coordinates in `owm_locations`. | Manual/predefined coordinate inventory. Add or remove locations by editing the inventory. |
| Caltrans CCTV | Queries the Caltrans stream-list page on every run and selects every camera whose county is `Los Angeles`; optional include/exclude lists can narrow it. | Dynamic geographic/administrative query, with optional manual filtering. |
| ALERTCalifornia | Opens the ALERTCalifornia gallery at the configured LA-area map bounds, discovers the cameras currently exposed by the site, and optionally applies include/exclude lists. | Dynamic geographic query, with the map bounds and optional filters chosen by the operator. |
| Caltrans PeMS | Logs into the Clearinghouse and downloads the newest District 7 files for the two configured file types. | Manual district and product selection; file discovery is dynamic. |
| GDELT GKG/events | Downloads the latest GDELT update and retains rows mentioning Los Angeles in the configured location fields. | Dynamic feed query with a hard-coded LA filter. |
| GDELT Visual KG | Downloads the latest Visual KG update and retains Los Angeles text/geographic matches. | Dynamic feed query with a hard-coded LA bounding box/text filter. |
| X and Citizen | Reads new messages delivered to the configured ingestion mailbox and advances a persistent IMAP UID checkpoint. | Event-driven. The mailbox, notification subscriptions, and subject/content rules define scope. Messages remain in the inbox. |
| Noise and seismic | Use their checked-in station/configuration files when enabled. | Manual inventories; disabled by default. |

Current weather conditions are obtained from the OpenWeather Current Weather
API at predefined geographic coordinates. OpenWeather produces these conditions
using weather models and observational sources including weather stations,
radar, and satellite data.

## Data fields and file formats

Raw provider values are preserved wherever practical. Most CSV files have no
header unless explicitly noted below, so consumers should use the documented
column order rather than infer it from the first record.

| Source | Stored fields/content |
|---|---|
| PurpleAir | Headerless CSV rows: `sensor_index`, `latitude`, `longitude`, `pm2_5`. Each hourly file contains one row per selected sensor. |
| OpenWeather | Headerless CSV row per location: `temperature_f`, `detailed_status`, `humidity_percent`, `wind_speed_m_s`, `wind_direction_degrees`. The location name is represented by its parent folder; coordinates come from `owm_locations`. Wind direction is meteorological degrees reported by OpenWeather. |
| Caltrans CCTV | JPEG snapshot. Camera identity is the parent folder and capture time is the filename. County, nearby place, camera name, and image URL are used during discovery but are not repeated inside the JPEG. |
| ALERTCalifornia | JPEG snapshot plus a same-timestamp `.location` text file containing `latitude,longitude,camera_direction`. Camera identity is the parent folder. |
| PeMS station 5-minute | Provider `.txt.gz` file. Rows contain the Caltrans station-observation schema, including timestamp, station/district/freeway/direction/lane type and aggregate/per-lane traffic measurements such as flow, occupancy, and speed. The extractor does not rewrite provider columns. |
| PeMS CHP incidents | Provider `.txt.zip` daily incident product. Incident fields and encoding are retained exactly as published by the PeMS Clearinghouse. |
| GDELT GKG/events | CSV with the original provider columns retained and numbered (`0`, `1`, ...). The current extractor writes both filtered GKG and event/export products into `gkg`; rows are filtered for Los Angeles before storage. |
| GDELT Visual KG | CSV with the original 12 Visual KG columns retained and numbered `0` through `11`, filtered for Los Angeles text or coordinates. A header-only file means that no rows matched. |
| X notifications | Raw `email_raw.v1` CSV: `schema_version`, `source`, `imap_uid`, `message_id`, `received_at`, `sender`, `subject`, `body`, `ingested_at`. |
| Citizen notifications | The same raw `email_raw.v1` CSV contract. Files are written only when messages are processed. |

Historical X and Citizen folders may contain the older enriched CSV schemas.
Those archives are intentionally not rewritten. SIGMUS and IncidentLens readers
accept both legacy enriched rows and the current raw schema.

## Observed daily storage estimates

These are planning estimates measured from the Los Angeles deployment's local
daily directories on 2026-08-31. They are uncompressed source-directory sizes,
not guaranteed quotas. Partial days, unavailable cameras, news volume, and the
number of incoming emails can change the result substantially.

| Source | Observed daily size | Planning guidance |
|---|---:|---|
| PurpleAir, 50 sensors hourly | about 30 KB | Scales approximately with sensor count and sampling frequency. |
| OpenWeather predefined locations hourly | about 45 KB | Scales with the number of configured coordinates. |
| Caltrans CCTV | about 0.5–0.65 GB on a full day | Largest source; the observed 30-day average was about 536 MB/day, including some partial days. |
| ALERTCalifornia | about 2–48 MB in the available sample | Highly dependent on site availability, discovered cameras, and successful browser runs. |
| PeMS station 5-minute | about 17–19 MB | One compressed District 7 daily file. |
| PeMS CHP incidents | about 0.3–0.45 MB | One compressed daily incident file. |
| GDELT GKG/events | about 13 MB average; roughly 0.4–31 MB observed | News volume and LA matches vary by day. |
| GDELT Visual KG | currently about 4 KB | Recent files were mostly header-only; allow more space when LA records match. |
| X notifications | typically 5–20 KB on active days | Event-driven; days without matching messages may have no folder. |
| Citizen notifications | typically 4–10 KB in the current sample | Event-driven and dependent on message volume and raw email content. |
| Noise/seismic | insufficient current data for a reliable estimate | Disabled by default; measure after enabling with the intended inventory. |

With the current inventories, a normal day is dominated by camera images and is
roughly 0.55–0.75 GB before archive/tar overhead. Thirty local calendar days
therefore require roughly 17–23 GB under present conditions. Capacity planning
should include additional headroom for full camera days and future inventory
growth.

The OpenWeather and generated PurpleAir inventory paths can be changed in
`config.json`. Some LA geographic bounds are defined in the extractor code, so
replacing an inventory alone does not fully retarget the system to another city.

The included `extractor_modules/cctv/cctv.kml` comes from Caltrans' California
Open Data dataset
[Closed Circuit Television](https://data.ca.gov/dataset/closed-circuit-television),
which describes CCTV locations on the State Highway Network and is published
under the Creative Commons Attribution license. Source: California Department
of Transportation (Caltrans).

## Test an extractor manually

Create the configured output directories first:

```bash
mkdir -p /mnt/urban-data/raw /mnt/urban-backups
```

Run one or more collectors as one-off Compose containers from the repository
root:

```bash
docker compose run --rm weather python -m extractor_modules.weather.weather_extract
docker compose run --rm air python -m extractor_modules.air.air_extract
docker compose run --rm cctv python -m extractor_modules.cctv.calcctv_extract
docker compose run --rm twitter-email python -m extractor_modules.email.generate_csv --scheduled
docker compose run --rm citizen-email python -m extractor_modules.email.citizen_scrape
```

These commands contact live services. PeMS, OpenWeather, PurpleAir, and email
collection fail if their corresponding credentials are absent or invalid.
Verify that a new dated directory and output file appear beneath
`${URBAN_DATA_DIR:-./pulled_data}` before relying on its scheduled service.

## Storage layout

```text
<save_folder>/
├── .config/nearby_purpleair_sensors.csv
├── .email_state/{twitter,citizen}.json
├── air_data/YYYYMMDD/YYYYMMDDHHMMSS.csv
├── alertcalifornia/YYYYMMDD/<camera>/
│   ├── YYYYMMDDHHMMSS.jpg
│   └── YYYYMMDDHHMMSS.location
├── citizen_data/YYYYMMDD/<epoch_ms>.csv
├── cctv/YYYYMMDD/<camera>/YYYYMMDDHHMMSS.jpg
├── gkg/YYYYMMDD/<provider_timestamp>.*.csv
├── noise_planet/YYYYMMDD/                       # if enabled
├── pem_data_chp_incidents_day/YYYYMMDD/*.txt.zip
├── pem_data_station_5min/YYYYMMDD/*.txt.gz
├── seismic/YYYYMMDD/<station>/                  # if enabled
├── twitter_data/YYYYMMDD/<epoch_ms>.csv
├── vkg/YYYYMMDD/<provider_timestamp>.vgkg.v3.csv
└── weather_data/YYYYMMDD/<location>/YYYYMMDDHHMMSS.csv

<backup_folder>/
└── raw/
    ├── air_data/YYYYMMDD.tar
    ├── cctv/YYYYMMDD.tar
    ├── weather_data/YYYYMMDD.tar
    └── <each-other-source>/YYYYMMDD.tar
```

The intended production configuration places `backup_folder` on the external
drive. Every completed date for every source is pushed there as
`<backup_folder>/raw/<source>/YYYYMMDD.tar`; archives are retained on the
external drive indefinitely unless an operator applies a separate archive
retention policy. The current day is deliberately not archived while collectors
may still be writing it, and is pushed during the next daily cleanup.

The local disk retains `retention_days` calendar days, including today (30 by
default). Once a local date is older than that window, it is deleted only after
its external archive has been created and validated. Existing archives are
refreshed when their source day changes. Today's directory and non-date entries
such as `.config` and `.email_state` are never cleanup candidates. If the
external drive is absent, read-only, or an archive cannot be validated, cleanup
fails safely before deleting any unverified local data.

Before enabling automatic cleanup in either deployment mode, preview the plan
and validate existing archives without changing data:

```bash
python -m extractor_modules.operations.archive --dry-run
```

Use `--max-days N` for a one-time retention override. During a real run, new
archives are written to temporary files, validated, and atomically renamed. The
deletion phase starts only after every completed day has a readable archive. If
any archive fails, the command exits nonzero before deleting raw directories.
On an existing installation, the first successful run may need substantial
temporary and backup capacity; review the dry-run summary and available space
before running without `--dry-run`.

The 10:00 completeness monitor checks both local date folders and archives,
because cleanup may already have moved yesterday off local storage. Continuous
feeds are expected through yesterday; PeMS receives one additional day of
publication grace. Twitter, Citizen, noise, and seismic are excluded by default
because they are event-driven or disabled. Alerts authenticate to Gmail using
`email_acc_info` and are sent to `DATA_ALERT_RECIPIENT` (or
`data_quality_alerts.recipient`).

## Troubleshooting

- Check `docker compose logs <service>` and the modification time of each
  source's newest file.
- If ALERTCalifornia stops after a browser update, rebuild the image so Chromium
  and chromedriver are updated together. For a local installation, ensure their
  versions are compatible.
- GDELT `lastupdate.txt` can lag or point to an incomplete download.
- PeMS daily files may be published late, especially near month boundaries.
- If a container reports a missing credential, confirm `.env` uses plain
  `NAME=value` assignments and that `URBAN_CONFIG_FILE` points to a readable
  configuration file.
- If files are written to an unexpected location, use absolute paths in
  `config.json` and confirm `URBAN_SYSTEM_CONFIG` points to that file.
- Do not enable HTTP-level debugging in the PeMS client: request tracing can
  include the login form and expose credentials in container logs.

## Tests

```bash
python -m pip install -r requirements-dev.txt
python -m pytest -q
```

Tests remain in the source repository for regression checking but are not copied
into the production container image.
