import os
import shutil
import time
from pathlib import Path
import openmc.data.njoy
from colorama import Fore, Style, init

# Initialize terminal color conversion
init(autoreset=True)

class InputGenerator:
    """Class for generating neutron data input files."""
    def __init__(self, element):
        self.element = element

    def index_majuscule(self, element):
        for i, char in enumerate(reversed(element)):
            if char.isupper():
                return len(element) - 1 - i
        return -1

    def gen_temperature_tsl(self, working_dir, element_t):
        endf_data_t = os.environ.get("OPENMC_ENDF_DATA_Thermal")
        if not endf_data_t:
            print(Fore.RED + "Error: OPENMC_ENDF_DATA_Thermal not set.")
            return

        endf_file_t = Path(endf_data_t) / element_t
        if not endf_file_t.exists():
            print(Fore.RED + f"File not found: {endf_file_t}")
            return

        with open(endf_file_t, "r") as fic:
            lines = [fic.readline() for _ in range(5)]
        
        if len(lines) > 1:
            print(lines[1].strip())

    def gen_name(self, element):
        basename = Path(element).stem
        parts = basename.split("-")
        if len(parts) >= 3:
            return parts[1], parts[2]
        return basename, "000"

    def gen_input(self, working_dir, element, isotop, elem_num, temper, length):
        line = (
            f"element_n = {element.ljust(length)} "
            f"name = {isotop.ljust(len(isotop))}{elem_num.ljust(6 - len(isotop))} "
            f"temperatures = {temper}\n"
        )
        
        output_file = Path(working_dir) / "inputs" / "input_n_global.i"
        output_file.parent.mkdir(parents=True, exist_ok=True)
        
        with open(output_file, "a") as fic:
            fic.write(line)

    def gen_input_tsl(self, working_dir, element_t, element_n, name_t, temper, length):
        line = (
            f"element_n = {element_n}\n"
            f"element_t = {element_t.ljust(length)} "
            f"name = {name_t.ljust(6)} "
            f"temperatures = {temper}\n\n"
        )
        
        output_file = Path(working_dir) / "inputs" / "input_tsl_global.i"
        output_file.parent.mkdir(parents=True, exist_ok=True)
        
        with open(output_file, "a") as fic:
            fic.write(line)


