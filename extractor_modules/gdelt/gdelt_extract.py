import os
import io

import pandas as pd
import requests


import argparse
from datetime import datetime, timedelta
from extractor_modules.common.config import get_config

# 1 Pull event, gkg, and vkg from the last update link (download to files)

def get_df(download_link, ftype):
    # Get the file
    csv_response = requests.get(download_link)
    if csv_response.status_code == 200:
        # Return the CSV content or save to a file
        content = io.BytesIO(csv_response.content)
        df = pd.read_csv(content, compression=ftype, sep='\t',
                                header=None, on_bad_lines='skip',)
        return df

# This takes in a time and returns the previous minute
#  Takes in a string of yyyymmddhhmmss
def minus_minutes(time_str, diff_in_minutes):
    time_obj = datetime.strptime(time_str, '%Y%m%d%H%M%S')
    new_time_minus_one_minute = time_obj - timedelta(minutes=diff_in_minutes)
    return new_time_minus_one_minute.strftime('%Y%m%d%H%M%S')


def replace_kg_link(kg_link, kg_type):

    kg_split = kg_link.split("/")
    prefix_str = '/'.join(kg_split[:-1])
    kg_end_str = kg_split[-1]

    kg_file_split = kg_end_str.split(".")
    kg_file_end = '.'.join(kg_file_split[1:])
    time_str = kg_file_split[0]

    new_time_str = time_str
    if kg_type == "vkg":
        new_time_str = minus_minutes(time_str, 1)
    elif kg_type == "gkg":
        new_time_str = minus_minutes(time_str, 15)
    new_kg_link = prefix_str + "/" + new_time_str + "." + kg_file_end

    return new_kg_link

#  This pulls vkg data
def pull_data_vkg(latest_update_link, save_folder):

    response = requests.get(latest_update_link)
    
    # Check if the request was successful
    if response.status_code == 200:
        # Extract the URL for the CSV file from the text
        lines = response.text.splitlines()

        for line in lines:
            parts = line.split()
            if len(parts) >= 3:

                csv_url = parts[2]  # Extract the URL
                csv_url = replace_kg_link(csv_url, "vkg")
                
                # Let's replace with an older link:
                # csv_url = "http://data.gdeltproject.org/gdeltv3/vgkg/20241118233400.vgkg.v3.csv.gz"

                # Get the datafrom from the gzipped csv
                dataframe = get_df(csv_url, "gzip")
                dataframe = filter_vkg(dataframe)
                save_to_csv(dataframe, csv_url, save_folder)
                return dataframe
            else:
                raise Exception(f"Failed to download CSV file. Status code: {response.status_code}")
    else:
        raise Exception(f"Failed to fetch the file. Status code: {response.status_code}")



# This pulls gdelt event data 
def pull_data_gkg(latest_update_link, data_type, save_folder):
    response = requests.get(latest_update_link)
    
    # Check if the request was successful
    if response.status_code == 200:
        # Extract the URL for the CSV file from the text
        lines = response.text.splitlines()

        urls = []
        for line in lines:  # Get each url
            parts = line.split()
            if len(parts) >= 3:
                csv_url = parts[2]  # Extract the URL
                urls.append(csv_url)

        # Get the one for this data type
        final_url = ""
        dataframe = None
        if data_type == "events":
            final_url = [x for x in urls if "export" in x][0]

            # Update the URL to get the most up to date csv, 15 min ago
            final_url = replace_kg_link(final_url, "gkg")

            dataframe = get_df(final_url, "zip")
            # dataframe.to_csv('output.txt', sep=',', index=False)

            dataframe = filter_events(dataframe)
            save_to_csv(dataframe, final_url, save_folder)
            
        elif data_type == "gkg":
            final_url = [x for x in urls if "gkg" in x][0]

            # Update the URL to get the most up to date csv, 15 min ago
            final_url = replace_kg_link(final_url, "gkg")

            dataframe = get_df(final_url, "zip")
            dataframe = filter_gkg(dataframe)
            save_to_csv(dataframe, final_url, save_folder)
        # Download and parse
        
        # return dataframe
                
    else:
        raise Exception(f"Failed to fetch the file. Status code: {response.status_code}")


def get_latlong_from_string(geo_string):

    latlong_str = geo_string.split("<FIELD>")[-2]
    latlong_tup = latlong_str.split(",")
    latlong_tup = [float(x) for x in latlong_tup]
    
    return latlong_tup


def coords_in_region(latlong_tup):

    # LA county coordinate square
    min_lat, max_lat = 33.5, 34.8
    min_lon, max_lon = -119.0, -117.0

    curr_lat, curr_long = latlong_tup

    return min_lat <= curr_lat <= max_lat and min_lon <= curr_long <= max_lon


