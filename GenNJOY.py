import sys
import subprocess
from colorama import Fore, Style, init

# Initialize colorama
init(autoreset=True)

# Header for the NJOY data processing tool
gen_njoy_header = """
  ****    ***           *   *    ****   ****  *   *
 *       *   *   *      **  *      *   *    *  * *
 *  ***  *****   * * *  * * *      *   *    *   *
 *    *  *       *   *  *  **  *   *   *    *   *
  ****    ***    *   *  *   *   ****    ****    *
"""


def display_header():
    print("\n       NJOY Data Processing Tool")
    print(Fore.BLUE + gen_njoy_header + Style.RESET_ALL)
    print(
        "This tool offers various options for generating input data \n"
        "and executing NJOY for neutron data processing.\n"
    )


def get_input_file(default="inputs/input_n.i"):
    file_path = input(
        f"Enter the path of the input file (Default: {default}): "
    ).strip()
    return file_path if file_path else default


def get_input_file_tsl(default="inputs/input_tsl.i"):
    file_path = input(
        f"Enter the path of the input file for TSL (Default: {default}): "
    ).strip()
    return file_path if file_path else default


def display_menu():
    print("Please select the option you wish to execute:\n")
    print("1 - Download Incident and Thermal Data (ENDF-B-VIII.0)")
    print("2 - Generate Inputs for Incident Neutron Data")
    print("3 - Generate Inputs for Thermal Neutron Scattering Data")
    print("4 - Execute NJOY for Incident Neutron Data")
    print("5 - Execute NJOY for Thermal Neutron Scattering Data")
    print("6 - Convert ACE Library Files to HDF5 Format")
    print("7 - Exit\n")


def process_choice(choice):
    python_executable = sys.executable
    try:
        if choice == "1":
            subprocess.run([python_executable, "src/download_data.py"])        
        if choice == "2":
            subprocess.run([python_executable, "src/gen_input_n.py"])
        elif choice == "3":
            subprocess.run([python_executable, "src/gen_input_tsl.py"])
        elif choice == "4":
            input_file = get_input_file()
            subprocess.run([python_executable, "src/gen_njoy_n.py", input_file])
        elif choice == "5":
            input_file = get_input_file_tsl()
            subprocess.run([python_executable, "src/gen_njoy_tsl.py",
                            input_file])
        elif choice == "6":
            # Here's where we integrate the new conversion script
            subprocess.run([python_executable, "src/conversion_ace_hdf5.py"])
        elif choice == "7":
            print("\nExiting the program. Goodbye!")
            return False
    except Exception as e:
        print("\nError: " + str(e) + "\n")
    return True


def main():
    running = True
    display_header()
    while running:
        display_menu()
        choice = input("Enter the option number (1-7): ")
        running = process_choice(choice)


if __name__ == "__main__":
    main()
