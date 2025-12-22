import os
import sys
import subprocess
import shutil
import warnings
from pathlib import Path
from colorama import Fore, Style, init

# إسكات التنبيهات للعملية الحالية (XML generation)
warnings.filterwarnings("ignore")

# Try importing openmc
try:
    import openmc.data
except ImportError:
    print(Fore.RED + "[CRITICAL] 'openmc' python package not found!")
    sys.exit(1)

# Initialize colorama
init(autoreset=True)

# --- Configuration ---
class Config:
    BASE_DIR = Path.cwd().resolve()
    CONVERTER_CMD = "openmc-ace-to-hdf5"
    
    DEFAULT_NEUTRON_DIR = BASE_DIR / "data" / "ace_neutrons"
    DEFAULT_TSL_DIR = BASE_DIR / "data" / "ace_tsl"
    OUTPUT_HDF5_DIR = BASE_DIR / "data" / "hdf5_library"

# --- Logging Helper ---
class Logger:
    @staticmethod
    def info(msg):
        print(f"{Fore.GREEN}[INFO] {msg}{Style.RESET_ALL}")
    
    @staticmethod
    def error(msg):
        print(f"{Fore.RED}[ERROR] {msg}{Style.RESET_ALL}")
        
    @staticmethod
    def warn(msg):
        print(f"{Fore.YELLOW}[WARN] {msg}{Style.RESET_ALL}")

    @staticmethod
    def header(msg):
        print(f"\n{Fore.CYAN}{'='*60}")
        print(f"{Fore.BLUE}{Style.BRIGHT}{msg.center(60)}")
        print(f"{Fore.CYAN}{'='*60}{Style.RESET_ALL}")

# --- Converter Class ---
class ACEConverter:
    def __init__(self):
        self._check_system_installation()
        self._setup_output_dir()

    def _check_system_installation(self):
        if not shutil.which(Config.CONVERTER_CMD):
            Logger.error(f"System command '{Config.CONVERTER_CMD}' not found!")
            sys.exit(1)
        else:
            Logger.info(f"Using system tool: {shutil.which(Config.CONVERTER_CMD)}")

    def _setup_output_dir(self):
        if not Config.OUTPUT_HDF5_DIR.exists():
            Config.OUTPUT_HDF5_DIR.mkdir(parents=True, exist_ok=True)

    def convert_library(self, input_dir: Path, library_type: str):
        """
        Convert ACE files to HDF5 using the binary tool, forcing silence on warnings.
        """
        if not input_dir.exists():
            Logger.warn(f"{library_type} directory not found: {input_dir}")
            return

        Logger.info(f"Scanning {library_type} in: {input_dir.name}...")
        
        # 1. Collect Valid ACE Files
        ace_files = []
        try:
            for file_path in input_dir.iterdir():
                if file_path.is_file() and file_path.name != "xsdir" and not file_path.name.startswith("."):
                    ace_files.append(str(file_path.resolve()))
        except Exception as e:
            Logger.error(f"Error scanning directory: {e}")
            return

        if not ace_files:
            Logger.warn(f"No ACE files found in {input_dir}. Skipping.")
            return

        Logger.info(f"Found {len(ace_files)} files. Starting conversion...")
        
        # 2. Construct Command
        cmd = [Config.CONVERTER_CMD, "-d", str(Config.OUTPUT_HDF5_DIR)] + ace_files
        
        # [FIX] Prepare Environment to Suppress Subprocess Warnings
        env = os.environ.copy()
        env["PYTHONWARNINGS"] = "ignore"
        
        # 3. Execute
        try:
            subprocess.run(cmd, check=True, env=env)
            Logger.info(f"Successfully converted {len(ace_files)} files from {library_type}.")
            
        except subprocess.CalledProcessError as e:
            Logger.error(f"Conversion failed for {library_type}. Exit Code: {e.returncode}")
        except OSError as e:
            if e.errno == 7: 
                 Logger.error("Too many files (Argument list too long). Try smaller batches.")
            else:
                 Logger.error(f"OS Error: {e}")

    def generate_xml_library(self):
        """
        Scans the output directory for .h5 files and generates cross_sections.xml
        """
        Logger.header("GENERATING CROSS_SECTIONS.XML")
        
        h5_files = list(Config.OUTPUT_HDF5_DIR.glob("*.h5"))
        if not h5_files:
            Logger.warn("No HDF5 files found to generate XML library.")
            return

        Logger.info(f"Found {len(h5_files)} HDF5 files. Indexing...")
        
        try:
            # Context manager (redundant but safe)
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                
                lib = openmc.data.DataLibrary()
                for h5_file in h5_files:
                    lib.register_file(h5_file)
                
                xml_path = Config.OUTPUT_HDF5_DIR / "cross_sections.xml"
                lib.export_to_xml(xml_path)
            
            Logger.info(f"XML Library generated successfully at:")
            print(f"       {Fore.CYAN}{xml_path}{Style.RESET_ALL}")
            
        except Exception as e:
            Logger.error(f"Failed to generate XML library: {e}")

# --- Entry Point ---
if __name__ == "__main__":
    Logger.header("ACE TO HDF5 CONVERSION SYSTEM")
    print(f"{Fore.CYAN}Mode: System Binary + Silent Execution{Style.RESET_ALL}")
    
    # 1. Get Paths
    print("-" * 50)
    try:
        def_n_disp = Config.DEFAULT_NEUTRON_DIR.relative_to(Config.BASE_DIR)
        def_tsl_disp = Config.DEFAULT_TSL_DIR.relative_to(Config.BASE_DIR)
    except ValueError:
        def_n_disp = Config.DEFAULT_NEUTRON_DIR
        def_tsl_disp = Config.DEFAULT_TSL_DIR

    n_in = input(f"Enter path for incident neutron data (default: '{def_n_disp}'): ").strip()
    tsl_in = input(f"Enter path for thermal scattering data (default: '{def_tsl_disp}'): ").strip()
    
    path_n = (Config.BASE_DIR / n_in).resolve() if n_in else Config.DEFAULT_NEUTRON_DIR
    path_tsl = (Config.BASE_DIR / tsl_in).resolve() if tsl_in else Config.DEFAULT_TSL_DIR
    
    # 2. Initialize
    converter = ACEConverter()
    
    # 3. Run
    converter.convert_library(path_n, "Incident Neutron Data")
    converter.convert_library(path_tsl, "Thermal Scattering Data")
    converter.generate_xml_library()
    
    Logger.header("PROCESS COMPLETED")