"""Generate snb.kicad_sch (KiCad 9 format, opens in KiCad 9/10) + snb.kicad_sym + a draw list for the PDF."""
import json, math, os, re, uuid
import sexpr
from sexpr import Sym, dump
import symbols as SY
from netlist import C

OUT = os.path.join(os.path.dirname(__file__), "..", "kicad")
POWER_LIB = os.environ.get("KICAD_POWER_LIB")  # path to KiCad power.kicad_sym (9.x)
NS = uuid.UUID("6f1c0a52-3c1e-4b7e-9d0e-5a1b2c3d4e5f")
ROOT = str(uuid.uuid5(NS, "root-sheet"))
POWER_NETS = {"GND": "GND", "+12V": "+12V", "+5V": "+5V"}


def uid(*k):
    return str(uuid.uuid5(NS, "/".join(map(str, k))))


def g(v):  # snap to 1.27 grid
    return round(round(v / 1.27) * 1.27, 4)


# ------------------------------------------------------------------ placement (schematic mm, Y down)
ROWS = [
    ("INPUT PROTECTION", 45, ["J1", "F1", "Q1", "R1", "D1", "D2", "C1", "C2", "C3", "C4", "C5", "C6"]),
    ("LM5116 CONTROLLER", 110, ["U1", "R2", "R3", "C7", "R4", "R5", "C8", "R6", "C9", "R7", "R8", "R9", "C10",
                                "C11", "R10", "C12", "D3", "C13"]),
    ("POWER STAGE + 12 V OUTPUT", 175, ["Q2", "R16", "Q3", "R11", "L1", "R12", "C14", "C15", "C16", "C17", "C18", "C19",
                                        "J3", "J4", "R13", "D4"]),
    ("RS-485 RECEIVER (NODE 1 OF EACH RUN ONLY)", 240, ["U2", "C20", "C21", "U3", "C22", "J2", "D5", "R14", "JP1",
                                                        "R15", "JP2", "J5", "H1", "H2", "H3", "H4"]),
]
WIDTH = {"LM5116": 62, "RS485": 44, "LDO_SOT89": 34, "Q_PMOS_GDS": 22, "Q_NMOS_PPAK": 22, "SM712": 34,
         "Screw_Terminal_01x02": 30, "Screw_Terminal_01x03": 30, "SolderJumper_2": 24, "SolderJumper_3": 26,
         "MountingHole": 10}


def place():
    pos = {}
    for title, y, refs in ROWS:
        x = 30
        for r in refs:
            s = C[r]["sym"]
            w = WIDTH.get(s, 13)
            off = 22 if s in ("LM5116", "RS485") else (10 if s.startswith("Screw") else 0)
            pos[r] = (g(x + off), g(y))
            x += w
    return pos


def pin_xy(X, Y, p):
    return g(X + p[3]), g(Y - p[4])


def outward(angle):
    return {0: (-1, 0), 180: (1, 0), 90: (0, 1), 270: (0, -1)}[angle]


# ------------------------------------------------------------------ power lib symbols
def power_symbols():
    t = sexpr.parse(open(POWER_LIB, encoding="utf-8").read())
    out = {}
    for s in sexpr.findall(t, "symbol"):
        if s[1] in ("GND", "+12V", "+5V", "PWR_FLAG"):
            s = list(s)
            s[1] = "power:" + s[1]
            out[s[1]] = s
    return out


def effects(size=1.27, hide=False, justify=None):
    e = [Sym("effects"), [Sym("font"), [Sym("size"), size, size]]]
    if justify:
        e.append([Sym("justify")] + [Sym(j) for j in justify.split()])
    if hide:
        e.append([Sym("hide"), Sym("yes")])
    return e


def prop(k, v, x, y, hide=False, size=1.27, justify=None, rot=0):
    return [Sym("property"), k, v, [Sym("at"), x, y, rot], effects(size, hide, justify)]


def instance(lib_id, ref, value, x, y, rot, pins, props, in_bom=True, fp=""):
    n = [Sym("symbol"), [Sym("lib_id"), lib_id], [Sym("at"), x, y, rot], [Sym("unit"), 1],
         [Sym("exclude_from_sim"), Sym("no")], [Sym("in_bom"), Sym("yes" if in_bom else "no")],
         [Sym("on_board"), Sym("yes")], [Sym("dnp"), Sym("no")], [Sym("uuid"), uid("sym", ref)]]
    n += props
    for p in pins:
        n.append([Sym("pin"), p, [Sym("uuid"), uid("pin", ref, p)]])
    n.append([Sym("instances"), [Sym("project"), "snb", [Sym("path"), "/" + ROOT,
                                                          [Sym("reference"), ref], [Sym("unit"), 1]]]])
    return n