# 2 Filter by events relating to los angeles/california
def filter_vkg(df_vkg):
    # Return a dataframe where events are filtered by USA/California/Los Angeles

    # Event location seems to exist on lines 5
    #  It seems that this line is also for actors (e.g. actor name), but includes location info
    mask_df = df_vkg.iloc[:, [4,5]].apply(lambda row: row.str.contains('Los Angeles', case=False, na=False).any(), axis=1)

    # We should also filter by estimated latlong coordinates
    # This checks if our location is in LA county
    for index, row in df_vkg.iterrows():
        geo_item = row.iloc[4]
        if type(geo_item) == str:  # We have a string here
            latlong_tup = get_latlong_from_string(geo_item)
            
            if coords_in_region(latlong_tup):
                mask_df.iloc[index] = True

    filtered_df = df_vkg[mask_df]
    return filtered_df

def filter_events(df_events):
    # Return a dataframe where events are filtered by USA/California/Los Angeles
    
    # Event location seems to exist on lines 37, 45, and 53.
    #  It seems that this line is also for actors (e.g. actor name), but includes location info

    mask_df = df_events.iloc[:, [6, 36, 44, 52]].apply(lambda row: row.str.contains('Los Angeles', case=False, na=False).any(), axis=1)

    filtered_df = df_events[mask_df]
    
    return filtered_df


def filter_gkg(df_gkg):

    # Return a dataframe where the gkg csv is filtered by Los Angeles
    #  Line/column 10 is the V2 enhanced locations
    mask_df = df_gkg.iloc[:, [10]].apply(lambda row: row.str.contains('Los Angeles', case=False, na=False).any(), axis=1)

    filtered_df = df_gkg[mask_df]

    return filtered_df

# General flow:



# 3 save these events to a csv in our files, named appropriately
def save_to_csv(df, csv_url, save_folder):

    filename = csv_url.split("/")[-1].split(".")[:-1]
    filename = '.'.join(filename)
    filepath = save_folder + "/" + filename
    df.to_csv(filepath, index=False)


def pull_data(chosen_sensors=[], exclude_sensors=[]):

    gkg_link = "http://data.gdeltproject.org/gdeltv2/lastupdate.txt"

    config_data = get_config()
    save_folder = config_data["save_folder"]

    # This makes the modality folder
    kg_type_folder = save_folder + "/gkg"
    if not os.path.exists(kg_type_folder):
        os.mkdir(kg_type_folder)
    # This makes the 'daily' folder
    current_day = datetime.now()
    current_day = current_day.strftime("%Y%m%d")
    day_folder = kg_type_folder + "/" + current_day
    if not os.path.exists(day_folder):
        os.mkdir(day_folder)
    

    # Important note - you must download the 'previous' minute of data otherwise you are downloading data which is new but incomplete

    print("Downloading data")

    # VKG is updated every minute, GKG is updated every 15 minutes
    pull_data_gkg(gkg_link, "gkg", day_folder)  # gkg or events
    pull_data_gkg(gkg_link, "events", day_folder)  # gkg or events



if __name__ == "__main__":

    parser = argparse.ArgumentParser()
    parser.add_argument("--type", type=str, help="Type of knowledge graph to pull (vkg or gkg)")
    args = parser.parse_args()

    vkg_link = "http://data.gdeltproject.org/gdeltv3/vgkg/lastupdate.txt"
    gkg_link = "http://data.gdeltproject.org/gdeltv2/lastupdate.txt"

    config_data = get_config()
    save_folder = config_data["save_folder"]

    # This makes the modality folder
    kg_type_folder = save_folder + "/" + args.type
    if not os.path.exists(kg_type_folder):
        os.mkdir(kg_type_folder)
    # This makes the 'daily' folder
    current_day = datetime.now()
    current_day = current_day.strftime("%Y%m%d")
    day_folder = kg_type_folder + "/" + current_day
    if not os.path.exists(day_folder):
        os.mkdir(day_folder)
    

    # Important note - you must download the 'previous' minute of data otherwise you are downloading data which is new but incomplete

    print("Downloading data")

    # VKG is updated every minute, GKG is updated every 15 minutes

    if args.type == "vkg": 
        pull_data_vkg(vkg_link, day_folder)
    elif args.type == "gkg":
        pull_data_gkg(gkg_link, "gkg", day_folder)  # gkg or events
        pull_data_gkg(gkg_link, "events", day_folder)  # gkg or events
    else:
        print("invalid KG type specified")

    # 12 cols in vkg
    # 61 cols in events
    # 27 cols in gkg
    # print(dataframe.iloc[0])
