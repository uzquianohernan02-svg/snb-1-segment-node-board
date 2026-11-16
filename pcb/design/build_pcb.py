"""Route the board, verify it independently, and write snb.kicad_pcb / snb.kicad_pro / tables."""
import json, os, pickle, sys, uuid
import sexpr
from sexpr import Sym, dump
import board as B
import silk
import route as R
from netlist import C, nets as netlist_nets

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "..", "kicad")
NS = uuid.UUID("6f1c0a52-3c1e-4b7e-9d0e-5a1b2c3d4e5f")
ROOT = str(uuid.uuid5(NS, "root-sheet"))


POWER_SYMBOL_NETS = ("GND", "+12V", "+5V")   # nets named by power symbols; all others are local labels
NC_PADS = {("D3", "2"): "unconnected-(D3-NC-Pad2)"}   # name KiCad gives a no-connect symbol pin
KELVIN_PADS = {("U1", "13")}                         # CSG: Kelvin track only, no zone connection

DRU = """(version 1)

# LM5116 HTSSOP-20 has 0.65 mm pitch (0.25 mm pad gap): its pads cannot meet the 0.3 mm Power
# netclass clearance, so copper next to U1 pads is checked against the 0.2 mm default instead.
(rule "U1 fine pitch"
  (constraint clearance (min 0.2mm))
  (condition "A.Type == 'Pad' && A.memberOfFootprint('U1')"))
"""


def kname(net):
    """Board net name exactly as KiCad derives it from the schematic."""
    return net if (net in POWER_SYMBOL_NETS or net.startswith("unconnected-")) else "/" + net


def uid(*k):
    return str(uuid.uuid5(NS, "/".join(map(str, k))))


# ------------------------------------------------------------------ independent verification
def verify(items, holes):
    errs = []
    # 1. clearance between different nets on shared layers
    n = len(items)
    for a in range(n):
        A = items[a]
        for b in range(a + 1, n):
            Bi = items[b]
            if A.kind == "pad" and Bi.kind == "pad" and A.ref == Bi.ref:
                continue
            if not (A.layers & Bi.layers) or (A.net == Bi.net and A.net):
                continue
            d = B.item_dist(A, Bi)
            if d < B.clr_pair(A, Bi) - 0.005:
                errs.append(f"clearance {d:.3f} mm: {desc(A)} <-> {desc(Bi)}")
    # 2. edge and hole clearance
    for it in items:
        x0, y0, x1, y1 = it.bbox
        if it.kind != "pad" and (x0 < B.EDGE - 0.01 or y0 < B.EDGE - 0.01 or x1 > B.BW - B.EDGE + 0.01
                                 or y1 > B.BH - B.EDGE + 0.01):
            errs.append(f"edge clearance: {desc(it)}")
        for hx, hy, hd in holes:
            h = B.Item("", {"F", "B"}, [("pt", (hx, hy), hd / 2)], "hole")
            if it.kind != "pad" and B.item_dist(it, h) < 0.3:
                errs.append(f"hole clearance: {desc(it)}")
    # 3. connectivity: each net one component (GND: via bottom plane)
    r = R.Router.__new__(R.Router)
    unconnected = []
    for net in sorted(netlist_nets()):
        its = [it for it in items if it.net == net]
        comps = R.Router.components(r, its)
        if net == "GND":
            plane = [c for c in comps if any("B" in it.layers for it in c)]
            rest = [c for c in comps if not any("B" in it.layers for it in c)]
            ncomp = (1 if plane else 0) + len(rest)
        else:
            ncomp = len(comps)
        if ncomp > 1:
            show = rest if net == "GND" else comps
            pads = [[f"{it.ref}.{it.pad}" for it in c if it.kind == "pad"] or [desc(c[0])] for c in show]
            unconnected.append(f"net {net}: {ncomp} separate groups {pads}")
    # 4. every pad's net matches the netlist
    for it in items:
        if it.kind == "pad" and it.pad:
            exp = C[it.ref]["pins"].get(it.pad, "")
            if exp != it.net:
                errs.append(f"pad net mismatch {it.ref}.{it.pad}: {it.net} vs {exp}")
    return errs, unconnected


