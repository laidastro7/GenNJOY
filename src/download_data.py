import os
import shutil
import urllib.request
import zipfile
import ssl
from pathlib import Path
from colorama import Fore, Style, init

# Initialize colorama
init(autoreset=True)

class Config:
    BASE_DIR = Path.cwd().resolve()
    DATA_DIR = BASE_DIR / "data"
    
    # Target Directories
    NEUTRON_DIR = DATA_DIR / "incident_neutron_endf"
    THERMAL_DIR = DATA_DIR / "thermal_scattering_endf"
    
    # Official NNDC URLs (ENDF/B-VIII.0)
    URL_NEUTRONS = "https://www.nndc.bnl.gov/endf-b8.0/zips/ENDF-B-VIII.0_neutrons.zip"
    URL_THERMAL  = "https://www.nndc.bnl.gov/endf-b8.0/zips/ENDF-B-VIII.0_thermal_scatt.zip"

class Downloader:
    @staticmethod
    def show_progress(block_num, block_size, total_size):
        """Displays a professional progress bar."""
        downloaded = block_num * block_size
        if total_size > 0:
            percent = downloaded * 100 / total_size
            bar_length = 40
            filled_length = int(bar_length * percent // 100)
            bar = '█' * filled_length + '-' * (bar_length - filled_length)
            print(f"\r    Progress: |{bar}| {percent:.1f}% ", end='', flush=True)
        else:
            print(f"\r    Downloaded: {downloaded / (1024*1024):.1f} MB", end='', flush=True)

    @staticmethod
    def download_and_extract(url, destination, label):
        """Downloads a ZIP file and extracts it to the destination."""
        print(f"\n{Fore.GREEN}[INFO] Processing {label}...{Style.RESET_ALL}")
        
        # Check if already exists
        if any(destination.iterdir()):
            print(f"       Target directory is not empty: {destination.name}")
            print(f"{Fore.YELLOW}       [SKIP] Assuming data is already present.{Style.RESET_ALL}")
            return

        zip_path = destination / "temp_download.zip"
        
        # 1. Download
        print(f"       Source: NNDC (Brookhaven National Lab)")
        print(f"       Downloading package...")
        
        # Bypass SSL context if needed (safe for NNDC public data)
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        
        try:
            with urllib.request.urlopen(url, context=ctx) as response, open(zip_path, 'wb') as out_file:
                total_size = int(response.getheader('Content-Length').strip())
                downloaded = 0
                block_size = 1024 * 8
                
                while True:
                    chunk = response.read(block_size)
                    if not chunk: break
                    out_file.write(chunk)
                    downloaded += len(chunk)
                    Downloader.show_progress(downloaded // block_size, block_size, total_size)
            print() # Newline after progress bar

        except Exception as e:
            print(f"\n{Fore.RED}[ERROR] Download failed: {e}{Style.RESET_ALL}")
            if zip_path.exists(): zip_path.unlink()
            return

        # 2. Extract
        print(f"       Extracting archive...")
        try:
            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                zip_ref.extractall(destination)
            
            # Clean up zip
            zip_path.unlink()
            
            # 3. Flatten Directory Structure
            # NNDC zips often extract into a subfolder (e.g., 'neutrons/'). We want files directly in 'destination'.
            Downloader.flatten_directory(destination)
            
            print(f"{Fore.GREEN}[SUCCESS] {label} ready.{Style.RESET_ALL}")
            
        except zipfile.BadZipFile:
            print(f"{Fore.RED}[ERROR] Downloaded file is corrupted.{Style.RESET_ALL}")

    @staticmethod
    def flatten_directory(base_dir):
        """Moves all files from subdirectories to the base directory."""
        for root, dirs, files in os.walk(base_dir):
            if Path(root) == base_dir:
                continue
            for file in files:
                src = Path(root) / file
                dst = base_dir / file
                if not dst.exists():
                    shutil.move(str(src), str(dst))
        
        # Remove empty directories
        for root, dirs, files in os.walk(base_dir, topdown=False):
            for name in dirs:
                p = Path(root) / name
                try:
                    p.rmdir()
                except OSError:
                    pass # Directory not empty

def main():
    print(f"\n{Fore.CYAN}{'='*60}")
    print(f"{Fore.BLUE}{Style.BRIGHT}{'NUCLEAR DATA ACQUISITION SYSTEM (NNDC DIRECT)'.center(60)}")
    print(f"{Fore.CYAN}{'='*60}{Style.RESET_ALL}")
    
    # Ensure directories exist
    if not Config.DATA_DIR.exists(): Config.DATA_DIR.mkdir()
    if not Config.NEUTRON_DIR.exists(): Config.NEUTRON_DIR.mkdir()
    if not Config.THERMAL_DIR.exists(): Config.THERMAL_DIR.mkdir()

    # 1. Download Neutrons
    Downloader.download_and_extract(
        Config.URL_NEUTRONS, 
        Config.NEUTRON_DIR, 
        "Incident Neutron Data (ENDF/B-VIII.0)"
    )

    # 2. Download Thermal
    Downloader.download_and_extract(
        Config.URL_THERMAL, 
        Config.THERMAL_DIR, 
        "Thermal Scattering Data (ENDF/B-VIII.0)"
    )

    print(f"\n{Fore.CYAN}{'='*60}{Style.RESET_ALL}")
    print("Process Complete.")
    print(f"Neutron Location: {Config.NEUTRON_DIR}")
    print(f"Thermal Location: {Config.THERMAL_DIR}")

if __name__ == "__main__":
    main()