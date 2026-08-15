import time
import socket
try:
    from apscheduler.schedulers.background import BackgroundScheduler
except ImportError:  # Keep config parsing/import checks usable in minimal environments.
    BackgroundScheduler = None
import json
import shutil
import os
from pathlib import Path

from extractor_modules.scheduling import apply_scheduling, parse_source_data

# Extractor modules
from extractor_modules.cctv.calcctv_extract import pull_data as pull_data_cctv
from extractor_modules.alertcalifornia.alertcalifornia_extract import pull_data as pull_data_alertcalifornia
from extractor_modules.air.air_extract import pull_data as pull_data_air_quality
from extractor_modules.weather.weather_extract import pull_data as pull_data_weather
from extractor_modules.gdelt.gdelt_extract import pull_data as pull_data_gdelt
from extractor_modules.pems.pems_extract import pull_data as pull_data_pems
from extractor_modules.email.generate_csv import pull_data as pull_data_twitter
from extractor_modules.email.citizen_scrape import pull_data as pull_data_citizen
from extractor_modules.clean_daily_data import delete_old_data


# MCP servers
from extractor_modules.setup_extractors_and_mcp import setup_mcp_servers

# Current config
current_config = {}


def test_func(p1, p2):
    return None


# Given the config data, parse for each source and call appropriate functions
def schedule_all_sources(scheduler, current_config_filepath):
    global current_config

    # Open the current config, load the data
    with open(current_config_filepath, "r") as f:
        config_data = json.load(f)

    # print([job.id for job in scheduler.get_jobs()])
   
   # Iterate through all keys in the config data
    for source, details in config_data.items():
        
        # Parse the details
        config_params = parse_source_data(details, source)

        # Update the current config if necessary
        if source not in current_config:
            current_config[source] = {}
        
        if source == "cctv":
            apply_scheduling(pull_data_cctv, config_params, scheduler, source)
        elif source == "alertcalifornia":
            apply_scheduling(pull_data_alertcalifornia, config_params, scheduler, source)
        elif source == "air_quality":
            apply_scheduling(pull_data_air_quality, config_params, scheduler, source)
        elif source == "weather":
            apply_scheduling(pull_data_weather, config_params, scheduler, source)
        elif source == "gdelt":
            apply_scheduling(pull_data_gdelt, config_params, scheduler, source)
        elif source == "pems":
            apply_scheduling(pull_data_pems, config_params, scheduler, source)
        elif source == "twitter":
            apply_scheduling(pull_data_twitter, config_params, scheduler, source)
        elif source == "citizen":
            apply_scheduling(pull_data_citizen, config_params, scheduler, source)
        elif source == "deletion":
            apply_scheduling(delete_old_data, config_params, scheduler, source)
            
            
        

if __name__ == "__main__":
    if BackgroundScheduler is None:
        raise RuntimeError("Extractor scheduling requires APScheduler; install requirements.txt")

    # Open our configs
    config_dir = Path(__file__).resolve().parent / "config"
    default_config_filepath = config_dir / "default.json"
    current_config_filepath = config_dir / "current.json"

    # If the current doesn't exist, copy it from the default
    if not os.path.exists(current_config_filepath):
        shutil.copy(default_config_filepath, current_config_filepath)

    # Set up scheduler
    scheduler = BackgroundScheduler()

    # Parse all sources on a regular interval
    scheduler.add_job(schedule_all_sources, "interval", seconds=5, id="schedule_all", args=[scheduler, current_config_filepath])
    scheduler.start()

    # Now set up the MCP servers
    setup_mcp_servers()
    
