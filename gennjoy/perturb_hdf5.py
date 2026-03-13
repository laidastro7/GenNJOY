import openmc.data
import os

def create_perturbed_library():
    print("\n" + "="*60)
    print(" 🛠️  GenNJOY Exact Perturbation Module (Feature 7)")
    print("="*60)
    
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
    print(f"\n[*] Scanning {isotope} for available neutron reactions...")
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
    # 4. Multiple MT Input
    # =========================================================
    while True:
        try:
            mt_input = input("\n[?] Enter the MT numbers separated by commas (e.g., 2, 4, 102): ").strip()
            mt_numbers = [int(x.strip()) for x in mt_input.split(',') if x.strip()]
            
            if not mt_numbers:
                print("[-] Please enter at least one MT number.")
                continue

            invalid_mts = [mt for mt in mt_numbers if mt not in valid_mts]
            if invalid_mts:
                print(f"[-] Error: The following MT numbers are invalid or have no cross-section data: {invalid_mts}")
                print("    Please try again and only use numbers from the list above.")
                continue
                
            break
        except ValueError:
            print("[-] Invalid format. Please enter valid integers separated by commas (e.g., 2, 4).")

    while True:
        try:
            pert_percent = float(input("[?] Enter the perturbation percentage (e.g., 1.0 for +1%, -1.5 for -1.5%): ").strip())
            break
        except ValueError:
            print("[-] Please enter a valid number.")

    # =========================================================
    # 5. Batch Isolated Generation
    # =========================================================
    print(f"\n[*] Processing perturbations: {pert_percent}% for MTs {mt_numbers} ...")
    fractional_change = pert_percent / 100.0
    multiplier = 1.0 + fractional_change

    for mt in mt_numbers:
        rx_name = mt_names.get(mt, "Reaction")
        print(f"\n  ==================================================")
        print(f"  -> Generating isolated library for MT={mt} ({rx_name})")
        
        nuc = openmc.data.IncidentNeutron.from_hdf5(orig_h5)
        
        rx = nuc.reactions[mt]
        for temp in rx.xs:
            rx.xs[temp].y *= multiplier
            
        pert_filename = f"{isotope}_pert_MT{mt}_{pert_percent}pct.h5"
        pert_h5_path = os.path.join(pert_dir, pert_filename)
        
        # -----------------------------------------------------------------
        # [Critical Fix]: Delete old file if exists to avoid h5py error
        # -----------------------------------------------------------------
        if os.path.exists(pert_h5_path):
            os.remove(pert_h5_path)
            print(f"  [*] Overwriting existing file...")
            
        try:
            # Also, adding mode='w' can ensure clean writing completely
            nuc.export_to_hdf5(pert_h5_path, mode='w')
        except TypeError:
            # For older OpenMC versions that may not accept mode parameter
            nuc.export_to_hdf5(pert_h5_path)

        if os.path.exists(orig_xml):
            pert_xml_filename = f'cross_sections_pert_{isotope}_MT{mt}_{pert_percent}pct.xml'
            pert_xml_path = os.path.join(pert_dir, pert_xml_filename)
            
            lib = openmc.data.DataLibrary.from_xml(orig_xml)
            for lib_entry in lib.libraries:
                if isotope in lib_entry['materials']:
                    lib_entry['path'] = pert_h5_path 
                else:
                    old_path = lib_entry['path']
                    if not os.path.isabs(old_path):
                        lib_entry['path'] = os.path.abspath(os.path.join(hdf5_dir, old_path))
                    
            lib.export_to_xml(pert_xml_path)
            
            print(f"  [+] Saved: {pert_filename}")
            print(f"  [+] Saved: {pert_xml_filename}")
        else:
            print(f"  [+] Saved: {pert_filename} (XML skipped)")

    print("\n" + "="*60)
    print(f"[+] SUCCESS: All individual perturbed libraries generated successfully in:")
    print(f"    📁 {pert_dir}")
    print("="*60)

if __name__ == "__main__":
    create_perturbed_library()