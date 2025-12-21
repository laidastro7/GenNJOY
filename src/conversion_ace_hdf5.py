import os
import shutil
import subprocess
import openmc.data
from colorama import Fore, Style, init

# Initialize colorama for colored console output
init(autoreset=True)

# Prepare data directories
folder_hdf5 = "data/hdf5"
if os.path.isdir(folder_hdf5):
    shutil.rmtree(folder_hdf5)
os.mkdir(folder_hdf5)


def get_directory_input(prompt, default):
    dir_path = input(prompt + f" (default: '{default}'): ").strip()
    return dir_path if dir_path else default

def verify_directory_contents(directory, special_file):
    # Check if the directory exists
    if not os.path.exists(directory):
        raise FileNotFoundError(f"The directory '{directory}' does not exist.")

    # Check for xsdir file
    if not os.path.isfile(os.path.join(directory, special_file)):
        raise FileNotFoundError(f"The '{special_file}' file is missing in the directory '{directory}'.")

    if os.path.exists(directory) and os.path.isdir(directory):
        # List everything in the directory
        if not os.listdir(directory):
            return True  # The directory is empty
        else:
            return False  # The directory is not empty
    else:
        raise FileNotFoundError(f"The directory '{directory}' does not exist.")

# Default paths
default_neutron_folder = "data/ace_neutrons"
default_thermal_folder = "data/ace_tsl"

# Get directory paths from user, or use default values
neutron_folder = get_directory_input("Enter the path for incident neutron data", default_neutron_folder)
thermal_folder = get_directory_input("Enter the path for thermal neutron scattering data", default_thermal_folder)

# Verify contents of the directories
try:
    verify_directory_contents(neutron_folder, "xsdir")
    #verify_directory_contents(thermal_folder, "xsdir")
except FileNotFoundError as e:
    print(Fore.RED + f"\nError:\n       {e}\n" + Style.RESET_ALL)
    exit(1)




# Run the openmc-ace-to-hdf5 script for incident neutrons
subprocess.run(
    [
        "src/openmc-ace-to-hdf5",
        "--destination",
        folder_hdf5,
        "--xsdir",
        os.path.join(neutron_folder, "xsdir"),
    ]
)

# Run the openmc-ace-to-hdf5 script for thermal scattering
subprocess.run(
    [
        "src/openmc-ace-to-hdf5",
        "--destination",
        folder_hdf5,
        "--xsdir",
        os.path.join(thermal_folder, "xsdir"),
    ]
)

# Create a new DataLibrary
library = openmc.data.DataLibrary()

# Register all HDF5 files in the library
for root, dirs, files in os.walk(folder_hdf5):
    for file in files:
        if file.endswith(".h5"):
            library.register_file(os.path.join(root, file))

# Export the library to XML
library.export_to_xml(os.path.join(folder_hdf5, "cross_sections.xml"))

message = "Program finished"
print(Fore.GREEN + "*" * 50 + Style.RESET_ALL)
print(Fore.GREEN + message.center(50) + Style.RESET_ALL)
print(Fore.GREEN + "*" * 50 + Style.RESET_ALL)
