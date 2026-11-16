"""Run KiCad's own ERC and DRC (kicad-cli) on the generated project.

DRC refills the copper zones and saves the board, so snb.kicad_pcb ships with filled GND pours.
Reports: ../kicad/snb-erc.json, ../kicad/snb-drc.json. Exit code 1 if any error-severity item remains.
"""
import collections, glob, json, os, shutil, subprocess, sys

HERE = os.path.dirname(os.path.abspath(__file__))
KDIR = os.path.normpath(os.path.join(HERE, "..", "kicad"))


def find_cli():
    c = os.environ.get("KICAD_CLI") or shutil.which("kicad-cli")
    if c:
        return c
    hits = sorted(glob.glob(r"C:\Program Files\KiCad\*\bin\kicad-cli.exe"))
    return hits[-1] if hits else None


def run(cli, *args):
    r = subprocess.run([cli, *args], cwd=KDIR, capture_output=True, text=True)
    if r.returncode not in (0, 5):          # 5 = violations found (with --exit-code-violations)
        print(r.stdout, r.stderr)
        sys.exit(f"kicad-cli failed: {' '.join(args)}")


def summarize(title, items):
    cnt = collections.Counter((v["severity"], v["type"]) for v in items)
    errs = sum(n for (s, _), n in cnt.items() if s == "error")
    warns = sum(n for (s, _), n in cnt.items() if s == "warning")
    print(f"{title}: {errs} errors, {warns} warnings")
    for (s, t), n in sorted(cnt.items()):
        print(f"   {s:8s} {n:3d}  {t}")
    return errs


if __name__ == "__main__":
    cli = find_cli()
    if not cli:
        print("kicad-cli not found: skipping KiCad ERC/DRC")
        sys.exit(0)
    run(cli, "sch", "erc", "--severity-all", "--format", "json", "-o", "snb-erc.json", "snb.kicad_sch")
    run(cli, "pcb", "drc", "--severity-all", "--schematic-parity", "--refill-zones", "--save-board",
        "--format", "json", "-o", "snb-drc.json", "snb.kicad_pcb")
    erc = json.load(open(os.path.join(KDIR, "snb-erc.json"), encoding="utf-8"))
    drc = json.load(open(os.path.join(KDIR, "snb-drc.json"), encoding="utf-8"))
    ev = [v for sh in erc["sheets"] for v in sh["violations"]]
    dv = drc["violations"] + drc["unconnected_items"] + drc["schematic_parity"]
    e1 = summarize("KiCad ERC", ev)
    e2 = summarize("KiCad DRC", dv)
    ver = os.path.join(HERE, "verify.json")
    res = json.load(open(ver))
    ver_txt = drc.get("kicad_version", "")
    for key, errs, items in (("kicad_erc", e1, ev), ("kicad_drc", e2, dv)):
        w = sum(1 for v in items if v["severity"] == "warning")
        res[key] = ("PASS" if not errs else f"FAIL ({errs})") + f" ({errs} errors, {w} warnings)"
    res["kicad_version"] = ver_txt
    json.dump(res, open(ver, "w"), indent=1)
    sys.exit(1 if (e1 or e2) else 0)
