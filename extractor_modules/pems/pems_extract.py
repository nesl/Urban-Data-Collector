import os
from datetime import datetime
import sys
from extractor_modules.common.config import get_config

from extractor_modules.pems.handler import PeMSHandler


# Get the most recent date
def get_date_from_filename(filename):

    date_str = filename.split(".")[0].split("_")[-3:]
    return ''.join([x for x in date_str])

# Create and save the files
def save_data(pems_obj, file_type, url, filename, data_folder):

    # Create the folders to save data in
    pem_folder = data_folder + "/pem_data_" + file_type
    if not os.path.exists(pem_folder):
        os.mkdir(pem_folder)

    curr_date_str = get_date_from_filename(filename)
    day_folder = pem_folder + "/" + curr_date_str
    if not os.path.exists(day_folder):
        os.mkdir(day_folder)

    #current_day = 
    # current_day = current_day.strftime("%Y%m%d")
    # day_folder = pem_folder + "/" + current_day
    # if not os.path.exists(day_folder):
    #     os.mkdir(day_folder)

    pem_filepath = day_folder + "/" + filename
    
    # Download data from the url
    url_of_file = "https://pems.dot.ca.gov" + url

    response = pems_obj.browser.open(url_of_file)

    # Save the data
    content_type = response.headers.get('Content-Type', '').lower()
    content_length = int(response.headers.get('Content-Length', '').lower())

    # If it's a downloadable file (e.g., a ZIP file), proceed to download
    if 'application' in content_type or 'octet-stream' in content_type:
        
        # Open a file to save the content (you can choose the file name and extension)
        with open(pem_filepath, "wb") as file:

            # Download chunks to show progress
            downloaded = 0
            chunk_size = 1024  # 1 KB chunk size
            while True:
                chunk = response.read(chunk_size)
                if not chunk:
                    break
                file.write(chunk)
                downloaded += len(chunk)

                # Track progress
                if content_length is not None:
                    percent = (downloaded / content_length) * 100
                    sys.stdout.write(f"\rDownloading: {percent:.2f}%")
                    sys.stdout.flush()
                else:
                    sys.stdout.write(f"\rDownloaded: {downloaded / (1024 * 1024):.2f} MB")
                    sys.stdout.flush()


            file.write(response.read())
        print("Download completed successfully.")
    else:
        print(f"Failed to download data.")



 
# For a particular file type, get all data for today.
#  
def extract_daily_data(pems_obj, data_folder, file_type, current_month, current_year, districts=[7]):

    # # Get the available districts for this type of data
    # districts = pems_obj.get_districts(file_type)

    # # For each district, get all data for today
    # files = pems_obj.get_files(2024, 2024, districts, file_type)
    # print(files)

    # District 7 is LA County
    clearing_url = pems_obj._get_urls(current_year, current_year, [7], [file_type])[0]

    response = pems_obj._open_url(url=clearing_url['url'])

    

    # Find the entry for today
    latest_entry = response["data"][current_month][-1]
    latest_url = latest_entry["url"]
    filename = latest_entry["file_name"]
    

    # Download the file for the last date
    save_data(pems_obj, file_type, latest_url, filename, data_folder)

def pull_data(chosen_sensors=[], exclude_sensors=[]):

    current_month = datetime.now().strftime("%B")  # e.g. November
    current_year = int(datetime.now().strftime("%Y"))  # e.g. 2024
    
    config_data = get_config()
    save_folder = config_data["save_folder"]

    # Create pems handler
    # https://github.com/Seb-Good/caltrans-pems
    # HTTP debugging logs request bodies and can expose the PeMS password.
    pems_obj = PeMSHandler(config_data["pem_username"], config_data["pem_password"], debug=False)
    

    # THis tells us what file types are available for download
    # print(pems_obj.get_file_types())

    file_types = ["station_5min", "chp_incidents_day"]

    

    extract_daily_data(pems_obj,save_folder, "station_5min", current_month, current_year)
    extract_daily_data(pems_obj,save_folder, "chp_incidents_day", current_month, current_year)



if __name__ == "__main__":

    current_month = datetime.now().strftime("%B")  # e.g. November
    current_year = int(datetime.now().strftime("%Y"))  # e.g. 2024
    
    config_data = get_config()
    save_folder = config_data["save_folder"]

    # Create pems handler
    # https://github.com/Seb-Good/caltrans-pems
    # HTTP debugging logs request bodies and can expose the PeMS password.
    pems_obj = PeMSHandler(config_data["pem_username"], config_data["pem_password"], debug=False)
    

    # THis tells us what file types are available for download
    # print(pems_obj.get_file_types())

    file_types = ["station_5min", "chp_incidents_day"]

    

    extract_daily_data(pems_obj,save_folder, "station_5min", current_month, current_year)
    extract_daily_data(pems_obj,save_folder, "chp_incidents_day", current_month, current_year)
