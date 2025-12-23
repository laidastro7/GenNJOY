import sys
import os
import re
import json
from pathlib import Path
from colorama import Fore, Style, init

# Initialize colorama
init(autoreset=True)

class Config:
    BASE_DIR = Path.cwd().resolve()
    THERMAL_DIR = BASE_DIR / "data" / "thermal_scattering_endf"
    NEUTRON_DIR = BASE_DIR / "data" / "incident_neutron_endf"
    
    INPUTS_DIR = BASE_DIR / "inputs"
    SRC_DIR = BASE_DIR / "src"
    
    # Target Files
    OUTPUT_FILE = INPUTS_DIR / "tsl_inventory.i"
    OUTPUT_JSON = SRC_DIR / "temperature_index.json"

# --- 1. KNOWLEDGE BASE ---
KNOWN_MAPPINGS = [
    # Cryogenic
    {"pat": "s-CH4",    "z": 1,  "a": 1,  "name": "s-ch4",  "fixed_temp": "22"},
    {"pat": "l-CH4",    "z": 1,  "a": 1,  "name": "l-ch4",  "fixed_temp": "100"},
    {"pat": "ortho-D",  "z": 1,  "a": 2,  "name": "d-orth", "fixed_temp": "19"}, 
    {"pat": "para-D",   "z": 1,  "a": 2,  "name": "d-para", "fixed_temp": "19"},
    {"pat": "ortho-H",  "z": 1,  "a": 1,  "name": "h-orth", "fixed_temp": "20"},
    {"pat": "para-H",   "z": 1,  "a": 1,  "name": "h-para", "fixed_temp": "20"},
    # Standard
    {"pat": "YinYH2",   "z": 39, "a": 89, "name": "y-yh2"},
    {"pat": "HinYH2",   "z": 1,  "a": 1,  "name": "h-yh2"},
    {"pat": "HinCH2",   "z": 1,  "a": 1,  "name": "poly"},
    {"pat": "HinC5O2H8","z": 1,  "a": 1,  "name": "luct"},
    {"pat": "benzene",  "z": 1,  "a": 1,  "name": "benz"},
    {"pat": "HinH2O",   "z": 1,  "a": 1,  "name": "lwtr"},
    {"pat": "DinD2O",   "z": 1,  "a": 2,  "name": "hwtr"},
    {"pat": "OinD2O",   "z": 8,  "a": 16, "name": "do16"},
    {"pat": "HinZrH",   "z": 1,  "a": 1,  "name": "h-zr"},
    {"pat": "ZrinZrH",  "z": 40, "a": 0,  "name": "zr-h"},
    {"pat": "HinIce",   "z": 1,  "a": 1,  "name": "hice"},
    {"pat": "OinIce",   "z": 8,  "a": 16, "name": "oice"},
    {"pat": "graphite", "z": 6,  "a": 0,  "name": "grph"},
    {"pat": "CinSiC",   "z": 6,  "a": 0,  "name": "c-sic"},
    {"pat": "SiinSiC",  "z": 14, "a": 0,  "name": "s-sic"},
    {"pat": "SiO2",     "z": 14, "a": 0,  "name": "sio2"},
    {"pat": "Be-metal", "z": 4,  "a": 9,  "name": "be"},
    {"pat": "BeinBeO",  "z": 4,  "a": 9,  "name": "be-o"},
    {"pat": "OinBeO",   "z": 8,  "a": 16, "name": "obeo"},
    {"pat": "UinUO2",   "z": 92, "a": 238,"name": "u-o2"},
    {"pat": "OinUO2",   "z": 8,  "a": 16, "name": "o-uo2"},
    {"pat": "UinUN",    "z": 92, "a": 238,"name": "u-un"},
    {"pat": "NinUN",    "z": 7,  "a": 14, "name": "n-un"},
    {"pat": "Al_",      "z": 13, "a": 27, "name": "al27"},
    {"pat": "Fe_",      "z": 26, "a": 56, "name": "fe56"},
]

