import os
import math
from typing import Tuple, List
from pydantic import BaseModel



# Import data source specific features
from extractor_modules.cctv.calcctv_extract import obtain_all_sensor_locations as get_cctv_locations
from extractor_modules.alertcalifornia.alertcalifornia_extract import get_camera_locations as get_alertcalifornia_locations
from extractor_modules.air.air_extract import obtain_all_sensor_locations as get_air_locations
from extractor_modules.weather.weather_extract import obtain_all_sensor_locations as get_owm_locations

# Type class used for Pydantic, specific to our tools
class Location(BaseModel):
    latitude: float
    longitude: float


# MCP server stuff
import json
from fastmcp import FastMCP

mcp = FastMCP(name="Data Extractor MCP")


# Geo utilities
def haversine_distance(lat1, lon1, lat2, lon2):
    """
    Compute great-circle distance between two points on Earth (in km).
    """
    R = 6371.0  # Earth radius in kilometers
    
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    
    a = math.sin(dphi/2)**2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda/2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    
    return R * c


@mcp.tool(
    name="add_nums",           # Custom tool name for the LLM
    description="A simple tool that adds two numbers together" # Custom description
)
def add_nums(a: float, b: float) -> float:
    "this is just a a test tool for MCP"
    return a + b

@mcp.tool(
    name="get_sensors_within_radius",           # Custom tool name for the LLM
    description="Takes in a target latitude and longitude value, a radius k in km, and a data source from the list of [cctv, alertcalifornia, air_quality, weather].  'cctv' sensors are highway cameras taking images around California.  'alertcalifornia' sensors are wildfire cameras positioned around various remote and urban areas in California.  'air_quality' measure PM2.5 from outdoor sensors around Los Angeles.  'weather' measures temperature, wind speed, humidity, and general weather descriptors from cities around Los Angeles.  This function returns all sensors within the radius of the target for the particular data source."
)
def get_within_radius(target: Location, k: float, data_source: str) -> List[str]:
    """
    Given target=(lat, lon), a data source type, ...],
    and radius k (km), return sublist of coords within k.
    """

    # Use the data source to identify the list of sensor coordinates
    coords = None
    if data_source == "cctv":
        coords = get_cctv_locations()
    elif data_source == "alertcalifornia":
        coords = get_alertcalifornia_locations()
    elif data_source == "air_quality":
        coords = get_air_locations()
    elif data_source == "weather":
        coords = get_owm_locations()
    else:
        raise ValueError(f"Unsupported data source: {data_source}")

    lat_t, lon_t = target.latitude, target.longitude
    close_sensors = []
    for sensor_id in coords.keys():
        lat, lon = coords[sensor_id]
        
        d = haversine_distance(lat_t, lon_t, lat, lon)
        
        if d <= k:
            close_sensors.append(str(sensor_id))
    return close_sensors

@mcp.tool(
    name="get_sensors_within_box",           # Custom tool name for the LLM
    description="Takes in a minimum and maximum latitude and longitude value, and a data source from the list of [cctv, alertcalifornia, air_quality, weather].  'cctv' sensors are highway cameras taking images around California.  'alertcalifornia' sensors are wildfire cameras positioned around various remote and urban areas in California.  'air_quality' measure PM2.5 from outdoor sensors around Los Angeles.  'weather' measures temperature, wind speed, humidity, and general weather descriptors from cities around Los Angeles.  This function returns all sensors within the bounding box created by the minimum and maximum latitude/longitude for the specified data source", # Custom description
)
def get_within_bbox(lat_min: float, lat_max: float, lon_min: float, lon_max: float, data_source: str) -> List[str]:
    """
    Given bounding box defined by [lat_min, lat_max, lon_min, lon_max]
    and list of coords=[(lat, lon), ...],
    return all coords within the box.
    """

    coords = None
    if data_source == "cctv":
        coords = get_cctv_locations()
    elif data_source == "alertcalifornia":
        coords = get_alertcalifornia_locations()
    elif data_source == "air_quality":
        coords = get_air_locations()
    elif data_source == "weather":
        coords = get_owm_locations()
    else:
        raise ValueError(f"Unsupported data source: {data_source}")

    close_sensors = []
    for sensor_id in coords.keys():
        lat, lon = coords[sensor_id]
        if lat_min <= lat <= lat_max and lon_min <= lon <= lon_max:
            close_sensors.append(str(sensor_id))
    return close_sensors



def get_config_data():

    current_config_filepath = "extractor_modules/config/current.json"

    # Open the current config, load the data
    with open(current_config_filepath, "r") as f:
        config_data = json.load(f)

    return config_data

def write_config_data(config_data):
    
    current_config_filepath = "extractor_modules/config/current.json"

    # Write back to the config file
    with open(current_config_filepath, "w") as f:
        json.dump(config_data, f, indent=4)

@mcp.tool(
    name="get_sensor_sampling",           # Custom tool name for the LLM
    description="Takes in a data source from the list of [cctv, alertcalifornia, air_quality, weather].  'cctv' sensors are highway cameras taking images around California.  'alertcalifornia' sensors are wildfire cameras positioned around various remote and urban areas in California.  'air_quality' measure PM2.5 from outdoor sensors around Los Angeles.  'weather' measures temperature, wind speed, humidity, and general weather descriptors from cities around Los Angeles.  This function returns the sampling rate of sensors within the data source.  This information is organized by set_number: \{'ids': [list of sensor IDs], 'frequency': 'frequency of sampling in cron'\}.  There is also a 'default' frequency for all other sensors.", # Custom description
)
def get_sensor_sampling(source: str) -> dict:

    config_data = get_config_data()

    return config_data[source]


