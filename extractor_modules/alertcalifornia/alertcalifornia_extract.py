import os
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager  # Optional, automatically manage ChromeDriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# from selenium.webdriver.firefox.service import Service as FirefoxService
# from webdriver_manager.firefox import GeckoDriverManager


from bs4 import BeautifulSoup
import time
import requests
from datetime import datetime
from utilities.util import get_config
import math
import csv
from tqdm import tqdm

# We have to do this entirely in Selenium - it seems bs4 doesn't work since there's
#  some degree of rendering happening
#  First, there is an 'origin map' which has a latlong centered on LA and a zoom of 10
#  For every camera ID listed, 
#       get the name and go to its url (add the id to the current query)
#       Get the image
#       Call Selenium if necessary


# Selenium workflow
#  Go to the current camera webpage
#  Click "show on map"
#  This will update the URL itself, which can be used to get the latlong

#  Update the URL to go to zoom 13 (which should get just the relevant cameras)
#  Iterate through every 'leaflet-marker-icon' where the z-index is above 0 (visible)
#       Then click on each icon to get the toggle window for showing the viewshed
#       Toggle the viewshed (for an unvisited ID)
#       Look for the class 'alert-fov-centerline', and get the d parameter (line parameters)
#           note that it is an svg representation (origin starts top left) so angle is different than cardinal
#       untoggle the viewshed
#       Record the ID from the toggle (to say that this has been done)

def fetch_class_content(html_content, class_name, to_filter):
    try:

        # Parse the webpage with BeautifulSoup
        soup = BeautifulSoup(html_content, 'html.parser')
        
        found_content = soup.find_all(class_=class_name)

        found_content = [x for x in found_content if to_filter not in x.get("class",[])]
        
        if found_content is not None:
            # Extract its content as a string
            print("Extracted content successfully.")
            return found_content
        else:
            print("No relevant class found on the page.")
            return None
    except Exception as e:
        print(f"An error occurred: {e}")
        return None

# Pull the camera id from the html info
#  The cam_html_info is a bs4 element
def pull_camera_id(cam_html_info):
    
    # Webdriver wait until page, timeout after 10 seconds
    time.sleep(1)
    WebDriverWait(driver, 10).until(
        EC.presence_of_element_located((By.CLASS_NAME, 'alert-ctt-thumb'))
    )

    # Find the image tag and get the 'src' attribute
    img_tag = cam_html_info.find('img', class_='alert-ctt-thumb')
    img_src = img_tag['src'] if img_tag else None

    # Ignore blank thumbnails
    if "blank_thumb" in img_src:
        return "",""
    else:
        try:
            cam_id = img_src.split("/public-camera-data/")[1].split("/latest-thumb")[0]
        except:  # usually this means the camera is unavailable, so return.
            return "", ""
        
        # Also get the name
        cam_name = cam_html_info.find('div', class_='alert-ctt-name').text
        
        return cam_id, cam_name

# Pull the image from the current camera webpage
def get_camera_image_link(cam_html_content):
    try:
        # Parse the webpage with BeautifulSoup
        soup = BeautifulSoup(cam_html_content, 'html.parser')
        
        found_content = soup.find('img', class_="leaflet-image-layer")
        print(found_content)
        
        if found_content is not None:
            img_link = found_content['src']

            return img_link
        else:
            print("No relevant class found on the page.")
            return None
    except Exception as e:
        print(f"An error occurred: {e}")
        return None

# 3: Create folder for region (go by hyperlink name) and save image
def save_cam_image(cam_tup, current_time, data_folder, current_day):

    img_url = cam_tup["cam_url"]

    # Create save folder
    save_folder = data_folder + "/alertcalifornia"
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
        
        return img_folder

    except Exception as e:
        print(f"An error occurred for image download: {e}")

# Save camera metadata
def save_cam_location(img_folder, current_time, cam_direction, lat_long):

    # Save the current direction into a position file
    location_filename = current_time + ".location"
    print(img_folder)
    print(location_filename)
    output_filepath = img_folder + "/" + location_filename
    # Save the image content to a file
    with open(output_filepath, "w") as file:
        file.write(str(lat_long[0]) + "," + str(lat_long[1]) + "," + str(cam_direction))

