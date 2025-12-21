import os
import re
import sys
import shutil
import openmc.data
from colorama import Fore, Style, init
import time


# Initialize terminal color conversion
init(autoreset=True)


class InputGenerator:
    """
    Class for generating neutron data input_global.
    """

    temperatures = ""

    def __init__(self, element):
        self.element = element

    def index_majuscule(self, element):
        """
        Method to get the index of the last uppercase letter in the given string.
        """
        pattern = re.compile("[A-Z]")
        start = -1
        while True:
            m = pattern.search(element, start + 1)
            if m is None:
                break
            start = m.start()
        return start

    def gen_temperature_tsl(self, dir, element_t):
        """
        Method to generate temperature for thermal scattering data.
        """
        os.chdir(dir)
        endf_data_t = os.environ["OPENMC_ENDF_DATA_Thermal"]
        endf_file_t = os.path.join(endf_data_t, element_t)
        with open(endf_file_t, "r") as fic:
            lines = fic.readlines()[0:5]
        print(lines[1])

    def gen_name(self, element):
        """
        Method to generate name for neutron data.
        """
        # Get the file name without the extension
        basename = os.path.splitext(os.path.basename(element))[0]
        # Split the element name and atomic mass
        parts = basename.split("-")
        # Get the symbol of the element
        isotop = parts[1]
        # Get the atomic mass of the isotope
        elem_num = parts[2]
        # Return the symbol of the element and the atomic mass of the isotope
        return isotop, elem_num

    def gen_input(self, dir, element, isotop, elem_num, temper, length):
        """
        Method to generate input for neutron data.
        """
        InputGenerator.temperatures = temper
        element_n = element.ljust(length)
        name = isotop.ljust(len(isotop)) + elem_num.ljust(6 - len(isotop))
        list = f"element_n = {element_n} name = {name} temperatures = {InputGenerator.temperatures}\n"
        line = "".join(list)
        with open(dir + "/inputs/input_n_global.i", "a") as fic:
            fic.write(line)

    def gen_input_tsl(self, dir, element_t, element_n, name_t, temper, lingth):
        InputGenerator.temperatures = temper
        list = (
            "element_n = "
            + element_n
            + "\n"
            + "element_t = "
            + element_t.ljust(lingth)
            + " name = "
            + name_t.ljust(6)
            + " temperatures = "
            + InputGenerator.temperatures
            + "\n\n"
        )
        line = "".join(list)
        with open(dir + "/inputs/input_tsl_global.i", "a") as fic:
            fic.write(line)


