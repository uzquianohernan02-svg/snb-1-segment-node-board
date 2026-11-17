"""Export the manufacturing package with kicad-cli into ../fab/.

  gerbers/                 Gerber X2 + Excellon drill (+ drill map), and snb-gerbers.zip for the board house
  snb-pos-node1.csv        pick-and-place, node 1 of each run (all parts)
  snb-pos-node2-4.csv      pick-and-place, nodes 2-4 (RS-485 receiver parts left off)
  snb-bom-node1.csv        assembly BOM, node 1 (one line per value/footprint)
  snb-bom-node2-4.csv      assembly BOM, nodes 2-4
  snb.step                 3D model for enclosure fit checks
  snb-top.png              3D render (top)

Run after kicad_check.py, so the board already has refilled zones.
"""
import csv, glob, os, shutil, subprocess, sys, zipfile
from kicad_check import find_cli, KDIR
from netlist import C

FAB = os.path.normpath(os.path.join(KDIR, "..", "fab"))
GER = os.path.join(FAB, "gerbers")
LAYERS = "F.Cu,B.Cu,F.Paste,B.Paste,F.Silkscreen,B.Silkscreen,F.Mask,B.Mask,Edge.Cuts"


def run(cli, *args):
    r = subprocess.run([cli, *args], cwd=KDIR, capture_output=True, text=True)
    if r.returncode != 0:
        print(r.stdout, r.stderr)
        sys.exit(f"kicad-cli failed: {' '.join(args)}")


def bom(path, refs):
    groups = {}
    for ref in refs:
        p = C[ref]
        key = (p["value"], p["fp"].split(":", 1)[1], p["mpn"])
        groups.setdefault(key, []).append(ref)
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["Comment", "Designator", "Footprint", "Manufacturer part (or equivalent)", "Qty"])
        for (val, fp, mpn), rs in sorted(groups.items(), key=lambda kv: kv[1][0]):
            w.writerow([val, ",".join(rs), fp, mpn, len(rs)])


def pos(src, path, refs):
    rows = list(csv.reader(open(src, encoding="utf-8")))
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(rows[0])
        for r in rows[1:]:
            if r[0] in refs:
                w.writerow(r)


if __name__ == "__main__":
    cli = find_cli()
    if not cli:
        print("kicad-cli not found: skipping fab export")
        sys.exit(0)
    shutil.rmtree(FAB, ignore_errors=True)
    os.makedirs(GER)
    run(cli, "pcb", "export", "gerbers", "--layers", LAYERS, "--subtract-soldermask", "--use-drill-file-origin",
        "-o", GER, "snb.kicad_pcb")
    run(cli, "pcb", "export", "drill", "--format", "excellon", "--excellon-separate-th", "--generate-map",
        "--map-format", "pdf", "--drill-origin", "plot", "-o", GER + os.sep, "snb.kicad_pcb")
    allpos = os.path.join(FAB, "_pos_all.csv")
    run(cli, "pcb", "export", "pos", "--format", "csv", "--units", "mm", "--side", "both", "--use-drill-file-origin", "-o", allpos, "snb.kicad_pcb")
    run(cli, "pcb", "export", "step", "--subst-models", "--no-dnp", "-f", "-o", os.path.join(FAB, "snb.step"),
        "snb.kicad_pcb")
    run(cli, "pcb", "render", "--side", "top", "--width", "1600", "--height", "1100", "--quality", "basic",
        "-o", os.path.join(FAB, "snb-top.png"), "snb.kicad_pcb")

    parts = [r for r in C if not r.startswith("H")]
    node1 = parts
    node24 = [r for r in parts if C[r]["variant"] == "ALL"]
    for name, refs in (("node1", node1), ("node2-4", node24)):
        pos(allpos, os.path.join(FAB, f"snb-pos-{name}.csv"), set(refs))
        bom(os.path.join(FAB, f"snb-bom-{name}.csv"), refs)
    os.remove(allpos)

    files = sorted(glob.glob(os.path.join(GER, "*")))
    with zipfile.ZipFile(os.path.join(FAB, "snb-gerbers.zip"), "w", zipfile.ZIP_DEFLATED) as z:
        for f in files:
            if not f.endswith(".pdf"):
                z.write(f, os.path.basename(f))
    print(f"fab: {len(files)} gerber/drill files, zip, pos + BOM for node1 ({len(node1)} parts) "
          f"and node2-4 ({len(node24)} parts), STEP, render -> {FAB}")
