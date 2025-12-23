import os
import sys
import subprocess
import shutil
import warnings
from pathlib import Path
from colorama import Fore, Style, init

# Suppress warnings for the current process
warnings.filterwarnings("ignore")

# Verify OpenMC Python API availability
try:
    import openmc.data
except ImportError:
    print(Fore.RED + "[CRITICAL] The 'openmc' python package is required but not found.")
    sys.exit(1)

# Initialize terminal styling
init(autoreset=True)

# --- Application Configuration ---
class AppConfig:
    """Holds global application settings and paths."""
    # [UPDATED] Points to the package directory (gennjoy/)
    BASE_DIR = Path(__file__).resolve().parent
    
    # System binary for conversion
    BINARY_TOOL_NAME = "openmc-ace-to-hdf5"
    
    # [UPDATED] Paths relative to the package installation directory
    DEFAULT_NEUTRON_PATH = BASE_DIR / "data" / "incident_neutron_ace"
    DEFAULT_THERMAL_PATH = BASE_DIR / "data" / "thermal_scattering_ace"
    LIBRARY_OUTPUT_PATH  = BASE_DIR / "data" / "hdf5_library"

# --- Logging Interface ---
class Log:
    """Standardized logging interface for the application."""
    @staticmethod
    def info(message):
        print(f"{Fore.GREEN}[INFO]{Style.RESET_ALL} {message}")
    
    @staticmethod
    def error(message):
        print(f"{Fore.RED}[ERROR]{Style.RESET_ALL} {message}")
        
    @staticmethod
    def warning(message):
        print(f"{Fore.YELLOW}[WARN]{Style.RESET_ALL} {message}")

    @staticmethod
    def banner(title):
        print(f"\n{Fore.CYAN}{'='*70}")
        print(f"{Fore.BLUE}{Style.BRIGHT}{title.center(70)}")
        print(f"{Fore.CYAN}{'='*70}{Style.RESET_ALL}")

    @staticmethod
    def section(title):
        print(f"\n{Fore.MAGENTA}>>> {title}{Style.RESET_ALL}")

# --- Core Logic ---
class LibraryCompilationManager:
    """
    Orchestrates the conversion of ACE datasets into an HDF5-based 
    OpenMC nuclear data library.
    """
    def __init__(self):
        self._validate_environment()
        self._initialize_workspace()

    def _validate_environment(self):
        """Ensures all system dependencies are met."""
        if not shutil.which(AppConfig.BINARY_TOOL_NAME):
            Log.error(f"System binary '{AppConfig.BINARY_TOOL_NAME}' is missing from PATH.")
            print(f"{Fore.YELLOW}Tip: Ensure OpenMC is installed and openmc-ace-to-hdf5 is accessible.{Style.RESET_ALL}")
            sys.exit(1)
        else:
            Log.info(f"System Tool Detected: {AppConfig.BINARY_TOOL_NAME}")

    def _initialize_workspace(self):
        """Prepares the output directory."""
        if not AppConfig.LIBRARY_OUTPUT_PATH.exists():
            try:
                AppConfig.LIBRARY_OUTPUT_PATH.mkdir(parents=True, exist_ok=True)
                Log.info(f"Output workspace created at: {AppConfig.LIBRARY_OUTPUT_PATH}")
            except PermissionError:
                Log.error(f"Permission denied creating: {AppConfig.LIBRARY_OUTPUT_PATH}")
                Log.error("Try running with sudo or check folder permissions.")
                sys.exit(1)

    def process_dataset(self, source_dir: Path, dataset_label: str):
        """
        Processes a specific ACE dataset (Neutron/Thermal) and converts it to HDF5.
        """
        Log.section(f"Processing Dataset: {dataset_label}")

        if not source_dir.exists():
            Log.warning(f"Source directory not found: {source_dir}")
            return

        Log.info(f"Scanning directory: {source_dir.name}...")
        
        # 1. Discovery Phase
        ace_files = []
        try:
            for file_path in source_dir.iterdir():
                # Filter out metadata files and hidden system files
                if file_path.is_file() and file_path.name != "xsdir" and not file_path.name.startswith("."):
                    ace_files.append(str(file_path.resolve()))
        except Exception as e:
            Log.error(f"Filesystem error: {e}")
            return

        if not ace_files:
            Log.warning("No valid ACE files identified in the source directory.")
            return

        Log.info(f"Identified {len(ace_files)} ACE files. Initiating conversion...")
        
        # 2. Execution Phase
        # Command Structure: openmc-ace-to-hdf5 -d <OUTPUT_DIR> <FILE_1> <FILE_2> ...
        cmd = [AppConfig.BINARY_TOOL_NAME, "-d", str(AppConfig.LIBRARY_OUTPUT_PATH)] + ace_files
        
        # Environment configuration to suppress subprocess warnings
        env = os.environ.copy()
        env["PYTHONWARNINGS"] = "ignore"
        
        try:
            subprocess.run(cmd, check=True, env=env)
            Log.info(f"Successfully compiled {len(ace_files)} files for {dataset_label}.")
            
        except subprocess.CalledProcessError as e:
            Log.error(f"Compilation failed with exit code: {e.returncode}")
        except OSError as e:
            if e.errno == 7: 
                 Log.error("Argument list too long. Consider batch processing.")
            else:
                 Log.error(f"System error: {e}")

    def finalize_library_indexing(self):
        """
        Generates the master 'cross_sections.xml' index for OpenMC.
        """
        Log.section("Finalizing Library Index")
        
        h5_inventory = list(AppConfig.LIBRARY_OUTPUT_PATH.glob("*.h5"))
        if not h5_inventory:
            Log.warning("No HDF5 libraries found in workspace. Indexing skipped.")
            return

        Log.info(f"Indexing {len(h5_inventory)} HDF5 libraries...")
        
        try:
            # Suppress API warnings during indexing
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                
                library = openmc.data.DataLibrary()
                for h5_file in h5_inventory:
                    library.register_file(h5_file)
                
                xml_path = AppConfig.LIBRARY_OUTPUT_PATH / "cross_sections.xml"
                library.export_to_xml(xml_path)
            
            Log.info("Master Index Generated Successfully.")
            print(f"       {Fore.CYAN}Location: {xml_path}{Style.RESET_ALL}")
            
        except Exception as e:
            Log.error(f"Indexing failed: {e}")