# Handle the logic for each camera
def load_and_save_cam_info(cam_html, data_folder, driver, cam_id, cam_name):


    print("Setting up for " + str(cam_id))

    # After getting the camera id, update the url
    new_camera_url = origin_url + "&id=" + str(cam_id)
    driver.get(new_camera_url)

    # Load the page and save the camera image
    WebDriverWait(driver, 10).until(
        EC.presence_of_element_located((By.CLASS_NAME, 'leaflet-image-layer'))
    )
    time.sleep(2)
    cam_html_content = driver.page_source

    img_link = get_camera_image_link(cam_html_content)
    cam_tup = {"cam_url":img_link, "cam_name":cam_name}

    # Get date and time information 
    current_time = datetime.now()
    current_time_str = current_time.strftime("%Y%m%d%H%M%S")
    current_day = current_time.strftime("%Y%m%d")

    # Save the camera image
    img_folder = save_cam_image(cam_tup, current_time_str, data_folder, current_day)

    if img_folder:

        # Get lat long for this camera 
        lat_long = interact_for_latlong(driver)

        # Get camera direction for this camera
        time.sleep(2)
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CLASS_NAME, 'leaflet-marker-icon'))
        )
        cam_direction = grab_cam_direction(driver, cam_name)

        # Save information to our files
        #  Assume the latlong is static, but the direction is changing every few minutes (some cameras are 360)
        save_cam_location(img_folder, current_time_str, cam_direction, lat_long)

        # Return our latlong - we are adding positions for all cameras in a single file
        return cam_name, lat_long
    
    else:
        return None



    
# Toggle the direction
def toggle_element_direction(driver, element_index):
    
    slider_elements = driver.find_elements(By.CLASS_NAME, "atw-slider")
    slider_elements[element_index-1].click()


# match cam name
def is_cam_match(driver,cam_name):
    print("Checking match with " + str(cam_name))
    html_content = driver.page_source
    soup = BeautifulSoup(html_content, "html.parser")

    # Find all elements with the class 'alert-context-item'
    alert_items = soup.find_all("tr", class_="alert-context-item")

    # Extract text inside the <a> tag for each alert item
    alert_texts = [item for item in alert_items if item.find("a")]

    # Iterate through each alert text and check if the name matches
    for i,x in enumerate(alert_texts):
        if x.find("a").get_text().strip() == cam_name.strip():
            toggle_element_direction(driver, i)
            time.sleep(1)
            return True
    return False


def get_line_angle(driver):
    
    html_content = driver.page_source
    soup = BeautifulSoup(html_content, "html.parser")

    # Get the line
    cam_svg_element = soup.find("path", class_="alert-fov-centerline leaflet-interactive")

    # Parse the line
    line_data = cam_svg_element["d"]
    line_data_split = line_data[1:].split("L")
    
    point1 = [int(x) for x in line_data_split[0].split()]
    point2 = [int(x) for x in line_data_split[1].split()]

    delta_x = (point1[0] - point2[0])*-1 # x axis is flipped on svg
    delta_y = point1[1] - point2[1]
    
    # Calculate angle
    angle = math.atan2(delta_y, delta_x)
    angle = math.degrees(angle)

    return angle


# Iteract with the map element to see if name matches
def interact_and_match_map(driver, cam_name):

    map_elements = driver.find_elements(By.CLASS_NAME, "leaflet-marker-icon")
    visible_icons = [x for x in map_elements if x.is_displayed()] # This step takes a while
    
    # Iterate through each icon and click it
    for icon in visible_icons:
        try:
            icon.click()
            print("Clicked on match")
            time.sleep(1)
            if is_cam_match(driver, cam_name):
                # Now, if we match then we can break and get the angle
                return get_line_angle(driver)
            else:
                icon.click() # Click it again to remove the view

        except:  # Some elements you can not click through (obscured)
            print("error with viewshed interaction")
            continue

    print("NO MATCH FOR ICON")
    return "no angle found"
        
    


# Grab angle
def grab_cam_direction(driver, cam_name):

    # Alter the current url to zoom 13 (most zoomed in)
    current_url = driver.current_url
    zoomed_url = current_url[:-2] + "13"
    
    driver.get(zoomed_url)
    time.sleep(2)
    WebDriverWait(driver, 10).until(
        EC.presence_of_element_located((By.CLASS_NAME, 'leaflet-marker-icon'))
    )
    # Now, list all the arrows and filter by z index >0
    map_html_content = driver.page_source
    print("Filtering map elements")

    return interact_and_match_map(driver, cam_name)



# parse latlong
def parse_latlong(updated_url):
    # Example: https://cameras.alertcalifornia.org/?pos=34.1800_-118.0300_10
    lat_long = updated_url.split("pos=")[1].split("_")
    return lat_long[:-1] # Last item is just the website's zoom parameter, so ignore

# Handle the interaction for getting lat long
def interact_for_latlong(driver):

    

    focus_on_cam_button = driver.find_element(By.ID, "overlay-btn-show_map")
    focus_on_cam_button.click()

    time.sleep(1)

    # Now, after the click, get the url and parse it to get latlong
    return parse_latlong(driver.current_url)


