# -*- coding: utf-8 -*-
import sys
import os
import DataGenerator
import json
from colorama import Fore, Style, init

init(autoreset=True)

current_directory = os.getcwd()

# Remove the existing input file if it exists
if os.path.isfile("inputs/input_tsl_global.i"):
    os.remove("inputs/input_tsl_global.i")

# Set the path for thermal nuclear data from ENDFB/VIII.0 library
#default_thermal_path = os.path.join(current_directory, "data/thermal_eval")
default_thermal_path =  "data/thermal_eval"
thermal_data_path = (
    input(
        f"Enter the path for thermal nuclear data\n(default: {default_thermal_path}): "
    ).strip()
    or default_thermal_path
)
os.environ["OPENMC_ENDF_DATA_Thermal"] = thermal_data_path

# Check if the directory for thermal nuclear data exists
if not os.path.isdir(thermal_data_path):
    print(f"\nError:\nDirectory '{thermal_data_path}' does not exist.\n")
    sys.exit()

print("-" * 50)

# Set the path for neutron nuclear data
#default_neutron_path = os.path.join(current_directory, "data/neutron_eval")
default_neutron_path =  "data/neutron_eval"
neutron_data_path = (
    input(
        f"Enter the path for neutron nuclear data\n(default: {default_neutron_path}): "
    ).strip()
    or default_neutron_path
)
os.environ["OPENMC_ENDF_DATA_Neutron"] = neutron_data_path

# Check if the directory for neutron nuclear data exists
if not os.path.isdir(neutron_data_path):
    print(f"\nError:\nDirectory '{neutron_data_path}' does not exist.\n")
    sys.exit()

print("-" * 50)

# Load the dictionaries from the JSON files
with open("src/dict_thermal.json", "r") as f:
    dict_thermal = json.load(f)

with open("src/dict_temperature.json", "r") as f:
    dict_temperature = json.load(f)

with open("src/dict_neutron.json", "r") as f:
    dict_neutron = json.load(f)

# Find the maximum length of the filenames in the thermal directory
max_length = max(len(file_name) for file_name in os.listdir(thermal_data_path))

# Generate input for each neutron data file
element_dict = {}
for file_name in os.listdir(neutron_data_path):
    try:
        input_generator = DataGenerator.InputGenerator(file_name)
        element = input_generator.element
        if element is None:
            raise IndexError
        index = input_generator.index_majuscule(element)
        name_n = input_generator.gen_name(element)
        name_n = "".join(name_n)
        element_dict[name_n] = element
    except IndexError:
        print(f"\nError:\n'{file_name}' is not a nuclear data file!\n")
        print("-" * 50)

num_passed = 0
num_failed = 0

# Generate input for each thermal data file
for file_name in os.listdir(thermal_data_path):
    try:
        input_generator = DataGenerator.InputGenerator(file_name)
        name_t = dict_thermal[file_name]
        temperature = dict_temperature[file_name]
        element_n = element_dict[dict_neutron[file_name]]
        input_line = input_generator.gen_input_tsl(
            current_directory,
            input_generator.element,
            element_n,
            name_t,
            temperature,
            max_length,
        )
        num_passed += 1
    except IndexError:
        # print(f"\nError:\n'{file_name}' is not a nuclear data file!\n")
        print(
            Fore.RED
            + f"\nError:\n'{file_name}' is not a nuclear data file!\n"
            + Style.RESET_ALL
        )
        print("-" * 50)
        num_failed += 1
    '''except KeyError:
        # print(f"\nError:\n'{file_name}' not found in dict_name_t.json!\n")
        print(
            Fore.RED
            + f"\nError:\n'{file_name}' not found in dict_name_t.json!\n"
            + Style.RESET_ALL
        )
        print("-" * 50)
        num_failed += 1'''

# Print the message in green
print(
    Fore.GREEN
    + "Total number of isotopes : {}".format(
        num_passed
    )
    + Style.RESET_ALL
)
#print(Fore.RED + "Number of Failed isotopes: {}".format(num_failed) + Style.RESET_ALL)

message = "Program finished"
width = 50
padding = (width - len(message) - 2) // 2
border = "*" * width
centered_message = "*{pad}{message}{pad}*".format(pad=" " * padding, message=message)

print(Fore.GREEN + border + Style.RESET_ALL)
print(Fore.GREEN + centered_message + Style.RESET_ALL)
print(Fore.GREEN + border + Style.RESET_ALL)
print("\n")