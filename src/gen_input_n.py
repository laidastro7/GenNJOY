# -*- coding: utf-8 -*-
import sys
import os
import DataGenerator
from colorama import Fore, Style, init

init(autoreset=True)
# Get the current working directory
current_directory = os.getcwd()

# Delete the 'input_global.i' file if it exists
if os.path.isfile("inputs/input_n_global.i"):
    os.remove("inputs/input_n_global.i")

try:
    # Prompt the user for the path to the nuclear data directory
    #default_path = os.path.join(current_directory, "data/neutron_eval")
    default_path = "data/neutron_eval"
    prompt_text = (
        "Enter the path to the nuclear data directory\n(Default: {}): ".format(
            default_path
        )
    )
    PATH_DATA = input(prompt_text) or default_path
    PATH_DATA = PATH_DATA.strip()
    # Set the environment variable for the nuclear data directory
    os.environ["OPENMC_ENDF_DATA"] = PATH_DATA
    # Verify that the directory exists
    assert os.path.isdir(PATH_DATA)
except AssertionError:
    print("\nError:\n        The directory '{}' does not exist.\n".format(PATH_DATA))
    sys.exit()

print("-".center(50, "-"))

try:
    # Prompt the user for temperatures
    default_temperatures = "300. 600. 900."
    prompt_text = "Enter the temperatures\n(Default: {}): ".format(default_temperatures)
    temperatures_input = input(prompt_text) or default_temperatures
    temperatures_input = temperatures_input.split()
    temperatures = [float(temp) for temp in temperatures_input]
    # Ensure all temperatures are non-negative
    assert all(temp >= 0 for temp in temperatures)
except ValueError:
    print("\nError:\n        Invalid temperature values.\n")
    sys.exit()
except AssertionError:
    print("\nError:\n        Negative temperature value(s) detected.\n")
    sys.exit()

# Convert temperatures to a string for display
temperature_string = " ".join(str(temp) for temp in temperatures)

print("-".center(50, "-"))

# Generate ACE files for all isotopes in the nuclear data directory
file_list = os.listdir(PATH_DATA)
max_file_name_length = max(len(file) for file in file_list)
num_isotopes = 0
for file in file_list:
    try:
        data = DataGenerator.InputGenerator(file)
        name = data.gen_name(data.element)
        line = data.gen_input(
            current_directory,
            data.element,
            name[0],
            name[1],
            temperature_string,
            max_file_name_length,
        )
        num_isotopes += 1
    except IndexError:
        print("\nError:\n        '{}' is not a valid nuclear data file.\n".format(file))
        print("-".center(50, "-"))

print(Fore.GREEN + "Total number of isotopes: " + str(num_isotopes) + Style.RESET_ALL)


message = "Program finished"
width = 50
padding = (width - len(message) - 2) // 2
border = "*" * width
centered_message = "*{pad}{message}{pad}*".format(pad=" " * padding, message=message)

print(Fore.GREEN + border + Style.RESET_ALL)
print(Fore.GREEN + centered_message + Style.RESET_ALL)
print(Fore.GREEN + border + Style.RESET_ALL)
print("\n")
