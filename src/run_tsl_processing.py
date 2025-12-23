import sys
import shutil
import time
import json
import os
from pathlib import Path
from multiprocessing import Process, cpu_count, Lock
from typing import List, Tuple, Dict
import njoy_execution_engine
from colorama import Fore, Style, init

# Initialize colorama
init(autoreset=True)

# --- Configuration & Constants ---
class Config:
    BASE_DIR = Path.cwd().resolve()
    SRC_DIR = BASE_DIR / "src"
    INPUTS_DIR = BASE_DIR / "inputs"
    
    # Output Directories for TSL
    OUTPUT_BASE = BASE_DIR / "data"
    OUTPUT_ACE = OUTPUT_BASE / "thermal_scattering_ace"
    
    # Critical Files
    XSDIR_TEMPLATE = SRC_DIR / "xsdir_mcnp5"
    XSDIR_MASTER = OUTPUT_ACE / "xsdir"
    TEMP_DICT_FILE = SRC_DIR / "temperature_index.json"

# --- Logging Helper ---
class Logger:
    @staticmethod
    def info(msg):
        print(f"{Fore.GREEN}[INFO] {msg}{Style.RESET_ALL}")
    
    @staticmethod
    def debug(msg):
        print(f"{Fore.CYAN}[DEBUG] {msg}{Style.RESET_ALL}")
    
    @staticmethod
    def warn(msg):
        print(f"{Fore.YELLOW}[WARN] {msg}{Style.RESET_ALL}")
    
    @staticmethod
    def error(msg):
        print(f"{Fore.RED}[ERROR] {msg}{Style.RESET_ALL}")
    
    @staticmethod
    def header(msg):
        print(f"\n{Fore.MAGENTA}{'='*60}")
        print(f"{Fore.BLUE}{Style.BRIGHT}{msg.center(60)}")
        print(f"{Fore.MAGENTA}{'='*60}{Style.RESET_ALL}")

