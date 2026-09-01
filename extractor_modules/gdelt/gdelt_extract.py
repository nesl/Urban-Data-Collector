import os
import io

import pandas as pd
import requests


from datetime import datetime, timedelta
from extractor_modules.common.config import get_config

# Pull event and GKG data from the last-update feed.

def get_df(download_link, ftype):
    """Download and parse a provider file, raising a useful HTTP error."""
    csv_response = requests.get(download_link, timeout=60)
    csv_response.raise_for_status()
    content = io.BytesIO(csv_response.content)
    return pd.read_csv(
        content, compression=ftype, sep="\t", header=None, on_bad_lines="skip"
    )

# This takes in a time and returns the previous minute
#  Takes in a string of yyyymmddhhmmss
def minus_minutes(time_str, diff_in_minutes):
    time_obj = datetime.strptime(time_str, '%Y%m%d%H%M%S')
    new_time_minus_one_minute = time_obj - timedelta(minutes=diff_in_minutes)
    return new_time_minus_one_minute.strftime('%Y%m%d%H%M%S')


def previous_interval_link(kg_link, interval_minutes=15):

    kg_split = kg_link.split("/")
    prefix_str = '/'.join(kg_split[:-1])
    kg_end_str = kg_split[-1]

    kg_file_split = kg_end_str.split(".")
    kg_file_end = '.'.join(kg_file_split[1:])
    time_str = kg_file_split[0]

    new_time_str = minus_minutes(time_str, interval_minutes)
    new_kg_link = prefix_str + "/" + new_time_str + "." + kg_file_end

    return new_kg_link


def get_latest_available_df(download_link, ftype, max_attempts=24):
    """Find the newest downloadable interval when lastupdate runs ahead of storage."""
    candidate = previous_interval_link(download_link)
    for _ in range(max_attempts):
        try:
            return candidate, get_df(candidate, ftype)
        except requests.HTTPError as exc:
            if exc.response is None or exc.response.status_code != 404:
                raise
            candidate = previous_interval_link(candidate)
    raise RuntimeError(
        f"No downloadable GDELT file found in the previous {max_attempts} intervals"
    )



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

            final_url, dataframe = get_latest_available_df(
                final_url, "zip"
            )
            # dataframe.to_csv('output.txt', sep=',', index=False)

            dataframe = filter_events(dataframe)
            save_to_csv(dataframe, final_url, save_folder)
            
        elif data_type == "gkg":
            final_url = [x for x in urls if "gkg" in x][0]

            final_url, dataframe = get_latest_available_df(
                final_url, "zip"
            )
            dataframe = filter_gkg(dataframe)
            save_to_csv(dataframe, final_url, save_folder)
        # Download and parse
        
        # return dataframe
                
    else:
        raise Exception(f"Failed to fetch the file. Status code: {response.status_code}")


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
    

    print("Downloading data")
    pull_data_gkg(gkg_link, "gkg", day_folder)  # gkg or events
    pull_data_gkg(gkg_link, "events", day_folder)  # gkg or events



if __name__ == "__main__":
    pull_data()
