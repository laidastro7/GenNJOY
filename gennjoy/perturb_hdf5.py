import os
import numpy as np

try:
    from gennjoy import fission_perturbation as fp
    from gennjoy import perturbation as P
except ImportError:  # running as a script from the package folder
    import fission_perturbation as fp
    import perturbation as P

def create_perturbed_library():
    print("\n" + "="*60)
    print(" 🛠️  GenNJOY Exact Perturbation Module (Feature 7)")
    print("="*60)
    
    try:
        import openmc.data
    except ImportError:
        print("[-] Error: OpenMC library is required for accurate HDF5 parsing.")
        print("    Please ensure your OpenMC environment is activated.")
        return

    base_dir = os.path.dirname(os.path.abspath(__file__))
    
    # =========================================================
    # 1. Confirm or change the default library directory path
    # =========================================================
    default_hdf5_dir = os.path.join(base_dir, 'data', 'hdf5_library')
    print(f"\n[?] Default HDF5 library directory:\n    {default_hdf5_dir}")
    custom_dir = input("    Press [Enter] to use default, or type a custom path: ").strip()
    
    hdf5_dir = custom_dir if custom_dir else default_hdf5_dir
    
    if not os.path.exists(hdf5_dir):
        print(f"[-] Error: The directory '{hdf5_dir}' does not exist.")
        return

    pert_dir = os.path.join(base_dir, 'data', 'hdf5_perturbed_library')
    os.makedirs(pert_dir, exist_ok=True)
    
    orig_xml = os.path.join(hdf5_dir, 'cross_sections.xml')

    # =========================================================
    # 2. Read and display available isotopes
    # =========================================================
    try:
        available_files = [f for f in os.listdir(hdf5_dir) if f.endswith('.h5')]
        available_isotopes = sorted([os.path.splitext(f)[0] for f in available_files])
    except Exception as e:
        print(f"[-] Error reading directory: {e}")
        return
        
    if not available_isotopes:
        print(f"[-] Error: No HDF5 (.h5) isotope files found in {hdf5_dir}.")
        return
        
    print("\n[*] Available Isotopes:")
    formatted_list = ", ".join(available_isotopes)
    print(f"    [ {formatted_list} ]")

    isotope = input("\n[?] Enter the target isotope from the list above: ").strip()
    orig_h5 = os.path.join(hdf5_dir, f"{isotope}.h5")
    
    if not os.path.exists(orig_h5):
        print(f"[-] Error: Library for '{isotope}' not found.")
        return

    if isotope.startswith('c_') and ('_in_' in isotope):
        print(f"[-] Error: '{isotope}' is a Thermal Scattering library, not an incident neutron library.")
        print("    Perturbation is currently supported for incident neutron libraries only.")
        return

    # =========================================================
    # 3. Load isotope and list the reactions that can be perturbed
    # =========================================================
    print(f"\n[*] Scanning {isotope} for available neutron reactions via OpenMC Engine...")
    try:
        nuc_test = openmc.data.IncidentNeutron.from_hdf5(orig_h5)
    except Exception as e:
        print(f"[-] Failed to load {orig_h5}: {e}")
        return

    options = P.perturbable_mts(nuc_test)
    print("-" * 70)
    print(f" Reactions of {isotope} that can be perturbed (data used by OpenMC in transport):")
    print("-" * 70)
    for mt, comps in options.items():
        name = P.REACTION_LABELS.get(mt, fp.NU_MTS.get(mt, "reaction"))
        if comps == [mt]:
            acts = "" if mt not in (fp.CHI_MT,) else " (outgoing energy, renormalised)"
        else:
            acts = f" -> applied to MT {_compact(comps)}"
        red = " [redundant sum]" if mt in nuc_test.reactions and nuc_test.reactions[mt].redundant else ""
        print(f"    MT = {mt:<5} | {name}{red}{acts}")
    print("-" * 70)
    valid_mts = list(options)

    # =========================================================
    # 4. Multiple MT Input & Perturbation Percentage
    # =========================================================
    while True:
        try:
            mt_input = input("\n[?] Enter the MT numbers separated by commas (e.g., 2, 4, 18, 102): ").strip()
            mt_numbers = [int(x.strip()) for x in mt_input.split(',') if x.strip()]
            if not mt_numbers:
                print("[-] Please enter at least one MT number.")
                continue
            invalid_mts = [mt for mt in mt_numbers if mt not in valid_mts]
            if invalid_mts:
                print(f"[-] Error: The following MT numbers cannot be perturbed: {invalid_mts}")
                continue
            break
        except ValueError:
            print("[-] Invalid format. Please enter valid integers separated by commas.")

    while True:
        try:
            pert_percent = float(input("[?] Enter the perturbation percentage (e.g., 1.0 for +1%, -1.5 for -1.5%): ").strip())
            break
        except ValueError:
            print("[-] Please enter a valid number.")

    couple = True
    if 2 in mt_numbers:
        ans = input("[?] Also scale the S(alpha,beta) cross sections of this nuclide below their upper "
                    "energy when MT=2 is perturbed? (y/n) [Default: y]: ").strip().lower()
        couple = ans != 'n'

    # =========================================================
    # 5. Read Energy Groups Directly from inputs/groups.i
    # =========================================================
    group_path = os.path.join(base_dir, 'inputs', 'groups.i')
    print("\n[*] Energy Group Structure")
    if not os.path.exists(group_path):
        print(f"[-] Error: File '{group_path}' not found!")
        return
    energy_bounds = list(P.group_bounds_from_file(group_path))
    num_groups = len(energy_bounds) - 1
    if num_groups < 1:
        print("[-] Error: 'groups.i' must contain at least two energy boundaries.")
        return
    print(f"    [+] {num_groups} energy groups loaded from 'groups.i' "
          f"({energy_bounds[0]:.3e} - {energy_bounds[-1]:.3e} eV)")

    # =========================================================
    # 6. One perturbed library per (MT, group)
    # =========================================================
    fractional_change = pert_percent / 100.0
    n_ok = n_fail = n_empty = 0
    for mt in mt_numbers:
        print("\n" + "=" * 60)
        print(f" Starting MT = {mt} ({P.REACTION_LABELS.get(mt, 'reaction')})")
        print("=" * 60)
        for g in range(1, num_groups + 1):
            e_low, e_high = energy_bounds[g - 1], energy_bounds[g]
            out = os.path.join(pert_dir, f"{isotope}_MT{mt}_G{g}_{pert_percent}pct")
            try:
                rep = P.write_perturbed_library(orig_xml, out, isotope, mt, e_low, e_high,
                                                fractional_change, couple_thermal=couple, verify=True)
            except Exception as e:
                print(f"  [-] Group {g}: failed ({e})")
                n_fail += 1
                continue
            if not rep.get("changed", True):
                print(f"  [!] Group {g} ({e_low:.3e}-{e_high:.3e} eV): no data in this group, nothing written")
                import shutil
                shutil.rmtree(out, ignore_errors=True)
                n_empty += 1
                continue
            ok = rep["verification"]["ok"] and all(t["verification"]["ok"] for t in rep["thermal"])
            n_ok += ok
            n_fail += not ok
            extra = f", S(a,b): {', '.join(t['name'] for t in rep['thermal'])}" if rep["thermal"] else ""
            print(f"  [{'+' if ok else '-'}] Group {g} ({e_low:.3e}-{e_high:.3e} eV): "
                  f"{'verified' if ok else 'VERIFICATION FAILED'}{extra} -> {os.path.basename(out)}/")
            for w in rep.get("warnings", []):
                print(f"      [!] {w}")

    print("\n" + "=" * 60)
    print(f"[+] {n_ok} perturbed libraries written and verified, {n_empty} empty groups, {n_fail} failures")
    print(f"    Folder: {pert_dir}")
    print("    Each sub-folder holds the perturbed HDF5 file(s), a cross_sections.xml and")
    print("    perturbation_report.json (targets, inserted grid points, verification).")
    print("=" * 60)


def _compact(mts):
    mts = sorted(mts)
    out, start, prev = [], mts[0], mts[0]
    for m in mts[1:] + [None]:
        if m is not None and m == prev + 1:
            prev = m
            continue
        out.append(f"{start}-{prev}" if prev > start else f"{start}")
        if m is not None:
            start = prev = m
    return ", ".join(out)


if __name__ == "__main__":
    create_perturbed_library()