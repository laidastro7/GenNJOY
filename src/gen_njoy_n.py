import os
import sys
import shutil
import time
from multiprocessing import Process, cpu_count
import DataGenerator
from colorama import Fore, Style, init

# Initialize colorama for colored console output
init(autoreset=True)
current_dir = os.getcwd()
start_time = time.time()


# -----------------------------------------------------------------------------
# input file
# -----------------------------------------------------------------------------
def run_njoy(input_file):
    try:
        with open(input_file, "r"):
            pass
    except FileNotFoundError:
        error_message = (
            "\nError:\n        No file '{}' found in " "directory '{}'\n"
        ).format(input_file, current_dir)
        print(Fore.RED + error_message + Style.RESET_ALL)
        sys.exit()


def get_input_file():
    try:
        return sys.argv[1]
    except IndexError:
        print(Fore.RED + "\nError:\n        No input file specified.")
        sys.exit()


if __name__ == "__main__":
    # Get input filename from command line arguments
    input_file_name = get_input_file()

    # Run NJOY processing
    run_njoy(input_file_name)

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
# Set path for nuclear data
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
        os.environ["OPENMC_ENDF_DATA"] = neutron_data_path
    else:
        # Prefix the relative path with "../"
        os.environ["OPENMC_ENDF_DATA"] = os.path.join("..", neutron_data_path)

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
# njoy execution on parallel mode
# -----------------------------------------------------------------------------
# Get CPU count for parallel processing
total_cpu_count = cpu_count()
print("-" * 50)
print("Number of CPUs in this system: {}".format(total_cpu_count))
try:
    user_cpu_input = (
        input(
            "Enter the number of CPUs to use for parallel "
            "processing (Default = {}): ".format(total_cpu_count)
        ).strip()
        or total_cpu_count
    )
    used_cpu_count = int(user_cpu_input)
except ValueError:
    print(Fore.RED + "\nError:\n        Invalid CPU count input.\n" + Style.RESET_ALL)
    sys.exit()
print("-" * 50)

# Prepare data directories
data_dir = "data/ace_neutrons"
if os.path.isdir(data_dir):
    shutil.rmtree(data_dir)
os.mkdir(data_dir)

input_dir = "data/njoy_inputs"
# Additional logic for input_dir if needed
# Prepare data directories
data_dir = "data/ace_neutrons"
if os.path.isdir(data_dir):
    shutil.rmtree(data_dir)
os.mkdir(data_dir)

# Initialize data generator with the input file
data_generator = DataGenerator.ACEGenerator(sys.argv[1])

# Search for "element" string in file and read lines
matched_file_input = data_generator.search_string_in_file(
    data_generator.filename, "element"
)
readlines = [line for _, line in matched_file_input]


def run_multi_cpu(start_index, end_index, directory):
    """
    Process a subset of data in parallel from start_index to end_index.
    """
    for line in readlines[start_index:end_index]:
        element, name, temperatures = data_generator.gen_parametre_njoy(line)
        ace_ascii, input_njoy = name, name + ".njoy"
        njoy_output = data_generator.run_njoy(
            current_dir,
            element,
            name,
            temperatures,
            ace_ascii,
            input_njoy,
            njoy_exec_path,
            directory,
        )

        # Process NJOY output
        process_njoy_output(njoy_output, temperatures, name, directory)


def process_njoy_output(file_ace, temperatures, name, directory):
    num_line = []
    for i, temperature in enumerate(temperatures, 1):
        suffix = "." + "{:02}".format(i) + "c"
        matched_file_ace = data_generator.search_string_in_file(file_ace, suffix)
        num_line.append(str(matched_file_ace[0][0]))
    data_generator.gen_xsdir(name, num_line, current_dir, directory, temperatures)


# Run processing on multiple CPUs
try:
    processes = []
    cpu = int(used_cpu_count)
    if cpu <= 0:
        raise ValueError("CPU count must be positive")

    # Calculate the workload for each CPU
    workload_per_cpu = len(readlines) // cpu + (len(readlines) % cpu > 0)
    for i in range(cpu):
        start, end = i * workload_per_cpu, min(
            (i + 1) * workload_per_cpu, len(readlines)
        )
        processes.append(Process(target=run_multi_cpu, args=(start, end, data_dir)))

    # Start and join the processes
    for process in processes:
        process.start()
    for process in processes:
        process.join()

    print("-".center(50, "-"))
    '''print(
        Fore.GREEN
        + "\nNumber of successfully generated isotopes: {}".format(len(readlines))
        + Style.RESET_ALL
    )'''
except ValueError as e:
    print(Fore.RED + "\nError:\n        {}\n".format(e) + Style.RESET_ALL)
    sys.exit()

# Print execution time and program completion message
print("-".center(50, "-"))
print(
    time.strftime(
        "Execution time: %Hh:%Mm:%Ss \n", time.gmtime(time.time() - start_time)
    )
)

message = "Program finished"
print(Fore.GREEN + "*" * 50 + Style.RESET_ALL)
print(Fore.GREEN + message.center(50) + Style.RESET_ALL)
print(Fore.GREEN + "*" * 50 + Style.RESET_ALL)