class ACEGenerator:
    def __init__(self, filename):
        self.filename = filename

    def search_string_in_file(self, file_name, string_to_search):
        """Search for the given string in file and return lines containing that string,
        along with line numbers"""
        line_number = 0
        list_of_results = []
        # Open the file in read only mode
        with open(file_name, "r") as read_obj:
            # Read all lines in the file one by one
            for line in read_obj:
                # For each line, check if line contains the string
                line_number += 1
                if string_to_search in line:
                    # If yes, then add the line number & line as a tuple in the list
                    list_of_results.append((line_number, line.rstrip()))
                    # print(line.rstrip())
        # Return list of tuples containing line numbers and lines where string is found
        return list_of_results

    def gen_parametre_njoy(self, readlines):
        # for line in readlines:
        s = readlines.split("=")
        resulta = []
        i = 1
        if len(s) > i:
            element = s[1].split()
            resulta.append((element[0]))
            i += 1
        if len(s) > i:
            name = s[2].split()
            resulta.append((name[0]))
            i += 1
        if len(s) > i:
            s[3] = s[3].split()
            temperatures = []
            for tem in s[3]:
                tem = float(tem)
                temperatures.append(tem)
            resulta.append((temperatures))

        return resulta

    def run_njoy(
        self,
        dir,
        element,
        name,
        temperatures,
        ace_ascii,
        input_njoy,
        PATH_njoy,
        rep_data,
    ):
        try:
            original_directory = os.getcwd()
            os.chdir(dir)
            endf_data = os.environ["OPENMC_ENDF_DATA"]
            endf_file = os.path.join(endf_data, element)

            if os.path.isdir(name):
                shutil.rmtree(name)
            os.mkdir(name)
            os.chdir(os.path.join(dir, name))

            openmc.data.njoy.make_ace(
                endf_file,
                error=0.001,
                temperatures=temperatures,
                acer=ace_ascii,
                input_filename=input_njoy,
                stdout=False,
                njoy_exec=PATH_njoy,
            )

            os.replace(ace_ascii, os.path.join(dir, rep_data, ace_ascii))
            os.replace(input_njoy, os.path.join(dir, "data/njoy_inputs", input_njoy))
            os.rename("xsdir", os.path.join(dir, rep_data, name + ".xsdir"))
            shutil.rmtree(os.path.join(dir, name))
            file_ace = os.path.join(dir, rep_data, ace_ascii)
            return file_ace

        except FileNotFoundError:
            print(
                "\nError:\n        No file '{}' found in directory '{}'\n".format(
                    element, endf_data
                )
            )
            sys.exit()
        finally:
            os.chdir(original_directory)

    def run_njoy_tsl(
        self,
        dir,
        element_n,
        element_t,
        name,
        temperatures,
        ace_ascii,
        input_njoy,
        PATH_njoy,
        rep_data,
    ):
        original_directory = os.getcwd()

        endf_data_n = os.environ["OPENMC_ENDF_DATA_Neutron"]
        endf_file_n = os.path.join(endf_data_n, element_n)

        endf_data_t = os.environ["OPENMC_ENDF_DATA_Thermal"]
        endf_file_t = os.path.join(endf_data_t, element_t)

        os.chdir(dir)
        if os.path.isdir(name):
            shutil.rmtree(name)
        os.mkdir(name)
        os.chdir(os.path.join(dir, name))

        try:
            if not os.path.isdir(dir):
                raise ValueError(f"The specified directory '{dir}' does not exist.")

            endf_data_n = os.environ.get("OPENMC_ENDF_DATA_Neutron")
            if not endf_data_n:
                raise EnvironmentError(
                    "The environment variable 'OPENMC_ENDF_DATA_Neutron' is not set."
                )

            endf_file_n = os.path.join(endf_data_n, element_n)
            if not os.path.exists(endf_file_n):
                raise FileNotFoundError(
                    f"The neutron file '{element_n}' cannot be found in '{endf_data_n}'."
                )

            endf_data_t = os.environ.get("OPENMC_ENDF_DATA_Thermal")
            if not endf_data_t:
                raise EnvironmentError(
                    "The environment variable 'OPENMC_ENDF_DATA_Thermal' is not set."
                )

            endf_file_t = os.path.join(endf_data_t, element_t)
            if not os.path.exists(endf_file_t):
                raise FileNotFoundError(
                    f"The thermal file '{element_t}' cannot be found in '{endf_data_t}'."
                )

            openmc.data.njoy.make_ace_thermal(
                endf_file_n,
                endf_file_t,
                error=0.01,
                iwt=2,
                temperatures=temperatures,
                ace=ace_ascii,
                input_filename=input_njoy,
                stdout=False,
                njoy_exec=PATH_njoy,
            )

            os.replace(ace_ascii, os.path.join(dir, rep_data, ace_ascii))
            os.replace(input_njoy, os.path.join(dir, "data/njoy_inputs", input_njoy))
            os.rename("xsdir", os.path.join(dir, rep_data, name + ".xsdir"))
            shutil.rmtree(os.path.join(dir, name))
            file_ace = os.path.join(dir, rep_data, ace_ascii)
            return file_ace

        except FileNotFoundError as e:
            print("\nErreur de Fichier :", e)
            sys.exit(1)
        except EnvironmentError as e:
            print("\nErreur d'Environnement :", e)
            sys.exit(1)
        except Exception as e:
            print("\nErreur Inattendue :", e)
            sys.exit(1)
        finally:
            os.chdir(original_directory)

    def gen_xsdir(self, name, num_line, dir, rep_data, valid_temperatures):
        # Read atomic weight ratio data from the xsdir_mcnp5 file
        xsdir_path = os.path.join(dir, rep_data, "xsdir")

        # Check if the xsdir file already exists
        if not os.path.exists(xsdir_path):
            with open(dir + "/src/xsdir_mcnp5", "r") as atomic_weight_file:
                atomic_weight_data = atomic_weight_file.read()

            # Create or open the xsdir file for writing
            xsdir_path = os.path.join(dir, rep_data, "xsdir")
            with open(xsdir_path, "w") as fic:
                # Write the atomic weight ratio data
                fic.write(atomic_weight_data)

                # Write the execution date
                fic.write("\n" + time.strftime("%m/%d/%Y") + "\n")

                # Write the word 'directory'
                fic.write("directory\n")

        with open(dir + "/" + rep_data + "/" + name + ".xsdir", "r") as fic:
            readlines = fic.readlines()

        i = 0
        # create loop for readlines and valid_temperatures

        for line, temp in zip(readlines, valid_temperatures):
            w = line.split()
            word1 = w[0].rjust(11)
            word2 = w[1].rjust(11)
            word3 = name.rjust(6)
            word4 = "0".rjust(3)
            word5 = "1".rjust(2)
            word6 = num_line[i].rjust(8)
            word7 = w[6].rjust(8)
            word8 = "0".rjust(2)
            word9 = "0".rjust(2)
            word10 = w[9].rjust(10)
            word11 = "ptable".rjust(8)
            i += 1
            xdt = (
                word1
                + word2
                + word3
                + word4
                + word5
                + word6
                + word7
                + word8
                + word9
                + word10
                + word11
                + "\n"
            )
            print(
                "The file"
                + Fore.GREEN
                + "{} ".format(word1)
                + Style.RESET_ALL
                + "was passed with a temperature of"
                + Fore.GREEN
                + " {}".format(temp)
                + Style.RESET_ALL
                + " K"
            )
            xsdir = "".join(xdt)

            with open(dir + "/" + rep_data + "/xsdir", "a") as fic:
                fic.write(xsdir)
        os.remove(dir + "/" + rep_data + "/" + name + ".xsdir")
