import os
import sys
import zipfile
import tarfile
import urllib.request
import shutil
from pathlib import Path
from colorama import Fore, Style, init

# Initialize colorama
init(autoreset=True)

class Config:
    BASE_DIR = Path.cwd().resolve()
    DATA_DIR = BASE_DIR / "data"
    
    # Target Folder Names
    NEUTRON_DIR_NAME = "incident_neutron_endf"
    THERMAL_DIR_NAME = "thermal_scattering_endf"

    # --- LIBRARY DATABASE (DIRECT LINKS) ---
    LIBRARIES = {
        "1": {
            "name": "ENDF/B-VIII.1 (Latest Standard - 2024) [.tar.gz]",
            "n_url": "https://www.nndc.bnl.gov/endf-releases/releases/B-VIII.1/neutrons/neutrons-version.VIII.1.tar.gz",
            "t_url": "https://www.nndc.bnl.gov/endf-releases/releases/B-VIII.1/thermal_scatt/thermal_scatt-version.VIII.1.tar.gz"
        },
        "2": {
            "name": "ENDF/B-VIII.0 (Stable Standard - 2018) [.zip]",
            "n_url": "https://www.nndc.bnl.gov/endf-b8.0/zips/ENDF-B-VIII.0_neutrons.zip",
            "t_url": "https://www.nndc.bnl.gov/endf-b8.0/zips/ENDF-B-VIII.0_thermal_scatt.zip"
        },
        "3": {
            "name": "ENDF/B-VII.1 (Legacy Standard - 2011) [.zip]",
            "n_url": "https://www.nndc.bnl.gov/endf-b7.1/zips/ENDF-B-VII.1-neutrons.zip",
            "t_url": "https://www.nndc.bnl.gov/endf-b7.1/zips/ENDF-B-VII.1-thermal_scatt.zip"
        },
    }

def reporthook(blocknum, blocksize, totalsize):
    """Progress Bar."""
    readsofar = blocknum * blocksize
    if totalsize > 0:
        percent = readsofar * 100 / totalsize
        s = "\r%5.1f%% %*d / %d" % (
            percent, len(str(totalsize)), readsofar, totalsize)
        sys.stderr.write(s)
        if readsofar >= totalsize:
            sys.stderr.write("\n")
    else:
        sys.stderr.write("read %d\n" % (readsofar,))

def select_library():
    """Displays menu and returns selected URLs."""
    print(f"\n{Fore.CYAN}--- Select Nuclear Data Library ---{Style.RESET_ALL}")
    
    for key, lib in Config.LIBRARIES.items():
        print(f"{Fore.GREEN}[{key}]{Style.RESET_ALL} {lib['name']}")
    print(f"{Fore.YELLOW}[C]{Style.RESET_ALL} Custom URL (Manual Input)")
    
    choice = input("\nSelect Option: ").strip().upper()
    
    if choice in Config.LIBRARIES:
        selected = Config.LIBRARIES[choice]
        print(f"\n{Fore.CYAN}Selected: {selected['name']}{Style.RESET_ALL}")
        return selected['n_url'], selected['t_url']
    
    elif choice == 'C':
        print(f"\n{Fore.YELLOW}--- Manual Input ---{Style.RESET_ALL}")
        n_url = input("Enter Incident Neutron URL (zip/tar.gz): ").strip()
        t_url = input("Enter Thermal Scattering URL (zip/tar.gz): ").strip()
        return n_url, t_url
    
    else:
        print(f"{Fore.RED}Invalid selection. Defaulting to ENDF/B-VIII.1{Style.RESET_ALL}")
        return Config.LIBRARIES["1"]['n_url'], Config.LIBRARIES["1"]['t_url']

def download_file(url):
    """Downloads file if not exists, returns local path."""
    if not url: return None
    
    filename = url.split('/')[-1]
    local_path = Config.DATA_DIR / filename
    
    if local_path.exists():
        print(f"{Fore.YELLOW}[CACHE] File '{filename}' already exists. Skipping download.{Style.RESET_ALL}")
        return local_path
    
    print(f"{Fore.BLUE}[DOWNLOADING] {filename}...{Style.RESET_ALL}")
    try:
        opener = urllib.request.build_opener()
        opener.addheaders = [('User-agent', 'Mozilla/5.0')]
        urllib.request.install_opener(opener)
        urllib.request.urlretrieve(url, local_path, reporthook)
        return local_path
    except Exception as e:
        print(f"{Fore.RED}[ERROR] Download failed: {e}{Style.RESET_ALL}")
        return None

