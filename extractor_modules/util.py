
import json

# Open up the config file
def get_config(filepath="./config.json"):
    with open(filepath, "rb") as file:
        json_data = json.load(file)
    return json_data