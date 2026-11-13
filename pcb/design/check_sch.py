"""Re-derive connectivity from the generated .kicad_sch and compare with netlist.py (schematic parity)."""
import os, sys
import sexpr
from netlist import C, nets

path = os.path.join(os.path.dirname(__file__), "..", "kicad", "snb.kicad_sch")
t = sexpr.parse(open(path, encoding="utf-8").read())
libs = {s[1]: s for s in sexpr.find(t, "lib_symbols")[1:]}


def lib_pins(lib):
    out = []
    for u in sexpr.findall(lib, "symbol"):
        for p in sexpr.findall(u, "pin"):
            at = sexpr.find(p, "at")
            out.append((sexpr.find(p, "number")[1], float(at[1]), float(at[2])))
    return out


parent = {}


def f(a):
    while parent.setdefault(a, a) != a:
        parent[a] = parent[parent[a]]
        a = parent[a]
    return a


def u(a, b):
    parent[f(a)] = f(b)


def key(x, y):
    return ("P", round(float(x), 3), round(float(y), 3))


pinpts = {}
for s in sexpr.findall(t, "symbol"):
    lib = sexpr.find(s, "lib_id")[1]
    at = sexpr.find(s, "at")
    X, Y, rot = float(at[1]), float(at[2]), int(float(at[3]))
    ref = [p for p in sexpr.findall(s, "property") if p[1] == "Reference"][0][2]
    for num, px, py in lib_pins(libs[lib]):
        # rotation (CCW in library coords), then Y flip
        import math
        r = math.radians(rot)
        rx, ry = px * math.cos(r) - py * math.sin(r), px * math.sin(r) + py * math.cos(r)
        k = key(X + rx, Y - ry)
        node = ("PIN", ref, num)
        u(node, k)
        if lib.startswith("power:") and not ref.startswith("#FLG"):
            u(k, ("NET", sexpr.find(libs[lib], "property")[2] if False else
                  [p for p in sexpr.findall(s, "property") if p[1] == "Value"][0][2]))
for w in sexpr.findall(t, "wire"):
    pts = sexpr.findall(sexpr.find(w, "pts"), "xy")
    u(key(pts[0][1], pts[0][2]), key(pts[1][1], pts[1][2]))
for l in sexpr.findall(t, "label"):
    at = sexpr.find(l, "at")
    u(key(at[1], at[2]), ("NET", l[1]))

groups = {}
for node in list(parent):
    if node[0] == "PIN" and not node[1].startswith("#"):
        groups.setdefault(f(node), set()).add((node[1], node[2]))
in_netlist = {(r, n) for r, p in C.items() for n in p["pins"]}
sch_nets = sorted(sorted(g) for g in groups.values() if not (len(g) == 1 and next(iter(g)) not in in_netlist))
ref_nets = sorted(sorted(set(v)) for v in nets().values())
# netlist has hidden stacked pins (Q2/Q3 2,3) connected through their visible twin - include them
ok = sch_nets == ref_nets
print("schematic connectivity matches netlist:", ok)
if not ok:
    a = {tuple(x) for x in sch_nets}
    b = {tuple(x) for x in ref_nets}
    for x in sorted(a - b):
        print("  only in schematic:", x)
    for x in sorted(b - a):
        print("  only in netlist:  ", x)
    sys.exit(1)
