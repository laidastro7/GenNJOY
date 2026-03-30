import os
import re
import shutil
import subprocess
from pathlib import Path
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
        endf_data_t = os.environ.get("GENNJOY_ENDF_DATA_THERMAL")
        if not endf_data_t:
            print(Fore.RED + "Error: GENNJOY_ENDF_DATA_THERMAL environment variable not set.")
            return

        path_from_env = Path(endf_data_t)
        if path_from_env.is_absolute():
            endf_file_t = path_from_env / element_t
        else:
            endf_file_t = Path(working_dir) / endf_data_t / element_t

        if not endf_file_t.exists():
            print(Fore.RED + f"File not found: {endf_file_t}")
            return

        try:
            with open(endf_file_t, "r") as fic:
                lines = [fic.readline() for _ in range(5)]
            
            if len(lines) > 1:
                print(lines[1].strip())
        except Exception as e:
            print(Fore.RED + f"Error reading ENDF file: {e}")

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
        
        output_file = Path(working_dir) / "inputs" / "neutron_inventory.i"
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
        
        output_file = Path(working_dir) / "inputs" / "tsl_inventory.i"
        output_file.parent.mkdir(parents=True, exist_ok=True)
        
        with open(output_file, "a") as fic:
            fic.write(line)


class ACEGenerator:
    """
    Class responsible for generating NJOY decks and running NJOY via subprocess.
    Independently handles ENDF parsing for MAT numbers and URR flags.
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
            print(Fore.RED + f"[njoy_execution_engine] Error reading file {file_path}: {e}")
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

    # --- INDEPENDENT ENDF PARSERS ---
    def _get_mat_number(self, file_path):
        """Extracts the MAT number from columns 66-70 of an ENDF file (Skipping TPID)."""
        with open(file_path, 'r', errors='ignore') as f:
            for line in f:
                if len(line) >= 75:
                    try:
                        mat = int(line[66:70].strip())
                        mf = int(line[70:72].strip())
                        if mat > 0 and mf > 0:
                            return mat
                    except ValueError:
                        continue
        raise ValueError(f"Could not find MAT number in {file_path}")

    def _get_za_number(self, file_path):
        """Extracts the ZA number from the ENDF MF=1 MT=451 HEAD record."""
        with open(file_path, 'r', errors='ignore') as f:
            for line in f:
                if len(line) >= 75:
                    try:
                        mf = int(line[70:72].strip())
                        mt = int(line[72:75].strip())
                        if mf == 1 and mt == 451:
                            za_str = line[0:11].strip()
                            za_str = re.sub(r'([0-9])([+-])', r'\1e\2', za_str)
                            za = int(float(za_str))
                            return za
                    except ValueError:
                        continue
        raise ValueError(f"Could not find ZA number in {file_path}")

    def _has_urr(self, file_path):
        """Detects if Unresolved Resonance Data exists by parsing ENDF-6 format for LRU=2 in MF=2 MT=151."""
        with open(file_path, 'r', errors='ignore') as f:
            for line in f:
                if len(line) >= 75:
                    mf = line[70:72].strip()
                    mt = line[72:75].strip()
                    if mf == '2' and mt == '151':
                        el_str = line[0:11]
                        eh_str = line[11:22]
                        lru_str = line[22:33].strip()
                        
                        if '.' in el_str and '.' in eh_str:
                            if lru_str == '2':
                                return True
        return False

    def _get_thermr_flags(self, file_path):
        """Detects if thermal scattering file has inelastic (MF=7, MT=4) or elastic (MF=7, MT=2) data."""
        icoh = 0
        iin = 0
        try:
            with open(file_path, 'r', errors='ignore') as f:
                for line in f:
                    if len(line) >= 75:
                        mf = line[70:72].strip()
                        mt = line[72:75].strip()
                        if mf == '7' and mt == '2':
                            icoh = 1
                        if mf == '7' and mt == '4':
                            iin = 2
        except Exception:
            pass
        
        if iin == 0 and icoh == 0:
            iin = 2 
            
        return iin, icoh

    # --- NJOY DECK GENERATORS ---
    def _build_neutron_deck(self, endf_file, mat, temperatures, ace_ascii, err=0.001):
        has_urr = self._has_urr(endf_file)
        temps_str = " ".join(str(t) for t in temperatures)
        ntemp = len(temperatures)
        
        deck = f"moder\n20 -21 /\n"
        deck += f"reconr\n-21 -22 /\n'pendf' /\n{mat} 0 0 /\n{err} 0. /\n0 /\n"
        deck += f"broadr\n-21 -22 -23 /\n{mat} {ntemp} 0 0 0. /\n{err} /\n{temps_str} /\n0 /\n"
        
        current_tape = 23
        
        deck += f"heatr\n-21 -{current_tape} -{current_tape+1} /\n{mat} 0 0 0 1 0 /\n"
        current_tape += 1
        
        deck += f"heatr\n-21 -{current_tape} -{current_tape+1} /\n{mat} 0 0 0 0 0 /\n"
        current_tape += 1
        
        deck += f"gaspr\n-21 -{current_tape} -{current_tape+1} /\n"
        current_tape += 1
        
        if has_urr:
            deck += f"unresr\n-21 -{current_tape} -{current_tape+1} /\n{mat} {ntemp} 10 1 /\n"
            deck += f"{temps_str} /\n"
            deck += f"1.0e10 10000.0 1000.0 300.0 100.0 30.0 10.0 1.0 0.1 1.0e-5 /\n"
            deck += f"0 /\n"
            current_tape += 1
            
            deck += f"purr\n-21 -{current_tape} -{current_tape+1} /\n{mat} {ntemp} 10 20 64 /\n"
            deck += f"{temps_str} /\n"
            deck += f"1.0e10 10000.0 1000.0 300.0 100.0 30.0 10.0 1.0 0.1 1.0e-5 /\n"
            deck += f"0 /\n"
            current_tape += 1
            
        for i, temp in enumerate(temperatures, 1):
            tape_ace = 50 + i * 2
            tape_xsdir = 51 + i * 2
            suffix = f".{i:02}"
            deck += f"acer\n-21 -{current_tape} 0 {tape_ace} {tape_xsdir} /\n1 1 1 {suffix} /\n'{ace_ascii}' /\n{mat} {temp} /\n1 /\n/\n"
            
        deck += "stop\n"
        return deck

    def _build_tsl_deck(self, mat_n, mat_t, temperatures, ace_ascii, iin, icoh, za, err=0.001):
        temps_str = " ".join(str(t) for t in temperatures)
        ntemp = len(temperatures)
        
        deck = f"moder\n20 -21 /\nmoder\n22 -23 /\n"
        deck += f"reconr\n-21 -24 /\n'pendf' /\n{mat_n} 0 0 /\n{err} 0. /\n0 /\n"
        deck += f"broadr\n-21 -24 -25 /\n{mat_n} {ntemp} 0 0 0. /\n{err} /\n{temps_str} /\n0 /\n"
        deck += f"thermr\n-23 -25 -26 /\n{mat_t} {mat_n} 20 {ntemp} {iin} {icoh} 0 1 221 0 /\n{temps_str} /\n{err} /\n"
        
        for i, temp in enumerate(temperatures, 1):
            tape_ace = 50 + i * 2
            tape_xsdir = 51 + i * 2
            suffix = f".{i:02}"
            deck += f"acer\n-23 -26 0 {tape_ace} {tape_xsdir} /\n2 1 1 {suffix} /\n'{ace_ascii}' /\n"
            deck += f"{mat_n} {temp} '{ace_ascii}' 1 /\n"
            deck += f"{za} /\n"
            deck += f"221 64 0 0 1 0.0 2 /\n"
            
        deck += "stop\n"
        return deck

    # --- EXECUTION ENGINES ---
    def run_njoy(self, base_dir, element, name, temperatures, ace_ascii, input_njoy, njoy_exec, output_path, err=0.001):
        original_cwd = Path.cwd()
        base_path = Path(base_dir)
        temp_dir = base_path / name
        dest_dir = Path(output_path)
        
        dest_dir.mkdir(parents=True, exist_ok=True)
        
        endf_data = os.environ.get("GENNJOY_ENDF_DATA")
        if not endf_data: raise EnvironmentError("GENNJOY_ENDF_DATA not set")
        
        path_from_env = Path(endf_data)
        if path_from_env.is_absolute(): endf_file = path_from_env / element
        else: endf_file = (base_path / path_from_env / element).resolve()

        if not endf_file.exists(): raise FileNotFoundError(f"ENDF file not found: {endf_file}")

        if temp_dir.exists(): shutil.rmtree(temp_dir)
        temp_dir.mkdir()

        try:
            os.chdir(temp_dir)

            # Setup Tapes and Inputs
            shutil.copy(str(endf_file), "tape20")
            mat = self._get_mat_number("tape20")
            deck = self._build_neutron_deck("tape20", mat, temperatures, ace_ascii, err)
            
            with open(input_njoy, "w") as f:
                f.write(deck)

            # RUN NJOY directly via subprocess
            with open(input_njoy, "r") as fin, open("njoy.out", "w") as fout:
                result = subprocess.run([njoy_exec], stdin=fin, stdout=fout, stderr=subprocess.STDOUT)
                if result.returncode != 0:
                    raise RuntimeError(f"NJOY execution failed. Check {temp_dir}/njoy.out")
            
            # Merge separate ACE tapes into one final ACE file
            dst_ace = dest_dir / ace_ascii
            with open(dst_ace, 'wb') as fout_ace:
                for i in range(1, len(temperatures) + 1):
                    tape_ace = temp_dir / f"tape{50 + i*2}"
                    if tape_ace.exists():
                        with open(tape_ace, 'rb') as fin:
                            shutil.copyfileobj(fin, fout_ace)
                            
            if not dst_ace.exists() or dst_ace.stat().st_size == 0:
                raise FileNotFoundError(f"ACE files not generated. Found: {[f.name for f in list(temp_dir.glob('*'))]}")

            # Merge separate XSDIR tapes into one final XSDIR file
            dst_xsdir = dest_dir / f"{name}.xsdir"
            with open(dst_xsdir, 'wb') as fout_xsdir:
                for i in range(1, len(temperatures) + 1):
                    tape_dir = temp_dir / f"tape{51 + i*2}"
                    if tape_dir.exists():
                        with open(tape_dir, 'rb') as fin:
                            shutil.copyfileobj(fin, fout_xsdir)
            
            njoy_inputs_dir = base_path / "data" / "njoy_input_decks"
            njoy_inputs_dir.mkdir(parents=True, exist_ok=True)
            
            src_input = temp_dir / input_njoy
            if src_input.exists(): shutil.move(str(src_input), str(njoy_inputs_dir / input_njoy))

            return str(dst_ace)

        except Exception as e:
            raise RuntimeError(f"NJOY failed: {e}")
            
        finally:
            os.chdir(original_cwd)
            if (dest_dir / ace_ascii).exists():
                 if temp_dir.exists(): shutil.rmtree(temp_dir)
            else:
                 print(Fore.RED + f"   -> Debug: Preserving temp dir {temp_dir} due to failure.")

    def run_njoy_tsl(self, base_dir, element_n, element_t, name, temperatures, ace_ascii, input_njoy, njoy_exec, output_rel_path, err=0.001):
        original_cwd = Path.cwd()
        base_path = Path(base_dir)
        temp_dir = base_path / name
        dest_dir = Path(output_rel_path)
        dest_dir.mkdir(parents=True, exist_ok=True)

        endf_data_n = os.environ.get("GENNJOY_ENDF_DATA_NEUTRON")
        endf_data_t = os.environ.get("GENNJOY_ENDF_DATA_THERMAL")
        
        if not endf_data_n or not endf_data_t:
             raise EnvironmentError("TSL Environment variables not set.")

        if Path(endf_data_n).is_absolute(): endf_file_n = Path(endf_data_n) / element_n
        else: endf_file_n = base_path / endf_data_n / element_n

        if Path(endf_data_t).is_absolute(): endf_file_t = Path(endf_data_t) / element_t
        else: endf_file_t = base_path / endf_data_t / element_t

        if not endf_file_n.exists(): raise FileNotFoundError(f"Neutron file missing: {endf_file_n}")
        if not endf_file_t.exists(): raise FileNotFoundError(f"Thermal file missing: {endf_file_t}")

        if temp_dir.exists(): shutil.rmtree(temp_dir)
        temp_dir.mkdir()

        try:
            os.chdir(temp_dir)
            
            # Setup Tapes and Inputs
            shutil.copy(str(endf_file_n), "tape20")
            shutil.copy(str(endf_file_t), "tape22")
            
            mat_n = self._get_mat_number("tape20")
            mat_t = self._get_mat_number("tape22")
            za = self._get_za_number("tape20")
            
            iin, icoh = self._get_thermr_flags("tape22")
            
            deck = self._build_tsl_deck(mat_n, mat_t, temperatures, ace_ascii, iin, icoh, za, err)
            
            with open(input_njoy, "w") as f:
                f.write(deck)

            # RUN NJOY directly via subprocess
            with open(input_njoy, "r") as fin, open("njoy.out", "w") as fout:
                result = subprocess.run([njoy_exec], stdin=fin, stdout=fout, stderr=subprocess.STDOUT)
                if result.returncode != 0:
                    raise RuntimeError(f"TSL Processing failed. Check {temp_dir}/njoy.out")

            # Merge separate ACE tapes for thermal scattering into one final ACE file
            dst_ace = dest_dir / ace_ascii
            with open(dst_ace, 'wb') as fout_ace:
                for i in range(1, len(temperatures) + 1):
                    tape_ace = temp_dir / f"tape{50 + i*2}"
                    if tape_ace.exists():
                        with open(tape_ace, 'rb') as fin:
                            shutil.copyfileobj(fin, fout_ace)

            # Merge separate XSDIR tapes for thermal scattering into one final XSDIR file
            dst_xsdir = dest_dir / f"{name}.xsdir"
            with open(dst_xsdir, 'wb') as fout_xsdir:
                for i in range(1, len(temperatures) + 1):
                    tape_dir = temp_dir / f"tape{51 + i*2}"
                    if tape_dir.exists():
                        with open(tape_dir, 'rb') as fin:
                            shutil.copyfileobj(fin, fout_xsdir)

            njoy_inputs_dir = base_path / "data" / "njoy_input_decks"
            njoy_inputs_dir.mkdir(parents=True, exist_ok=True)
            
            src_input = temp_dir / input_njoy
            if src_input.exists(): shutil.move(str(src_input), str(njoy_inputs_dir / input_njoy))

            return str(dest_dir / ace_ascii)

        except Exception as e:
            raise RuntimeError(f"TSL Processing failed for {name}: {e}")
        finally:
            os.chdir(original_cwd)
            if (dest_dir / ace_ascii).exists():
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
            if needs_newline: f.write("\n")
            f.writelines(formatted_block)
            
        local_xsdir.unlink()