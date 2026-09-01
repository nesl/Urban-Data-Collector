# Urban Observations

Urban Observations collects live and daily data for Los Angeles from public
feeds, authenticated APIs, traffic and wildfire cameras, and email alerts. Raw
observations are written to a configurable data directory for use by SIGMUS,
IncidentLens, or other analysis pipelines.

## Requirements

- Enough storage for camera images and daily archives
- Accounts or API keys for PeMS, OpenWeather, PurpleAir, and Gmail
- Docker Engine with the Compose plugin
- Python 3 on the host (standard library only, used by `docker-start` to read JSON)

## Configuration

The deployment reads operator settings and credentials from `config.json`.
Create it by copying `config.example.json`; the file is ignored by Git because
it contains plaintext secrets.

| Field | What to enter | Used by |
|---|---|---|
| `save_folder` | Data directory on the host. Relative paths such as `./data` start at the repository; absolute paths such as `/media/user/External Drive/data` are also supported. | All extractors and the data check |
| `backup_folder` | Archive directory on the host, with the same relative-or-absolute path rules as `save_folder`. | Cleanup and the data check |
| `retention_days` | Number of recent daily data directories to retain locally before cleanup archives older days. Use a positive integer, such as `30`. | `cleanup` |
| `pem_username` | Caltrans PeMS account username. | `pems` |
| `pem_password` | Caltrans PeMS account password. | `pems` |
| `open_weather_map_api_key` | OpenWeather API key. | `weather` |
| `purpleair_api_key` | PurpleAir read API key. | `air` and the sensor-inventory refresh command |
| `email_acc_info.email` | Gmail address that receives X/IFTTT and Citizen messages and sends data-quality alerts. | `twitter-email`, `citizen-email`, and `data-alert` |
| `email_acc_info.password` | Gmail app password for that address, not its normal account password. | Email services and `data-alert` |
| `data_quality_alerts.recipient` | Address that should receive missing-data alerts; it can differ from the ingestion Gmail address. | `data-alert` |

The checked-in weather locations, PurpleAir sensors, and CCTV document are
collector resources rather than configuration fields. Instructions for changing
the PurpleAir inventory appear later in this README.

Docker itself cannot read JSON values while constructing bind mounts. The
included `docker-start` wrapper reads these two fields before invoking Compose,
resolves and creates the directories, and mounts only those exact paths. This
supports external disks and paths containing spaces without exposing all of
`/media`, `/mnt`, or the host filesystem to every container. The wrapper does
not schedule or supervise jobs; Docker Compose still does that work.

## Quick start

Copy the example once, put your accounts and API keys in `config.json`, and
start everything (by everything, we mean all services shown in the below table):

```bash
cp config.example.json config.json
chmod 600 config.json
./docker-start up
```


Compose builds eight dependency-focused images from shared layers and runs ten
independently scheduled containers. Every image inherits the same slim Python
base plus the scheduler and configuration loader; each target then adds only
its collector code and dependencies. The two email services share the email
image, and the two operational services share the operations image. Chromium is
installed only in the ALERTCalifornia image.

| Compose service | Image | Kind | Access mechanism and purpose |
|---|---|---|---|
| `gdelt-gkg` | `urban-data-collector-gdelt` | Extractor | Polls the public GDELT event/GKG HTTP feeds, saves Los Angeles matches, and downloads and parses the webpages referenced by matching GKG rows. |
| `pems` | `urban-data-collector-pems` | Extractor | Signs in to the Caltrans PeMS Clearinghouse and downloads District 7 traffic-station and CHP-incident files. |
| `cctv` | `urban-data-collector-cctv` | Extractor | Scrapes the Caltrans camera stream list and downloads snapshots from Los Angeles County cameras. |
| `alertcalifornia` | `urban-data-collector-alertcalifornia` | Extractor | Uses Chromium browser automation to discover ALERTCalifornia cameras and capture images and locations. |
| `weather` | `urban-data-collector-weather` | Extractor | Calls the OpenWeather API for every coordinate in the checked-in weather inventory. |
| `air` | `urban-data-collector-air` | Extractor | Calls the PurpleAir API for every sensor in the checked-in PurpleAir inventory. |
| `twitter-email` | `urban-data-collector-email` | Extractor | Reads new X/IFTTT notification messages from Gmail over IMAP and stores the raw messages. |
| `citizen-email` | `urban-data-collector-email` | Extractor | Reads new Citizen alert messages from Gmail over IMAP and stores the raw messages. |
| `cleanup` | `urban-data-collector-operations` | Operation | Archives completed data days to the backup directory and removes old local days only after archive validation. |
| `data-alert` | `urban-data-collector-operations` | Operation | Checks that expected daily datasets exist locally or in backup archives and sends a missing-data email over SMTP. |

