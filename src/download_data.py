import requests
from bs4 import BeautifulSoup
import re
import os
import zipfile

def create_directory(dir_path):
    """Create a directory if it does not exist."""
    try:
        if not os.path.exists(dir_path):
            os.makedirs(dir_path)
    except OSError as error:
        print(f"Error creating directory {dir_path}: {error}\n")
        exit(1)

def download_and_extract(file_url, destination_dir):
    """Download and extract a zip file."""
    try:
        local_filename = os.path.join(destination_dir, file_url.split('/')[-1])

        with requests.get(file_url, stream=True) as r:
            r.raise_for_status()
            with open(local_filename, 'wb') as f:
                for chunk in r.iter_content(chunk_size=8192):
                    f.write(chunk)

        with zipfile.ZipFile(local_filename, 'r') as zip_ref:
            zip_ref.extractall(destination_dir)
            for file in zip_ref.namelist():
                file_path = os.path.join(destination_dir, file)
                file_size_bytes = os.path.getsize(file_path)
                file_size_kilobytes = file_size_bytes / 1024  # Convert bytes to kilobytes
                print(f" - {file} (Size: {file_size_kilobytes:.2f} KB)")  # Print size in KB

        os.remove(local_filename)
    except requests.HTTPError as http_err:
        print(f"HTTP error occurred: {http_err}\n")
    except requests.RequestException as req_err:
        print(f"Error downloading file: {req_err}\n")
    except zipfile.BadZipFile as bz_err:
        print(f"Bad ZIP file: {bz_err}\n")
    except OSError as os_err:
        print(f"OS error: {os_err}\n")

def process_data(url, destination_dir):
    """Process data from a given URL and download it to a specified directory."""
    try:
        response = requests.get(url)
        response.raise_for_status()
        soup = BeautifulSoup(response.content, 'html.parser')

        links = soup.find_all('a', href=re.compile(r"\.zip$"))
        file_links = [url + link.get('href') for link in links]

        print(f"Downloading files from: {url}\n")
        for file_link in file_links:
            download_and_extract(file_link, destination_dir)

        print(f"{len(file_links)} files have been downloaded and extracted to the directory: {os.path.abspath(destination_dir)}\n")
    except requests.HTTPError as http_err:
        print(f"HTTP error occurred while processing URL {url}: {http_err}\n")
    except requests.RequestException as req_err:
        print(f"Request error occurred while processing URL {url}: {req_err}\n")

# Destination directories
neutron_eval_dir = os.path.abspath('data/neutron_eval')
thermal_eval_dir = os.path.abspath('data/thermal_eval')

# Create directories if they do not exist
create_directory(neutron_eval_dir)
create_directory(thermal_eval_dir)

# Data URLs
neutron_data_url = 'https://www-nds.iaea.org/public/download-endf/ENDF-B-VIII.0/n/'
thermal_data_url = 'https://www-nds.iaea.org/public/download-endf/ENDF-B-VIII.0/tsl/'

# Process the data
try:
    process_data(neutron_data_url, neutron_eval_dir)
    process_data(thermal_data_url, thermal_eval_dir)
except Exception as e:
    print(f"An error occurred: {e}\n")
