# Urban Observations

Urban Observations collects live and daily data for Los Angeles from public
feeds, authenticated APIs, traffic and wildfire cameras, and email alerts. Raw
observations are written to a configurable data directory for use by SIGMUS,
IncidentLens, or other analysis pipelines.

## Requirements

- Enough storage for camera images and daily archives
- Accounts or API keys for PeMS, OpenWeather, PurpleAir, OpenAI, and Gmail
- Docker Engine with the Compose plugin for the recommended deployment
- For the legacy non-Docker deployment: Python 3.10+, cron, Chromium, and a
  compatible chromedriver

## Choose one deployment mode

The repository supports two alternative ways to run the same collectors. Do
not run both on one dataset.

| Mode | Scheduling | Host setup | Intended use |
|---|---|---|---|
| Docker Compose (recommended) | APScheduler inside each source container | Docker only; no host crontab | New and production deployments |
| Local Python + cron | Host `crontab` invokes the virtual environment | Python, browser dependencies, and cron | Existing non-Docker deployments |

The Docker services do not run cron. Their scheduler accepts familiar
five-field cron expressions, but it runs as Python inside each container. The
checked-in `cron_jobs` file is used only by the local Python deployment.

## Installation

### Docker Compose (recommended)

Docker Compose replaces both the Python virtual environment and host cron. Each
data source runs as a long-lived service with its own in-container APScheduler;
all services write through the same mounted data and backup directories.

```bash
cp config.docker.example.json config.json
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

Docker schedules are defined directly in `compose.yaml`; Docker does not read
the `cron_jobs` file. The two files currently use equivalent timings for their
respective deployment modes. A job is never run more than once concurrently
within its service; failures are logged and the next scheduled run still
occurs. Inspect all logs with
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

The email-backed X collector runs with `--delete`: successfully processed
messages are deleted from the ingestion mailbox. Test email credentials using a
dedicated mailbox before enabling that service. `docker compose up -d` enables
all services; use an explicit service list for a staged rollout.

Do not install `cron_jobs` or start `extractor_scheduler` alongside Compose,
because that would duplicate collection and could race on the email mailbox.

### Local Python and cron (legacy alternative)

```bash
git clone <repository-url> urban-observations
cd urban-observations
python -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
cp config.example.json config.json
cp .env.example .env
chmod 600 config.json .env
```

Edit `config.json` and choose storage locations. Absolute paths are recommended
for scheduled deployments:

```json
{
  "save_folder": "/mnt/urban-data/raw",
  "backup_folder": "/mnt/urban-backups",
  "retention_days": 30,
  "owm_locations": "./extractor_modules/weather/owm_locations.txt",
  "purpleair_sensors": "./extractor_modules/air/nearby_purpleair_sensors.csv"
}
```

Keep the remaining credential placeholders from `config.example.json`. They are
resolved from `.env` when an extractor starts. Do not commit `config.json` or
`.env`; both are ignored by Git.

## Credentials

Fill in `.env`:

```dotenv
PEMS_USERNAME=your_pems_username
PEMS_PASSWORD=your_pems_password
OPEN_WEATHER_MAP_API_KEY=your_openweather_key
PURPLEAIR_API_KEY=your_purpleair_key
OPENAI_API_KEY=your_openai_key
INGEST_EMAIL=collector@example.com
INGEST_EMAIL_PASSWORD=your_gmail_app_password
```

The Gmail password should be an app password, not the normal account password.
Use a dedicated ingestion mailbox because successfully processed notification
messages are deleted.

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

## Configure notification sources

X and Citizen data arrive through the Gmail account configured above.

### X

Create an IFTTT applet using
[Email new tweets from a specific X user](https://ifttt.com/applets/VFS5xmgc-email-new-tweets-from-a-specific-x-user).
Configure one applet for each X account to monitor and send the messages to the
ingestion mailbox. The extractor recognizes notification subjects containing
`twitter` and uses the configured OpenAI key to extract the author, incident
type, location, time, and message text.

### Citizen

Register for the desired location alerts in the Citizen app and have those
alerts delivered to the same ingestion mailbox. The Citizen extractor reads and
parses those alert emails. No Citizen API credential is required by this
repository.

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

`compose.yaml` and `cron_jobs` contain equivalent default schedules for their
respective deployment methods.

| Source | Data access | Frequency | Output beneath `save_folder` |
|---|---|---:|---|
| GDELT Visual KG | `http://data.gdeltproject.org/gdeltv3/vgkg/lastupdate.txt` and the data URL listed there | every minute | `vkg/YYYYMMDD/` |
| GDELT Events/GKG | `http://data.gdeltproject.org/gdeltv2/lastupdate.txt` and the CSV ZIP URLs listed there | every 15 minutes | `gkg/YYYYMMDD/` |
| Caltrans PeMS | Authenticated Clearinghouse downloads from `https://pems.dot.ca.gov`; District 7 `station_5min` and `chp_incidents_day` files | daily at 08:00 | `pem_data_station_5min/YYYYMMDD/`, `pem_data_chp_incidents_day/YYYYMMDD/` |
| Caltrans CCTV | Camera list and streams discovered from `https://cwwp2.dot.ca.gov/vm/streamlist.htm`; LA County cameras | every 15 minutes | `cctv/YYYYMMDD/` |
| ALERTCalifornia | Cameras discovered from `https://cameras.alertcalifornia.org/?pos=33.9639_-118.2898_10`; LA County bounds | every 30 minutes | `alertcalifornia/YYYYMMDD/` |
| OpenWeather | OpenWeather API at the locations listed by `owm_locations` | hourly | `weather_data/YYYYMMDD/` |
| PurpleAir | PurpleAir API for the outdoor sensors listed by `purpleair_sensors` | hourly | `air_data/YYYYMMDD/` |
| X notifications | IFTTT email notifications read through `imap.gmail.com` | every 5 minutes | `twitter_data/YYYYMMDD/` |
| Citizen notifications | Registered Citizen alert emails read through `imap.gmail.com` | every 30 minutes | `citizen_data/YYYYMMDD/` |
| Cleanup and backup | Local storage maintenance | daily at 08:00 | archives completed days under `backup_folder` |