### Alternative ways to run

If you want to just run a single service (not all of them), start one service or a selected group by putting its service name after `up`:

```bash
./docker-start up air
./docker-start up air weather cctv
```

There is no `.env` file to copy or maintain. `config.json` is ignored by Git and
is the single credential/configuration file. It contains plaintext credentials,
so keep its permissions restricted and never commit it.

Use the wrapper for lifecycle commands so Compose always receives the storage
mounts selected by `config.json`:

```bash
./docker-start ps
./docker-start logs --follow cctv
./docker-start stop cctv
./docker-start down
```

Omit the service after `logs -f` to follow everything. With the example
configuration, Compose stores collected data in `./data`, backups in
`./backups`, and uses `America/Los_Angeles` for schedules. Change the two paths
in `config.json` to choose other relative directories or absolute locations on
the host, including mounted external drives.

## Change collection frequency

Edit the service's `--cron` value in `compose.yaml`, then recreate that service.
Schedules use five-field cron syntax: minute, hour, day of month, month, and day
of week. For example, change the `weather` command from hourly:

```yaml
"--cron", "0 * * * *"
```

to every 30 minutes:

```yaml
"--cron", "*/30 * * * *"
```

Apply the change with `./docker-start up weather`.

Each source is a long-running container with its own APScheduler process. A job
is never run more than once concurrently within its service; failures are logged
and the next scheduled run still occurs. Scheduled times use
`America/Los_Angeles` by default.

The repository already contains the default PurpleAir sensor inventory, so no
initialization command is required before starting the air service. See
"PurpleAir sensor inventory" below when you want to replace that list.

After startup, confirm that the schedulers are running and inspect each source
before relying on unattended collection:

```bash
./docker-start ps
./docker-start logs --tail=50 weather cctv alertcalifornia
find ./data -type f | head
```

The email-backed collectors preserve messages in the ingestion mailbox. Each
stores a stable IMAP UID checkpoint beneath `<save_folder>/.email_state`, so it
processes only mail that arrived after the previous successful run. Test email
credentials using a dedicated mailbox before enabling those services.
`./docker-start up` enables all services; use an explicit service list for a
staged rollout.

Do not start a second scheduler against the same mounted dataset because that
would duplicate collection and could race on the email mailbox.

## Configuration and credentials

Fill the corresponding values directly in `config.json`; use
`config.example.json` as the complete template. Account settings include
`pem_username`, `pem_password`, `open_weather_map_api_key`,
`purpleair_api_key`, `email_acc_info`, and the alert recipient under
`data_quality_alerts`.

Set the destination for missing-data alerts explicitly. It may be the ingestion
mailbox or a different operations address:

```json
"data_quality_alerts": {
  "recipient": "operations@example.com"
}
```

The Gmail password must be an app password, not the normal account password.
The collectors preserve messages and use UID checkpoints to process only new
mail. The alert recipient may be different from the ingestion email address.

The OpenWeather coordinate list, PurpleAir sensor inventory, and
Caltrans CCTV document are application resources. Their stable paths are owned
by the relevant collector/container and do not belong in `config.json`.

## Provider account setup

### PurpleAir

