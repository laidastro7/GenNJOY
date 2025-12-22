import sys
import json
import re
from pathlib import Path
from colorama import Fore, Style, init

# Initialize colorama
init(autoreset=True)

class Config:
    BASE_DIR = Path.cwd().resolve()
    INPUTS_DIR = BASE_DIR / "inputs"
    INPUT_FILE = INPUTS_DIR / "tsl_inventory.i"
    OUTPUT_JSON = BASE_DIR / "src" / "dict_temperature.json"

def generate_dictionary():
    print(f"\n{Fore.CYAN}{'='*60}")
    print(f"{Fore.BLUE}{Style.BRIGHT}{'TEMPERATURE DICTIONARY GENERATOR'.center(60)}")
    print(f"{Fore.CYAN}{'='*60}{Style.RESET_ALL}")

    if not Config.INPUT_FILE.exists():
        print(f"{Fore.RED}[ERROR] Input file not found: {Config.INPUT_FILE}{Style.RESET_ALL}")
        return

    print(f"{Fore.YELLOW}Reading from: {Config.INPUT_FILE}{Style.RESET_ALL}")

    with open(Config.INPUT_FILE, 'r') as f:
        content = f.read()

    # Dictionary Structure: {"element_name": "temp1 temp2 temp3 ..."}
    # Note: The old script expects the KEY to be the 'element_t' (e.g. tsl-013_Al_027.endf)
    # or the internal name? Let's check the old script logic.
    # Usually it maps "isotope_name" -> "temps".
    # Based on your input, element_t seems to be the file name. 
    # Let's map filename -> temps string.

    temp_dict = {}
    
    # Split blocks
    blocks = content.split('\n\n')
    
    count = 0
    for block in blocks:
        if not block.strip(): continue
        
        # Regex to find element_t and temperatures
        # element_t = tsl-013_Al_027.endf
        # temperatures = 20 80 ...
        
        t_match = re.search(r"element_t\s*=\s*(\S+)", block)
        temp_match = re.search(r"temperatures\s*=\s*(.+)", block)
        
        if t_match and temp_match:
            key = t_match.group(1).strip() # The filename
            
            # Clean up temperatures (remove commas if any, just space separated)
            raw_temps = temp_match.group(1).replace(',', ' ').split()
            # Convert to float and back to string to standardize
            try:
                clean_temps = [str(float(t)) for t in raw_temps]
                val = " ".join(clean_temps)
                
                temp_dict[key] = val
                count += 1
                print(f"[{count:02}] {key[:25].ljust(25)} -> {val[:30]}...")
            except:
                print(f"{Fore.RED}[SKIP] Invalid temps in {key}{Style.RESET_ALL}")

    # Write JSON
    Config.OUTPUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    
    with open(Config.OUTPUT_JSON, 'w') as f:
        json.dump(temp_dict, f, indent=4)
        
    print("-" * 60)
    print(f"{Fore.GREEN}[SUCCESS] Generated dictionary with {len(temp_dict)} entries.{Style.RESET_ALL}")
    print(f"Saved to: {Config.OUTPUT_JSON}")

if __name__ == "__main__":
    generate_dictionary()