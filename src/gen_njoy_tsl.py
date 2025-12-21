# -*- coding: utf-8 -*-
import os
import time
import shutil
import sys
import DataGenerator
from multiprocessing import Process
import json
from colorama import Fore, Style, init

init(autoreset=True)
# Start timing
start_time = time.time()

# Get current directory
dir = os.getcwd()
# -----------------------------------------------------------------------------
# input file
# -----------------------------------------------------------------------------
# Check for input file
try:
    with open(sys.argv[1], "r") as file:
        pass
except IndexError:
    print(
        Fore.RED + "\nError: " + Style.RESET_ALL + "\n        No input file provided."
    )
    print(
        "        (Example of execution: 'python3 gen_njoy_tsl.py inputs/input_tsl.i'.)\n"
    )
    sys.exit()
except FileNotFoundError:
    print(
        Fore.RED
        + "\nError: "
        + Style.RESET_ALL
        + "\n        No file '{}' found in directory '{}'\n".format(
            sys.argv[1], dir + "inputs"
        )
    )
    sys.exit()

# -----------------------------------------------------------------------------
# njoy executable
# -----------------------------------------------------------------------------
# Relative path to the njoy_bin directory
relative_njoy_bin_dir = "njoy_bin"

# Convert the relative path to an absolute path
absolute_njoy_bin_dir = os.path.abspath(relative_njoy_bin_dir)

# Update LD_LIBRARY_PATH to include the njoy_bin directory
os.environ["LD_LIBRARY_PATH"] = (
    absolute_njoy_bin_dir + ":" + os.environ.get("LD_LIBRARY_PATH", "")
)

# Set default path for the njoy executable
default_njoy_exec_path = os.path.join(relative_njoy_bin_dir, "njoy")

# Prompt user for the path to the njoy executable or use default
try:
    prompt_message = "Enter the PATH to the njoy executable (Default: {}): ".format(
        default_njoy_exec_path
    )

    if os.path.isabs(default_njoy_exec_path):
        pass
    else:
        default_njoy_exec_path = os.path.abspath(default_njoy_exec_path)

    njoy_exec_path = input(prompt_message).strip() or default_njoy_exec_path

    print("-" * 50)

    # Check if the njoy executable exists at the specified path
    if not os.path.exists(njoy_exec_path) and not shutil.which("njoy"):
        print(
            Fore.RED + "\nError:\n        njoy executable not found at "
            "'{}' nor in system PATH.\n".format(njoy_exec_path) + Style.RESET_ALL
        )
        sys.exit()
except Exception as e:
    print(
        Fore.RED
        + "\nError:\n        Unexpected error: {}\n".format(e)
        + Style.RESET_ALL
    )
    sys.exit()

# -----------------------------------------------------------------------------
# incident nuclear data evaluation
# -----------------------------------------------------------------------------
# Set path for incident nuclear data
try:
    default_neutron_data_path = "data/neutron_eval"
    prompt_neutron_data = (
        "Enter the path to the incident nuclear data (Default: {}): ".format(
            default_neutron_data_path
        )
    )
    neutron_data_path = input(prompt_neutron_data).strip()
    neutron_data_path = neutron_data_path or default_neutron_data_path

    # Check if the path is absolute or relative
    if os.path.isabs(neutron_data_path):
        os.environ["OPENMC_ENDF_DATA_Neutron"] = neutron_data_path
    else:
        # Prefix the relative path with "../"
        os.environ["OPENMC_ENDF_DATA_Neutron"] = os.path.join("..", neutron_data_path)

    # Validate the directory path
    if not os.path.isdir(neutron_data_path):
        print(
            Fore.RED
            + "\nError:\n        Invalid directory '{}'.\n".format(neutron_data_path)
            + Style.RESET_ALL
        )
        sys.exit()
except Exception as e:
    print(
        Fore.RED
        + "\nError:\n        Unexpected error: {}\n".format(e)
        + Style.RESET_ALL
    )
    sys.exit()