Create a developer account at [PurpleAir Develop](https://develop.purpleair.com/),
create a read API key, and place it in `config.json` as `purpleair_api_key`.
Never commit that file.

With the current 50-sensor hourly inventory, budget approximately 2,500
PurpleAir points per day. A fresh allocation of 1,000,000 free points lasts
about 400 days, or roughly 13 months, at that rate. For the currently deployed
account, set an operational reminder to replace or replenish the account/key in
early May 2027; that date reflects the existing deployment's usage timeline,
not 13 months from a newly created account.

### Caltrans PeMS

[Apply for a PeMS account](https://pems.dot.ca.gov/?dnode=apply), then place the
approved username and password in `pem_username` and `pem_password`. PeMS
indicates that account applications involve manual review, so allow time for a
person to approve the account before testing the extractor.

### OpenWeather

Create an OpenWeather account, generate an API key, and place it in
`open_weather_map_api_key`. The free API currently advertises limits of 60 API
calls per minute and 1,000,000 calls per month. The hourly collector makes one
call per predefined coordinate, so keep the number of entries in
the checked-in OpenWeather location inventory within the account quota. See the
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
in `email_acc_info.password`. Do not use or store the normal Google account
password. Google may revoke app passwords after the Google account password is
changed, in which case generate a replacement and update `config.json`.

### Data-quality alert defaults

Normal installations do not need a `data_quality_alerts` object in
`config.json`. The monitor defaults to Gmail SMTP (`smtp.gmail.com:465`) and the
following expectations:

- A value of `1` means that yesterday's folder/archive must exist.
- A value of `2` means that the folder/archive from two days ago must exist,
  giving the provider one extra publication day.
- Air, ALERTCalifornia, CCTV, GKG, and weather use `1`.
- Both PeMS products use `2` because PeMS publication is delayed.
- Event-driven X/Citizen and disabled noise/seismic are not checked by default.

Set only `data_quality_alerts.recipient` for the standard deployment. Advanced users can
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
The tracked file `extractor_modules/air/nearby_purpleair_sensors.csv` is the
inventory used by default. Because it is part of the repository and Docker
image, a fresh checkout can collect from those sensors immediately. It uses
this format:

```text
sensor_index,latitude,longitude
```

The file has no header. Each row contains a numeric PurpleAir sensor index,
latitude, and longitude.

To replace the inventory, provide a center point and radius. This command reads
`purpleair_api_key` from the current `config.json`, queries PurpleAir for outdoor
sensors, selects up to 50 sensors distributed across the search area, and
overwrites the tracked CSV:

```bash
./docker-start compose run --rm air \
  python -m extractor_modules.air.refresh_sensors \
  --location 34.0549 -118.2426 \
  --radius-km 30 \
  --sensor-count 50
```

The coordinates above are downtown Los Angeles. `--location` takes latitude
then longitude; `--radius-km` must be positive. Review the resulting Git diff
before committing it:

```bash
git diff -- extractor_modules/air/nearby_purpleair_sensors.csv
```

This calls PurpleAir's
[Get Sensors API](https://api.purpleair.com/#api-sensors-get-sensors-data),
selects outdoor sensors around the requested location and writes the same
three-column format consumed by the hourly collector. API calls consume
PurpleAir points. PurpleAir data is subject to its
[Data Licensing requirements](https://www2.purpleair.com/pages/license),
including attribution and distribution restrictions. Confirm that committing
and distributing an updated inventory complies with the terms applicable to
your PurpleAir account.

## Data sources and collection schedule

`compose.yaml` contains the production schedules.

| Source | Data access | Frequency | Output beneath `save_folder` |
|---|---|---:|---|
| GDELT Events/GKG | `http://data.gdeltproject.org/gdeltv2/lastupdate.txt` and the CSV ZIP URLs listed there | every 15 minutes | `gkg/YYYYMMDD/` |
| Caltrans PeMS | Authenticated Clearinghouse downloads from `https://pems.dot.ca.gov`; District 7 `station_5min` and `chp_incidents_day` files | daily at 08:00 | `pem_data_station_5min/YYYYMMDD/`, `pem_data_chp_incidents_day/YYYYMMDD/` |
| Caltrans CCTV | Camera list and streams discovered from `https://cwwp2.dot.ca.gov/vm/streamlist.htm`; LA County cameras | every 15 minutes | `cctv/YYYYMMDD/` |
| ALERTCalifornia | Cameras discovered from `https://cameras.alertcalifornia.org/?pos=33.9639_-118.2898_10`; LA County bounds | every 30 minutes | `alertcalifornia/YYYYMMDD/` |
| OpenWeather | OpenWeather API at the locations in the checked-in weather inventory; includes wind speed and direction | hourly | `weather_data/YYYYMMDD/` |
| PurpleAir | PurpleAir API for the tracked sensor inventory in `extractor_modules/air` | hourly | `air_data/YYYYMMDD/` |
| X notifications | IFTTT email notifications read through `imap.gmail.com` | every 5 minutes | `twitter_data/YYYYMMDD/` |
| Citizen notifications | Registered Citizen alert emails read through `imap.gmail.com` | every 30 minutes | `citizen_data/YYYYMMDD/` |
| Cleanup and backup | Local storage maintenance | daily at 08:00 | archives completed days under `backup_folder` |
| Data completeness alert | Local folders and backup archives; email sent with the ingestion Gmail account | daily at 10:00 | no data output; set `data_quality_alerts.recipient` |

NoiseCapture and SCEDC seismic collector code is included but has no service in
`compose.yaml`, so it is disabled by default. Test it manually and add an
explicit Compose service before enabling it.

The Los Angeles deployment also uses these checked-in inventories:

- `extractor_modules/weather/owm_locations.txt`
- `extractor_modules/air/nearby_purpleair_sensors.csv`
- `extractor_modules/cctv/cctv.kml`
- `extractor_modules/seismic/seismic_stations.txt`

## Collection scope and operator choices

The collectors do not all discover devices in the same way. Some query a
provider for everything in a geographic area, while others depend on an
operator-maintained inventory or a deliberately selected subset.

| Source | How collection scope is chosen | Manual choice or dynamic query |
|---|---|---|
| PurpleAir | The `extractor_modules.air.refresh_sensors` command queries outdoor sensors around the requested `--location` and `--radius-km`, then K-means selects the requested number of geographically distributed sensors and updates the tracked inventory. Hourly collection uses only that saved inventory. | Both. Geographic discovery is automatic, while the search area and sensor count are operator choices and cost controls. |
| OpenWeather | Calls the OpenWeather Current Weather API for the coordinates in `extractor_modules/weather/owm_locations.txt`. | Manual/predefined coordinate inventory. Add or remove locations by editing the inventory. |
| Caltrans CCTV | Queries the Caltrans stream-list page on every run and selects every camera whose county is `Los Angeles`; optional include/exclude lists can narrow it. | Dynamic geographic/administrative query, with optional manual filtering. |
| ALERTCalifornia | Opens the ALERTCalifornia gallery at the configured LA-area map bounds, discovers the cameras currently exposed by the site, and optionally applies include/exclude lists. | Dynamic geographic query, with the map bounds and optional filters chosen by the operator. |
| Caltrans PeMS | Logs into the Clearinghouse and downloads the newest District 7 files for the two configured file types. | Manual district and product selection; file discovery is dynamic. |
| GDELT GKG/events | Downloads the latest GDELT update and retains rows mentioning Los Angeles in the configured location fields. | Dynamic feed query with a hard-coded LA filter. |
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
| OpenWeather | Headerless CSV row per location: `temperature_f`, `detailed_status`, `humidity_percent`, `wind_speed_m_s`, `wind_direction_degrees`. The location name is represented by its parent folder; coordinates come from the checked-in weather inventory. Wind direction is meteorological degrees reported by OpenWeather. |
| Caltrans CCTV | JPEG snapshot. Camera identity is the parent folder and capture time is the filename. County, nearby place, camera name, and image URL are used during discovery but are not repeated inside the JPEG. |
| ALERTCalifornia | JPEG snapshot plus a same-timestamp `.location` text file containing `latitude,longitude,camera_direction`. Camera identity is the parent folder. |
| PeMS station 5-minute | Provider `.txt.gz` file. Rows contain the Caltrans station-observation schema, including timestamp, station/district/freeway/direction/lane type and aggregate/per-lane traffic measurements such as flow, occupancy, and speed. The extractor does not rewrite provider columns. |
| PeMS CHP incidents | Provider `.txt.zip` daily incident product. Incident fields and encoding are retained exactly as published by the PeMS Clearinghouse. |
| GDELT GKG/events | CSV with the original provider columns retained and numbered (`0`, `1`, ...). The extractor writes both filtered GKG and event/export products into `gkg`; rows are filtered for Los Angeles before storage. Each GKG CSV also has a same-stem directory (for example, `20260805070000.gkg/`) containing SHA-256-named raw `.html`, parsed-body `.txt`, and request/parser `.json` files plus `manifest.json`. Parsing uses Newspaper without an LLM. Failed or blocked URLs retain JSON error metadata. |
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
| GDELT GKG/events and article pages | Provider CSVs average about 13 MB/day. Article HTML, parsed text, and metadata add an estimated 0.4 GB/day at roughly 1,170 URLs/day (one live 47-URL interval used 17 MB). | News volume, page size, publisher blocking, and LA matches vary substantially; allow at least 0.5 GB/day. |
| X notifications | typically 5–20 KB on active days | Event-driven; days without matching messages may have no folder. |
| Citizen notifications | typically 4–10 KB in the current sample | Event-driven and dependent on message volume and raw email content. |
| Noise/seismic | insufficient current data for a reliable estimate | Disabled by default; measure after enabling with the intended inventory. |

With the current inventories and GKG article capture, a normal day is expected
to use roughly 0.95–1.25 GB before archive/tar overhead. Thirty local calendar
days therefore require approximately 29–38 GB under present conditions.
Capacity planning should include additional headroom for full camera days,
unusually large news days, and future inventory growth.

The OpenWeather and PurpleAir inventories are part of their collectors. Some LA geographic
bounds are defined in extractor code, so replacing an inventory alone does not
fully retarget the system to another city.

The included `extractor_modules/cctv/cctv.kml` comes from Caltrans' California
Open Data dataset
[Closed Circuit Television](https://data.ca.gov/dataset/closed-circuit-television),
which describes CCTV locations on the State Highway Network and is published
under the Creative Commons Attribution license. Source: California Department
of Transportation (Caltrans).

## Run a service immediately for testing

`docker-start run-now` creates a temporary container with the selected service's
configuration and exact storage mounts. It replaces the normal scheduler with
that service's extractor, so collection starts immediately and the temporary
container exits when finished. It does not wait for the configured cron
frequency.

For example, run CCTV now:

```bash
./docker-start run-now cctv
```

The equivalent commands for all extractors are:

```bash
./docker-start run-now gdelt-gkg
./docker-start run-now pems
./docker-start run-now cctv
./docker-start run-now alertcalifornia
./docker-start run-now weather
./docker-start run-now air
./docker-start run-now twitter-email
./docker-start run-now citizen-email
```

The operational containers can also be tested without changing data or sending
an alert:

```bash
./docker-start run-now cleanup --dry-run
./docker-start run-now data-alert --dry-run
```

These commands contact live services. PeMS, OpenWeather, PurpleAir, and email
collection fail if their corresponding credentials are absent or invalid.
Verify that a new dated directory and output file appear beneath
the configured `save_folder` before relying on its scheduled service.

If the scheduled service is already running, its next run could overlap the
temporary test container. For debugging a collector in isolation, stop and
restart only that service around the test:

```bash
./docker-start stop cctv
./docker-start run-now cctv
./docker-start start cctv
```

## Storage layout

```text
<save_folder>/
├── .email_state/{twitter,citizen}.json
├── air_data/YYYYMMDD/YYYYMMDDHHMMSS.csv
├── alertcalifornia/YYYYMMDD/<camera>/
│   ├── YYYYMMDDHHMMSS.jpg
│   └── YYYYMMDDHHMMSS.location
├── citizen_data/YYYYMMDD/<epoch_ms>.csv
├── cctv/YYYYMMDD/<camera>/YYYYMMDDHHMMSS.jpg
├── gkg/YYYYMMDD/
│   ├── <provider_timestamp>.*.csv
│   └── <provider_timestamp>.gkg/               # article capture for each GKG interval
│       ├── <url_hash>.html
│       ├── <url_hash>.txt
│       ├── <url_hash>.json
│       └── manifest.json
├── noise_planet/YYYYMMDD/                       # if enabled
├── pem_data_chp_incidents_day/YYYYMMDD/*.txt.zip
├── pem_data_station_5min/YYYYMMDD/*.txt.gz
├── seismic/YYYYMMDD/<station>/                  # if enabled
├── twitter_data/YYYYMMDD/<epoch_ms>.csv
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
`email_acc_info` and are sent to `data_quality_alerts.recipient`.

## Troubleshooting

- Check `./docker-start logs <service>` and the modification time of each
  source's newest file.
- If ALERTCalifornia stops after a browser update, rebuild the image so Chromium
  and chromedriver are updated together. For a local installation, ensure their
  versions are compatible.
- GDELT `lastupdate.txt` can lag or point to an incomplete download.
- PeMS daily files may be published late, especially near month boundaries.
- If a container reports a missing credential, confirm the corresponding value
  is present directly in `config.json`.
- If files are written to an unexpected location, check `save_folder` and
  `backup_folder` in `config.json`. Relative paths start at the repository;
  absolute paths are used directly.
- Do not enable HTTP-level debugging in the PeMS client: request tracing can
  include the login form and expose credentials in container logs.

## Tests

```bash
python -m pip install -r requirements/dev.txt
python -m pytest -q
```

Tests remain in the source repository for regression checking but are not copied
into the production container image.
