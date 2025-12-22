import sys
import subprocess
import shutil
from pathlib import Path
from typing import List, Optional
from colorama import Fore, Style, init

# Initialize colorama for colored output
init(autoreset=True)

# --- Project Configuration ---
BASE_DIR = Path(__file__).resolve().parent
SRC_DIR = BASE_DIR / "src"
INPUTS_DIR = BASE_DIR / "inputs"

# --- Header & Branding ---
GEN_NJOY_HEADER = """
         ____            _   _     _  ___ __   __
        / ___| ___ _ __ | \ | |   | |/ _ \\ \ / /
       | |  _ / _ \ '_ \|  \| |_  | | | | \ V / 
       | |_| |  __/ | | | |\  | |_| | |_| || |  
        \____|\___|_| |_|_| \_|\___/ \___/ |_|  
"""

def display_header():
    """Display the official banner and tool description."""
    print("\n" + Fore.CYAN + "="*62)
    print(Fore.BLUE + Style.BRIGHT + GEN_NJOY_HEADER + Style.RESET_ALL)
    print(Fore.CYAN + "="*62)
    print(Style.BRIGHT + "   Automated Nuclear Data Processing Framework (NJOY + OpenMC)")
    print("   Author: Dr. Mohamed Laid YAHIAOUI et al.")
    print("-" * 62)
    print("   System Mode: [Global PATH Execution]")
    print("-" * 62 + "\n")

# --- System Validation Module ---

def verify_system_njoy():
    """
    [CRITICAL] Check if NJOY is installed in the system PATH.
    Refuses to start if 'njoy' command is not found.
    """
    njoy_path = shutil.which("njoy")
    
    if njoy_path:
        print(Fore.GREEN + f"[System Check] NJOY detected at: {njoy_path}")
        return True
    else:
        print(Fore.RED + "="*60)
        print(Fore.RED + Style.BRIGHT + "[CRITICAL ERROR] NJOY executable not found!")
        print(Fore.RED + "="*60)
        print(Fore.YELLOW + "   The tool cannot find 'njoy' in your system PATH.")
        print("   Please ensure NJOY2016 is installed and accessible globally.")
        print("   Try running 'njoy' in your terminal to verify.")
        print(Fore.RED + "="*60 + "\n")
        return False

# --- Helper Functions ---

def run_script(script_name: str, args: Optional[List[str]] = None):
    """
    Execute a module from the 'src' directory.
    """
    script_path = SRC_DIR / script_name
    
    if not script_path.exists():
        print(Fore.RED + f"[Error] Module not found: {script_name}")
        return

    command = [sys.executable, str(script_path)]
    if args:
        command.extend(args)

    print(Fore.CYAN + f"[*] Initializing module: {script_name}...")
    try:
        # Pass the system environment variables to the subprocess
        subprocess.run(command, check=True)
        print(Fore.GREEN + f"[Success] Module '{script_name}' completed successfully.")
    except subprocess.CalledProcessError as e:
        print(Fore.RED + f"[Failed] Module '{script_name}' exited with error code: {e.returncode}.")
    except Exception as e:
        print(Fore.RED + f"[Error] Unexpected system error: {e}")

def get_validated_input_file(prompt_text: str, default_filename: str) -> str:
    """Prompt the user for a file path with validation."""
    default_path = INPUTS_DIR / default_filename
    print(Fore.YELLOW + f"   > {prompt_text}")
    user_input = input(f"     (Press Enter for Default: {default_filename}): ").strip()
    
    file_path_str = user_input if user_input else str(default_path)
    file_path = Path(file_path_str)

    if not file_path.exists():
        print(Fore.RED + f"   [!] File not found: {file_path}")
        retry = input("       Proceed anyway? (y/n): ").lower()
        if retry != 'y':
            return ""
            
    return str(file_path)

def display_menu():
    """Display the operation menu."""
    print(Fore.WHITE + Style.BRIGHT + "MAIN MENU: Select an Operation")
    print("." * 42)
    print(f" {Fore.GREEN}1.{Style.RESET_ALL} Download Raw Data (ENDF/B-VIII.0)")
    print(f" {Fore.GREEN}2.{Style.RESET_ALL} Generate NJOY Inputs (Incident Neutrons)")
    print(f" {Fore.GREEN}3.{Style.RESET_ALL} Generate NJOY Inputs (Thermal Scattering)")
    print(f" {Fore.GREEN}4.{Style.RESET_ALL} Run NJOY Processing (Incident Neutrons)")
    print(f" {Fore.GREEN}5.{Style.RESET_ALL} Run NJOY Processing (Thermal Scattering)")
    print(f" {Fore.GREEN}6.{Style.RESET_ALL} Convert ACE Libraries to HDF5 (OpenMC)")
    print(f" {Fore.RED}7.{Style.RESET_ALL} Exit")
    print("." * 42 + "\n")

# --- Core Logic ---

def process_choice(choice: str) -> bool:
    """Process the user's menu selection."""
    
    if choice == "1":
        print("\n--- Downloading ENDF/B-VIII.0 Library ---")
        run_script("download_data.py")
    
    elif choice == "2":
        print("\n--- Generating NJOY Input Decks (Neutron) ---")
        run_script("gen_input_n.py")
    
    elif choice == "3":
        print("\n--- Generating NJOY Input Decks (TSL) ---")
        run_script("gen_input_tsl.py")
    
    elif choice == "4":
        print("\n--- Executing NJOY (Neutron Processing) ---")
        # Ensure NJOY is available before running
        if verify_system_njoy():
            input_file = get_validated_input_file(
                "Please specify the NJOY input file path:", 
                "neutron_process_batch.i"
            )
            if input_file:
                run_script("gen_njoy_n.py", [input_file])
    
    elif choice == "5":
        print("\n--- Executing NJOY (Thermal Scattering Processing) ---")
        # Ensure NJOY is available before running
        if verify_system_njoy():
            input_file = get_validated_input_file(
                "Please specify the TSL input file path:", 
                "tsl_process_batch.i"
            )
            if input_file:
                run_script("gen_njoy_tsl.py", [input_file])
    
    elif choice == "6":
        print("\n--- Converting ACE to HDF5 ---")
        run_script("conversion_ace_hdf5.py")
    
    elif choice == "7":
        print(Fore.MAGENTA + "\n   Thank you for using GenNJOY. Goodbye!\n")
        return False
    
    else:
        print(Fore.RED + "\n[!] Invalid selection. Please enter a number between 1 and 7.")
    
    return True

# --- Entry Point ---

def main():
    try:
        display_header()
        
        # Optional: Verify NJOY at startup
        # verify_system_njoy() 
        
        running = True
        while running:
            display_menu()
            choice = input(Fore.YELLOW + "Select option [1-7]: " + Style.RESET_ALL).strip()
            running = process_choice(choice)
            if running:
                print("\n" + "-"*42 + "\n")
    except KeyboardInterrupt:
        print(Fore.RED + "\n\n[!] Session interrupted by user. Exiting...")
        sys.exit(0)

if __name__ == "__main__":
    main()