# Kill headless processes
def kill_chrome_headless():
    """Deprecated compatibility hook.

    Older versions terminated every headless Chrome process on the host, which
    could stop unrelated services and failed when psutil returned a null
    command line. Each collector now owns and closes its WebDriver instead.
    """
    return None

# Incremental scroll
def incremental_scroll(driver):

    div_element = driver.find_element(By.ID, "quilt") 
    # last_height = driver.execute_script("return arguments[0].scrollHeight", div_element)
    scroll_increment = 350
    # Keep scrolling until we reach the bottom
    for i in range(20):
        # Scroll down by the increment
        driver.execute_script("arguments[0].scrollTop += arguments[1];", div_element, scroll_increment)

        # Wait a bit for the content to load
        time.sleep(0.5)


# Function for pulling most recent day folder, and getting camera locations
def get_camera_locations():
    
    data_folder = get_config()["save_folder"]
    ca_folder = data_folder + "/alertcalifornia"

    if not os.path.exists(ca_folder):
        raise ValueError(f"No alertcalifornia folder found in {data_folder}")

    # Get most recent day folder
    day_folders = [f for f in os.listdir(ca_folder) if os.path.isdir(os.path.join(ca_folder, f))]
    if not day_folders:
        raise ValueError(f"No day folders found in {ca_folder}")

    most_recent_day = max(day_folders)
    most_recent_day_folder = os.path.join(ca_folder, most_recent_day)

    # Now, iterate through each camera folder and get the latlong from the .location file
    sensor_locations = {} # sensor_id -> (lat, long)
    camera_folders = [f for f in os.listdir(most_recent_day_folder) if os.path.isdir(os.path.join(most_recent_day_folder, f))]
    for cam_folder in camera_folders:
        cam_folder_path = os.path.join(most_recent_day_folder, cam_folder)
        location_files = [f for f in os.listdir(cam_folder_path) if f.endswith(".location")]
        if location_files:
            latest_location_file = max(location_files)  # Assuming filenames are sortable by time
            location_file_path = os.path.join(cam_folder_path, latest_location_file)
            with open(location_file_path, "r") as file:
                content = file.read().strip()
                lat, long, _ = content.split(",")
                sensor_locations[cam_folder] = (float(lat), float(long))

    return sensor_locations

def pull_data(chosen_sensors=[], exclude_sensors=[]):

    # Kill processes from before if error
    kill_chrome_headless()

    # Intitial config information
    data_folder = get_config()["save_folder"]


    #  This URL roughly covers LA county and Orange
    origin_url = "https://cameras.alertcalifornia.org/?pos=33.9639_-118.2898_10"
    # Set up browser options
    browser_options = Options()
    browser_options.add_argument("--headless")  # Enable headless mode
    browser_options.add_argument("--no-sandbox")
    browser_options.add_argument("--disable-dev-shm-usage")

    # Initialize the WebDriver with the options
    driver_path = os.environ.get("CHROMEDRIVER")
    service = Service(driver_path or ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=browser_options)
    driver.get(origin_url)

    # Sleep for some time before getting the page source (wait for load)
    time.sleep(2)

    # Scroll all the way through the gallery down to activate all camera locations
    incremental_scroll(driver)

    html_content = driver.page_source

    # Get all the camera html containers
    camera_html_info_list = fetch_class_content(html_content, "alert-ctt-root", "alert-ctt-hidden")
    
    # Iterate through each camera and scrape info
    camera_positions = []
    for cam_html in tqdm(camera_html_info_list):

        # Get cam name and info
        cam_id, cam_name = pull_camera_id(cam_html)
        # If the cam id is empty, skip it
        if not cam_id:
            continue

        if cam_name in chosen_sensors:
            cam_data = load_and_save_cam_info(cam_html, data_folder, driver, cam_id, cam_name)
            if cam_data is not None:
                cam_name, lat_long = cam_data
                camera_positions.append((cam_name, lat_long[0], lat_long[1]))
        elif not chosen_sensors and cam_name not in exclude_sensors:
            cam_data = load_and_save_cam_info(cam_html, data_folder, driver, cam_id, cam_name)
            if cam_data is not None:
                cam_name, lat_long = cam_data
                camera_positions.append((cam_name, lat_long[0], lat_long[1]))
        

    driver.quit()


if __name__ == "__main__":
    pull_data()


# Notes:
#  The number of cameras it iterates through depends on the browser window size
#   The larger the viewport, the more cameras.  
