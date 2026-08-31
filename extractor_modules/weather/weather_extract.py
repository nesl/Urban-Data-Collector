import os

from pyowm import OWM
from pyowm.utils import config
from pyowm.utils import timestamps
import csv
from datetime import datetime
from extractor_modules.common.config import get_config

# Save to file
def save_weather_to_file(curr_datetime, data, save_folder, current_day):

    # Create save folder
    weather_folder = save_folder + "/weather_data"
    if not os.path.exists(weather_folder):
        os.mkdir(weather_folder)
    day_folder = weather_folder + "/" + current_day
    if not os.path.exists(day_folder):
        os.mkdir(day_folder)
    # Create neighborhood folder
    neighborhood_folder = day_folder + "/" + data[-1] # This is the location
    if not os.path.exists(neighborhood_folder):
        os.mkdir(neighborhood_folder)
    
    # Create filepath
    filepath = neighborhood_folder + "/" + curr_datetime + ".csv"

    # Write to CSV
    with open(filepath, mode='w', newline='') as file:
        writer = csv.writer(file)
        writer.writerow(data[:-1])    # Write weather data

# Call OpenWeatherMap and get the temperature
def extract_weather(weather_manager, save_folder, owm_names, owm_coordinates):

    for i,location in enumerate(owm_coordinates):

        lat, long = location.split(", ")[:2]
        lat, long = float(lat), float(long)
        location_name = owm_names[i]

        # Search for current weather in London (Great Britain) and get details
        # observation = weather_manager.weather_at_place(location)
        observation = weather_manager.weather_at_coords(lat, long)
        weather = observation.weather


        # Get the time of this weather observation
        # Get the reference time (Unix timestamp) of the weather observation
        timestamp = weather.reference_time()
        # Convert the Unix timestamp to a human-readable date and time
        weather_time = datetime.utcfromtimestamp(timestamp).strftime('%Y%m%d%H%M%S')
        current_day = datetime.now().strftime("%Y%m%d")


        # Define the header and data
        # header = ['Temperature (F)', 'Status', 'Humidity (%)', 'Wind Speed (m/s)']
        wind = weather.wind()
        data = [
            weather.temperature('fahrenheit')['temp'],
            weather.detailed_status,
            weather.humidity,
            wind.get('speed'),
            wind.get('deg'),
            location_name
        ]

        save_weather_to_file(weather_time, data, save_folder, current_day)
        
def read_owm_locations(owm_locations_file):

    owm_data = []

    with open(owm_locations_file, "r") as owm_locations:
        owm_list = owm_locations.readlines()
        
        for line in owm_list:
            owm_name = ', '.join(line.split(",")[:2]).strip()
            owm_coordinates = [x.strip() for x in line.split(",")[2:]]

            owm_data.append((owm_name, owm_coordinates[0], owm_coordinates[1]))
    
    return owm_data


# Obtain all sensor IDs and their corresponding latlong
def obtain_all_sensor_locations():

    config_data = get_config()
    nearby_sensors_file = config_data["owm_locations"]

    loaded_data = {} # sensor_id -> (lat, long)
    tuples = read_owm_locations(nearby_sensors_file)

    for tup in tuples:
        loaded_data[tup[0]] = (float(tup[1]), float(tup[2]))
    
    return loaded_data

def pull_data(chosen_sensors=[], exclude_sensors=[]):

    config_data = get_config()
    owm_key = config_data["open_weather_map_api_key"]
    save_folder = config_data["save_folder"]
    owm = OWM(owm_key)
    owm_locations_file = config_data["owm_locations"]


    # Also read in the weather data
    with open(owm_locations_file, "r") as owm_locations:
        owm_list = owm_locations.readlines()
        owm_names = [', '.join(x.split(",")[:2]) for x in owm_list]
        owm_names = [x.strip() for x in owm_names]

        owm_coordinates = [', '.join(x.split(",")[2:]) for x in owm_list]
        owm_coordinates = [x.strip() for x in owm_coordinates]
        
    
    # Sensors of interest
    if chosen_sensors:
        chosen_owm_names = [x for x in owm_names if x in chosen_sensors]
        chosen_owm_coordinates = [owm_coordinates[i] for i,x in enumerate(owm_names) if x in chosen_sensors]
        owm_names = chosen_owm_names
        owm_coordinates = chosen_owm_coordinates
    elif not chosen_sensors and exclude_sensors:
        chosen_owm_names = [x for x in owm_names if x not in exclude_sensors]
        chosen_owm_coordinates = [owm_coordinates[i] for i,x in enumerate(owm_names) if x not in exclude_sensors]
        owm_names = chosen_owm_names
        owm_coordinates = chosen_owm_coordinates

    weather_manager = owm.weather_manager()

    # Extract weather and save
    extract_weather(weather_manager, save_folder, owm_names, owm_coordinates)


if __name__ == "__main__":

    config_data = get_config()
    owm_key = config_data["open_weather_map_api_key"]
    save_folder = config_data["save_folder"]
    owm = OWM(owm_key)
    owm_locations_file = config_data["owm_locations"]


    # Also read in the weather data
    with open(owm_locations_file, "r") as owm_locations:
        owm_list = owm_locations.readlines()
        owm_names = [', '.join(x.split(",")[:2]) for x in owm_list]
        owm_names = [x.strip() for x in owm_names]

        owm_coordinates = [', '.join(x.split(",")[2:]) for x in owm_list]
        owm_coordinates = [x.strip() for x in owm_coordinates]
        
    

    weather_manager = owm.weather_manager()

    # Extract weather and save
    extract_weather(weather_manager, save_folder, owm_names, owm_coordinates)