class ACEGenerator:
    """
    Class responsible for running NJOY and managing files (Professional Edition).
    """
    def __init__(self, filename):
        self.filename = filename

    def search_string_in_file(self, file_path, string_to_search):
        results = []
        path = Path(file_path)
        if not path.exists():
            return results
        try:
            with open(path, "r", errors='ignore') as f:
                for i, line in enumerate(f, 1):
                    if string_to_search in line:
                        results.append((i, line.rstrip()))
        except Exception as e:
            print(Fore.RED + f"[DataGenerator] Error reading file {file_path}: {e}")
        return results

    def gen_parametre_njoy(self, line_content):
        parts = line_content.replace('=', ' ').split()
        element = None
        name = None
        temperatures = []
        
        iterator = iter(parts)
        for part in iterator:
            if part in ['element', 'element_n']:
                try: element = next(iterator)
                except StopIteration: pass
            elif part == 'name':
                try: name = next(iterator)
                except StopIteration: pass
            elif part == 'temperatures':
                while True:
                    try:
                        val = next(iterator)
                        if val[0].isdigit() or val[0] == '.': temperatures.append(float(val))
                        else: break
                    except (StopIteration, ValueError): break
        
        if not element or not name:
            s = line_content.split("=")
            if len(s) > 1: element = s[1].split()[0]
            if len(s) > 2: name = s[2].split()[0]
            if len(s) > 3: 
                try: temperatures = [float(t) for t in s[3].split()]
                except ValueError: pass

        return [element, name, temperatures]

    def run_njoy(self, base_dir, element, name, temperatures, ace_ascii, input_njoy, njoy_exec, output_path):
        """
        Executes NJOY using updated directory conventions.
        """
        original_cwd = Path.cwd()
        base_path = Path(base_dir)
        temp_dir = base_path / name
        dest_dir = Path(output_path)
        
        dest_dir.mkdir(parents=True, exist_ok=True)
        
        endf_data = os.environ.get("OPENMC_ENDF_DATA")
        if not endf_data:
            raise EnvironmentError("OPENMC_ENDF_DATA not set")
            
        endf_file = Path(endf_data) / element
        if not endf_file.exists():
            endf_file = (base_path / endf_data / element).resolve()
            if not endf_file.exists():
                raise FileNotFoundError(f"ENDF file not found: {endf_file}")

        if temp_dir.exists():
            shutil.rmtree(temp_dir)
        temp_dir.mkdir()

        try:
            os.chdir(temp_dir)

            # RUN NJOY
            openmc.data.njoy.make_ace(
                str(endf_file),
                error=0.001,
                temperatures=temperatures,
                acer=ace_ascii,
                input_filename=input_njoy,
                stdout=False,
                njoy_exec=njoy_exec,
            )
            
            # MOVE ARTIFACTS
            src_ace = temp_dir / ace_ascii
            dst_ace = dest_dir / ace_ascii
            
            if src_ace.exists():
                shutil.move(str(src_ace), str(dst_ace))
            else:
                files = list(temp_dir.glob('*'))
                raise FileNotFoundError(f"ACE file {ace_ascii} not generated. Found: {[f.name for f in files]}")

            src_xsdir = temp_dir / "xsdir"
            dst_xsdir = dest_dir / f"{name}.xsdir"
            if src_xsdir.exists():
                shutil.move(str(src_xsdir), str(dst_xsdir))
            
            # [UPDATED] Move Input Deck to 'njoy_input_decks'
            njoy_inputs_dir = base_path / "data" / "njoy_input_decks"
            njoy_inputs_dir.mkdir(parents=True, exist_ok=True)
            src_input = temp_dir / input_njoy
            if src_input.exists():
                shutil.move(str(src_input), str(njoy_inputs_dir / input_njoy))

            return str(dst_ace)

        except Exception as e:
            raise RuntimeError(f"NJOY failed: {e}")
            
        finally:
            os.chdir(original_cwd)
            if (dest_dir / ace_ascii).exists():
                 if temp_dir.exists(): shutil.rmtree(temp_dir)
            else:
                 print(Fore.RED + f"   -> Debug: Preserving temp dir {temp_dir} due to failure.")

    def run_njoy_tsl(self, base_dir, element_n, element_t, name, temperatures, ace_ascii, input_njoy, njoy_exec, output_rel_path):
        original_cwd = Path.cwd()
        base_path = Path(base_dir)
        temp_dir = base_path / name
        dest_dir = Path(output_rel_path)
        dest_dir.mkdir(parents=True, exist_ok=True)

        endf_data_n = os.environ.get("OPENMC_ENDF_DATA_Neutron")
        endf_data_t = os.environ.get("OPENMC_ENDF_DATA_Thermal")
        
        if not endf_data_n or not endf_data_t:
             raise EnvironmentError("TSL Environment variables not set.")

        endf_file_n = Path(endf_data_n) / element_n
        endf_file_t = Path(endf_data_t) / element_t

        if not endf_file_n.exists(): raise FileNotFoundError(f"Neutron file missing: {endf_file_n}")
        if not endf_file_t.exists(): raise FileNotFoundError(f"Thermal file missing: {endf_file_t}")

        if temp_dir.exists(): shutil.rmtree(temp_dir)
        temp_dir.mkdir()

        try:
            os.chdir(temp_dir)
            
            openmc.data.njoy.make_ace_thermal(
                str(endf_file_n),
                str(endf_file_t),
                error=0.01,
                iwt=2,
                temperatures=temperatures,
                ace=ace_ascii,
                input_filename=input_njoy,
                stdout=False,
                njoy_exec=njoy_exec,
            )

            src_ace = temp_dir / ace_ascii
            if src_ace.exists(): shutil.move(str(src_ace), str(dest_dir / ace_ascii))
            
            src_xsdir = temp_dir / "xsdir"
            if src_xsdir.exists(): shutil.move(str(src_xsdir), str(dest_dir / f"{name}.xsdir"))

            # [UPDATED] Move Input Deck to 'njoy_input_decks'
            njoy_inputs_dir = base_path / "data" / "njoy_input_decks"
            njoy_inputs_dir.mkdir(parents=True, exist_ok=True)
            src_input = temp_dir / input_njoy
            if src_input.exists(): shutil.move(str(src_input), str(njoy_inputs_dir / input_njoy))

            return str(dest_dir / ace_ascii)

        except Exception as e:
            raise RuntimeError(f"TSL Processing failed for {name}: {e}")
        finally:
            os.chdir(original_cwd)
            if temp_dir.exists(): shutil.rmtree(temp_dir, ignore_errors=True)

    def gen_xsdir(self, name, num_line, base_dir, output_path, valid_temperatures):
        data_dir = Path(output_path)
        master_xsdir = data_dir / "xsdir"
        local_xsdir = data_dir / f"{name}.xsdir"
        
        if not master_xsdir.exists():
             with open(master_xsdir, 'w') as f: f.write("directory\n")

        if not local_xsdir.exists():
            return

        with open(local_xsdir, "r") as f:
            lines = f.readlines()

        formatted_block = []
        for i, (line, temp) in enumerate(zip(lines, valid_temperatures)):
            parts = line.split()
            if len(parts) < 10: continue

            address = num_line[i] if (num_line and i < len(num_line)) else parts[5]
            
            w1 = parts[0].rjust(11)
            w2 = parts[1].rjust(11)
            w3 = name.rjust(6)
            w4 = "0".rjust(3)
            w5 = "1".rjust(2)
            w6 = str(address).rjust(8)
            w7 = parts[6].rjust(8)
            w8 = "0".rjust(2)
            w9 = "0".rjust(2)
            w10 = parts[9].rjust(10)
            w11 = "ptable".rjust(8)
            
            formatted_block.append(f"{w1}{w2}{w3}{w4}{w5}{w6}{w7}{w8}{w9}{w10}{w11}\n")

        needs_newline = False
        if master_xsdir.exists() and master_xsdir.stat().st_size > 0:
            with open(master_xsdir, 'rb') as f:
                f.seek(-1, 2)
                last_char = f.read(1)
                if last_char != b'\n':
                    needs_newline = True
        
        with open(master_xsdir, "a") as f:
            if needs_newline:
                f.write("\n")
            f.writelines(formatted_block)
            
        local_xsdir.unlink()