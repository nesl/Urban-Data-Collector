import os
from datetime import datetime
import asyncio
import csv
import argparse

from sklearn.cluster import KMeans
from scipy.spatial import distance

from aiopurpleair import API
import numpy as np
import time

from utilities.util import get_config


def save_air_info(air_info, filename, current_day, save_folder):

    # Create save folders
    air_data_folder = save_folder + "/air_data"
    if not os.path.exists(air_data_folder):
        os.mkdir(air_data_folder)
    day_folder = air_data_folder + "/" + current_day
    if not os.path.exists(day_folder):
        os.mkdir(day_folder) 
    
    filepath = day_folder + "/" + filename + ".csv"

    # Open the CSV file in write mode
    with open(filepath, mode='w', newline='') as file:
        writer = csv.writer(file)
        # Write the tuple as a single row in the CSV
        for tup in air_info:
            writer.writerow(tup)


def save_sensor_info(sensor_info, filename, save_folder="."):

    filepath = save_folder + "/" + filename + ".csv"

    # Open the CSV file in write mode
    with open(filepath, mode='w', newline='') as file:
        writer = csv.writer(file)
        # Write the tuple as a single row in the CSV
        for tup in sensor_info:
            writer.writerow(tup)


def retrieve_nearby_sensors_from_file(filepath):

    with open(filepath, mode='r', newline='') as file:
        reader = csv.reader(file)
        # Convert each row (list) into a tuple and return a list of tuples
        data = [tuple(row) for row in reader]
    return data


# Obtain all sensor IDs and their corresponding latlong
def obtain_all_sensor_locations():

    config_data = get_config()
    nearby_sensors_file = config_data["purpleair_sensors"]

    loaded_data = {} # sensor_id -> (lat, long)
    tuples = retrieve_nearby_sensors_from_file(nearby_sensors_file)

    for tup in tuples:
        loaded_data[tup[0]] = (float(tup[1]), float(tup[2]))
    
    return loaded_data



async def get_sensor_readings(api, current_date, current_day, nearby_sensors, data_folder):

    # Get sensor indices only
    sensor_indices = [int(x[0]) for x in nearby_sensors]

    
    # Only get the instaneous pm2.5 readings from 10km around the center lat/long of LA
    sensor_results = await api.sensors.async_get_sensors(
        ["pm2.5"], sensor_indices=sensor_indices
    )
    air_info = []
    # Iterate through each sensor
    for tup in nearby_sensors:

        # Extract PM2.5 data from the sensor
        sensor_id = tup[0]
        latitude = tup[1]
        longitude = tup[2]
        pm25 = sensor_results.data[int(sensor_id)].pm2_5
        
        air_info.append((sensor_id, latitude, longitude, pm25))

    # Save the info
    save_air_info(air_info, current_date, current_day, data_folder)


# Get a spread of sensors
def get_even_distribution(nearby_sensors, num_centroids=50):
    sensor_ids = [sensor[0] for sensor in nearby_sensors]  # Extract sensor IDs
    sensor_coords = np.array([sensor[1:-1] for sensor in nearby_sensors])  # Extract lat/lon coordinates

    kmeans = KMeans(n_clusters=num_centroids, random_state=42)
    kmeans.fit(sensor_coords)

    # Get the centroids (representative coordinates)
    centroids = kmeans.cluster_centers_

    # Find the closest sensor to each centroid
    selected_sensors = []
    for centroid in centroids:
        # Calculate distances from centroid to all sensors
        distances = distance.cdist([centroid], sensor_coords, 'euclidean')
        nearest_index = np.argmin(distances)  # Index of the closest sensor
        s_id, lat, long = sensor_ids[nearest_index], sensor_coords[nearest_index][0].item(), sensor_coords[nearest_index][1].item()
        selected_sensors.append((s_id, lat, long))  # Add the closest sensor

    # Remove duplicates (if any)
    selected_sensors = list(set(selected_sensors))  # Use set to remove duplicates

    print(selected_sensors)
    return selected_sensors

