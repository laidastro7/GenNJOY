import os
import sys
import shutil
import time
from multiprocessing import Process, cpu_count
import DataGenerator
from colorama import Fore, Style, init

init(autoreset=True)


def run_njoy(input_filename):
    """
    Function to run the NJOY processing with the given input file.
    """
    start_time = time.time()
    current_directory = os.getcwd()

    try:
        with open(input_filename, 'r'):
            pass
    except FileNotFoundError:
        print("\nError:\n        No file '{}' found in directory '{}'\n".format(input_filename, current_directory))
        sys.exit()


if __name__ == "__main__":
    try:
        input_filename = sys.argv[1]
    except IndexError:
        print("\nError:\n        No input file specified.")
        print("        (Example: 'python3 gen_njoy.py neutron_process_batch.i'.)\n")
        sys.exit()

    run_njoy(input_filename)


start_time = time.time()
current_directory = os.getcwd()
try:
    with open(sys.argv[1], 'r'):
        pass
except IndexError:
    print("\nError:\n        No input file specified.")
    print("        (Example: 'python3 gen_njoy.py inputs/neutron_process_batch.i'.)\n")
    sys.exit()
except FileNotFoundError:
    print("\nError:\n        No file '{}' in directory '{}'\n".format(sys.argv[1], current_directory+"/inputs"))
    sys.exit()


# Définissez le chemin vers le dossier njoy_bin
njoy_folder = os.path.join(current_directory, "njoy_bin")

# Mettez à jour LD_LIBRARY_PATH pour inclure le dossier njoy_bin
os.environ['LD_LIBRARY_PATH'] = njoy_folder + ":" + os.environ.get('LD_LIBRARY_PATH', '')

# Définissez le chemin par défaut de l'exécutable njoy
default_njoy_executable_path = os.path.join(njoy_folder, "njoy")

try:
    # Demandez à l'utilisateur d'entrer le chemin de l'exécutable njoy, ou utilisez le chemin par défaut
    executable_path = input("Enter the PATH to the njoy executable (default is '{}'): ".format(default_njoy_executable_path)).strip() or default_njoy_executable_path
    print('-' * 50)

    # Vérifiez si l'exécutable njoy existe au chemin spécifié
    if not os.path.exists(executable_path):
        raise AssertionError("njoy executable not found")

except AssertionError as e:
    print("\nError:\n        {} at '{}'.\n".format(e, executable_path))
    sys.exit()


try:
    default_path_data = os.path.join(current_directory, "data/neutron_eval")
    path_data = input("Enter the path to the nuclear data (default is '{}'): ".format(default_path_data)).strip() or default_path_data
    os.environ['OPENMC_ENDF_DATA'] = path_data
    assert os.path.isdir(path_data)
except AssertionError:
    print("\nError:\n        Invalid directory '{}'.\n".format(path_data))
    sys.exit()

cpu_count = cpu_count()
print('-' * 50)
print("Number of CPUs in this system: {}".format(cpu_count))
cpu_input = input("Enter the number of CPUs to use for parallel processing (default is {}): ".format(cpu_count)).strip() or cpu_count
cpu_count = int(cpu_input)
print('-' * 50)

data_directory = 'data/ace_neutrons'
if os.path.isdir(data_directory):
    shutil.rmtree(data_directory)
os.mkdir(data_directory)

input_directory = 'data/njoy_inputs'
'''
if os.path.isdir(input_directory):
    shutil.rmtree(input_directory)
os.mkdir(input_directory)
'''
data_generator = DataGenerator.ACEGenerator(sys.argv[1])
matched_file_input = data_generator.search_string_in_file(data_generator.filename, "element")
readlines = [elem2 for elem1, elem2 in matched_file_input]

def run_multi_cpu(first, last, data_directory):
    for line in readlines[first:last]:
        njoy_params = data_generator.gen_parametre_njoy(line)
        element, name, temperatures = njoy_params[0], njoy_params[1], njoy_params[2]
        ace_ascii = name
        input_njoy = name + '.njoy'
        njoy_output = data_generator.run_njoy(current_directory, element, name, temperatures, ace_ascii, input_njoy, executable_path, data_directory)
        file_ace = njoy_output
        num_line = []
        for i, temperature in enumerate(temperatures, 1):
            suffix = '.' + '{:02}'.format(i) + 'c'
            matched_file_ace = data_generator.search_string_in_file(file_ace, suffix)
            num_line.append(str(matched_file_ace[0][0]))
        data_generator.gen_xsdir(name, num_line, current_directory, data_directory, temperatures)

#============ RUN MULTI CPUs =========================================
try:
	p = []
	cpu = int(cpu_count) 
	if cpu < 0:
		raise ValueError("Negative value")
	division = len(readlines) // cpu	
	remainder  = len(readlines) % cpu
	if remainder == 0:
		num_isotop_cpu = division 
	else:
		num_isotop_cpu = division + 1
	first = 0	
	final = num_isotop_cpu
	i=0
	while i < cpu:
		p.append(Process(target=run_multi_cpu, args=(first, final, data_directory, )))
		first+=num_isotop_cpu
		final+=num_isotop_cpu
		i+=1
	
	i = 0
	while i < cpu:
		p[i].start()
		i+=1
	
	i = 0
	while i < cpu:
		p[i].join()
		i+=1
	print('-'.center(50, '-'))
	print(Fore.GREEN + "\nNumber of successfully generated isotopes: {}".format(len(readlines)) + Style.RESET_ALL)
except ZeroDivisionError:
	print("\nError:\n        Choose a 'CPUs' number different from zero.\n")
	sys.exit()
except ValueError:
	print("\nError:\n        Incorrect 'CPUs' value.\n")
	sys.exit()
#======================================================================
print('-'.center(50, '-'))
print(time.strftime("Execution time: %Hh:%Mm:%Ss \n",time.gmtime(time.time() - start_time)))

message = "Program finished"
width = 50
padding = (width - len(message) - 2) // 2 
border = "*" * width
centered_message = "*{pad}{message}{pad}*".format(pad=' ' * padding, message=message)

print(Fore.RED + border + Style.RESET_ALL)
print(Fore.RED + centered_message + Style.RESET_ALL)
print(Fore.RED + border + Style.RESET_ALL)
print('\n')