# --- Main Execution Entry Point ---
if __name__ == "__main__":
    Log.banner("OPENMC HDF5 LIBRARY COMPILER")
    print(f"{Fore.CYAN}   System Status: Ready | Silent Mode: Active{Style.RESET_ALL}")
    print("-" * 70)
    
    # 1. User Input Acquisition
    # Attempt to show paths relative to the package dir for cleaner display
    try:
        def_n_disp = AppConfig.DEFAULT_NEUTRON_PATH.relative_to(AppConfig.BASE_DIR)
        def_t_disp = AppConfig.DEFAULT_THERMAL_PATH.relative_to(AppConfig.BASE_DIR)
    except ValueError:
        # Fallback if paths are somehow outside BASE_DIR
        def_n_disp = AppConfig.DEFAULT_NEUTRON_PATH
        def_t_disp = AppConfig.DEFAULT_THERMAL_PATH

    print(f"{Fore.YELLOW}Configuring Data Sources:{Style.RESET_ALL}")
    
    # Prompt with the package default paths
    neutron_source_input = input(f"   >> Incident Neutron Data Path [Default: internal/{def_n_disp}]: ").strip()
    thermal_source_input = input(f"   >> Thermal Scattering Data Path [Default: internal/{def_t_disp}]: ").strip()
    
    # Path Resolution
    # If user hits enter, use the internal package data paths.
    # If user enters a path, resolve it relative to where they ran the command (Path.cwd()) if relative,
    # or just use it if absolute.
    if neutron_source_input:
        neutron_source_path = Path(neutron_source_input).resolve()
    else:
        neutron_source_path = AppConfig.DEFAULT_NEUTRON_PATH

    if thermal_source_input:
        thermal_source_path = Path(thermal_source_input).resolve()
    else:
        thermal_source_path = AppConfig.DEFAULT_THERMAL_PATH
    
    # 2. Pipeline Initialization
    manager = LibraryCompilationManager()
    
    # 3. Pipeline Execution
    manager.process_dataset(neutron_source_path, "Incident Neutron Data")
    manager.process_dataset(thermal_source_path, "Thermal Scattering Data")
    
    # 4. Finalization
    manager.finalize_library_indexing()
    
    Log.banner("COMPILATION PIPELINE COMPLETED")