@mcp.tool(
    name="delete_sampling_set",           # Custom tool name for the LLM
    description="Takes in a list of strings representing 1 or more set numbers, data source from the list of [cctv, alertcalifornia, air_quality, weather].  'cctv' sensors are highway cameras taking images around California.  'alertcalifornia' sensors are wildfire cameras positioned around various remote and urban areas in California.  'air_quality' measure PM2.5 from outdoor sensors around Los Angeles.  'weather' measures temperature, wind speed, humidity, and general weather descriptors from cities around Los Angeles.  Remember that this should be used in conjunction with 'get_sensor_sampling' to identify existing sets.  The main goal of this function is to revert sampling frequencies of certain sensor sets back to the default value.", # Custom description
)
def delete_sampling_set(source: str, set_number_list: List[str]) -> None:

    config_data = get_config_data()

    for set_number in set_number_list:
        if set_number in config_data[source] and set_number != "default":
            del config_data[source][set_number]

    write_config_data(config_data)


def realign_keys(d: dict) -> dict:
    # preserve original order (Python 3.7+ dicts do this)
    new_dict = {}
    if "default" in d:
        new_dict["default"] = d["default"]
    
    # Then reindex the numeric keys in order
    numeric_items = [(k, v) for k, v in d.items() if k != "default"]

    
    for i, (k, v) in enumerate(numeric_items, start=1):
        new_dict[str(i)] = v

    return new_dict


@mcp.tool(
    name="modify_sensor_sampling_rates",           # Custom tool name for the LLM
    description="Takes in a list of sensor IDs, a string representing the cron frequency for sampling, and data source from the list of [cctv, alertcalifornia, air_quality, weather].  'cctv' sensors are highway cameras taking images around California.  'alertcalifornia' sensors are wildfire cameras positioned around various remote and urban areas in California.  'air_quality' measure PM2.5 from outdoor sensors around Los Angeles.  'weather' measures temperature, wind speed, humidity, and general weather descriptors from cities around Los Angeles.  Remember that this should be used in conjunction with 'get_sensor_sampling' to identify formatting and existing sets.  The main goal of this function is to modify sampling rates of the given sensor IDs.  It will automatically handle moving sensor IDs between sets, and create new sets if necessary.", # Custom description
)
def modify_sensor_sampling_rates(source: str, sensor_ids: List[str], frequency: str) -> None:

    config_data = get_config_data()

    # Iterate through each existing set and remove the sensor ID if it exists and frequency does not match the new frequency

    to_add = sensor_ids.copy()
    frequency_exists, matching_set = False, ""
    for s_id in sensor_ids:
        for set_number, details in config_data[source].items():

            if set_number == "default": # Skip this case
                continue

            # Check if the frequency already exists
            if frequency == details["frequency"]:
                frequency_exists = True
                matching_set = set_number

            if s_id in details["ids"] and details["frequency"] != frequency:
                details["ids"].remove(s_id)
                break
            elif s_id in details["ids"] and details["frequency"] == frequency:
                # If the sensor ID is already in a set with the correct frequency, we can skip adding it again
                # print("Sensor ID already in set with correct frequency, skipping:", s_id)
                to_add.remove(s_id)
                break

    print(config_data[source])

    # Clean up the dictionary - remove empty sets and re-align key numbers
    keys_to_delete = []
    for set_number, details in config_data[source].items():
        if set_number != "default" and len(details["ids"]) == 0:
            keys_to_delete.append(set_number)
    for to_delete in keys_to_delete:
        del config_data[source][to_delete]
    
    print("Post delete")
    print(config_data[source])
    config_data[source] = realign_keys(config_data[source])
    print("Post align")
    print(config_data[source])
    # we go through the remaining ids to add and them
    if frequency_exists and matching_set != "":
        config_data[source][matching_set]["ids"].extend(to_add)
    else:
        # Create a new set number
        existing_set_nums = [int(k) for k in config_data[source].keys() if k != "default"]
        new_set_id = str(len(existing_set_nums)+1)

        config_data[source][new_set_id] = {"ids": sensor_ids, "frequency": frequency}
    print("Post add")
    print(config_data)

    write_config_data(config_data)
    


def setup_mcp_servers():
    mcp.run(transport="http", port=8000, path="/extractor")


if __name__ == "__main__":


    # res = modify_sensor_sampling_rates("cctv", ["5"], "*/21 * * * *")
    # res = modify_sensor_sampling_rates("cctv", ["15"], "*/25 * * * *")
    
    # res = get_within_radius((34.046143, -118.442731), 5, "cctv")

    # Location by kennth hahn state park
    #  res = get_within_radius((34.012028, -118.370251), 5, "alertcalifornia")

    # res = get_within_bbox(33.9, 34.1, -118.5, -118.3, "cctv")
    
    # print(res)

    mcp.run(transport="http", port=8000, path="/extractor")