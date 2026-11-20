import openmc
import numpy as np
import csv
import os
import matplotlib.pyplot as plt
from scipy.stats import linregress

# ==============================================================================
# 1. Basic Simulation Settings
# ==============================================================================
# Set the absolute path to the generated cross-sections library
# Path to the cross_sections.xml written by GenNJOY option 6. It can also be given
# through the OPENMC_CROSS_SECTIONS environment variable.
if 'OPENMC_CROSS_SECTIONS' not in os.environ:
    openmc.config['cross_sections'] = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'hdf5_library', 'cross_sections.xml')

# Target temperatures
hzp_temps = np.arange(550, 660, 10)  # 550 to 650
hfp_temps = np.arange(850, 960, 10)  # 850 to 950
all_temps = np.concatenate((hzp_temps, hfp_temps))

enrichment = 3.1 / 100.0  # Example enrichment (3.1%)
pitch = 1.26678           # Cell pitch

def setup_mosteller_model(fuel_temp):
    """Creates materials and geometry for the Mosteller model at a given temp."""
    # --- Define Materials ---
    uo2 = openmc.Material(name=f'UO2_{fuel_temp}K')
    uo2.add_nuclide('U235', enrichment)
    uo2.add_nuclide('U238', 1.0 - enrichment)
    uo2.add_nuclide('O16', 2.0)
    uo2.set_density('g/cm3', 10.399)
    uo2.temperature = fuel_temp  

    zirconium = openmc.Material(name='Cladding')
    for iso, fraction in [('Zr90', 0.5145), ('Zr91', 0.1122), ('Zr92', 0.1715), 
                          ('Zr94', 0.1738), ('Zr96', 0.0280)]:
        zirconium.add_nuclide(iso, fraction)
    zirconium.set_density('g/cm3', 6.55)
    zirconium.temperature = 600.0

    moderator = openmc.Material(name='Borated_Water')
    moderator.add_nuclide('H1', 2.0)
    moderator.add_nuclide('O16', 1.0)
    moderator.add_nuclide('B10', 0.0014 * 0.199)
    moderator.add_nuclide('B11', 0.0014 * 0.801)
    moderator.set_density('g/cm3', 0.71)
    moderator.add_s_alpha_beta('c_H_in_H2O')
    moderator.temperature = 600.0

    materials = openmc.Materials([uo2, zirconium, moderator])

    # --- Define Geometry ---
    r_fuel = 0.39433 if fuel_temp >= 800 else 0.39398
    
    fuel_outer = openmc.ZCylinder(r=r_fuel)
    clad_inner = openmc.ZCylinder(r=0.40226)
    clad_outer = openmc.ZCylinder(r=0.45972)
    
    left = openmc.XPlane(x0=-pitch/2, boundary_type='reflective')
    right = openmc.XPlane(x0=pitch/2, boundary_type='reflective')
    bottom = openmc.YPlane(y0=-pitch/2, boundary_type='reflective')
    top = openmc.YPlane(y0=pitch/2, boundary_type='reflective')

    fuel_cell = openmc.Cell(fill=uo2, region=-fuel_outer)
    gap_cell = openmc.Cell(fill=None, region=+fuel_outer & -clad_inner)
    clad_cell = openmc.Cell(fill=zirconium, region=+clad_inner & -clad_outer)
    mod_region = +clad_outer & +left & -right & +bottom & -top
    mod_cell = openmc.Cell(fill=moderator, region=mod_region)

    geometry = openmc.Geometry([fuel_cell, gap_cell, clad_cell, mod_cell])
    
    return materials, geometry, {uo2: 'yellow', zirconium: 'gray', moderator: 'lightblue'}

def generate_tiff_plots():
    """Generates publication-quality TIFF images at 600 DPI with LZW compression to reduce file size."""
    print("\n[*] Generating high-resolution TIFF plots (600 DPI) for the paper...")
    materials, geometry, color_dict = setup_mosteller_model(600)
    
    # Plot 1: XY Radial Cross Section
    fig, ax = plt.subplots(figsize=(5, 5))
    geometry.root_universe.plot(width=(pitch, pitch), basis='xy', 
                                pixels=(2000, 2000), axes=ax, 
                                colors=color_dict, color_by='material')
    ax.set_title("Mosteller Pin-Cell (Radial XY)", fontsize=14)
    ax.set_xlabel("X (cm)"); ax.set_ylabel("Y (cm)")
    
    # التعديل هنا: إضافة pil_kwargs لضغط الصورة باستخدام LZW
    fig.savefig('model_xy_cross_section.tiff', dpi=600, format='tiff', 
                bbox_inches='tight', pil_kwargs={'compression': 'tiff_lzw'})
    plt.close(fig)

    # Plot 2: XZ Axial Cross Section
    fig, ax = plt.subplots(figsize=(5, 5))
    geometry.root_universe.plot(width=(pitch, pitch*1.5), basis='xz', 
                                pixels=(2000, 3000), axes=ax, 
                                colors=color_dict, color_by='material')
    ax.set_title("Mosteller Pin-Cell (Axial XZ)", fontsize=14)
    ax.set_xlabel("X (cm)"); ax.set_ylabel("Z (cm)")
    
    # التعديل هنا أيضاً
    fig.savefig('model_xz_cross_section.tiff', dpi=600, format='tiff', 
                bbox_inches='tight', pil_kwargs={'compression': 'tiff_lzw'})
    plt.close(fig)
    
    print("  [+] Saved: 'model_xy_cross_section.tiff' (LZW Compressed)")
    print("  [+] Saved: 'model_xz_cross_section.tiff' (LZW Compressed)")