# -----------------------------------------------------------------------------
# thermal nuclear data evaluation
# -----------------------------------------------------------------------------
# Set path for thermal nuclear data
try:
    default_thermal_data_path = "data/thermal_eval"
    prompt_thermal_data = (
        "Enter the path to the thermal nuclear data (Default: {}): ".format(
            default_thermal_data_path
        )
    )
    thermal_data_path = input(prompt_thermal_data).strip()
    thermal_data_path = thermal_data_path or default_thermal_data_path

    # Check if the path is absolute or relative
    if os.path.isabs(thermal_data_path):
        os.environ["OPENMC_ENDF_DATA_Thermal"] = thermal_data_path
    else:
        # Prefix the relative path with "../"
        os.environ["OPENMC_ENDF_DATA_Thermal"] = os.path.join("..", thermal_data_path)

    # Validate the directory path
    if not os.path.isdir(thermal_data_path):
        print(
            Fore.RED
            + "\nError:\n        Invalid directory '{}'.\n".format(thermal_data_path)
            + Style.RESET_ALL
        )
        sys.exit()
except Exception as e:
    print(
        Fore.RED
        + "\nError:\n        Unexpected error: {}\n".format(e)
        + Style.RESET_ALL
    )
    sys.exit()


# -----------------------------------------------------------------------------
# njoy execution on parallel mode
# -----------------------------------------------------------------------------
# ------------------ CPU count -----------------------------------
cpuCount = os.cpu_count()
print("Number of CPUs in this system:", cpuCount)
text = (
    "Enter the number of CPUs for parallel execution "
    + "(Default = "
    + str(cpuCount)
    + "): "
)
cpu = input(text) or cpuCount
# -------- Processed tsl nuclear data directory --------------
print("-".center(50, "-"))
rep_data = "data/ace_tsl"
if os.path.isdir(rep_data) == True:
    shutil.rmtree(rep_data)
    os.mkdir(rep_data)
else:
    os.mkdir(rep_data)

data_generator = DataGenerator.ACEGenerator(sys.argv[1])
matched_file_n = data_generator.search_string_in_file(
    data_generator.filename, "element_n"
)
readlines_n = []
for line_num, line_content in matched_file_n:
    readlines_n.append(line_content)

matched_file_t = data_generator.search_string_in_file(
    data_generator.filename, "element_t"
)
readlines_t = []
for line_num, line_content in matched_file_t:
    readlines_t.append(line_content)

with open("src/dict_temperature.json", "r") as f:
    dict_temperature = json.load(f)


# Define function to check if temperature is valid
def is_valid_temperature(temp, element_t):
    if element_t in dict_temperature:
        temperatures = dict_temperature[element_t].split()
        # convert temperatures to float
        temperatures = [float(i) for i in temperatures]
        if temp in temperatures:
            return True
        else:
            return False
    else:
        print(
            Fore.RED
            + "\nError: "
            + Style.RESET_ALL
            + "\n The isotope {} does not exist in the dictionary".format(element_t)
        )


