import os
import numpy as np
from PIL import Image
from utilities.util import get_config
from tqdm import tqdm
import tarfile
import shutil

# tar func
def package_dir(orig_dir, tar_path):
    with tarfile.open(tar_path, "w") as tar:
        tar.add(orig_dir, arcname=os.path.basename(orig_dir))


# Remove old folder
def remove_folder(dir_to_remove):

    try:
        shutil.rmtree(dir_to_remove)
        print(f"Folder '{dir_to_remove}' and its contents have been deleted.")
    except Exception as e:
        print(f"An error occurred: {e}")



if __name__ == "__main__":

    config_data = get_config()
    save_folder = config_data["save_folder"]
    backup_folder = config_data["backup_folder"]

    # Visit the CCTV folder and iterate through each day and camera.
    #  compress by day for each camera (so each day/camera has a compressed file)

    data_backup = os.path.join(backup_folder, "raw/cctv")

    
    
    # for day_folder in tqdm(os.listdir("temp")):

    #     day_path = os.path.join("temp", day_folder)
    #     if '.tar' in day_path:
    #         continue

    #     for camera_file in os.listdir(day_path):

    #         camera_day_path = os.path.join(day_path, camera_file)
            
    #         if ".tar" not in camera_day_path:
    #             continue

    #         with tarfile.open(camera_day_path, "r") as tar:
    #             tar.extractall(day_path)

    #         # # Create package
    #         # package_dir(camera_day_dir, save_cam_folder+".tar")
    #         # remove old directory
    #         os.remove(camera_day_path)

    #     # Extract the day folder
    #     package_dir(day_path, day_path+".tar")
    #     # Also remove the old folder
    #     remove_folder(day_path)



    for day_folder in tqdm(os.listdir(data_backup)):

        if ".tar" in day_folder:
            continue
        
        day_path = os.path.join(data_backup, day_folder)

        save_day_folder = os.path.join("temp", day_folder)
        # os.makedirs(save_day_folder, exist_ok=True)

        package_dir(day_path, save_day_folder+".tar")
        remove_folder(day_path)

        # for camera_folder in os.listdir(day_path):

        #     camera_day_dir = os.path.join(day_path, camera_folder)

        #     save_cam_folder = os.path.join(save_day_folder, camera_folder)
        #     os.makedirs(save_day_folder, exist_ok=True)

        #     # Create package
        #     package_dir(camera_day_dir, save_cam_folder+".tar")
        #     # remove old directory
        #     remove_folder(camera_day_dir)
            