def extract_and_organize(archive_path, target_folder_name):
    """Extracts, organizes, AND CLEANS UP."""
    if not archive_path: return

    final_path = Config.DATA_DIR / target_folder_name
    
    # 1. Clean existing target
    if final_path.exists() and any(final_path.iterdir()):
        print(f"{Fore.YELLOW}[INFO] '{target_folder_name}' exists. Replacing...{Style.RESET_ALL}")
        try:
            shutil.rmtree(final_path)
        except: pass

    # 2. Extract to temp
    print(f"{Fore.BLUE}[EXTRACTING] Processing archive...{Style.RESET_ALL}")
    temp_extract_dir = Config.DATA_DIR / "temp_extract"
    if temp_extract_dir.exists(): shutil.rmtree(temp_extract_dir)
    temp_extract_dir.mkdir()

    try:
        if str(archive_path).endswith('.tar.gz') or str(archive_path).endswith('.tgz'):
            with tarfile.open(archive_path, "r:gz") as tar:
                tar.extractall(temp_extract_dir)
        else:
            with zipfile.ZipFile(archive_path, 'r') as zip_ref:
                zip_ref.extractall(temp_extract_dir)
        
        # 3. Find correct subfolder
        search_keyword = ""
        if "neutron" in target_folder_name: search_keyword = "neutron"
        elif "thermal" in target_folder_name: search_keyword = "thermal"
        
        found_dir = None
        for root, dirs, files in os.walk(temp_extract_dir):
            for d in dirs:
                if search_keyword in d.lower():
                    found_dir = Path(root) / d
                    break
            if found_dir: break
        
        if not found_dir:
            items = list(temp_extract_dir.iterdir())
            if len(items) == 1 and items[0].is_dir():
                found_dir = items[0]
            else:
                found_dir = temp_extract_dir

        print(f"{Fore.BLUE}[INSTALLING] Moving '{found_dir.name}' to data/{target_folder_name}...{Style.RESET_ALL}")
        shutil.move(str(found_dir), str(final_path))
        
        # 4. CLEANUP (Temp folder + Original Archive)
        if temp_extract_dir.exists(): shutil.rmtree(temp_extract_dir)
        
        if archive_path.exists():
            os.remove(archive_path)
            print(f"{Fore.YELLOW}[CLEANUP] Deleted archive: {archive_path.name}{Style.RESET_ALL}")

        print(f"{Fore.GREEN}[SUCCESS] Setup complete for {target_folder_name}.{Style.RESET_ALL}")

    except Exception as e:
        print(f"{Fore.RED}[ERROR] Extraction/Cleanup failed: {e}{Style.RESET_ALL}")

def main():
    print(f"\n{Fore.CYAN}{'='*60}")
    print(f"{Fore.BLUE}{Style.BRIGHT}{'NUCLEAR DATA LIBRARY MANAGER'.center(60)}")
    print(f"{Fore.CYAN}{'='*60}{Style.RESET_ALL}")

    Config.DATA_DIR.mkdir(parents=True, exist_ok=True)

    n_url, t_url = select_library()

    print(f"\n{Fore.MAGENTA}{'-'*60}{Style.RESET_ALL}")
    archive_n = download_file(n_url)
    extract_and_organize(archive_n, Config.NEUTRON_DIR_NAME)
    
    print(f"\n{Fore.MAGENTA}{'-'*60}{Style.RESET_ALL}")
    archive_t = download_file(t_url)
    extract_and_organize(archive_t, Config.THERMAL_DIR_NAME)

    print(f"\n{Fore.CYAN}{'='*60}")
    print(f"{Fore.GREEN}Library Setup Complete & Workspace Cleaned.{Style.RESET_ALL}")
    print(f"Neutron Data: {Config.DATA_DIR / Config.NEUTRON_DIR_NAME}")
    print(f"Thermal Data: {Config.DATA_DIR / Config.THERMAL_DIR_NAME}")

if __name__ == "__main__":
    main()