def desc(it):
    if it.kind == "pad":
        return f"pad {it.ref}.{it.pad} [{it.net}]"
    x0, y0, x1, y1 = it.bbox
    return f"{it.kind} [{it.net}] near ({(x0 + x1) / 2:.2f},{(y0 + y1) / 2:.2f}) {''.join(sorted(it.layers))}"


# ------------------------------------------------------------------ writers
def K(x, y):
    return round(x + B.OX, 4), round(y + B.OY, 4)


def fp_node(ref, netcode, refpos):
    p = C[ref]
    x, y, rot = B.PLACE[ref]
    t = B.load_fp(p["fp"])
    lib = p["fp"]
    node = [Sym("footprint"), lib, [Sym("layer"), "F.Cu"], [Sym("uuid"), uid("fp", ref)],
            [Sym("at"), *K(x, y)] + ([rot] if rot else [])]
    cnt = [0]

    def fix(n):
        if not isinstance(n, list):
            return n
        out = []
        for c in n:
            if isinstance(c, list) and c and c[0] == "uuid":
                cnt[0] += 1
                out.append([Sym("uuid"), uid("fpi", ref, cnt[0])])
            else:
                out.append(fix(c))
        return out

    for c in t[2:]:
        if not isinstance(c, list):
            continue
        k = c[0]
        if k in ("version", "generator", "generator_version", "layer"):
            continue
        c = fix(c)
        if k == "property":
            if c[1] == "Reference":
                c[2] = ref
                bx, by, ang, size, layer = refpos
                lx, ly = silk.board_coords_to_local(ref, bx, by)
                sexpr.find(c, "at")[:] = [Sym("at"), lx, ly, ang]
                sexpr.find(c, "layer")[:] = [Sym("layer"), layer]
                fnt = sexpr.find(sexpr.find(c, "effects"), "font")
                sexpr.find(fnt, "size")[:] = [Sym("size"), size, size]
                if sexpr.find(fnt, "thickness"):
                    sexpr.find(fnt, "thickness")[:] = [Sym("thickness"), 0.15 if size >= 1 else 0.12]
            elif c[1] == "Value":
                c[2] = p["value"]
            elif c[1] == "Description":
                c[2] = p["desc"]
            at = sexpr.find(c, "at")
            if at is not None and c[1] != "Reference":
                a = float(at[3]) if len(at) > 3 else 0.0
                at[:] = [Sym("at"), at[1], at[2], (a + rot) % 360]
        elif k == "fp_text":
            at = sexpr.find(c, "at")
            if at is not None:
                a = float(at[3]) if len(at) > 3 else 0.0
                at[:] = [Sym("at"), at[1], at[2], (a + rot) % 360]
        elif k == "pad":
            at = sexpr.find(c, "at")
            a = float(at[3]) if len(at) > 3 else 0.0
            at[:] = [Sym("at"), at[1], at[2]] + ([(a + rot) % 360] if (a + rot) % 360 else [])
            num = c[1]
            net = p["pins"].get(num, "") if num else ""
            net = net or NC_PADS.get((ref, num), "")
            if (ref, num) in KELVIN_PADS:
                c.append([Sym("zone_connect"), 0])
            if net:
                pos = next(i for i, q in enumerate(c) if isinstance(q, list) and q[0] == "uuid") \
                    if any(isinstance(q, list) and q[0] == "uuid" for q in c) else len(c)
                c.insert(pos, [Sym("net"), netcode[net], kname(net)])
            if not any(isinstance(q, list) and q[0] == "uuid" for q in c):
                cnt[0] += 1
                c.append([Sym("uuid"), uid("pad", ref, num, cnt[0])])
        node.append(c)
        if k == "property" and c[1] == "Value":
            node.append([Sym("property"), "Footprint", lib, [Sym("at"), 0, 0, rot], [Sym("layer"), "F.Fab"],
                         [Sym("hide"), Sym("yes")], [Sym("uuid"), uid("fpfp", ref)],
                         [Sym("effects"), [Sym("font"), [Sym("size"), 1.27, 1.27], [Sym("thickness"), 0.15]]]])
            node.append([Sym("property"), "Description", p["desc"], [Sym("at"), 0, 0, rot], [Sym("layer"), "F.Fab"],
                         [Sym("hide"), Sym("yes")], [Sym("uuid"), uid("fpdesc", ref)],
                         [Sym("effects"), [Sym("font"), [Sym("size"), 1.27, 1.27], [Sym("thickness"), 0.15]]]])
            node.append([Sym("property"), "Fitted",
                         "Node 1 only (RS-485 RX)" if p["variant"] == "RX" else "All nodes",
                         [Sym("at"), 0, 0, rot], [Sym("layer"), "F.Fab"],
                         [Sym("hide"), Sym("yes")], [Sym("uuid"), uid("fpfit", ref)],
                         [Sym("effects"), [Sym("font"), [Sym("size"), 1.27, 1.27], [Sym("thickness"), 0.15]]]])
            if p["mpn"]:
                node.append([Sym("property"), "MPN", p["mpn"], [Sym("at"), 0, 0, rot], [Sym("layer"), "F.Fab"],
                             [Sym("hide"), Sym("yes")], [Sym("uuid"), uid("fpmpn", ref)],
                             [Sym("effects"), [Sym("font"), [Sym("size"), 1.27, 1.27], [Sym("thickness"), 0.15]]]])
            node += [[Sym("path"), "/" + uid("sym", ref)], [Sym("sheetname"), "/"], [Sym("sheetfile"), "snb.kicad_sch"]]
    return node


