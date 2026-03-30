import sys
import shutil
import time
import os
import re
import subprocess
from pathlib import Path
from multiprocessing import Process, cpu_count, Lock
from typing import List
from colorama import Fore, Style, init

init(autoreset=True)

# ==========================================
# 1. Path Settings (Config & Logger)
# ==========================================
class Config:
    BASE_DIR = Path(__file__).resolve().parent
    INPUTS_DIR = BASE_DIR / "inputs"
    OUTPUT_BASE = BASE_DIR / "data"
    OUTPUT_COV = OUTPUT_BASE / "covariance_matrices"
    OUTPUT_PLOTS = OUTPUT_BASE / "covariance_plots"
    ENDF_DIR = OUTPUT_BASE / "incident_neutron_endf"
    
    GROUPS_FILE = INPUTS_DIR / "groups.i"
    FLUX_FILE = INPUTS_DIR / "flux.i"

class Logger:
    # Define the path and filename for the log file
    LOG_FILE = Config.BASE_DIR / "execution_njoy.log"

    @classmethod
    def _write_to_file(cls, msg):
        """Internal helper: write clean text (without color codes) to the file."""
        try:
            with open(cls.LOG_FILE, "a", encoding="utf-8") as f:
                f.write(msg + "\n")
        except Exception:
            pass

    @staticmethod
    def info(msg):  
        print(f"{Fore.GREEN}[INFO] {msg}{Style.RESET_ALL}")
        Logger._write_to_file(f"[INFO] {msg}")
        
    @staticmethod
    def debug(msg): 
        print(f"{Fore.CYAN}[DEBUG] {msg}{Style.RESET_ALL}")
        Logger._write_to_file(f"[DEBUG] {msg}")
        
    @staticmethod
    def warn(msg):  
        print(f"{Fore.YELLOW}[WARN] {msg}{Style.RESET_ALL}")
        Logger._write_to_file(f"[WARN] {msg}")
        
    @staticmethod
    def error(msg): 
        print(f"{Fore.RED}[ERROR] {msg}{Style.RESET_ALL}")
        Logger._write_to_file(f"[ERROR] {msg}")
        
    @staticmethod
    def header(msg):
        print(f"\n{Fore.MAGENTA}{'='*60}")
        print(f"{Fore.BLUE}{Style.BRIGHT}{msg.center(60)}")
        print(f"{Fore.MAGENTA}{'='*60}{Style.RESET_ALL}")
        # Write the header into the log file
        Logger._write_to_file(f"\n{'='*60}\n{msg.center(60)}\n{'='*60}")

# ==========================================
# 2. Data processing and parsing helper functions
# ==========================================
def get_mat_number(endf_file_path):
    try:
        with open(endf_file_path, "r", encoding="utf-8", errors="ignore") as f:
            for line in f:
                if len(line) >= 75:
                    mat_str = line[66:70].strip()
                    mf_str = line[70:72].strip()
                    mt_str = line[72:75].strip()
                    if mf_str == '1' and mt_str == '451' and mat_str.isdigit():
                        return int(mat_str)
    except Exception: pass
    return None

def has_urr_data(endf_file_path):
    try:
        with open(endf_file_path, 'r', encoding="utf-8", errors='ignore') as f:
            for line in f:
                if len(line) >= 75:
                    mf = line[70:72].strip()
                    mt = line[72:75].strip()
                    if mf == '2' and mt == '151':
                        el_str = line[0:11]
                        eh_str = line[11:22]
                        lru_str = line[22:33].strip()
                        if '.' in el_str and '.' in eh_str and lru_str == '2':
                            return True
    except Exception: pass
    return False

def get_covariance_mts(endf_file_path):
    mts = set()
    try:
        with open(endf_file_path, 'r', encoding="utf-8", errors='ignore') as f:
            for line in f:
                if len(line) >= 75:
                    mf_str = line[70:72].strip()
                    mt_str = line[72:75].strip()
                    if mf_str == '33' and mt_str.isdigit():
                        mt = int(mt_str)
                        if mt != 451:
                            mts.add(mt)
    except Exception: pass
    return sorted(list(mts))

