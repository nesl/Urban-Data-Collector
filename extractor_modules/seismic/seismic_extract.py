import os
from obspy.clients.fdsn import Client
from obspy import UTCDateTime
from obspy import read
from datetime import datetime, timedelta

import boto3 # AWS access Python API
from botocore import UNSIGNED
from botocore.config import Config

from extractor_modules.common.config import get_config
import json

# Save data into our database
def save_earthquake_data(events, curr_date):

    # Earthquake data:
    earthquake_filepath = "seismic/" + curr_date + ".xml"
    events.write(earthquake_filepath, format="QUAKEML")

# Save time and loation info
def save_spatiotemporal_info(waveform_filepath, station_location, save_path, channel_of_interest):

    # Open the waveform and get the time information
    ch = read(waveform_filepath)
    # Get start and end timestamp
    start_time = min(tr.stats.starttime for tr in ch).isoformat()
    end_time = max(tr.stats.endtime for tr in ch).isoformat()
    # Get the total samples, average sample rate, channel tyupe
    total_samples = sum(tr.stats.npts for tr in ch)  # Sum of all samples across traces
    avg_sample_rate = sum(tr.stats.sampling_rate for tr in ch) / len(ch)  # Average sampling rate

    json_data = {
        "start_time": start_time,
        "end_time": end_time,
        "total_samples": total_samples,
        "avg_sample_rate": avg_sample_rate,
        "channel_type": channel_of_interest,
        "latitude": station_location[0],
        "longitude": station_location[1]
    }

    with open(save_path, "w") as json_file:
        json.dump(json_data, json_file, indent=4)


def save_waveform_data(key, curr_date, curr_day, data_folder, channel_of_interest):

    key_link, station, station_location = key

    # Add data folder
    save_folder = data_folder + "/seismic"
    
    if not os.path.exists(save_folder):
        os.mkdir(save_folder)

    day_folder = save_folder + "/" + curr_day
    if not os.path.exists(day_folder):
        os.mkdir(day_folder)

    # Station folder
    station_folder = day_folder + "/" + station
    if not os.path.exists(station_folder):
        os.mkdir(station_folder)

    # Earthquake data:
    waveform_filepath = station_folder + "/" + station + "_" + curr_date + ".ms"
    
    try:

        # CI refers to the seismic network, in this case Caltech USGS socal
        # BHZ/HHZ/etc is the component code, describing the frequency, instrument, orientation.

        # key_link = "continuous_waveforms/2024/2024_323/CIGSC__BHZ___2024323.ms" # - year and day of the year
        
        # Save the file
        s3.Bucket(BUCKET_NAME).download_file(key_link, waveform_filepath)
        # Save the time and location info
        spatiotemporal_filepath = station_folder + "/" + station + ".json"
        save_spatiotemporal_info(waveform_filepath, station_location, \
            spatiotemporal_filepath, channel_of_interest)

        
    except:
        print("station " + station + " has no data")
    
        return # If there's an error, it's because this particular station didn't have any data for this channel
        #  They won't always have data for the chosen day, and I haven't really experimented with whether they are just late
        #  to upload or some other reason why they don't have data.
    # waveforms.write(waveform__filepath, format="MSEED")

# Get stations within a particular latlong region
def get_relevant_stations(minlat, maxlat, minlong, maxlong, obs_client, channel_of_interest):

    inventory = obs_client.get_stations(
        network="CI",  # Southern California Seismic Network
        minlatitude=minlat,
        maxlatitude=maxlat,
        minlongitude=minlong,
        maxlongitude=maxlong,
        level="channel"  # Fetch basic station metadata
    )

    relevant_stations = []
    available_stations = 0
    total_stations = 0
    
    for network in inventory:
        for station in network:
            component_codes = [channel.code for channel in station]
            if channel_of_interest in component_codes:
                available_stations += 1
                relevant_stations.append({
                    "station": station.code,
                    "location": [station.latitude, station.longitude]
                    })
                # print(f"Station: {station.code}, Location: {station.latitude}, {station.longitude}, Channels: {component_codes}")

            component_codes = str(component_codes)
            total_stations += 1
            

    # Create string
    # relevant_station_str = ','.join(relevant_stations)
    print(f"Stations with channel of interest {channel_of_interest}: {available_stations} / {total_stations}")
    
    return relevant_stations

# Format the data for accessing scedc
def format_scedc_query(day_of_year, year, relevant_stations, channel_of_interest):


    queries = []
    key_header = "continuous_waveforms/"+year+"/"+year+"_"+day_of_year+"/"+"CI"
    for station_data in relevant_stations:
        station = station_data["station"]
        location = station_data["location"]
        query = key_header + station + "__" + channel_of_interest + "___" + year + day_of_year + ".ms"
        queries.append((query, station, location))
    
    return queries
        

if __name__ == "__main__":


    # Look at this link:
    # https://scedc.caltech.edu/data/getstarted-pds.html

    # Request from scedc (south cali earthquake data center)
    client = Client("SCEDC")
    channel_of_interest = "BHZ" # BHZ is broadband high gain, vertical, commonly used for earthquake monitoring

    # Define time range (starts yesterday and ends today)
    # end_time = UTCDateTime().date  # Start of today (00:00:00 UTC)
    # start_time = end_time - timedelta(seconds=86400)    # start of yesterday

    # Query the event catalog
    #  These latitutde longitude regions cover most of LA county
    min_latitude = 33.5
    max_latitude = 34.8
    min_longitude = -119.0
    max_longitude = -117.0

    # events = client.get_events(
    #     starttime=start_time, endtime=end_time,
    #     minlatitude=min_latitude,
    #     maxlatitude=max_latitude,
    #     minlongitude=min_longitude,
    #     maxlongitude=max_longitude
    # )
    
    # Get relevant stations to collect waveform data from
    relevant_stations = get_relevant_stations(min_latitude, max_latitude,
        min_longitude, max_longitude, client, channel_of_interest)

    
    
    # # Query the waveform data

    # waveforms = client.get_waveforms(
    #     network="CI",    # Southern California Seismic Network
    #     station=station_str,     # Wildcard for all stations
    #     location="*",    # Wildcard for all locations
    #     channel="HH*",   # Example for all HH channels
    #     starttime=start_time,
    #     endtime=end_time
    # )

    # Connect to S3 and pull data
    s3 = boto3.resource('s3', config=Config(signature_version=UNSIGNED))
    BUCKET_NAME = 'scedc-pds'

    day_of_year = str(datetime.now().timetuple().tm_yday-1)

    current_year = str(datetime.now().year)
    if int(day_of_year) < 0:
        day_of_year = "364"
        current_year = str(datetime.now().year-1)
    day_of_year = day_of_year.zfill(3)

    save_folder = get_config()["save_folder"]

    # Get queries
    query_keys = format_scedc_query(day_of_year, current_year, relevant_stations, channel_of_interest)
    current_time = datetime.now()
    current_date = current_time.strftime("%Y%m%d%H%M%S")
    current_day = current_time.strftime("%Y%m%d")
    for key in query_keys:
        save_waveform_data(key, current_date, current_day, save_folder, channel_of_interest)
        
    # key = "continuous_waveforms/2017/2017_180/CIGSC__BHZ___2017180.ms"
    # key = "continuous_waveforms/2024/2024_323/CIGSC__BHZ___2024323.ms"
    # s3.Bucket(BUCKET_NAME).download_file(key, "seismic/temp.ms")

    
