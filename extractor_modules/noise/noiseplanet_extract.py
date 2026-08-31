import os
import shutil
import requests
import zipfile
import json
import argparse
from datetime import datetime, timedelta, timezone, time
from zoneinfo import ZoneInfo
import pandas as pd
from extractor_modules.common.config import get_config
from tqdm import tqdm

def download_file_with_progress(url, output_path):
    response = requests.get(url, stream=True)

    if response.status_code == 200:

        total_size = int(response.headers.get('content-length', 0))
        block_size = 1024  # download in 1KB chunks

        with open(output_path, 'wb') as f, tqdm(
            total=total_size, unit='iB', unit_scale=True
        ) as bar:
            for data in response.iter_content(block_size):
                f.write(data)
                bar.update(len(data))
        
        print("Download successful!")
    else:
        print("Failed to download the file. Status code:", response.status_code)
        exit(1)
    

def download_and_extract(zip_url, extract_dir, target_prefix):
    # Delete existing extraction directory if it exists
    if os.path.exists(extract_dir):
        print(f"Existing directory '{extract_dir}' found. Deleting it...")
        shutil.rmtree(extract_dir)

    local_zip_path = 'temp/United_States.zip'
    print("Downloading zip file...")
    download_file_with_progress(zip_url, local_zip_path)

    os.makedirs(extract_dir, exist_ok=True)
    print("Extracting files...")

    with zipfile.ZipFile(local_zip_path, 'r') as zip_ref:
        zip_ref.extractall(extract_dir)

    print("Extraction completed!")
    print("Filtering files...")

    # Remove files that don't match the target prefix
    for filename in os.listdir(extract_dir):
        file_path = os.path.join(extract_dir, filename)

        if os.path.isfile(file_path):
            if not filename.startswith(target_prefix):
                os.remove(file_path)

    os.remove(local_zip_path)
    print("File filtering completed!")