def parse_covariance_batch(filepath):
    jobs = []
    filepath = Path(filepath)
    if not filepath.exists(): return jobs
    with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"): continue
            matches = re.findall(r"(\w+)\s*=\s*([^\s]+)", line)
            entry = {k: v for k, v in matches}
            if "element_n" in entry and "name" in entry and "temperatures" in entry:
                try:
                    entry["temperatures"] = float(entry["temperatures"])
                    jobs.append(entry)
                except ValueError: pass
    return jobs

# ==========================================
# 3. Automatic formatting and NJOY input construction
# ==========================================
def format_groups_for_njoy(groups_text):
    if '/' in groups_text: return groups_text.strip() + "\n"
    tokens = groups_text.split()
    if not tokens: return ""
    ngn = len(tokens) - 1
    return f" {ngn} /\n " + " ".join(tokens) + " /\n"

def format_flux_for_njoy(flux_text):
    if '/' in flux_text: return flux_text.strip() + "\n"
    lines = flux_text.strip().split('\n')
    pairs = [f" {p.split()[0]} {p.split()[1]}" for p in lines if len(p.split()) >= 2]
    np = len(pairs)
    if np == 0: return ""
    return f" 0.0 0.0 0 0 1 {np}\n {np} 2\n" + "\n".join(pairs) + "\n /\n"

def build_covariance_input(mat_number, temp, ign_val, iwt_val, groups_text, flux_text, cov_mts, generate_plots=False, has_urr=False):
    content = (
        "-- RECONR : Pointwise cross section reconstruction\n"
        "reconr\n"
        " 20 21 /\n"
        " 'PENDF generated for Covariance' /\n"
        f" {mat_number} 0 0 /\n"
        " 0.001 0.0 /\n"
        " 0 /\n"
        
        f"\n-- BROADR : Doppler broadening to {temp} K\n"
        "broadr\n"
        " 20 21 22 /\n"
        f" {mat_number} 1 0 0 0 /\n"
        " 0.001 /\n"
        f" {temp} /\n"
        " 0 /\n"
    )
    
    current_tape = 22
    
    content += (
        "\n-- HEATR : Kinematic limits and KERMA factors\n"
        "heatr\n"
        f" 20 {current_tape} {current_tape+1} /\n"
        f" {mat_number} 0 0 0 1 0 /\n"
        "\n-- HEATR : Total KERMA and damage energy production\n"
        "heatr\n"
        f" 20 {current_tape+1} {current_tape+2} /\n"
        f" {mat_number} 0 0 0 0 0 /\n"
        "\n-- GASPR : Gas production cross sections\n"
        "gaspr\n"
        f" 20 {current_tape+2} {current_tape+3} /\n"
    )
    current_tape += 3
    
    if has_urr:
        content += (
            "\n-- UNRESR : Unresolved resonance treatment\n"
            "unresr\n"
            f" 20 {current_tape} {current_tape+1} /\n"
            f" {mat_number} 1 10 1 /\n"
            f" {temp} /\n"
            " 1.0e10 10000.0 1000.0 300.0 100.0 30.0 10.0 1.0 0.1 1.0e-5 /\n"
            " 0 /\n"
            "\n-- PURR : Probability tables for unresolved resonances\n"
            "purr\n"
            f" 20 {current_tape+1} {current_tape+2} /\n"
            f" {mat_number} 1 10 20 64 /\n"
            f" {temp} /\n"
            " 1.0e10 10000.0 1000.0 300.0 100.0 30.0 10.0 1.0 0.1 1.0e-5 /\n"
            " 0 /\n"
        )
        current_tape += 2

    gendf_tape = current_tape + 1

    content += (
        "\n-- GROUPR : Group constants generation\n"
        "groupr\n"
        f" 20 {current_tape} 0 {gendf_tape} /\n"
        f" {mat_number} {ign_val} 0 {iwt_val} 3 1 1 1 /\n"
        " 'GROUPR generated for Covariance' /\n"
        f" {temp} /\n"
        " 1.0e10 /\n"
    )
    
    if ign_val == 1 and groups_text: content += format_groups_for_njoy(groups_text)
    if iwt_val == 1 and flux_text: content += format_flux_for_njoy(flux_text)
    elif iwt_val == 4: content += " 0.1 0.025 820.3e3 1.4e6 /\n"
        
    content += " 3 /\n 0 /\n 0 /\n"

    content += (
        "\n-- ERRORR : Covariance matrix generation\n"
        "errorr\n"
        f" 20 {current_tape} {gendf_tape} 33 0 0 /\n"
        f" {mat_number} {ign_val} {iwt_val} 1 1 /\n"
        f" 1 {temp} /\n"
        " 0 33 1 1 -1 0.0 0.0 /\n"
    )
    
    if ign_val == 1 and groups_text: content += format_groups_for_njoy(groups_text)
    if iwt_val == 1 and flux_text: content += format_flux_for_njoy(flux_text)
    elif iwt_val == 4: content += " 0.1 0.025 820.3e3 1.4e6 /\n"

    if not cov_mts: cov_mts = [2, 102]
   # --- Dynamic COVR setup ---
    if not cov_mts: cov_mts = [2, 102]
    num_mts = len(cov_mts)
    
    # Generate lines so each reaction is listed on its own line
    mts_lines = "".join([f" {mat_number} {mt} {mat_number} {mt} /\n" for mt in cov_mts])

    content += (
        "\n-- COVR : Covariance matrix formatting and tracing\n"
        "covr\n"
        " 33 0 43 /\n"
        " 1 /\n"
        " /\n"
        f" {num_mts} {num_mts} /\n"
        f"{mts_lines}"
    )

    if generate_plots:
        content += (
            "\n-- VIEWR : Generate PostScript plot\n"
            "viewr\n"
            " 43 53 /\n"
        )

    content += "\nstop\n"
    return content