def board_file(items, template):
    tpl = sexpr.parse(open(template, encoding="utf-8").read())
    netnames = sorted({it.net for it in items if it.net} | set(netlist_nets()) | set(NC_PADS.values()))
    netnames = ["GND"] + [n for n in netnames if n != "GND"]
    netcode = {n: i + 1 for i, n in enumerate(netnames)}
    pcb = [Sym("kicad_pcb"), [Sym("version"), 20241229], [Sym("generator"), "pcbnew"],
           [Sym("generator_version"), "9.0"]]
    for k in ("general", "paper", "layers", "setup"):
        n = sexpr.find(tpl, k)
        if k == "general":
            n = [Sym("general"), [Sym("thickness"), 1.6], [Sym("legacy_teardrops"), Sym("no")]]
        if k == "setup":
            st = sexpr.find(n, "stackup")
            for ly in sexpr.findall(st, "layer"):
                if ly[1] in ("F.Cu", "B.Cu"):
                    th = sexpr.find(ly, "thickness")
                    th[1] = 0.07           # 2 oz copper
                if ly[1] == "dielectric 1":
                    sexpr.find(ly, "thickness")[1] = 1.43
        if k == "layers":
            for ly in n[1:]:
                if ly[1] == "F.Cu":
                    ly[:] = ly[:3]
                if ly[1] == "B.Cu":
                    ly[:] = ly[:3]
        pcb.append(n)
    pcb.append([Sym("title_block"), [Sym("title"), "Segment Node Board SNB-1"], [Sym("date"), "2026-11-13"],
                [Sym("rev"), "A"], [Sym("company"), "Permanent Architectural LED Lighting Systems"],
                [Sym("comment"), 1, "24 V Class 2 in -> 12 V / 6 A out + RS-485 receiver. 2 layers, 2 oz Cu, 1.6 mm FR4"],
                [Sym("comment"), 2, "Prototype layout: refill zones (B) and run DRC in KiCad before fabrication"]])
    pcb.append([Sym("net"), 0, ""])
    for n in netnames:
        pcb.append([Sym("net"), netcode[n], kname(n)])
    # silkscreen labels
    texts = [("SNB-1 Rev A  24V->12V 6A NODE", 30, 40, 1.5), ("24V IN", 3.2, 30.5, 1.0), ("RS-485 IN", 64.9, 72.6, 1.0),
             ("12V OUT", 117.8, 37.5, 1.0), ("DATA OUT", 104.9, 72.6, 1.0),
             ("A  B  GND", 64.9, 84.0, 0.9), ("GND BI DO", 104.9, 84.0, 0.9), ("+  -", 1.2, 19.5, 0.9)]
    lay = silk.Layout()
    texts = [(s, *lay.label(s, x, y, sz), sz) for s, x, y, sz in texts]
    refpos = {ref: lay.reference(ref) for ref in sorted(C, key=lambda r: (B.courtyard(r) or (0, 0, 9, 9))[2] -
                                                        (B.courtyard(r) or (0, 0, 0, 0))[0])}
    fab = sorted(r for r, v in refpos.items() if v[4] == "F.Fab")
    print(f"silk: {len(refpos) - len(fab)} designators on silkscreen, {len(fab)} on Fab only: {' '.join(fab)}")
    for ref in C:
        pcb.append(fp_node(ref, netcode, refpos[ref]))
    # board outline
    x0, y0 = K(0, 0); x1, y1 = K(B.BW, B.BH)
    pcb.append([Sym("gr_rect"), [Sym("start"), x0, y0], [Sym("end"), x1, y1],
                [Sym("stroke"), [Sym("width"), 0.1], [Sym("type"), Sym("default")]], [Sym("fill"), Sym("no")],
                [Sym("layer"), "Edge.Cuts"], [Sym("uuid"), uid("edge")]])
    for i, (s, x, y, sz) in enumerate(texts):
        pcb.append([Sym("gr_text"), s, [Sym("at"), *K(x, y), 0], [Sym("layer"), "F.SilkS"], [Sym("uuid"), uid("txt", i)],
                    [Sym("effects"), [Sym("font"), [Sym("size"), sz, sz], [Sym("thickness"), 0.15]]]])
    # copper
    for k, it in enumerate(items):
        if it.kind == "track":
            p = it.prims[0]
            pcb.append([Sym("segment"), [Sym("start"), *K(*p[1])], [Sym("end"), *K(*p[2])], [Sym("width"), it.width],
                        [Sym("layer"), f"{next(iter(it.layers))}.Cu"], [Sym("net"), netcode[it.net]],
                        [Sym("uuid"), uid("trk", k)]])
        elif it.kind == "via":
            p = it.prims[0]
            pcb.append([Sym("via"), [Sym("at"), *K(*p[1])], [Sym("size"), it.width], [Sym("drill"), it.drill],
                        [Sym("layers"), "F.Cu", "B.Cu"], [Sym("net"), netcode[it.net]], [Sym("uuid"), uid("via", k)]])
        elif it.kind == "poly":
            pts = it.prims[0][1]
            pcb.append([Sym("gr_poly"), [Sym("pts")] + [[Sym("xy"), *K(*q)] for q in pts],
                        [Sym("stroke"), [Sym("width"), 0], [Sym("type"), Sym("solid")]], [Sym("fill"), Sym("yes")],
                        [Sym("layer"), f"{next(iter(it.layers))}.Cu"], [Sym("net"), netcode[it.net]],
                        [Sym("uuid"), uid("poly", k)]])
    # GND zones (top = lowest priority pour, bottom = solid plane). KiCad fills them on refill (B).
    m = 0.3
    pts = [K(m, m), K(B.BW - m, m), K(B.BW - m, B.BH - m), K(m, B.BH - m)]
    for L in ("B", "F"):
        pcb.append([Sym("zone"), [Sym("net"), netcode["GND"]], [Sym("net_name"), kname("GND")], [Sym("layer"), f"{L}.Cu"],
                    [Sym("uuid"), uid("zone", L)], [Sym("name"), f"GND_{L}"], [Sym("hatch"), Sym("edge"), 0.5],
                    [Sym("connect_pads"), [Sym("clearance"), 0.3]], [Sym("min_thickness"), 0.25],
                    [Sym("filled_areas_thickness"), Sym("no")],
                    [Sym("fill"), Sym("yes"), [Sym("thermal_gap"), 0.4], [Sym("thermal_bridge_width"), 0.6]],
                    [Sym("polygon"), [Sym("pts")] + [[Sym("xy"), *q] for q in pts]]])
    pcb.append([Sym("embedded_fonts"), Sym("no")])
    return pcb, netcode