def find_neutron_partner_smart(tsl_filename):
    if not Config.NEUTRON_DIR.exists(): return None, None, None
    target_z, target_a, ace_name, fixed_temp = None, None, None, None

    for entry in KNOWN_MAPPINGS:
        if entry["pat"] in tsl_filename:
            target_z = entry["z"]
            target_a = entry["a"]
            ace_name = entry["name"]
            fixed_temp = entry.get("fixed_temp")
            break
    
    if target_z is None:
        match = re.search(r"tsl-(\d+)_([A-Za-z]+)_(\d+)", tsl_filename)
        if match:
            target_z = int(match.group(1))
            target_a = int(match.group(3))
            ace_name = f"{match.group(2).lower()}{target_a:02}"
    
    if target_z is not None:
        z_str = f"{target_z:03}"
        best_match = None
        for f in Config.NEUTRON_DIR.iterdir():
            if not f.name.startswith(f"n-{z_str}_"): continue
            try:
                parts = f.name.replace('.endf','').split('_')
                file_a = int(parts[2])
            except: continue
            if target_a == file_a: return f.name, ace_name, fixed_temp
            if target_a == 0 and file_a == 0: best_match = f.name
            if target_a == 0 and not best_match: best_match = f.name 
        if best_match: return best_match, ace_name, fixed_temp

    return None, None, None

# --- 2. HEADER MINING ---
def extract_header_temperatures(file_path):
    if not file_path.exists(): return None
    try:
        with open(file_path, 'r', errors='ignore') as f:
            lines = [next(f) for _ in range(100)]
    except: return None

    found = False
    temp_block = ""
    STOP_KEYWORDS = ["reference", "history", "njoy", "evaluation", "dist-", "http", "doi", "copyright"]

    for line in lines:
        raw_content = line[:66].strip()
        clean_content = raw_content.strip('*#').strip()
        lower_line = clean_content.lower()

        if not found:
            if "temperatures" in lower_line:
                found = True
                temp_block += " " + clean_content
                if lower_line.endswith('.') or lower_line.endswith('k') or lower_line.endswith('deg'): break
        else:
            if any(kw in lower_line for kw in STOP_KEYWORDS): break
            if not clean_content: break
            if not any(c.isdigit() for c in clean_content): break
            temp_block += " " + clean_content
            if lower_line.endswith('.') or lower_line.endswith('k') or lower_line.endswith('deg'): break
    
    if found and temp_block:
        normalized = re.sub(r'[=:,]', ' ', temp_block)
        candidates = re.findall(r"(\d+\.?\d*)", normalized)
        valid_temps = []
        for c in candidates:
            try:
                val = float(c)
                if val == 1451.0 or val > 1800.0 or val < 0.1: continue
                if 90.0 < val < 100.0 and '.' in str(val): continue 
                valid_temps.append(val)
            except: continue
        
        if valid_temps:
            unique_temps = sorted(list(set(valid_temps)))
            return " ".join([f"{t:g}" for t in unique_temps])

    # Contextual Backup
    full_header = "".join([l[:66] for l in lines])
    match_context = re.search(r"\bat\s+(\d+\.?\d*)\s*[kK]", full_header, re.IGNORECASE)
    if match_context:
        return match_context.group(1)
    return None

# --- 3. JSON DICTIONARY GENERATOR (INTEGRATED) ---
def generate_json_dictionary():
    """Generates the temperature_index.json from the just-created .i file."""
    print(f"\n{Fore.CYAN}{'-'*20} Generating JSON Dictionary {'-'*20}{Style.RESET_ALL}")
    
    if not Config.OUTPUT_FILE.exists():
        print(f"{Fore.RED}[ERROR] Input file not found: {Config.OUTPUT_FILE}{Style.RESET_ALL}")
        return

    with open(Config.OUTPUT_FILE, 'r') as f:
        content = f.read()

    temp_dict = {}
    blocks = content.split('\n\n')
    
    for block in blocks:
        if not block.strip(): continue
        t_match = re.search(r"element_t\s*=\s*(\S+)", block)
        temp_match = re.search(r"temperatures\s*=\s*(.+)", block)
        
        if t_match and temp_match:
            key = t_match.group(1).strip()
            raw_temps = temp_match.group(1).replace(',', ' ').split()
            try:
                clean_temps = [str(float(t)) for t in raw_temps]
                val = " ".join(clean_temps)
                temp_dict[key] = val
            except: pass

    Config.OUTPUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    with open(Config.OUTPUT_JSON, 'w') as f:
        json.dump(temp_dict, f, indent=4)
        
    print(f"{Fore.GREEN}[SUCCESS] Updated {Config.OUTPUT_JSON.name} with {len(temp_dict)} entries.{Style.RESET_ALL}")