# --- Core Processor Class ---
class TSLProcessor:
    def __init__(self, input_file: Path, njoy_cmd: str, cpu_limit: int):
        self.input_file = input_file
        self.njoy_cmd = njoy_cmd
        self.cpu_limit = cpu_limit
        self.lock = Lock()
        self.temp_dict = self._load_temp_dict()
        
        if not self.input_file.exists():
            Logger.error(f"Input file not found at: {self.input_file}")
            sys.exit(1)
            
        self._setup_directories()

    def _load_temp_dict(self) -> Dict:
        """Load the temperature dictionary safely."""
        if not Config.TEMP_DICT_FILE.exists():
            Logger.error(f"Temperature dictionary not found at: {Config.TEMP_DICT_FILE}")
            sys.exit(1)
        try:
            with open(Config.TEMP_DICT_FILE, 'r') as f:
                return json.load(f)
        except Exception as e:
            Logger.error(f"Failed to load JSON dictionary: {e}")
            sys.exit(1)

    def _setup_directories(self):
        """Prepare output directories and initialize xsdir."""
        Logger.debug(f"Output Directory set to: {Config.OUTPUT_ACE}")
        
        if Config.OUTPUT_ACE.exists():
            Logger.debug("Cleaning previous TSL output directory...")
            try:
                shutil.rmtree(Config.OUTPUT_ACE)
            except OSError as e:
                Logger.warn(f"Could not clean directory: {e}")
        
        Config.OUTPUT_ACE.mkdir(parents=True, exist_ok=True)
        
        if Config.XSDIR_TEMPLATE.exists():
            shutil.copy(Config.XSDIR_TEMPLATE, Config.XSDIR_MASTER)
            Logger.debug(f"Initialized xsdir from template.")
        else:
            Logger.warn(f"Template xsdir not found. Creating empty file.")
            Config.XSDIR_MASTER.touch()

    def _validate_temperatures(self, element_t: str, requested_temps: List[float]) -> List[float]:
        """Check if requested temperatures exist in the dictionary."""
        if element_t not in self.temp_dict:
            Logger.warn(f"Isotope {element_t} not found in dictionary.")
            return []
        
        # Parse dictionary temps (string -> float list)
        try:
            allowed_temps = [float(t) for t in self.temp_dict[element_t].split()]
        except ValueError:
            Logger.error(f"Malformed temperature string in JSON for {element_t}")
            return []

        valid_temps = []
        for t in requested_temps:
            if t in allowed_temps:
                valid_temps.append(t)
            else:
                Logger.warn(f"Temp {t}K not supported for {element_t}. Allowed: {allowed_temps}")
        
        return valid_temps

    def _process_pair(self, pair: Tuple[str, str]):
        """Process a single (Neutron Line, Thermal Line) pair."""
        line_n, line_t = pair
        gen = njoy_execution_engine.ACEGenerator(str(self.input_file))
        
        try:
            # Parse Parameters
            params_n = gen.gen_parametre_njoy(line_n)
            params_t = gen.gen_parametre_njoy(line_t)
            
            element_n = params_n[0] # e.g. H1_H2O
            # Neutron parameters might just need the element name
            
            element_t = params_t[0] # e.g. hydrogen_in_light_water
            name = params_t[1]      # e.g. lwtr
            raw_temps = params_t[2] # e.g. [293.6, 600.0]
            
            if not element_n or not element_t or not name:
                Logger.error(f"Invalid parameters parsed. N:{element_n}, T:{element_t}, Name:{name}")
                return

            # Validate Temperatures
            valid_temps = self._validate_temperatures(element_t, raw_temps)
            if not valid_temps:
                Logger.error(f"No valid temperatures found for {element_t}. Skipping.")
                return

            ace_ascii = name
            input_njoy = f"{name}.njoy"
            
            base_dir_str = str(Config.BASE_DIR)
            output_abs_path = str(Config.OUTPUT_ACE)

            Logger.info(f"Processing TSL: {name} (N:{element_n} + T:{element_t})")

            # 1. Run NJOY TSL
            file_ace_path = gen.run_njoy_tsl(
                base_dir_str,
                element_n,
                element_t,
                name,
                valid_temps,
                ace_ascii,
                input_njoy,
                self.njoy_cmd,
                output_abs_path
            )
            
            # 2. Check and Merge XSDIR
            if file_ace_path and Path(file_ace_path).exists():
                # Find line numbers in ACE file
                num_lines = []
                for i, _ in enumerate(valid_temps, 1):
                    suffix = f".{i:02}t" # TSL suffix is usually .0xt
                    matches = gen.search_string_in_file(file_ace_path, suffix)
                    if matches:
                        num_lines.append(str(matches[0][0]))
                    else:
                        Logger.warn(f"Suffix {suffix} not found inside ACE file {ace_ascii}")

                # Merge XSDIR (Locked)
                with self.lock:
                    gen.gen_xsdir(
                        name,
                        num_lines,
                        base_dir_str,
                        output_abs_path,
                        valid_temps
                    )
                Logger.info(f"SUCCESS: {name} processed and merged.")
            else:
                Logger.error(f"ACE file missing for {name}")

        except Exception as e:
            Logger.error(f"FAILED to process {name if 'name' in locals() else 'Unknown'}. Error: {e}")
            Logger.warn(f"Debug info: Temp dir '{name}' preserved if created.")

    def _worker(self, pairs: List[Tuple[str, str]]):
        """Worker function."""
        for pair in pairs:
            self._process_pair(pair)

    def execute(self):
        """Main execution engine."""
        Logger.header("STARTING THERMAL SCATTERING PROCESSING (DEBUG MODE)")
        
        gen = njoy_execution_engine.ACEGenerator(str(self.input_file))
        
        # Read lines
        Logger.debug(f"Reading input file: {self.input_file}")
        try:
            matches_n = gen.search_string_in_file(gen.filename, "element_n")
            matches_t = gen.search_string_in_file(gen.filename, "element_t")
            
            lines_n = [line for _, line in matches_n]
            lines_t = [line for _, line in matches_t]
            
            if len(lines_n) != len(lines_t):
                Logger.warn(f"Mismatch in input lines! N: {len(lines_n)}, T: {len(lines_t)}. Using minimum count.")
            
            # Pair them up
            pairs = list(zip(lines_n, lines_t))
            
        except Exception as e:
            Logger.error(f"Failed to read input file: {e}")
            return
        
        total_jobs = len(pairs)
        if total_jobs == 0:
            Logger.error("No valid element_n/element_t pairs found.")
            return

        Logger.info(f"Found {total_jobs} TSL jobs to process.")
        
        # Distribute Work
        procs = []
        effective_cpu = max(1, min(self.cpu_limit, total_jobs))
        
        chunk_size = total_jobs // effective_cpu + (1 if total_jobs % effective_cpu else 0)
        
        for i in range(effective_cpu):
            start = i * chunk_size
            end = start + chunk_size
            chunk = pairs[start:end]
            if not chunk: continue
            
            p = Process(target=self._worker, args=(chunk,))
            procs.append(p)
            p.start()
        
        for p in procs:
            p.join()
            
        Logger.header("PROCESSING FINISHED")
        print(f"Check output at: {Config.OUTPUT_ACE}")
        print(f"Check xsdir at:  {Config.XSDIR_MASTER}")