def run_openmc_for_temp(fuel_temp):
    """Executes the simulation and returns k-effective."""
    materials, geometry, _ = setup_mosteller_model(fuel_temp)
    materials.export_to_xml()
    geometry.export_to_xml()

    # --- Simulation Settings ---
    settings = openmc.Settings()
    settings.batches = 1000     
    settings.inactive = 50
    settings.particles = 100000 
    
    bounds = [-pitch/2, -pitch/2, -1, pitch/2, pitch/2, 1]
    uniform_dist = openmc.stats.Box(bounds[:3], bounds[3:], only_fissionable=True)
    settings.source = openmc.IndependentSource(space=uniform_dist)
    settings.export_to_xml()

    # Silent run
    openmc.run(output= True)
    
    with openmc.StatePoint(f'statepoint.{settings.batches}.h5') as sp:
        k_eff = sp.k_combined
    
    # Clean up statepoint files
    os.remove(f'statepoint.{settings.batches}.h5')
    os.remove('summary.h5')
    
    return k_eff.nominal_value, k_eff.std_dev

# ==============================================================================
# 2. Main Execution Block
# ==============================================================================
if __name__ == "__main__":
    # Generate High-Resolution TIFF plots first
    generate_tiff_plots()
    
    results = []
    csv_filename = "mosteller_results.csv"

    print(f"\n[*] Starting simulation for {len(all_temps)} temperatures...")

    with open(csv_filename, mode='w', newline='') as csv_file:
        writer = csv.writer(csv_file)
        writer.writerow(["Temperature (K)", "k-effective", "Std Dev", "Reactivity (rho)"])

        for temp in all_temps:
            print(f"    - Running simulation for {temp}K ...")
            k_val, k_err = run_openmc_for_temp(temp)
            rho = (k_val - 1.0) / k_val
            
            results.append({'temp': temp, 'k': k_val, 'err': k_err, 'rho': rho})
            writer.writerow([temp, k_val, k_err, rho])
            csv_file.flush()

    print(f"\n[+] Simulation complete! All results saved in '{csv_filename}'.")

    # ==============================================================================
    # 3. Data Analysis for the Paper
    # ==============================================================================
    print("\n" + "="*60)
    print(" Doppler Reactivity Coefficient Analysis")
    print("="*60)

    # A. Standard Two-Point Method (600K -> 900K)
    rho_600 = next((item['rho'] for item in results if item['temp'] == 600), None)
    rho_900 = next((item['rho'] for item in results if item['temp'] == 900), None)

    if rho_600 is not None and rho_900 is not None:
        dc_two_point = (rho_900 - rho_600) / (900.0 - 600.0)
        print("\n[Method 1: Standard Two-Point Method]")
        print(f"  - Formula : D_c = [rho(900K) - rho(600K)] / (900 - 600)")
        print(f"  - D_c Value : {dc_two_point * 1e5:.3f} pcm/K")

    # B. Linear Least Squares Fitting (LLSF) Method
    def calculate_ftrc_llsf(data_subset, label):
        temps = [r['temp'] for r in data_subset]
        rhos = [r['rho'] for r in data_subset]
        slope, intercept, r_value, p_value, std_err = linregress(temps, rhos)
        
        print(f"\n[{label}]")
        print(f"  - D_c (LLSF Slope): {slope * 1e5:.3f} +/- {std_err * 1e5:.3f} pcm/K")
        print(f"  - R-squared (R²)  : {r_value**2:.5f}")

    print("\n[Method 2: Linear Least Squares Fitting (LLSF)]")
    hzp_data = [r for r in results if r['temp'] in hzp_temps]
    hfp_data = [r for r in results if r['temp'] in hfp_temps]

    calculate_ftrc_llsf(hzp_data, "Hot Zero Power (HZP) Range : 550K - 650K")
    calculate_ftrc_llsf(hfp_data, "Hot Full Power (HFP) Range : 850K - 950K")
    print("="*60)