def build():
    pos = place()
    items, draw = [], []
    pwr_n = [0]
    used_power = set()

    def wire(a, b):
        items.append([Sym("wire"), [Sym("pts"), [Sym("xy"), *a], [Sym("xy"), *b]],
                      [Sym("stroke"), [Sym("width"), 0], [Sym("type"), Sym("default")]],
                      [Sym("uuid"), uid("w", a, b)]])
        draw.append(("wire", a, b))

    def label(net, at, d):
        ang = {(-1, 0): 180, (1, 0): 0, (0, -1): 90, (0, 1): 270}[d]
        just = "left bottom" if ang in (0, 90) else "right bottom"
        items.append([Sym("label"), net, [Sym("at"), at[0], at[1], ang], effects(1.27, justify=just),
                      [Sym("uuid"), uid("lbl", net, at)]])
        draw.append(("label", net, at, ang))

    def power(net, at, d):
        pwr_n[0] += 1
        ref = f"#PWR{pwr_n[0]:02d}"
        if net == "GND":
            rot = {(0, 1): 0, (0, -1): 180, (-1, 0): 270, (1, 0): 90}[d]
        else:
            rot = {(0, -1): 0, (0, 1): 180, (-1, 0): 90, (1, 0): 270}[d]
        used_power.add(net)
        items.append(instance("power:" + net, ref, net, at[0], at[1], rot, ["1"],
                              [prop("Reference", ref, at[0], at[1] + 3, hide=True),
                               prop("Value", net, at[0], at[1] + (3.5 if net == "GND" else -3.5)),
                               prop("Footprint", "", at[0], at[1], hide=True),
                               prop("Datasheet", "", at[0], at[1], hide=True),
                               prop("Description", "", at[0], at[1], hide=True)], in_bom=True))
        draw.append(("power", net, at, d))

    for ref, p in C.items():
        s = SY.S[p["sym"]]
        X, Y = pos[ref]
        props = []
        # reference/value text placement
        if p["sym"] in ("LM5116", "RS485", "LDO_SOT89", "SM712"):
            top = max([pp[4] for pp in s["pins"]] + [0]) + 3.5
            props += [prop("Reference", ref, X, g(Y - top - 2.5)), prop("Value", p["value"], X, g(Y - top))]
        elif p["sym"].startswith("Screw") or p["sym"] == "MountingHole":
            props += [prop("Reference", ref, X, Y - 6.5), prop("Value", p["value"], X, Y + 7.5)]
        elif p["sym"].startswith("SolderJumper"):
            props += [prop("Reference", ref, X, Y - 3.5), prop("Value", p["value"], X, Y + 6)]
        else:
            props += [prop("Reference", ref, X + 2.5, Y - 1.27, justify="left"),
                      prop("Value", p["value"], X + 2.5, Y + 1.27, justify="left")]
        props += [prop("Footprint", p["fp"], X, Y, hide=True), prop("Datasheet", "", X, Y, hide=True),
                  prop("Description", p["desc"], X, Y, hide=True)]
        if p["mpn"]:
            props.append(prop("MPN", p["mpn"], X, Y, hide=True))
        props.append(prop("Fitted", "Node 1 only (RS-485 RX)" if p["variant"] == "RX" else "All nodes",
                          X, Y, hide=True))
        pins = [pp[0] for pp in s["pins"]]
        items.append(instance("snb:" + p["sym"], ref, p["value"], X, Y, 0, pins, props,
                              in_bom=not (p["sym"] == "MountingHole" or p["sym"].startswith("SolderJumper")),
                              fp=p["fp"]))
        draw.append(("sym", p["sym"], ref, p["value"], X, Y))
        done = set()
        for pp in s["pins"]:
            num = pp[0]
            if pp[7]:  # hidden stacked pin
                continue
            net = p["pins"].get(num)
            if net is None:
                continue
            a = pin_xy(X, Y, pp)
            if a in done:
                continue
            done.add(a)
            d = outward(pp[5])
            b = (g(a[0] + d[0] * 2.54), g(a[1] + d[1] * 2.54))
            wire(a, b)
            if net in POWER_NETS:
                power(net, b, d)
            else:
                label(net, b, d)

    # PWR_FLAGs on VIN, GND and +12V (sources that ERC cannot otherwise see)
    fx, fy = g(330), g(260)
    for i, net in enumerate(["VIN", "GND", "+12V"]):
        at = (g(fx + i * 20), fy)
        pwr_n[0] += 1
        ref = f"#FLG{i + 1:02d}"
        items.append(instance("power:PWR_FLAG", ref, "PWR_FLAG", at[0], at[1], 0, ["1"],
                              [prop("Reference", ref, at[0], at[1] - 5, hide=True),
                               prop("Value", "PWR_FLAG", at[0], at[1] - 4),
                               prop("Footprint", "", at[0], at[1], hide=True),
                               prop("Datasheet", "", at[0], at[1], hide=True),
                               prop("Description", "", at[0], at[1], hide=True)]))
        draw.append(("flag", at))
        b = (at[0], g(at[1] + 2.54))
        wire(at, b)
        if net in POWER_NETS:
            power(net, b, (0, 1) if net == "GND" else (0, 1))
        else:
            label(net, b, (0, 1))

    # block titles + notes
    for title, y, _ in ROWS:
        items.append([Sym("text"), title, [Sym("exclude_from_sim"), Sym("no")], [Sym("at"), 20, y - 22, 0],
                      effects(2.0, justify="left bottom"), [Sym("uuid"), uid("t", title)]])
        draw.append(("title", title, 20, y - 22))
    notes = ["NOTES:",
             "1. Input: 24 V Class 2 driver output (2.5 A max). Output: 12 V, 5 A load, 6.2 A min current limit.",
             "2. U1 VCCX tied to GND: internal 7.4 V VCC regulator drives the gates.",
             "3. Node 1 of each run: fit RS-485 section (U2, U3, C20-C22, J2, J5, D5, R14, R15, JP1, JP2).",
             "   Nodes 2-4: leave that section unfitted; WS2815 DI/BI/GND run continuously in the strip.",
             "4. JP1: close only on the last receiver of the RS-485 line. JP2 default = BI to GND.",
             "5. Mounting holes are not connected: Class 2 DC output is not bonded to earth.",
             "6. Values marked for bench tuning: R12/C14 snubber, R9/C10/C11 loop compensation."]
    for i, n in enumerate(notes):
        items.append([Sym("text"), n, [Sym("exclude_from_sim"), Sym("no")], [Sym("at"), 20, 268 + i * 3.6, 0],
                      effects(1.6, justify="left bottom"), [Sym("uuid"), uid("note", i)]])
        draw.append(("note", n, 20, 268 + i * 3.6))

    # lib symbols
    libs = [SY.lib_symbol(n) for n in sorted({p["sym"] for p in C.values()})]
    pw = power_symbols()
    libs += [pw[k] for k in sorted(pw)]
    sch = [Sym("kicad_sch"), [Sym("version"), 20250114], [Sym("generator"), "eeschema"],
           [Sym("generator_version"), "9.0"], [Sym("uuid"), ROOT], [Sym("paper"), "A3"],
           [Sym("title_block"), [Sym("title"), "Segment Node Board SNB-1: 24 V to 12 V / 6 A + RS-485 RX"],
            [Sym("date"), "2026-11-17"], [Sym("rev"), "B (prototype, not bench-tested)"],
            [Sym("company"), "Permanent Architectural LED Lighting Systems"],
            [Sym("comment"), 1, "Based on Engineering Specification Rev 4 + Engineer's Assumptions (Nov 13, 2026)"],
            [Sym("comment"), 2, "Not PE-stamped. Not UL-listed. Requires bench verification before production."]],
           [Sym("lib_symbols")] + libs]
    sch += items
    sch += [[Sym("sheet_instances"), [Sym("path"), "/", [Sym("page"), "1"]]], [Sym("embedded_fonts"), Sym("no")]]
    return sch, draw, pos


if __name__ == "__main__":
    os.makedirs(OUT, exist_ok=True)
    sch, draw, pos = build()
    open(os.path.join(OUT, "snb.kicad_sch"), "w", encoding="utf-8", newline="\n").write(dump(sch) + "\n")
    SY.write_lib(os.path.join(OUT, "snb.kicad_sym"))
    json.dump({"draw": draw, "pos": pos}, open(os.path.join(os.path.dirname(__file__), "sch_draw.json"), "w"))
    print("schematic written,", sum(1 for d in draw if d[0] == "sym"), "symbols,",
          sum(1 for d in draw if d[0] == "label"), "labels,", sum(1 for d in draw if d[0] == "power"), "power syms")