# --- Helpers ---
def get_njoy_cmd():
    sys_path = shutil.which("njoy")
    default = sys_path if sys_path else "njoy"
    print("-" * 50)
    user_input = input(f"Enter NJOY command/path (Default: {default}): ").strip()
    cmd = user_input if user_input else default
    
    if not shutil.which(cmd) and not Path(cmd).exists():
        Logger.error(f"NJOY executable '{cmd}' not found!")
    return cmd

def get_cpu_count():
    total = cpu_count()
    print("-" * 50)
    user_input = input(f"Enter CPUs to use (Default: {total}): ").strip()
    try:
        count = int(user_input) if user_input else total
        return max(1, count)
    except:
        return 1

# --- Entry Point ---
if __name__ == "__main__":
    start_time = time.time()
    
    if len(sys.argv) < 2:
        Logger.error("Usage: python run_tsl_processing.py <input_file>")
        sys.exit(1)
        
    input_file_path = Path(sys.argv[1]).resolve()
    
    njoy_cmd = get_njoy_cmd()
    
    # Nuclear Data Paths (Neutron AND Thermal)
    print("-" * 50)
    def_n = "data/incident_neutron_endf"
    def_t = "data/thermal_scattering_endf"
    
    nd_n = input(f"Enter Incident Neutron data path (Default: {def_n}): ").strip() or def_n
    nd_t = input(f"Enter Thermal Scattering data path (Default: {def_t}): ").strip() or def_t
    
    # Resolve Absolute Paths
    abs_n = Path(nd_n).resolve()
    abs_t = Path(nd_t).resolve()
    
    # Fallback to relative check if absolute fails (cwd based)
    if not abs_n.exists() and (Config.BASE_DIR / nd_n).exists():
        abs_n = (Config.BASE_DIR / nd_n).resolve()
    if not abs_t.exists() and (Config.BASE_DIR / nd_t).exists():
        abs_t = (Config.BASE_DIR / nd_t).resolve()

    if not abs_n.exists():
        Logger.error(f"Neutron data not found: {abs_n}")
        sys.exit(1)
    if not abs_t.exists():
        Logger.error(f"Thermal data not found: {abs_t}")
        sys.exit(1)
            
    os.environ["OPENMC_ENDF_DATA_Neutron"] = str(abs_n)
    os.environ["OPENMC_ENDF_DATA_Thermal"] = str(abs_t)
    
    Logger.debug("Environment variables set for OpenMC.")

    cpu_limit = get_cpu_count()
    
    processor = TSLProcessor(input_file_path, njoy_cmd, cpu_limit)
    processor.execute()
    
    elapsed = time.time() - start_time
    print(f"\n{Fore.GREEN}Total Time: {time.strftime('%Hh:%Mm:%Ss', time.gmtime(elapsed))}")