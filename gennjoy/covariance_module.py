import re
import shutil
import subprocess
from pathlib import Path
from colorama import Fore, init
import os

init(autoreset=True)

def get_mat_from_njoy_deck(base_dir, iso):
    """
    Lire MAT à partir de GenNJOY/gennjoy/data/njoy_input_decks/<iso>.njoy.
    """
    deck_path = Path(base_dir) / "data" / "njoy_input_decks" / f"{iso}.njoy"
    if not deck_path.exists():
        return None

    try:
        lines = deck_path.read_text(encoding="utf-8", errors="ignore").splitlines()
        in_reconr = False
        for line in lines:
            s = line.strip().lower()
            if s.startswith("reconr"):
                in_reconr = True
                continue
            if in_reconr:
                if s.startswith("'"):
                    continue
                m = re.search(r"^\s*(\d+)\s+\d+\s*/", line)
                if m:
                    return int(m.group(1))
                if (not s) or ("/" in s and "err" in s):
                    in_reconr = False
    except Exception:
        return None
    return None

def get_mat_number(endf_file_path, base_dir, iso):
    mat = get_mat_from_njoy_deck(base_dir, iso)
    if mat is not None:
        return mat
    try:
        with open(endf_file_path, "r", encoding="utf-8", errors="ignore") as f:
            first_line = f.readline()
        field = first_line[66:70].strip()
        if field.isdigit():
            return int(field)
    except Exception:
        pass
    return None

def parse_covariance_batch(filepath):
    jobs = []
    filepath = Path(filepath)
    if not filepath.exists():
        return jobs
    with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            matches = re.findall(r"(\w+)\s*=\s*([^\s]+)", line)
            entry = {k: v for k, v in matches}
            if "element_n" in entry and "name" in entry and "temperatures" in entry:
                try:
                    entry["temperatures"] = float(entry["temperatures"])
                    jobs.append(entry)
                except ValueError:
                    pass
    return jobs

def find_pendf_file(pendf_dir: Path, iso: str):
    if not pendf_dir.exists():
        return None
    preferred = pendf_dir / f"{iso}_reconr.pendf"
    if preferred.exists():
        return preferred
    candidates = list(pendf_dir.glob("*.pendf"))
    if candidates:
        return candidates[0]
    candidates = [p for p in pendf_dir.iterdir() if p.is_file() and "pendf" in p.name.lower()]
    if candidates:
        return candidates[0]
    tape21 = pendf_dir / "tape21"
    if tape21.exists():
        return tape21
    return None

def build_covariance_input(mat_number, temp, generate_plots=False):
    """
    Génère l'input NJOY en mode binaire (tapes négatives).
    -33 : stockage intermédiaire des covariances.
    -34 : sortie finale au format COVERX binaire.
    """
    ign = 19 
    
    content = (
        "errorr\n"
        "20 21 0 33 /\n"      # Sortie vers tape binaire 33
        f"{mat_number} {ign} 4 1 /\n"
        f"0 {temp} /\n"
        "0 /\n"                # <-- CORRECTION : Juste '0 /' pour arrêter errorr
        "covr\n"
        "33 34 35 /\n"       # Lit le binaire -33, écrit le binaire -34
        "1 /\n"
        "/\n"
        "/\n"
        f"{mat_number} /\n"    # Fin de covr
    )

    # Note : viewr utilise TOUJOURS des tapes positives (35, 36) car c'est du texte/PostScript
    if generate_plots:
        content += (
            "viewr\n"
            "35 36 /\n"
        )

    content += "stop\n"
    return content


def copy_existing_tapes(work_dir: Path, cov_dir: Path, name: str):
    for tape_file in sorted(work_dir.glob("tape*")):
        if tape_file.is_file():
            shutil.copy(tape_file, cov_dir / f"{name}_{tape_file.name}")

