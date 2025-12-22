import sys
import os
import re
from pathlib import Path
from colorama import Fore, Style, init

# Initialize colorama
init(autoreset=True)

class Config:
    BASE_DIR = Path.cwd().resolve()
    
    # Source Directory (Where ENDF files are)
    NEUTRON_DIR = BASE_DIR / "data" / "incident_neutron_endf"
    
    # Output Directory & File
    INPUTS_DIR = BASE_DIR / "inputs"
    OUTPUT_FILE = INPUTS_DIR / "input_n_global.i"

def get_ace_name(filename):
    """
    Parses ENDF filename to generate a short ACE name.
    Standard NNDC format: n-ZZZ_El_AAA.endf (e.g., n-001_H_001.endf -> H1)
    """
    # Remove extension
    stem = Path(filename).stem # n-001_H_001
    
    # Try splitting by underscore
    parts = stem.split('_')
    
    if len(parts) >= 3:
        # parts[1] is Element (H), parts[2] is Mass (001)
        element = parts[1]
        try:
            mass = int(parts[2]) # Convert 001 to 1
            return f"{element}{mass}"
        except ValueError:
            return f"{element}{parts[2]}"
            
    # Fallback: Return stem if pattern doesn't match
    return stem

def main():
    print(f"\n{Fore.CYAN}{'='*60}")
    print(f"{Fore.BLUE}{Style.BRIGHT}{'NJOY INPUT GENERATOR (AUTO-SCAN)'.center(60)}")
    print(f"{Fore.CYAN}{'='*60}{Style.RESET_ALL}")

    # 1. Validate Source Directory
    if not Config.NEUTRON_DIR.exists():
        print(f"{Fore.RED}[ERROR] Source directory not found: {Config.NEUTRON_DIR}")
        print(f"       Please run the download script first (Option 1).{Style.RESET_ALL}")
        sys.exit(1)

    # 2. Scan for ENDF files
    print(f"{Fore.YELLOW}Scanning directory: {Config.NEUTRON_DIR.name}...{Style.RESET_ALL}")
    
    # Filter for files starting with 'n-' (Standard NNDC naming) or ending in .endf
    endf_files = sorted([
        f for f in Config.NEUTRON_DIR.iterdir() 
        if f.is_file() and (f.name.startswith("n-") or f.suffix == ".endf")
    ])

    if not endf_files:
        print(f"{Fore.RED}[ERROR] No ENDF files found in source directory.{Style.RESET_ALL}")
        sys.exit(1)

    print(f"{Fore.GREEN}[INFO] Found {len(endf_files)} neutron data files.{Style.RESET_ALL}")

    # 3. Request Temperatures
    print("-" * 50)
    print("Please enter the desired temperatures in Kelvin (separated by space).")
    print("Example: 293.6 600.0 900.0")
    user_temps = input(f"{Fore.CYAN}>> Temperatures: {Style.RESET_ALL}").strip()

    if not user_temps:
        print(f"{Fore.RED}[ERROR] No temperatures provided. Exiting.{Style.RESET_ALL}")
        sys.exit(1)

    # 4. Generate Input File
    Config.INPUTS_DIR.mkdir(parents=True, exist_ok=True)
    
    print(f"\nGenerating {Config.OUTPUT_FILE.name}...")
    
    with open(Config.OUTPUT_FILE, 'w') as f:
        for file_path in endf_files:
            filename = file_path.name
            ace_name = get_ace_name(filename)
            
            # Formatting as requested:
            # element_n = <file>   name = <short_name>   temperatures = <temps>
            line = (
                f"element_n = {filename.ljust(25)} "
                f"name = {ace_name.ljust(8)} "
                f"temperatures = {user_temps}\n"
            )
            f.write(line)
            # print(f"   Processed: {filename} -> {ace_name}")

    print("-" * 50)
    print(f"{Fore.GREEN}[SUCCESS] Generated inputs for {len(endf_files)} isotopes.{Style.RESET_ALL}")
    print(f"Output File: {Config.OUTPUT_FILE}")
    print(f"Temperatures set to: {user_temps}")

if __name__ == "__main__":
    main()