NoiseCapture and SCEDC seismic collectors are included but disabled in
`cron_jobs` by default. Their commented entries run daily at 03:30 and 08:00,
respectively. Test them manually before enabling them.

The Los Angeles deployment also uses these checked-in inventories:

- `extractor_modules/weather/owm_locations.txt`
- `extractor_modules/air/nearby_purpleair_sensors.example.csv` (synthetic format example)
- `extractor_modules/cctv/cctv.kml`
- `extractor_modules/seismic/seismic_stations.txt`

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

Then run one or more collectors from the repository root:

```bash
python -m extractor_modules.weather.weather_extract
python -m extractor_modules.air.air_extract
python -m extractor_modules.cctv.calcctv_extract
python -m extractor_modules.email.generate_csv --scheduled --delete
python -m extractor_modules.email.citizen_scrape
```

These commands contact live services. PeMS, OpenWeather, PurpleAir, and email
collection fail if their corresponding credentials are absent or invalid.
Verify that a new dated directory and output file appear under `save_folder`
before installing the schedule.

## Install the cron schedule (local Python mode only)

Open `cron_jobs` and replace the three `/ABSOLUTE/PATH/...` values at the top:

```cron
URBAN_OBSERVATIONS_ROOT=/opt/urban-observations
URBAN_SYSTEM_CONFIG=/opt/urban-observations/config.json
URBAN_ENV_FILE=/opt/urban-observations/.env
```

Install and inspect the schedule:

```bash
crontab cron_jobs
crontab -l
tail -f cron.log
```

Each cron entry calls `scripts/run_scheduled.sh`. The wrapper loads `.env`,
exports its variables, changes to the repository root, and runs the virtual
environment's Python interpreter. This is necessary because cron does not
normally load the user's interactive shell configuration.

The wrapper uses `.venv/bin/python` by default. Set `URBAN_PYTHON` in
`cron_jobs` only when intentionally using a virtual environment stored
elsewhere; it must be an absolute path to an executable Python interpreter.

Do not run the cron schedule and the in-process scheduler simultaneously; doing
so downloads duplicate observations and can process the same mailbox
concurrently.

## Advanced alternative: single-process scheduler

This is retained for integrations that use the extractor MCP services. It is
not part of the Docker Compose deployment. Instead of cron, the local extractors
can be scheduled by one long-running process:

```bash
python -m extractor_modules.extractor_scheduler
```

Its runtime schedule is stored in the ignored file
`extractor_modules/config/current.json`. On first launch it is created from the
checked-in `extractor_modules/config/default.json`. The process reloads changes
every five seconds and also starts the extractor MCP services. Run it under a
process supervisor such as systemd.

## Storage layout

```text
<save_folder>/
├── air_data/YYYYMMDD/
├── alertcalifornia/YYYYMMDD/
├── citizen_data/YYYYMMDD/
├── cctv/YYYYMMDD/
├── gkg/YYYYMMDD/
├── noise_planet/YYYYMMDD/            # if enabled
├── pem_data_chp_incidents_day/YYYYMMDD/
├── pem_data_station_5min/YYYYMMDD/
├── seismic/YYYYMMDD/<station>/        # if enabled
├── twitter_data/YYYYMMDD/
├── vkg/YYYYMMDD/
└── weather_data/YYYYMMDD/
```

The daily cleanup job archives every completed `YYYYMMDD` directory beneath
`<backup_folder>/raw/<source>/` and retains exactly `retention_days` completed
days locally for each source. Today's directory and non-date entries are never
cleanup candidates. Use separate storage for `backup_folder` if it is intended
to protect against a disk failure.

Before enabling automatic cleanup in either deployment mode, preview the plan
and validate existing archives without changing data:

```bash
python -m extractor_modules.clean_daily_data --dry-run
```

Use `--max-days N` for a one-time retention override. During a real run, new
archives are written to temporary files, validated, and atomically renamed. The
deletion phase starts only after every completed day has a readable archive. If
any archive fails, the command exits nonzero before deleting raw directories.
On an existing installation, the first successful run may need substantial
temporary and backup capacity; review the dry-run summary and available space
before running without `--dry-run`.

## Troubleshooting

- Check `cron.log` and the modification time of each source's newest file.
- If ALERTCalifornia stops after a browser update, rebuild the image so Chromium
  and chromedriver are updated together. For a local installation, ensure their
  versions are compatible.
- GDELT `lastupdate.txt` can lag or point to an incomplete download.
- PeMS daily files may be published late, especially near month boundaries.
- If cron reports a missing credential, confirm `URBAN_ENV_FILE` is an absolute,
  readable path and that `.env` uses plain `NAME=value` assignments.
- If files are written to an unexpected location, use absolute paths in
  `config.json` and confirm `URBAN_SYSTEM_CONFIG` points to that file.
- Do not enable HTTP-level debugging in the PeMS client: request tracing can
  include the login form and expose credentials in `cron.log`.

## Tests

```bash
python -m pytest -q
```