def run_errorr_covr(
    njoy_exec,
    endf_path,
    pendf_path,
    cov_dir,
    plots_dir,
    name,
    mat_number,
    temp,
    generate_plots=False,
    execute_njoy=True,
):
    cov_dir = Path(cov_dir)
    plots_dir = Path(plots_dir)

    work_dir = cov_dir / f"{name}_work"
    work_dir.mkdir(parents=True, exist_ok=True)

    input_content = build_covariance_input(mat_number, temp, generate_plots)

    print(Fore.CYAN + f" -> Workdir : {work_dir}")

    try:
        shutil.copy(endf_path, work_dir / "tape20")
        shutil.copy(pendf_path, work_dir / "tape21")

        njoy_inp = work_dir / "input.njoy"
        njoy_out = work_dir / "output.njoy"

        with open(njoy_inp, "w", encoding="utf-8") as f:
            f.write(input_content)

        shutil.copy(njoy_inp, cov_dir / f"{name}_cov.inp")
        print(Fore.GREEN + f" [OK] Input NJOY généré : {cov_dir / f'{name}_cov.inp'}")

        if not execute_njoy:
            copy_existing_tapes(work_dir, cov_dir, name)
            return True

        print(Fore.CYAN + f" -> Running NJOY : {name} MAT={mat_number} T={temp} K")

        with open(njoy_inp, "r", encoding="utf-8") as stdin_f, \
             open(njoy_out, "w", encoding="utf-8") as stdout_f:
            subprocess.run(
                [njoy_exec],
                stdin=stdin_f,
                stdout=stdout_f,
                stderr=subprocess.STDOUT,
                check=True,
                cwd=work_dir,
            )

        shutil.copy(njoy_out, cov_dir / f"{name}_cov.out")
        
        # --- Copie des fichiers finaux ---
        if (work_dir / "tape34").exists():
            shutil.copy(work_dir / "tape34", cov_dir / f"{name}.coverx")
            print(Fore.GREEN + f" [OK] Matrice COVERX générée : {cov_dir / f'{name}.coverx'}")

        if generate_plots and (work_dir / "tape36").exists():
            plots_dir.mkdir(parents=True, exist_ok=True)
            plot_file = plots_dir / f"{name}_plot.ps"
            shutil.copy(work_dir / "tape36", plot_file)
            print(Fore.GREEN + f" [OK] Graphique viewr généré : {plot_file}")

        print(Fore.GREEN + f" [OK] {name} : Traitement terminé avec succès.")
        
        # --- Nettoyage du dossier temporaire après succès ---
        shutil.rmtree(work_dir)
        print(Fore.MAGENTA + f" [CLEANUP] Fichiers temporaires supprimés pour {name}.")
        
        return True

    except subprocess.CalledProcessError as e:
        # --- 1. Affichage de l'erreur NJOY ---
        if (work_dir / "output.njoy").exists():
            shutil.copy(work_dir / "output.njoy", cov_dir / f"{name}_cov.out")
            print(Fore.RED + f"\n [ERROR] NJOY a échoué pour {name} (exit code {e.returncode})")
            print(Fore.YELLOW + " --- Raison de l'erreur (extraite de NJOY) ---")
            try:
                with open(work_dir / "output.njoy", "r", encoding="utf-8") as out_f:
                    lines = out_f.readlines()
                    for line in lines[-20:]:
                        if line.strip():
                            print(Fore.YELLOW + "    " + line.strip())
            except Exception:
                pass
            print(Fore.YELLOW + " -----------------------------------------------\n")
        else:
            print(Fore.RED + f" [ERROR] NJOY failed for {name} (exit code {e.returncode})")

        # --- 2. SAUVETAGE DU FICHIER COVERX (Salvage) ---
        if (work_dir / "tape34").exists():
            shutil.copy(work_dir / "tape34", cov_dir / f"{name}.coverx")
            print(Fore.GREEN + f" [SALVAGE] Matrice COVERX récupérée avec succès : {cov_dir / f'{name}.coverx'}")

        # En cas d'erreur, on garde le dossier work pour déboguer
        copy_existing_tapes(work_dir, cov_dir, name)
        return False

def process_covariance_batch(
    base_dir,
    njoy_exec=None,
    input_file="inputs/covariance_process_batch.i",
    execute_njoy=True,
    generate_plots=True,
):
    if execute_njoy and (not njoy_exec or not os.path.isfile(njoy_exec)):
        print(Fore.RED + f" [ERROR] Chemin njoy_exec '{njoy_exec}' invalide.")
        return

    base_path = Path(base_dir).resolve()
    batch_file = (base_path / input_file).resolve()
    endf_dir = base_path / "data" / "incident_neutron_endf"
    pendf_root = base_path / "data" / "njoy_tapes"
    cov_out_dir = base_path / "data" / "covariance_matrices"
    plots_out_dir = base_path / "data" / "covariance_plots"

    cov_out_dir.mkdir(parents=True, exist_ok=True)
    if generate_plots:
        plots_out_dir.mkdir(parents=True, exist_ok=True)

    jobs = parse_covariance_batch(batch_file)
    if not jobs:
        print(Fore.RED + f"Aucune entrée valide dans : {batch_file}")
        return

    for job in jobs:
        iso = job["name"]
        temperature = job["temperatures"]
        endf_file = endf_dir / job["element_n"]
        iso_dir = pendf_root / iso
        pendf_file = find_pendf_file(iso_dir, iso)

        print(Fore.CYAN + f"\n[PROCESS] isotope={iso}  T={temperature} K")

        if not endf_file.exists():
            print(Fore.YELLOW + f" [SKIP] ENDF introuvable -> {endf_file}")
            continue
        if pendf_file is None:
            print(Fore.YELLOW + f" [SKIP] PENDF introuvable dans -> {iso_dir}")
            continue

        mat = get_mat_number(endf_file_path=endf_file, base_dir=base_path, iso=iso)
        if mat is None:
            print(Fore.YELLOW + f" [SKIP] Impossible de déterminer MAT.")
            continue

        # Optionnel: Désactivation de viewr pour les isotopes qui font crasher les graphiques
        plot_pour_cet_isotope = generate_plots
        if mat in [125, 525] or iso.upper() in ["H1", "B10"]:
            if generate_plots:
                print(Fore.YELLOW + f" [INFO] {iso} : Standard détecté (MAT {mat}). Désactivation de viewr pour éviter le crash.")
                plot_pour_cet_isotope = False

        run_errorr_covr(
            njoy_exec=njoy_exec,
            endf_path=endf_file,
            pendf_path=pendf_file,
            cov_dir=cov_out_dir,
            plots_dir=plots_out_dir,
            name=iso,
            mat_number=mat,
            temp=temperature,
            generate_plots=plot_pour_cet_isotope,
            execute_njoy=execute_njoy,
        )

if __name__ == "__main__":
    process_covariance_batch(
        base_dir="/mnt/d/work_ubuntu/GenNJOY/gennjoy",
        njoy_exec="/chemin/vers/njoy",  # N'oubliez pas de mettre votre chemin vers l'exécutable
        input_file="inputs/covariance_process_batch.i",
        execute_njoy=True,
        generate_plots=True,  # Graphiques désactivés pour que l'O-16 et le B-10 se terminent proprement !
    )