async def get_nearby_sensors(api, output_file):

    # Only get the instaneous pm2.5 readings from 10km around the center lat/long of LA
    sensor_results = await api.sensors.async_get_nearby_sensors(
        ["location_type"], 34.0549, -118.2426, 30
    )

    nearby_sensors = []
    # Iterate through each sensor
    for result in sensor_results:

        # Get the sensor object
        sensor_data = result.sensor


        # Extract PM2.5 data from the sensor
        sensor_id = sensor_data.sensor_index
        latitude = sensor_data.latitude
        longitude = sensor_data.longitude
        location_type = sensor_data.location_type
        
        if location_type.value == 0:
            nearby_sensors.append((sensor_id, latitude, longitude, location_type.value))

    filtered_sensors = get_even_distribution(nearby_sensors)
    
    # Save the inventory at the path selected in config.json.
    output_dir = os.path.dirname(os.path.abspath(output_file))
    os.makedirs(output_dir, exist_ok=True)
    with open(output_file, mode="w", newline="") as file:
        writer = csv.writer(file)
        writer.writerows(filtered_sensors)

def pull_data(chosen_sensors=[], exclude_sensors=[]):

    config_data = get_config()
    api_key = config_data["purpleair_api_key"]
    save_folder = config_data["save_folder"]
    nearby_sensors_file = config_data["purpleair_sensors"]

    # Run our API
    API_KEY = API(api_key)


    # Only run this when you change the search area for nearby sensors
    #  It will auto save results into air_data/nearby_sensors.csv
    # This should also cost about 295 points, 2 pts for lat/long, 145 sensors, and 5 points for API usage
    # asyncio.run(get_nearby_sensors(API_KEY))
    
    nearby_sensors = retrieve_nearby_sensors_from_file(nearby_sensors_file)
    
    
    # This will take about 105 points, since there are 50 sensors and each pm2.5
    #  measure costs 2 points, and a base 5pts for using this endpoint.
    current_date = datetime.now().strftime("%Y%m%d%H%M%S")
    current_day = datetime.now().strftime("%Y%m%d")
    asyncio.run(get_sensor_readings(API_KEY, current_date, current_day, nearby_sensors, save_folder))
    


if __name__ == "__main__":
    config_data = get_config()
    api_key = config_data["purpleair_api_key"]
    save_folder = config_data["save_folder"]
    nearby_sensors_file = config_data["purpleair_sensors"]

    parser = argparse.ArgumentParser(description="Collect PurpleAir observations")
    parser.add_argument(
        "--refresh-sensors",
        action="store_true",
        help="query the Get Sensors API and regenerate the configured sensor inventory",
    )
    args = parser.parse_args()

    # Run our API
    API_KEY = API(api_key)

    if args.refresh_sensors:
        asyncio.run(get_nearby_sensors(API_KEY, nearby_sensors_file))
        print(f"PurpleAir sensor inventory written to {nearby_sensors_file}")
        raise SystemExit(0)


    # Only run this when you change the search area for nearby sensors
    #  It will auto save results into air_data/nearby_sensors.csv
    # This should also cost about 295 points, 2 pts for lat/long, 145 sensors, and 5 points for API usage
    # asyncio.run(get_nearby_sensors(API_KEY))
    
    nearby_sensors = retrieve_nearby_sensors_from_file(nearby_sensors_file)
    
    
    # This will take about 105 points, since there are 50 sensors and each pm2.5
    #  measure costs 2 points, and a base 5pts for using this endpoint.
    current_date = datetime.now().strftime("%Y%m%d%H%M%S")
    current_day = datetime.now().strftime("%Y%m%d")
    asyncio.run(get_sensor_readings(API_KEY, current_date, current_day, nearby_sensors, save_folder))
    
