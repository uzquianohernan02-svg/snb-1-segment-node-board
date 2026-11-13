"""Re-run all independent checks on the generated files and write verify.json."""
import json, os, pickle, subprocess, sys
import sexpr
import board as B
import build_pcb as BP
import render as RD
from netlist import C

HERE = os.path.dirname(os.path.abspath(__file__))
res = {}
r = subprocess.run([sys.executable, "-X", "utf8", os.path.join(HERE, "check_sch.py")], capture_output=True, text=True)
res["sch"] = "PASS" if "True" in r.stdout else "FAIL"

s = sexpr.parse(open(os.path.join(HERE, "..", "kicad", "snb.kicad_sch"), encoding="utf-8").read())
p = sexpr.parse(open(os.path.join(HERE, "..", "kicad", "snb.kicad_pcb"), encoding="utf-8").read())
syms, fps = {}, {}
for x in sexpr.findall(s, "symbol"):
    pr = {q[1]: q[2] for q in sexpr.findall(x, "property")}
    if not pr["Reference"].startswith("#"):
        syms[pr["Reference"]] = (sexpr.find(x, "uuid")[1], pr["Value"], pr["Footprint"])
for f in sexpr.findall(p, "footprint"):
    pr = {q[1]: q[2] for q in sexpr.findall(f, "property")}
    fps[pr["Reference"]] = (sexpr.find(f, "path")[1].strip("/"), pr["Value"], f[1])
bad = [k for k in syms if syms[k] != fps.get(k)]
res["parity"] = f"PASS ({len(syms)} parts)" if not bad else "FAIL " + " ".join(bad)

items, holes = RD.load()
errs, unc = BP.verify(items, holes)
cl = [e for e in errs if e.startswith("clearance")]
ed = [e for e in errs if not e.startswith("clearance")]
res["clearance"] = "PASS (0 violations)" if not cl else f"FAIL ({len(cl)})"
res["edge"] = "PASS" if not ed else f"FAIL ({len(ed)})"
res["conn"] = f"PASS ({len({it.net for it in items if it.net})} nets)" if not unc else f"FAIL ({len(unc)})"
cy = {k: B.courtyard(k) for k in C}
ov = []
ks = [k for k in cy if cy[k]]
for i, a in enumerate(ks):
    for b in ks[i + 1:]:
        A, Bb = cy[a], cy[b]
        if A[0] < Bb[2] and Bb[0] < A[2] and A[1] < Bb[3] and Bb[1] < A[3]:
            ov.append(a + "/" + b)
res["court"] = "PASS" if not ov else "FAIL " + " ".join(ov)
json.dump(res, open(os.path.join(HERE, "verify.json"), "w"), indent=1)
print(json.dumps(res, indent=1))
for e in errs + unc:
    print("  ", e)