def load_geojson(file_path):
    with open(file_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    return data

# def extract_areas(file_path):
#     loaded_data = load_geojson(file_path)
#     extracted_data = []

#     for feature in loaded_data["features"]:
#         properties = feature["properties"]
#         geometry = feature["geometry"]
#         extracted_data.append({
#             "cell_q": properties.get("cell_q"),
#             "cell_r": properties.get("cell_r"),
#             "la50": properties.get("la50"),
#             "laeq": properties.get("laeq"),
#             "lden": properties.get("lden"),
#             "mean_pleasantness": properties.get("mean_pleasantness"),
#             "measure_count": properties.get("measure_count"),
#             "first_measure": properties.get("first_measure_ISO_8601"),
#             "last_measure": properties.get("last_measure_ISO_8601"),
#             "coordinates": geometry["coordinates"]
#         })

#     df = pd.DataFrame(extracted_data)
#     df = df.sort_values(by=["first_measure", "last_measure"])
#     df = df.drop(columns=["cell_q", "cell_r", "lden", "measure_count"])

#     return df

def extract_points(file_path):
    loaded_data = load_geojson(file_path)
    extracted_data = []

    for feature in loaded_data["features"]:
        properties = feature["properties"]
        geometry = feature["geometry"]
        coordinates = geometry["coordinates"]
        extracted_data.append({
            "pk_track": properties.get("pk_track"),
            "time_ISO8601": properties.get("time_ISO8601"),
            "time_epoch": properties.get("time_epoch"),
            "time_gps_ISO8601": properties.get("time_gps_ISO8601"),
            "time_gps_epoch": properties.get("time_gps_epoch"),
            "noise_level": properties.get("noise_level"),
            "speed": properties.get("speed"),
            "accuracy": properties.get("accuracy"),
            "longitude": coordinates[0],
            "latitude": coordinates[1],
            "altitude": coordinates[2]
        })

    df = pd.DataFrame(extracted_data)
    df = df.sort_values(by="time_epoch")
    df = df.drop(columns=["pk_track", "time_ISO8601", "time_epoch", "time_gps_epoch"])

    return df

# def extract_tracks(file_path):
#     loaded_data = load_geojson(file_path)
#     extracted_data = []

#     for feature in loaded_data["features"]:
#         properties = feature["properties"]
#         geometry = feature["geometry"]
#         geom_type = geometry["type"]
#         coordinates = geometry["coordinates"]
#         extracted_data.append({
#             "geometry_type": geom_type,
#             "pk_track": properties.get("pk_track"),
#             "track_uuid": properties.get("track_uuid"),
#             "gain_calibration": properties.get("gain_calibration"),
#             "time_ISO8601": properties.get("time_ISO8601"),
#             "time_epoch": properties.get("time_epoch"),
#             "noise_level": properties.get("noise_level"),
#             "time_length": properties.get("time_length"),
#             "pleasantness": properties.get("pleasantness"),
#             "tags": properties.get("tags"),
#             "party_tag": properties.get("party_tag"),
#             "coordinates": coordinates
#         })

#     df = pd.DataFrame(extracted_data)
#     df = df.sort_values(by="time_epoch")
#     df = df.drop(columns=["geometry_type", "pk_track", "track_uuid", "time_epoch", "party_tag"])

#     return df

# def compute_centroid(coord_nested):
#     # Assume polygon structure, take first element
#     coords = coord_nested[0]
#     poly = Polygon(coords)
#     centroid = poly.centroid

#     return [centroid.x, centroid.y]

def process_data():
    # Define URLs and file prefixes
    zip_url = 'https://data.noise-planet.org/noisecapture/United%20States.zip'
    extract_dir = 'noiseplanet_data'
    target_prefix = "United States_California_Los Angeles"

    # Download, extract, and filter the ZIP file contents
    download_and_extract(zip_url, extract_dir, target_prefix)
    print("Reformatting data...")

    # Define file paths 
    # file_path_areas = os.path.join(extract_dir, f"{target_prefix}.areas.geojson")
    file_path_points = os.path.join(extract_dir, f"{target_prefix}.points.geojson")
    # file_path_tracks = os.path.join(extract_dir, f"{target_prefix}.tracks.geojson")

    # Extract dataframes
    # df_areas = extract_areas(file_path_areas)
    df_points = extract_points(file_path_points)
    # df_tracks = extract_tracks(file_path_tracks)

    # Process areas dataframe: compute centroids and rename columns
    # df_areas.rename(columns={
    #     "la50": "median_sound_level",
    #     "laeq": "mean_sound_level",
    #     "first_measure": "start_time",
    #     "last_measure": "end_time"
    # }, inplace=True)
    # df_areas["center"] = df_areas["coordinates"].apply(compute_centroid)
    # df_areas["longitude"] = df_areas["center"].apply(lambda x: x[0])
    # df_areas["latitude"] = df_areas["center"].apply(lambda x: x[1])
    # df_areas.drop(columns=["coordinates", "center"], inplace=True)

    # Process points dataframe: adjust timestamps and rename columns
    df_points.rename(columns={"noise_level": "mean_sound_level", "time_gps_ISO8601": "start_time"}, inplace=True)
    df_points['start_time'] = pd.to_datetime(df_points['start_time'], utc=True)
    df_points['end_time'] = df_points['start_time'] + pd.Timedelta(seconds=1)
    df_points['start_time'] = df_points['start_time'].apply(lambda dt: dt.isoformat())
    df_points['end_time'] = df_points['end_time'].apply(lambda dt: dt.isoformat())

    print(df_points.columns)

    # Process tracks dataframe: compute centroid, adjust timestamps, and rename columns
    # def get_center_tracks(coord_nested):
    #     if not isinstance(coord_nested, list) or len(coord_nested) == 0:
    #         return [None, None]
    #     try:
    #         coords = coord_nested[0]
    #         poly = Polygon(coords)
    #         centroid = poly.centroid
    #         return [centroid.x, centroid.y]
    #     except Exception:
    #         return [None, None]

    # df_tracks["center"] = df_tracks["coordinates"].apply(get_center_tracks)
    # df_tracks["longitude"] = df_tracks["center"].apply(lambda x: x[0])
    # df_tracks["latitude"] = df_tracks["center"].apply(lambda x: x[1])
    # df_tracks["start_time"] = pd.to_datetime(df_tracks["time_ISO8601"], utc=True)
    # df_tracks["start_time"] = df_tracks["start_time"].apply(lambda dt: dt.isoformat())
    # df_tracks["time_length"] = pd.to_timedelta(df_tracks["time_length"].astype(int), unit='s')
    # df_tracks["end_time"] = (pd.to_datetime(df_tracks["start_time"], utc=True) + df_tracks["time_length"]).apply(lambda dt: dt.isoformat())

    # df_tracks.drop(columns=["coordinates", "center", "gain_calibration"], inplace=True)
    # df_tracks.drop(columns="time_length", inplace=True)
    # df_tracks.drop(columns="time_ISO8601", inplace=True)

    # df_tracks.rename(columns={"noise_level": "mean_sound_level"}, inplace=True)

    # Merge the dataframes on start_time, end_time, longitude, and latitude
    # df_merged = pd.merge(df_areas, df_points, on=['start_time', 'end_time', 'longitude', 'latitude'], how='outer')
    # df_merged = pd.merge(df_merged, df_tracks, on=['start_time', 'end_time', 'longitude', 'latitude'], how='outer')

    df_merged = df_points
    df_merged.sort_values(by=['start_time', 'end_time'], inplace=True)

    # Merge duplicate rows if needed
    def merge_mean_sound_levels(row):
        values = [row.get('mean_sound_level_x'), row.get('mean_sound_level_y'), row.get('mean_sound_level')]
        non_nan = [v for v in values if pd.notna(v)]

        return non_nan[0] if len(non_nan) == 1 else (sum(non_nan) / len(non_nan) if non_nan else None)

    def merge_pleasantness(row):
        values = [row.get('mean_pleasantness'), row.get('pleasantness')]
        non_nan = [v for v in values if pd.notna(v)]

        return non_nan[0] if len(non_nan) == 1 else (sum(non_nan) / len(non_nan) if non_nan else None)

    df_merged['mean_sound_level'] = df_merged.apply(merge_mean_sound_levels, axis=1)
    df_merged['pleasantness'] = df_merged.apply(merge_pleasantness, axis=1)
    df_merged.drop(columns=['mean_sound_level_x', 'mean_sound_level_y', 'mean_pleasantness'], inplace=True, errors='ignore')

    # Remove duplicate rows with the same start and end times 
    def merge_category(df, i, category):
        val1 = df.iloc[i][category]
        val2 = df.iloc[i + 1][category]

        if pd.notna(val1) and pd.notna(val2):
            if category == 'tags':
                merged_tags = val1 + [tag for tag in val2 if tag not in val1]
                df.at[i, category] = merged_tags
            elif isinstance(val1, str) or isinstance(val2, str):
                df.at[i, category] = f"{val1}, {val2}"
            else:
                df.at[i, category] = (val1 + val2) / 2
        elif pd.isna(val1):
            df.at[i, category] = val2
        elif pd.isna(val2):
            df.at[i, category] = val1

    def merge_row_pair(df, i):
        if df.iloc[i]['start_time'] == df.iloc[i + 1]['start_time'] and df.iloc[i]['end_time'] == df.iloc[i + 1]['end_time']:
            # columns_to_merge = ['median_sound_level', 'pleasantness', 'longitude', 'latitude',
            #                     'speed', 'accuracy', 'altitude', 'mean_sound_level', 'tags']
            columns_to_merge = ['pleasantness', 'longitude', 'latitude',
                    'speed', 'accuracy', 'altitude', 'mean_sound_level']

            for category in columns_to_merge:
                merge_category(df, i, category)

            return True
        
        return False

    def merge_duplicate_rows(df):
        rows_to_drop = []
        i = 0

        while i < len(df) - 1:
            if df.iloc[i]['start_time'] == df.iloc[i + 1]['start_time'] and df.iloc[i]['end_time'] == df.iloc[i + 1]['end_time']:
                merge_row_pair(df, i)
                rows_to_drop.append(df.index[i + 1])

            i += 1

        df.drop(index=rows_to_drop, inplace=True)
        df.reset_index(drop=True, inplace=True)

    merge_duplicate_rows(df_merged)

    # Convert times to datetime objects
    df_merged['start_time'] = pd.to_datetime(df_merged['start_time'], utc=True)
    df_merged['end_time'] = pd.to_datetime(df_merged['end_time'], utc=True)

    # Now filter using datetime comparisons
    local_tz = ZoneInfo("America/Los_Angeles")
    now_local = datetime.now(local_tz)
    yesterday_local = (now_local - timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
    today_local = yesterday_local + timedelta(days=1)

    start_utc = yesterday_local.astimezone(ZoneInfo("UTC"))
    end_utc = today_local.astimezone(ZoneInfo("UTC"))

    df_merged = df_merged[
        (df_merged["start_time"] >= start_utc) & (df_merged["start_time"] < end_utc)
    ]

    # Convert to UNIX
    df_merged['start_time'] = df_merged['start_time'].astype('int64') // 10**9
    df_merged['end_time'] = df_merged['end_time'].astype('int64') // 10**9

    # Clean up extraction directory
    print("Reformatting completed!")
    shutil.rmtree('noiseplanet_data')

    return df_merged

if __name__ == "__main__":

    data_folder = get_config()["save_folder"]

    df_final = process_data()

    current_time = datetime.now()
    current_time_str = current_time.strftime("%Y%m%d%H%M%S")
    current_day = current_time.strftime("%Y%m%d")

    # Create save folder
    save_folder = data_folder + "/noise_planet"
    if not os.path.exists(save_folder):
        os.mkdir(save_folder)
    day_folder = save_folder + "/" + current_day
    if not os.path.exists(day_folder):
        os.mkdir(day_folder)

    
    # Create filename based on current UTC date (YYYYMMDD)
    prev_date_str = (datetime.now(timezone.utc) - timedelta(days=2)).strftime("%Y%m%d")
    output_filename = os.path.join(day_folder, f"{prev_date_str}.csv")
    
    df_final.to_csv(output_filename, index=False)
    print(f"Data saved to {output_filename}")
