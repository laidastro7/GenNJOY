"""
Plots of the multigroup covariance matrices (NJOY COVR + VIEWR), as in the first
version of the article: relative standard deviation, correlation matrix and cross
section for one reaction per page.

    python plot_covariances.py                 # all reactions of the S/U study
    python plot_covariances.py U238:102 U235:18

Input : covariance_600K/<nuclide>.coverx (ERRORR output written by process_covariances.py)
Output: covariance_600K/plots/<nuclide>_MT<mt>.pdf, .png (300 dpi) and .tiff (600 dpi),
        and fig_covariances.png/.tiff (the two reactions of the article side by side)
Needs : njoy, ps2pdf (Ghostscript), pdftoppm (Poppler)
"""
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import su_common as C

DEFAULT = [("U238", 102), ("U235", 18), ("U238", 2), ("U238", 4), ("U238", 18), ("U238", 16),
           ("U235", 2), ("U235", 4), ("U235", 102), ("O16", 2), ("O16", 4), ("O16", 102),
           ("O16", 107), ("H1", 2), ("H1", 102)]
ARTICLE = [("U238", 102), ("U235", 18)]


def mat_number(coverx):
    line = open(coverx).readlines()[1]
    return int(line[66:70])


def plot_one(nuc, mt, out_dir, njoy):
    cov = C.COVARIANCE_DIR / f"{nuc}.coverx"
    if not cov.exists():
        print(f"  {cov} not found, skipped")
        return None
    mat = mat_number(cov)
    with tempfile.TemporaryDirectory() as td:
        td = Path(td)
        shutil.copy(cov, td / "tape33")
        deck = ("covr\n 33 0 43 /\n 1 /\n /\n 1 1 /\n"
                f" {mat} {mt} {mat} {mt} /\n"
                "viewr\n 43 53 /\nstop\n")
        (td / "input").write_text(deck)
        with open(td / "input") as fi, open(td / "output", "w") as fo:
            subprocess.run([njoy], stdin=fi, stdout=fo, stderr=subprocess.STDOUT, cwd=td)
        ps = td / "tape53"
        if not ps.exists() or ps.stat().st_size < 1000:
            print(f"  {nuc} MT={mt}: no plot produced (no covariance data?)")
            return None
        stem = out_dir / f"{nuc}_MT{mt}"
        # VIEWR writes a portrait page drawn upside down; keep the page as drawn and
        # turn the images by 180 degrees (same orientation as in the first version)
        subprocess.run(["ps2pdf", "-dAutoRotatePages=/None", str(ps), str(stem.with_suffix(".pdf"))], check=True)
    for fmt, res in (("png", 300), ("tiff", 600)):
        args = ["pdftoppm", f"-{fmt}", "-r", str(res), "-singlefile"]
        if fmt == "tiff":
            args += ["-tiffcompression", "lzw"]
        subprocess.run(args + [str(stem.with_suffix(".pdf")), str(stem)], check=True)
        _orient(stem, "png" if fmt == "png" else "tif", res)
    print(f"  {nuc} MT={mt}: {stem.with_suffix('.pdf').name}, .png (300 dpi), .tif (600 dpi)")
    return stem


def _orient(stem, ext, res):
    from PIL import Image, ImageChops
    f = Path(f"{stem}.{ext}")
    im = Image.open(f).convert("RGB").rotate(180)
    bbox = ImageChops.difference(im, Image.new("RGB", im.size, (255, 255, 255))).getbbox()
    im = im.crop(bbox)
    if ext == "png":
        im.save(f, dpi=(res, res))
    else:
        im.save(f, dpi=(res, res), compression="tiff_lzw")


def side_by_side(stems, out):
    """The two article panels side by side (VIEWR pages cropped to the plot frame)."""
    from PIL import Image
    imgs = [Image.open(f"{s}.png").convert("RGB") for s in stems]
    h = max(i.height for i in imgs)
    gap = 40
    canvas = Image.new("RGB", (sum(i.width for i in imgs) + gap * (len(imgs) - 1), h), (255, 255, 255))
    x = 0
    for i in imgs:
        canvas.paste(i, (x, 0))
        x += i.width + gap
    canvas.save(f"{out}.png", dpi=(300, 300))
    canvas.save(f"{out}.tiff", dpi=(300, 300), compression="tiff_lzw")
    print(f"  {out}.png / .tiff")


def main():
    njoy = shutil.which("njoy")
    for tool in ("ps2pdf", "pdftoppm"):
        if shutil.which(tool) is None:
            sys.exit(f"{tool} not found (install Ghostscript / Poppler)")
    if njoy is None:
        sys.exit("njoy not found in PATH")
    pairs = [(a.split(":")[0], int(a.split(":")[1])) for a in sys.argv[1:]] or DEFAULT
    out_dir = C.COVARIANCE_DIR / "plots"
    out_dir.mkdir(parents=True, exist_ok=True)
    stems = {}
    for nuc, mt in pairs:
        s = plot_one(nuc, mt, out_dir, njoy)
        if s:
            stems[(nuc, mt)] = s
    if all(p in stems for p in ARTICLE):
        side_by_side([stems[p] for p in ARTICLE], out_dir / "fig_covariances")


if __name__ == "__main__":
    main()