def run_multi_cpu(first, final, rep_data):
    i = 0
    j = 0
    while i < len(readlines_n[first:final]) and j < len(readlines_t[first:final]):
        line_n = readlines_n[first + i]
        line_t = readlines_t[first + j]
        njoy_param_n = data_generator.gen_parametre_njoy(line_n)
        njoy_param_t = data_generator.gen_parametre_njoy(line_t)
        element_n = njoy_param_n[0]
        element_t = njoy_param_t[0]
        file_name = njoy_param_t[1]
        temperatures = njoy_param_t[2]

        if all(is_valid_temperature(temp, element_t) for temp in temperatures):
            ace_ascii = file_name

            input_njoy = file_name + ".njoy"
            njoy_tsl_output = data_generator.run_njoy_tsl(
                dir,
                element_n,
                element_t,
                file_name,
                temperatures,
                ace_ascii,
                input_njoy,
                njoy_exec_path,
                rep_data,
            )
            ace_file = njoy_tsl_output
            k = 1
            line_numbers = []
            while k <= len(temperatures):
                suffix = "." + "{:02}".format(k) + "t"
                matched_ace_file = data_generator.search_string_in_file(
                    ace_file, suffix
                )
                line_numbers.append(str(matched_ace_file[0][0]))
                k += 1

        else:
            # eliminate invalid temperatures
            valid_temperatures = [
                temp for temp in temperatures if is_valid_temperature(temp, element_t)
            ]
            print(
                Fore.RED
                + " Error: "
                + Style.RESET_ALL
                + "\n The temperature(s)"
                + Fore.RED
                + "{}".format(set(temperatures) - set(valid_temperatures))
                + Style.RESET_ALL
                + " in {} is(are) not found in dict_temperature.json".format(element_t)
                + "\n"
            )
            ace_ascii = file_name
            print("name = ", ace_ascii)
            input_njoy = file_name + ".njoy"
            njoy_tsl_output = data_generator.run_njoy_tsl(
                dir,
                element_n,
                element_t,
                file_name,
                valid_temperatures,
                ace_ascii,
                input_njoy,
                njoy_exec_path,
                rep_data,
            )
            ace_file = njoy_tsl_output
            k = 1
            line_numbers = []
            while k <= len(valid_temperatures):
                suffix = "." + "{:02}".format(k) + "t"
                matched_ace_file = data_generator.search_string_in_file(
                    ace_file, suffix
                )
                line_numbers.append(str(matched_ace_file[0][0]))
                k += 1

        data_generator.gen_xsdir(file_name, line_numbers, dir, rep_data, temperatures)
        i += 1
        j += 1


try:
    # Check if the data directory exists
    if os.path.isdir(rep_data) == False:
        raise ValueError("Data directory does not exist")
    # Create a process for each CPU and distribute the workload
    processes = []
    num_cpus = int(cpu)
    if num_cpus <= 0:
        raise ValueError("Invalid CPU value")
    num_isotopes_per_cpu = len(readlines_n) // num_cpus
    remainder = len(readlines_n) % num_cpus
    if remainder == 0:
        isotopes_per_process = num_isotopes_per_cpu
    else:
        isotopes_per_process = num_isotopes_per_cpu + 1
    first_isotope_index = 0
    final_isotope_index = isotopes_per_process
    for i in range(num_cpus):
        processes.append(
            Process(
                target=run_multi_cpu,
                args=(
                    first_isotope_index,
                    final_isotope_index,
                    rep_data,
                ),
            )
        )
        first_isotope_index += isotopes_per_process
        final_isotope_index += isotopes_per_process
    # Start the processes
    for process in processes:
        process.start()
    # Wait for the processes to finish
    for process in processes:
        process.join()
    print("-".center(50, "-"))
    '''print(
        Fore.GREEN
        + "\nNumber of successfully generated isotopes: {}".format(len(readlines_t))
        + Style.RESET_ALL
    )'''
except ValueError as e:
    print(Fore.RED + "\nError: " + Style.RESET_ALL + "{}".format(e))
    sys.exit()
except Exception as e:
    print(Fore.RED + "\nError: " + Style.RESET_ALL + " {}".format(e))
    sys.exit()

# ======================================================================
print(
    time.strftime(
        "\nExecution time: %Hh:%Mm:%Ss \n", time.gmtime(time.time() - start_time)
    )
)
message = "Program finished"
width = 50
padding = (width - len(message) - 2) // 2
border = "*" * width
centered_message = "*{pad}{message}{pad}*".format(pad=" " * padding, message=message)

print(Fore.GREEN + border + Style.RESET_ALL)
print(Fore.GREEN + centered_message + Style.RESET_ALL)
print(Fore.GREEN + border + Style.RESET_ALL)
print("\n")