def project_file(template):
    d = json.load(open(template, encoding="utf-8"))
    r = d["board"]["design_settings"]["rules"]
    r.update(min_clearance=0.2, min_track_width=0.2, min_via_diameter=0.6, min_through_hole_diameter=0.3,
             min_copper_edge_clearance=0.5, min_hole_to_hole=0.25, min_via_annular_width=0.13)
    cls = d["net_settings"]["classes"][0]
    cls.update(clearance=B.CLR, track_width=0.25, via_diameter=0.6, via_drill=0.3)
    power = dict(cls)
    power.update(name="Power", clearance=B.CLR_POWER, track_width=1.0, via_diameter=0.8, via_drill=0.4, priority=0)
    d["net_settings"]["classes"] = [cls, power]
    d["net_settings"]["netclass_patterns"] = [{"netclass": "Power", "pattern": kname(p)} for p in B.POWER_NETS]
    d["meta"]["filename"] = "snb.kicad_pro"
    d["sheets"] = [[ROOT, "Root"]]
    d.setdefault("boards", [])
    d["boards"] = []
    return d


if __name__ == "__main__":
    tpl_dir = os.environ["KICAD_TEMPLATE_DIR"]
    r = R.Router()
    ok = r.run()
    pickle.dump(([(i.net, sorted(i.layers), i.prims, i.kind, i.ref, i.pad, i.width, i.drill) for i in r.items],
                 r.holes), open(os.path.join(HERE, "routed.pkl"), "wb"))
    errs, unc = verify(r.items, r.holes)
    print("\nVERIFY: router ok =", ok)
    print(f"  clearance/edge/hole/pad errors: {len(errs)}")
    for e in errs[:40]:
        print("   ", e)
    print(f"  unconnected nets: {len(unc)}")
    for e in unc:
        print("   ", e)
    os.makedirs(OUT, exist_ok=True)
    pcb, netcode = board_file(r.items, os.path.join(tpl_dir, "ecc83-pp_v2.kicad_pcb"))
    open(os.path.join(OUT, "snb.kicad_pcb"), "w", encoding="utf-8", newline="\n").write(dump(pcb) + "\n")
    json.dump(project_file(os.path.join(tpl_dir, "ecc83-pp_v2.kicad_pro")),
              open(os.path.join(OUT, "snb.kicad_pro"), "w", encoding="utf-8"), indent=2)
    open(os.path.join(OUT, "snb.kicad_dru"), "w", newline="\n").write(DRU)
    open(os.path.join(OUT, "sym-lib-table"), "w", newline="\n").write(
        '(sym_lib_table\n\t(version 7)\n\t(lib (name "snb")(type "KiCad")(uri "${KIPRJMOD}/snb.kicad_sym")'
        '(options "")(descr "Segment node board symbols"))\n)\n')
    nt = sum(1 for i in r.items if i.kind == "track"); nv = sum(1 for i in r.items if i.kind == "via")
    print(f"written: {nt} track segments, {nv} vias, {len(netcode)} nets")
