import os
import pandas as pd

def get_column_of_interest(filepath, col_num):

    # Load the CSV file into a DataFrame
    df = pd.read_csv(filepath)

    # Get the last column
    last_column = df.iloc[:, col_num]

    return last_column.tolist()



if __name__ == "__main__":

    
    gdelt_data_dir = "../pulled_data/gkg"
    gdelt_vkg_data_dir = "../pulled_data/vkg"

    # Get all files in this directory
    gdelt_files = os.listdir(gdelt_data_dir)
    gdelt_event_files = [x for x in gdelt_files if "export" in x]
    gdelt_event_files = [os.path.join(gdelt_data_dir, x) for x in gdelt_event_files]
    gdelt_gkg_files = [x for x in gdelt_files if "gkg" in x]
    gdelt_gkg_files = [os.path.join(gdelt_data_dir, x) for x in gdelt_gkg_files]

    vkg_files = os.listdir(gdelt_vkg_data_dir)
    vkg_files = [x for x in vkg_files if "vgkg" in x]
    vkg_files = [os.path.join(gdelt_vkg_data_dir, x) for x in vkg_files]

    # Iterate and get all last columns
    event_sources = []
    for x in gdelt_event_files:
        event_sources.extend(get_column_of_interest(x,-1))
    print(set(event_sources))

    gkg_sources = []
    for x in gdelt_gkg_files:
        gkg_sources.extend(get_column_of_interest(x, 4))
    print(set(gkg_sources))

    vkg_sources = []
    for x in vkg_files:
        vkg_sources.extend(get_column_of_interest(x, 1))
    print(set(vkg_sources))
    print(len(set(vkg_sources)))