# ==========================================
# 4. Main processor (engine)
# ==========================================
class CovarianceProcessor:
    def __init__(self, input_file, njoy_cmd, cpu_limit, ign_val, iwt_val, groups_text, flux_text, generate_plots, job_mts_dict):
        self.input_file = input_file
        self.njoy_cmd = njoy_cmd
        self.cpu_limit = cpu_limit
        self.ign_val = ign_val
        self.iwt_val = iwt_val
        self.groups_text = groups_text
        self.flux_text = flux_text
        self.generate_plots = generate_plots
        self.job_mts_dict = job_mts_dict
        self.lock = Lock()
        self._setup_directories()

    def _setup_directories(self):
        Config.OUTPUT_COV.mkdir(parents=True, exist_ok=True)
        if self.generate_plots: Config.OUTPUT_PLOTS.mkdir(parents=True, exist_ok=True)

    def _process_isotope(self, job: dict):
        iso = job["name"]
        temperature = job["temperatures"]
        endf_file = Config.ENDF_DIR / job["element_n"]

        with self.lock: Logger.info(f"Processing Covariance: {iso} ({temperature} K)")

        if not endf_file.exists():
            with self.lock: Logger.warn(f"[{iso}] ENDF file missing: {endf_file}")
            return

        mat_number = get_mat_number(endf_file)
        if mat_number is None:
            with self.lock: Logger.error(f"[{iso}] Cannot determine MAT number.")
            return

        plot_active = self.generate_plots
        has_urr_val = has_urr_data(endf_file)
        cov_mts = self.job_mts_dict.get(iso, [2, 102])

        cov_dir = Config.OUTPUT_COV
        plots_dir = Config.OUTPUT_PLOTS
        work_dir = cov_dir / f"{iso}_work"
        work_dir.mkdir(parents=True, exist_ok=True)

        input_content = build_covariance_input(
            mat_number, temperature, self.ign_val, self.iwt_val, 
            self.groups_text, self.flux_text, cov_mts, plot_active, has_urr_val
        )
        
        try:
            shutil.copy(endf_file, work_dir / "tape20")
            njoy_inp = work_dir / "input.njoy"
            njoy_out = work_dir / "output.njoy"

            with open(njoy_inp, "w", encoding="utf-8") as f: f.write(input_content)

            with open(njoy_inp, "r", encoding="utf-8") as stdin_f, \
                 open(njoy_out, "w", encoding="utf-8") as stdout_f:
                subprocess.run([self.njoy_cmd], stdin=stdin_f, stdout=stdout_f,
                               stderr=subprocess.STDOUT, check=True, cwd=work_dir, timeout=3600)

            shutil.copy(njoy_out, cov_dir / f"{iso}_cov.out")
            shutil.copy(njoy_inp, cov_dir / f"{iso}_cov.in")
            
            if (work_dir / "tape33").exists():
                shutil.copy(work_dir / "tape33", cov_dir / f"{iso}.coverx")
                with self.lock: Logger.info(f"SUCCESS: {iso} COVERX Matrix generated.")

            if plot_active and (work_dir / "tape53").exists():
                plots_dir.mkdir(parents=True, exist_ok=True)
                ps_file = plots_dir / f"{iso}_plot.ps"
                pdf_file = plots_dir / f"{iso}_plot.pdf"
                shutil.copy(work_dir / "tape53", ps_file)
                try:
                    subprocess.run(["ps2pdf", str(ps_file), str(pdf_file)], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                    os.remove(ps_file)
                    with self.lock: Logger.info(f"SUCCESS: {iso} Plot saved as PDF.")
                except Exception:
                    with self.lock: Logger.warn(f"[{iso}] ps2pdf missing. Plot saved as PS instead.")

            shutil.rmtree(work_dir)

        except subprocess.TimeoutExpired:
            with self.lock: Logger.error(f"[{iso}] NJOY HUNG (Timeout Expired).")
        except subprocess.CalledProcessError as e:
            with self.lock: Logger.error(f"[{iso}] NJOY failed (exit code {e.returncode}).")
            if (work_dir / "output.njoy").exists():
                shutil.copy(work_dir / "output.njoy", cov_dir / f"{iso}_cov.out")
                shutil.copy(work_dir / "input.njoy", cov_dir / f"{iso}_cov.in")
            if (work_dir / "tape33").exists():
                shutil.copy(work_dir / "tape33", cov_dir / f"{iso}.coverx")
                with self.lock: Logger.warn(f"[{iso}] Salvaged COVERX Matrix despite error.")

    def _worker(self, jobs: List[dict]):
        for job in jobs: self._process_isotope(job)

    def execute(self):
        Logger.header("STARTING COVARIANCE PROCESSING")
        jobs = parse_covariance_batch(self.input_file)
        if not jobs:
            Logger.error("No valid entries found in the batch file!")
            return
        total_isotopes = len(jobs)
        Logger.info(f"Found {total_isotopes} isotopes to process.")
        
        procs = []
        effective_cpu = max(1, min(self.cpu_limit, total_isotopes))
        chunk_size = total_isotopes // effective_cpu + (1 if total_isotopes % effective_cpu else 0)
        
        for i in range(effective_cpu):
            start = i * chunk_size
            chunk = jobs[start : start + chunk_size]
            if not chunk: continue
            p = Process(target=self._worker, args=(chunk,))
            procs.append(p)
            p.start()
        
        for p in procs: p.join()
        Logger.header("PROCESSING FINISHED")
        print(f"Check matrices at: {Config.OUTPUT_COV}")

# ==========================================
# 5. Interactive interface (CLI)
# ==========================================
def run_interactive_covariance():
    start_time = time.time()
    
    default_batch = Config.INPUTS_DIR / "covariance_process_batch.i"
    try: display_batch_default = f"[Internal] {default_batch.relative_to(Config.BASE_DIR)}"
    except ValueError: display_batch_default = str(default_batch)

    print("-" * 50)
    batch_input = input(f"Please specify the NJOY covariance input file path (Default: {display_batch_default}): ").strip()
    input_file_path = Path(batch_input).resolve() if batch_input else default_batch

    if not input_file_path.exists():
        Logger.error(f"Batch file not found: {input_file_path}")
        sys.exit(1)
        
    print("-" * 50)
    use_groups = input("Read custom energy groups from inputs/groups.i? (y/n) [Default: y]: ").strip().lower()
    if use_groups != 'n':
        ign_val = 1
        if not Config.GROUPS_FILE.exists():
            Logger.error(f"Groups file not found: {Config.GROUPS_FILE}")
            sys.exit(1)
        groups_text = Config.GROUPS_FILE.read_text(encoding="utf-8")
        Logger.info("Custom energy groups (ign=1) loaded.")
    else:
        ign_val = 19
        groups_text = ""
        Logger.info("Default NJOY energy groups (ign=19) selected.")

    print("-" * 50)
    print("[*] Select Weighting Spectrum (iwt):")
    print("    1 = External flux from 'flux.i'")
    print("    2 = Constant")
    print("    3 = 1/E (Standard)")
    print("    4 = 1/E + Fission Spectrum")
    iwt_input = input("[?] Enter option [Default: 3]: ").strip()
    
    iwt_val = int(iwt_input) if iwt_input in ['1', '2', '3', '4'] else 3
    flux_text = ""
    
    if iwt_val == 1:
        if not Config.FLUX_FILE.exists():
            Logger.error(f"Flux file not found: {Config.FLUX_FILE}")
            sys.exit(1)
        flux_text = Config.FLUX_FILE.read_text(encoding="utf-8")
        Logger.info("External energy spectrum loaded.")
    else:
        Logger.info(f"Weight function iwt={iwt_val} selected.")

    sys_path = shutil.which("njoy")
    default_njoy = sys_path if sys_path else "njoy"
    print("-" * 50)
    njoy_input = input(f"Enter NJOY command/path (Default: {default_njoy}): ").strip()
    njoy_cmd = njoy_input if njoy_input else default_njoy

    default_nd_path = Config.BASE_DIR / "data" / "incident_neutron_endf"
    try: display_default = f"[Internal] {default_nd_path.relative_to(Config.BASE_DIR)}"
    except ValueError: display_default = str(default_nd_path)

    print("-" * 50)
    nd_input = input(f"Enter path to incident neutron data (Default: {display_default}): ").strip()
    abs_nd_path = Path(nd_input).resolve() if nd_input else default_nd_path
        
    if not abs_nd_path.exists():
        Logger.error(f"Nuclear data path not found: {abs_nd_path}")
        sys.exit(1)
    Config.ENDF_DIR = abs_nd_path 

    # --- Extract reactions ---
    jobs = parse_covariance_batch(input_file_path)
    print("-" * 50)
    print("[*] Select Reactions (MT) for COVR plots:")
    print("    1 = Auto-plot ALL available MTs in the ENDF file (MF=33)")
    print("    2 = Standard important MTs only (1, 2, 4, 16, 18, 102) if available")
    print("    3 = Manual selection for each isotope")
    mt_option = input("[?] Enter option [Default: 1]: ").strip()
    
    job_mts_dict = {}
    for job in jobs:
        iso_name = job["name"]
        endf_file = Config.ENDF_DIR / job["element_n"]
        avail_mts = get_covariance_mts(endf_file)
        
        if mt_option == '2':
            job_mts_dict[iso_name] = [m for m in [1, 2, 4, 16, 18, 102] if m in avail_mts] or [2, 102]
        elif mt_option == '3':
            print(f"\n[*] {iso_name} | Available MTs: {avail_mts}")
            # Change the prompt to request comma-separated input
            user_mts = input("    Enter MTs separated by comma (Enter for all): ").strip()
            # Use replace(',', ' ') so commas are accepted flexibly
            job_mts_dict[iso_name] = [int(x) for x in user_mts.replace(',', ' ').split() if x.isdigit()] if user_mts else avail_mts
        else:
            job_mts_dict[iso_name] = avail_mts if avail_mts else [2, 102]

    total_cores = cpu_count()
    print("-" * 50)
    cpu_input = input(f"Enter CPUs to use (Default: {total_cores}): ").strip()
    cpu_limit = max(1, int(cpu_input)) if cpu_input.isdigit() else total_cores

    print("-" * 50)
    plot_input = input("Generate Viewr plots? (y/n) [Default: y]: ").strip().lower()
    generate_plots = False if plot_input == 'n' else True
    
    processor = CovarianceProcessor(
        input_file_path, njoy_cmd, cpu_limit, 
        ign_val, iwt_val, groups_text, flux_text, generate_plots, job_mts_dict
    )
    processor.execute()
    
    elapsed = time.time() - start_time
    print(f"\n{Fore.GREEN}Total Time: {time.strftime('%Hh:%Mm:%Ss', time.gmtime(elapsed))}")

if __name__ == "__main__":
    run_interactive_covariance()