# --- MAIN EXECUTION ---
def main():
    print(f"\n{Fore.CYAN}{'='*60}")
    print(f"{Fore.BLUE}{Style.BRIGHT}{'TSL GENERATOR: DUAL OUTPUT (FILE + JSON)'.center(60)}")
    print(f"{Fore.CYAN}{'='*60}{Style.RESET_ALL}")

    if not Config.THERMAL_DIR.exists():
        print(f"{Fore.RED}[ERROR] Thermal directory missing.{Style.RESET_ALL}")
        sys.exit(1)
        
    tsl_files = sorted([f for f in Config.THERMAL_DIR.iterdir() if f.name.startswith("tsl-") and f.name.endswith(".endf")])
    Config.INPUTS_DIR.mkdir(parents=True, exist_ok=True)
    
    count = 0
    with open(Config.OUTPUT_FILE, 'w') as f:
        for i, tsl_path in enumerate(tsl_files, 1):
            fname = tsl_path.name
            
            n_file, ace_name, fixed_temp = find_neutron_partner_smart(fname)
            print(f"[{i:02}] {fname[:22].ljust(22)}", end='')
            
            if not n_file:
                print(f" -> {Fore.RED}SKIP (No Mapping){Style.RESET_ALL}")
                continue
            
            if fixed_temp:
                temps = fixed_temp
                print(f" | T: {Fore.CYAN}{temps.ljust(17)}{Style.RESET_ALL}", end='')
            else:
                temps = extract_header_temperatures(tsl_path)
                if not temps:
                    readme = tsl_path.with_suffix(".readme")
                    if readme.exists(): temps = extract_header_temperatures(readme)
                
                if temps:
                    disp = (temps[:15] + '..') if len(temps) > 15 else temps
                    print(f" | T: {Fore.GREEN}{disp.ljust(17)}{Style.RESET_ALL}", end='')
                else:
                    temps = "293.6"
                    print(f" | T: {Fore.YELLOW}Def (293.6)      {Style.RESET_ALL}", end='')

            if not ace_name: ace_name = fname.replace("tsl-","")[:4]
            
            entry = (
                f"element_n = {n_file}\n"
                f"element_t = {fname.ljust(30)} "
                f"name = {ace_name.ljust(6)} "
                f"temperatures = {temps}\n\n"
            )
            f.write(entry)
            count += 1
            print(f" -> {Fore.GREEN}OK{Style.RESET_ALL}")

    print("-" * 60)
    print(f"{Fore.GREEN}[SUCCESS] Generated {Config.OUTPUT_FILE.name}{Style.RESET_ALL}")
    
    # 2. GENERATE JSON AUTOMATICALLY
    generate_json_dictionary()
    
    # 3. FINAL WARNING
    print(f"\n{Fore.YELLOW}{'#'*60}")
    print(f"{'⚠️  VERIFICATION REQUIRED  ⚠️'.center(60)}")
    print(f"{'#'*60}")
    print(f"Please manually verify the temperatures in BOTH files:")
    print(f"1. {Style.BRIGHT}{Config.OUTPUT_FILE}{Style.RESET_ALL}{Fore.YELLOW}")
    print(f"2. {Style.BRIGHT}{Config.OUTPUT_JSON}{Style.RESET_ALL}{Fore.YELLOW}")
    print(f"{'#'*60}{Style.RESET_ALL}")

if __name__ == "__main__":
    main()