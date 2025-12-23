import sys
import os
import re
from pathlib import Path
from colorama import Fore, Style, init

# Initialize colorama
init(autoreset=True)

class Config:
    # Points to the package directory to locate internal data/inputs
    BASE_DIR = Path(__file__).resolve().parent
    
    # Source Directory
    NEUTRON_DIR = BASE_DIR / "data" / "incident_neutron_endf"
    
    # Default Output
    INPUTS_DIR = BASE_DIR / "inputs"
    DEFAULT_OUTPUT_FILE = INPUTS_DIR / "neutron_inventory.i"
    BATCH_FILE = INPUTS_DIR / "neutron_process_batch.i"

    # Default Temperatures
    DEFAULT_TEMPS_LIST = [293.6, 600.0, 900.0]

def get_short_name(filename):
    """
    Converts 'n-001_H_002.endf' -> 'H2'
    Converts 'n-092_U_235.endf' -> 'U235'
    """
    # Regex to capture Symbol and Mass
    match = re.search(r"n-\d+_([A-Za-z]+)_(\d+)(\w*)", filename)
    if match:
        sym = match.group(1)      # H
        mass = int(match.group(2)) # 002 -> 2
        meta = match.group(3)      # m1 (optional)
        return f"{sym}{mass}{meta}"
    
    # Fallback
    return Path(filename).stem

def get_user_temperatures():
    """Prompts user for temperatures."""
    print("-" * 50)
    def_str = " ".join([str(t) for t in Config.DEFAULT_TEMPS_LIST])
    print(f"Default Temperatures: {Fore.YELLOW}{def_str}{Style.RESET_ALL} Kelvin")
    print("Enter temperatures (space separated) or press Enter to use defaults.")
    
    try:
        user_input = input(f"{Fore.CYAN}>> Temperatures: {Style.RESET_ALL}").strip()
    except:
        user_input = ""

    if not user_input:
        print(f"{Fore.GREEN}[INFO] Using default temperatures.{Style.RESET_ALL}")
        return Config.DEFAULT_TEMPS_LIST

    try:
        cleaned = user_input.replace(',', ' ')
        temps = [float(t) for t in cleaned.split()]
        return sorted(list(set(temps)))
    except ValueError:
        print(f"{Fore.RED}[ERROR] Invalid input. Using defaults.{Style.RESET_ALL}")
        return Config.DEFAULT_TEMPS_LIST

def main():
    print(f"\n{Fore.CYAN}{'='*60}")
    print(f"{Fore.BLUE}{Style.BRIGHT}{'NEUTRON INPUT GENERATOR (SINGLE LINE)'.center(60)}")
    print(f"{Fore.CYAN}{'='*60}{Style.RESET_ALL}")

    # Ensure inputs directory exists
    Config.INPUTS_DIR.mkdir(parents=True, exist_ok=True)

    # 1. Argument Handling
    if len(sys.argv) > 1:
        target_file = Path(sys.argv[1]).resolve()
        if target_file.is_dir():
            target_file = target_file / "neutron_inventory.i"
    else:
        target_file = Config.DEFAULT_OUTPUT_FILE

    # 2. Validate Source
    if not Config.NEUTRON_DIR.exists():
        print(f"{Fore.RED}[ERROR] Source directory not found: {Config.NEUTRON_DIR}")
        print(f"{Fore.YELLOW}Tip: Run Option 1 (Download ENDF Library) first.{Style.RESET_ALL}")
        sys.exit(1)

    # 3. Get Temperatures
    selected_temps = get_user_temperatures()
    temps_str = " ".join([str(t) for t in selected_temps])

    # 4. Scan Files
    print(f"\n{Fore.YELLOW}Scanning directory...{Style.RESET_ALL}")
    try:
        files = sorted([
            f for f in Config.NEUTRON_DIR.iterdir() 
            if f.is_file() and (f.name.startswith("n-") or f.suffix == ".endf")
        ])
    except Exception as e:
        print(f"{Fore.RED}[ERROR] Failed to scan directory: {e}")
        sys.exit(1)

    if not files:
        print(f"{Fore.RED}[ERROR] No ENDF files found in {Config.NEUTRON_DIR.name}.{Style.RESET_ALL}")
        print(f"{Fore.YELLOW}Tip: Run Option 1 to populate the data directory.{Style.RESET_ALL}")
        sys.exit(1)

    print(f"{Fore.GREEN}[INFO] Found {len(files)} neutron files.{Style.RESET_ALL}")

    # 5. Generate Output (Single Line Format)
    try:
        count = 0
        with open(target_file, 'w') as f:
            for n_file in files:
                fname = n_file.name
                short_name = get_short_name(fname)
                
                # Exact format requested:
                # element_n = n-001_H_001.endf          name = H1       temperatures = 293.6 600.0
                entry = (
                    f"element_n = {fname.ljust(25)} "
                    f"name = {short_name.ljust(8)} "
                    f"temperatures = {temps_str}\n"
                )
                f.write(entry)
                count += 1
                
                if count % 50 == 0:
                    sys.stdout.write(f"\r[PROCESSING] {count} isotopes...")
                    sys.stdout.flush()

        print(f"\n\n{Fore.GREEN}[SUCCESS] Generated: {target_file.name}{Style.RESET_ALL}")
        print(f"Path: {target_file}")

        # --- NEW INSTRUCTION MESSAGE ---
        print(f"\n{Fore.YELLOW}{'='*60}")
        print(f"{Style.BRIGHT}NEXT STEP (ACTION REQUIRED):")
        print(f"{'='*60}{Style.RESET_ALL}")
        print(f"1. Open the generated file: {Fore.CYAN}{target_file.name}{Style.RESET_ALL}")
        print(f"2. Copy the lines of the isotopes you want to process.")
        print(f"3. Paste them into the batch file: {Fore.CYAN}inputs/{Config.BATCH_FILE.name}{Style.RESET_ALL}")
        print(f"   (This batch file is what Option 4 will execute)")
        print(f"{Fore.YELLOW}{'='*60}{Style.RESET_ALL}\n")
        
    except PermissionError:
        print(f"\n{Fore.RED}[ERROR] Permission denied writing to: {target_file}{Style.RESET_ALL}")
        print("Try running with higher privileges or check folder permissions.")

if __name__ == "__main__":
    main()