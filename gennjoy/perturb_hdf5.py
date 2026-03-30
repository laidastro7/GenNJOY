import os
import numpy as np

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
    # 3. Load isotope and extract available reactions
    # =========================================================
    print(f"\n[*] Scanning {isotope} for available neutron reactions via OpenMC Engine...")
    try:
        nuc_test = openmc.data.IncidentNeutron.from_hdf5(orig_h5)
    except Exception as e:
        print(f"[-] Failed to load {orig_h5}: {e}")
        return

    mt_names = {
        2: "Elastic Scattering",
        4: "Inelastic Scattering (Total)",
        16: "(n,2n) Reaction",
        18: "Fission (Total)",
        27: "Absorption (Total)",
        102: "Radiative Capture (n,gamma)",
        103: "(n,p) Reaction",
        104: "(n,d) Reaction",
        105: "(n,t) Reaction",
        107: "(n,alpha) Reaction"
    }

    print("-" * 50)
    print(f" Available Reactions for {isotope}:")
    print("-" * 50)
    
    valid_mts = []
    for mt in sorted(nuc_test.reactions.keys()):
        rx = nuc_test.reactions[mt]
        if hasattr(rx, 'xs') and rx.xs: 
            valid_mts.append(mt)
            name = mt_names.get(mt, "Other Specific Reaction")
            print(f"    👉 MT = {mt:<4} | {name}")
    print("-" * 50)

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
                print(f"[-] Error: The following MT numbers are invalid or have no cross-section data: {invalid_mts}")
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

    # =========================================================
    # 5. Read Energy Groups Directly from inputs/groups.i
    # =========================================================
    inputs_dir = os.path.join(base_dir, 'inputs')
    os.makedirs(inputs_dir, exist_ok=True)
    group_path = os.path.join(inputs_dir, 'groups.i')
    
    print("\n[*] Energy Group Structure")
    if not os.path.exists(group_path):
        print(f"[-] Error: File '{group_path}' not found!")
        print("    Please make sure 'groups.i' is created inside the 'inputs' folder.")
        return
        
    try:
        with open(group_path, 'r') as f:
            content = f.read().replace(',', ' ').split()
            energy_bounds = sorted([float(val) for val in content])
            
        if len(energy_bounds) < 2:
            print("[-] Error: 'groups.i' must contain at least two energy boundaries.")
            return
            
        num_groups = len(energy_bounds) - 1
        print(f"    [+] Automatically loaded {num_groups} energy groups from 'groups.i':")
        for i in range(num_groups):
            print(f"        Group {i+1}: {energy_bounds[i]:.5e} eV  to  {energy_bounds[i+1]:.5e} eV")
            
        target_groups = list(range(1, num_groups + 1))
    except Exception as e:
        print(f"[-] Error reading groups: {e}")
        return

    # =========================================================
    # 6. Sequential Isolated Generation
    # =========================================================
    fractional_change = pert_percent / 100.0
    print(f"\n[*] Processing perturbations...")

    for mt in mt_numbers:
        rx_name = mt_names.get(mt, "Reaction")
        print(f"\n" + "="*60)
        print(f" 🚀 Starting MT = {mt} ({rx_name})")
        print("="*60)
        
        for g in target_groups:
            try:
                E_low = energy_bounds[g-1]
                E_high = energy_bounds[g]
                print(f"\n  -> Processing Group {g} (Energy Range: {E_low:.3e} to {E_high:.3e} eV)")
                                    
                    # Load a fresh copy of the isotope for each energy group
                nuc = openmc.data.IncidentNeutron.from_hdf5(orig_h5)
                
                if mt not in nuc.reactions:
                    print(f"     [-] Error: MT={mt} not found. Skipping.")
                    break
                    
                rx = nuc.reactions[mt]
                pert_filename = f"{isotope}_pert_MT{mt}_G{g}_{pert_percent}pct.h5"
                xml_filename = f"cross_sections_pert_{isotope}_MT{mt}_G{g}_{pert_percent}pct.xml"
                
                changed = False
                               
                # Apply perturbation to the cross-section data
                for temp in rx.xs:
                    xs_obj = rx.xs[temp]
                    if not hasattr(xs_obj, 'x') or not hasattr(xs_obj, 'y'): 
                        continue 
                    
                    x_vals = xs_obj.x
                    y_vals = xs_obj.y
                    mask = (x_vals >= E_low) & (x_vals <= E_high)
                    
                    if not np.any(mask):
                        continue
                        
                    changed = True
                    delta_y = y_vals[mask] * fractional_change
                    y_vals[mask] += delta_y
                    
                    # 2. Adjust associated total cross sections (MT=1, MT=27) to preserve physical consistency
                    redundant_mts = [1] 
                    if mt in [18, 102, 103, 104, 105, 107]:
                        redundant_mts.append(27)
                        
                    for r_mt in redundant_mts:
                        if r_mt in nuc.reactions:
                            r_rx = nuc.reactions[r_mt]
                            if temp in r_rx.xs and hasattr(r_rx.xs[temp], 'x') and hasattr(r_rx.xs[temp], 'y'):
                                r_x = r_rx.xs[temp].x
                                r_y = r_rx.xs[temp].y
                                
                                if np.array_equal(r_x, x_vals):
                                    r_y[mask] += delta_y
                                else:
                                    delta_interp = np.interp(r_x, x_vals[mask], delta_y, left=0.0, right=0.0)
                                    r_y += delta_interp
                
                # Smart check: if no data was modified (empty group), do not create files
                if not changed:
                    print(f"     [!] Warning: No cross section data in this energy group. Skipped generation.")
                    continue

                # 3. Save the perturbed HDF5 file for this group
                pert_h5_path = os.path.join(pert_dir, pert_filename)
                if os.path.exists(pert_h5_path):
                    os.remove(pert_h5_path)
                    
                try:
                    nuc.export_to_hdf5(pert_h5_path, mode='w')
                except TypeError:
                    nuc.export_to_hdf5(pert_h5_path)

                # 4. Save the custom XML file for this group
                if os.path.exists(orig_xml):
                    pert_xml_path = os.path.join(pert_dir, xml_filename)
                    lib = openmc.data.DataLibrary.from_xml(orig_xml)
                    for lib_entry in lib.libraries:
                        if isotope in lib_entry['materials']:
                            lib_entry['path'] = pert_h5_path 
                        else:
                            old_path = lib_entry['path']
                            if not os.path.isabs(old_path):
                                lib_entry['path'] = os.path.abspath(os.path.join(hdf5_dir, old_path))
                    lib.export_to_xml(pert_xml_path)
                    
                    print(f"     [+] Saved HDF5: {pert_filename}")
                    print(f"     [+] Saved XML : {xml_filename}")
                    
            except Exception as e:
                print(f"  [-] Failed to process Group {g} for MT={mt}. Error: {e}")

    print("\n" + "="*60)
    print(f"[+] SUCCESS: Perturbation libraries generated successfully in:")
    print(f"    📁 {pert_dir}")
    print("="*60)

if __name__ == "__main__":
    create_perturbed_library()