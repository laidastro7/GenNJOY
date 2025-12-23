import sys
import shutil
import time
import os
from pathlib import Path
from multiprocessing import Process, cpu_count, Lock
from typing import List
import njoy_execution_engine
from colorama import Fore, Style, init

# Initialize colorama
init(autoreset=True)

# --- Configuration & Constants ---
class Config:
    BASE_DIR = Path.cwd().resolve()
    SRC_DIR = BASE_DIR / "src"
    INPUTS_DIR = BASE_DIR / "inputs"
    
    # [UPDATED] Output Directory
    OUTPUT_BASE = BASE_DIR / "data"
    OUTPUT_ACE = OUTPUT_BASE / "incident_neutron_ace"
    
    # Critical Files
    XSDIR_TEMPLATE = SRC_DIR / "xsdir_mcnp5"
    XSDIR_MASTER = OUTPUT_ACE / "xsdir"

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
class NeutronProcessor:
    def __init__(self, input_file: Path, njoy_cmd: str, cpu_limit: int):
        self.input_file = input_file
        self.njoy_cmd = njoy_cmd
        self.cpu_limit = cpu_limit
        self.lock = Lock()
        
        if not self.input_file.exists():
            Logger.error(f"Input file not found at: {self.input_file}")
            sys.exit(1)
            
        self._setup_directories()

    def _setup_directories(self):
        Logger.debug(f"Output Directory set to: {Config.OUTPUT_ACE}")
        
        if Config.OUTPUT_ACE.exists():
            Logger.debug("Cleaning previous output directory...")
            try:
                shutil.rmtree(Config.OUTPUT_ACE)
            except OSError as e:
                Logger.warn(f"Could not clean directory: {e}")
        
        Config.OUTPUT_ACE.mkdir(parents=True, exist_ok=True)
        
        if Config.XSDIR_TEMPLATE.exists():
            shutil.copy(Config.XSDIR_TEMPLATE, Config.XSDIR_MASTER)
            Logger.debug(f"Initialized xsdir from template.")
        else:
            Logger.warn(f"Template xsdir not found at {Config.XSDIR_TEMPLATE}. Creating empty file.")
            Config.XSDIR_MASTER.touch()

    def _process_isotope(self, line_data: str):
        gen = njoy_execution_engine.ACEGenerator(str(self.input_file))
        
        try:
            params = gen.gen_parametre_njoy(line_data)
            element = params[0]
            name = params[1]
            temperatures = params[2]
            
            if not element or not name:
                Logger.error(f"Invalid line format: {line_data.strip()}")
                return
                
        except Exception as e:
            Logger.error(f"Error parsing line: {line_data.strip()} | {e}")
            return

        ace_ascii = name
        input_njoy = f"{name}.njoy"
        
        base_dir_str = str(Config.BASE_DIR)
        output_abs_path = str(Config.OUTPUT_ACE)

        Logger.info(f"Processing Isotope: {name} (Element: {element})")

        try:
            file_ace_path = gen.run_njoy(
                base_dir_str,
                element,
                name,
                temperatures,
                ace_ascii,
                input_njoy,
                self.njoy_cmd,
                output_abs_path
            )
            
            Logger.debug(f"NJOY finished for {name}. Checking ACE file...")

            if file_ace_path and Path(file_ace_path).exists():
                num_lines = []
                for i, _ in enumerate(temperatures, 1):
                    suffix = f".{i:02}c"
                    matches = gen.search_string_in_file(file_ace_path, suffix)
                    if matches:
                        num_lines.append(str(matches[0][0]))
                    else:
                        Logger.warn(f"Suffix {suffix} not found inside ACE file {ace_ascii}")

                with self.lock:
                    gen.gen_xsdir(
                        name,
                        num_lines,
                        base_dir_str,
                        output_abs_path,
                        temperatures
                    )
                Logger.info(f"SUCCESS: {name} processed and merged.")
            else:
                Logger.error(f"ACE file missing for {name} at {file_ace_path}")

        except Exception as e:
            Logger.error(f"FAILED to process {name}. Error: {e}")
            Logger.warn(f"NOTE: Temporary folder '{name}' was preserved for debugging.")

    def _worker(self, lines: List[str]):
        for line in lines:
            self._process_isotope(line)

    def execute(self):
        Logger.header("STARTING NEUTRON DATA PROCESSING (DEBUG MODE)")
        
        gen = njoy_execution_engine.ACEGenerator(str(self.input_file))
        
        Logger.debug(f"Reading input file: {self.input_file}")
        try:
            matches = gen.search_string_in_file(gen.filename, "element")
            lines = [line for _, line in matches]
        except Exception as e:
            Logger.error(f"Failed to read input file: {e}")
            return
        
        total_isotopes = len(lines)
        if total_isotopes == 0:
            Logger.error("No isotopes found in input file! Check if lines start with 'element'.")
            return

        Logger.info(f"Found {total_isotopes} isotopes to process.")
        
        procs = []
        effective_cpu = min(self.cpu_limit, total_isotopes)
        effective_cpu = max(1, effective_cpu)
        
        chunk_size = total_isotopes // effective_cpu + (1 if total_isotopes % effective_cpu else 0)
        
        for i in range(effective_cpu):
            start = i * chunk_size
            end = start + chunk_size
            chunk = lines[start:end]
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
        Logger.error(f"NJOY executable '{cmd}' not found! Execution will likely fail.")
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
        Logger.error("Usage: python run_neutron_processing.py <input_file>")
        sys.exit(1)
        
    input_file_path = Path(sys.argv[1]).resolve()
    
    njoy_cmd = get_njoy_cmd()
    
    # [UPDATED] Default Data Path
    default_nd = "data/incident_neutron_endf"
    print("-" * 50)
    nd_input = input(f"Enter path to incident neutron data (Default: {default_nd}): ").strip()
    nd_path = nd_input if nd_input else default_nd
    
    abs_nd_path = Path(nd_path).resolve()
    if not abs_nd_path.exists():
        if (Config.BASE_DIR / nd_path).exists():
            abs_nd_path = (Config.BASE_DIR / nd_path).resolve()
        else:
            Logger.error(f"Nuclear data path not found: {abs_nd_path}")
            sys.exit(1)
            
    os.environ["OPENMC_ENDF_DATA"] = str(abs_nd_path)
    Logger.debug(f"OPENMC_ENDF_DATA set to: {os.environ['OPENMC_ENDF_DATA']}")

    cpu_limit = get_cpu_count()
    
    processor = NeutronProcessor(input_file_path, njoy_cmd, cpu_limit)
    processor.execute()
    
    elapsed = time.time() - start_time
    print(f"\n{Fore.GREEN}Total Time: {time.strftime('%Hh:%Mm:%Ss', time.gmtime(elapsed))}")