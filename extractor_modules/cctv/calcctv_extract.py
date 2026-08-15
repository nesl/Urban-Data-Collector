import os
from bs4 import BeautifulSoup
import requests
import re
from datetime import datetime
from utilities.util import get_config


import xml.etree.ElementTree as ET

# 1: Get all links
def fetch_tbody_content(url):
    try:
        # Fetch the webpage content
        response = requests.get(url)
        response.raise_for_status()  # Ensure the request was successful
        
        # Parse the webpage with BeautifulSoup
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # Find the first 'tbody' tag
        tbody = soup.find('table')
        if tbody is not None:
            # Extract its content as a string
            tbody_content = str(tbody)
            print("Extracted 'tbody' content successfully.")
            return tbody_content
        else:
            print("No 'tbody' tag found on the page.")
            return None
    except Exception as e:
        print(f"An error occurred: {e}")
        return None


# 2: Filter by Los Angeles county
def filter_by_county(html_text, location_of_interest="Los Angeles"):
    
    soup = BeautifulSoup(html_text, 'html.parser')
    # Extract the row with the data (skip the header row)
    data_rows = soup.find_all('tr')[1:]

    cam_data = []

    # Iterate through every row
    for row in data_rows:

        # Extract the county
        county = row.find('td', headers='header102').text

        if county.strip() == "":
            continue # We skip if nothing valid is here
        
        # Extract the neighborhood (Nearby Place)
        neighborhood = row.find('td', headers='header103').text

        # Extract the hyperlink text and URL
        link_cell = row.find('td', headers='header104').find('a')
        hyperlink_text = link_cell.text
        url = link_cell['href']

        # Filter out
        if county == location_of_interest:
            cam_data.append( {
                "county" : county,
                "neighborhood" : neighborhood,
                "cam_name": hyperlink_text,
                "cam_url" : url
            })
    
    return cam_data


# 3: Create folder for region (go by hyperlink name) and save image
def save_cam_image(cam_tup, current_time, data_folder, current_day):

    cam_url = cam_tup["cam_url"]

    # First, get the image
    img_url = get_image_url(cam_url)

    # Create save folder
    save_folder = data_folder + "/cctv"
    if not os.path.exists(save_folder):
        os.mkdir(save_folder)
    day_folder = save_folder + "/" + current_day
    if not os.path.exists(day_folder):
        os.mkdir(day_folder)

    # Next, download the image
    try:
        # Send a GET request to fetch the image
        response = requests.get(img_url)
        response.raise_for_status()  # Check for request errors

        # Finally, save the image
        foldername = ''.join([x for x in cam_tup["cam_name"] if x != "/"])
        img_folder = day_folder + "/" + foldername
        if not os.path.exists(img_folder):
            os.mkdir(img_folder)

        img_filename = current_time + ".jpg"
        output_filepath = img_folder + "/" + img_filename
        # Save the image content to a file
        with open(output_filepath, "wb") as file:
            file.write(response.content)

    except Exception as e:
        print(f"An error occurred for image download: {e}")

    
def get_image_url(cam_url):
    
    try:
        # Fetch the webpage content
        response = requests.get(cam_url)
        response.raise_for_status()  # Ensure the request was successful
        
        # Parse the webpage with BeautifulSoup
        soup = BeautifulSoup(response.content, 'html.parser')
        
        img_div = soup.find('script', string=re.compile('posterURL'))
        
        
        if img_div is not None:
            # Get the posterURL
            poster_url = [x for x in str(img_div).split("\n") if "posterURL" in x][0]
            
            poster_url = poster_url.split("\"")[1]
            
            return poster_url
            
        else:
            print("No 'vjs-poster' tag found on the page.")
            return None
    except Exception as e:
        print(f"An error occurred: {e}")
        return None


# Obtain all sensor IDs and their corresponding latlong
def obtain_all_sensor_locations():


    loaded_data = {} # sensor_id -> (lat, long)

    # Load your file
    tree = ET.parse("extractor_modules/cctv/cctv.kml")   # replace with actual file path
    root = tree.getroot()

    # KML files usually use namespaces, so let's handle that
    ns = {"kml": "http://www.opengis.net/kml/2.2"}

    # Find all Placemark elements (with or without namespace)
    for placemark in root.findall(".//kml:Placemark", ns):
        name = placemark.find("kml:name", ns)
        coords = placemark.find(".//kml:coordinates", ns)

        if name is not None and coords is not None:
            # print("Name:", name.text.strip())
            # print("Coordinates:", coords.text.strip())

            # Note that the lat/long order are reversed for kml
            long, lat = coords.text.strip().split(",")
            lat = float(lat)
            long = float(long)

            loaded_data[name.text.strip()] = [lat, long]
    
    return loaded_data



# Function for running service
#  Either it pulls from a specific set of sensors, or it pulls from all sensors
#  except those in a given list.  If both lists are empty, it pulls from all sensors
def pull_data(chosen_sensors=[], exclude_sensors=[]):

    
    url = "https://cwwp2.dot.ca.gov/vm/streamlist.htm"
    tbody_content = fetch_tbody_content(url)
    cam_tuples = filter_by_county(tbody_content)

    print(len(cam_tuples))

    # Some timer here:
    current_time = datetime.now()
    current_time_str = current_time.strftime("%Y%m%d%H%M%S")
    current_day = current_time.strftime("%Y%m%d")

    # Get folder for saving data into
    data_folder = get_config()["save_folder"]

    for cam_tup in cam_tuples:
        
        cam_name = cam_tup["cam_name"]

        # If there are chosen sensors, we only pull from those
        if cam_name in chosen_sensors:
            save_cam_image(cam_tup, current_time_str, data_folder, current_day)
        elif not chosen_sensors and cam_name not in exclude_sensors:
            save_cam_image(cam_tup, current_time_str, data_folder, current_day)

if __name__ == "__main__":

    url = "https://cwwp2.dot.ca.gov/vm/streamlist.htm"
    tbody_content = fetch_tbody_content(url)
    cam_tuples = filter_by_county(tbody_content)

    print(len(cam_tuples))

    # Some timer here:
    current_time = datetime.now()
    current_time_str = current_time.strftime("%Y%m%d%H%M%S")
    current_day = current_time.strftime("%Y%m%d")

    # Get folder for saving data into
    data_folder = get_config()["save_folder"]

    for cam_tup in cam_tuples:
        
        cam_name = cam_tup["cam_name"]

        
        save_cam_image(cam_tup, current_time_str, data_folder, current_day)



