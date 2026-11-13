"""
Project symbol library 'snb'. Symbol coordinates follow KiCad library convention (Y up).
Pin: (number, name, etype, x, y, angle, length, hidden)
     (x, y) is the connection point; angle is the direction from the connection point to the body.
Graphics: ("rect", x1, y1, x2, y2, fill) | ("line", [(x, y), ...], width) | ("circle", x, y, r, fill)
          ("arc", (sx, sy), (mx, my), (ex, ey)) | ("text", s, x, y, size)
"""
from sexpr import Sym, q

S = {}


def sym(name, ref, pins, gfx, desc="", show_pin_names=True, show_pin_numbers=True):
    S[name] = dict(ref=ref, pins=pins, gfx=gfx, desc=desc,
                   pn=show_pin_names, pnum=show_pin_numbers)


P = "passive"
# ---- two-terminal vertical parts: pin 1 at top (y=+3.81), pin 2 at bottom
sym("R", "R", [("1", "~", P, 0, 3.81, 270, 1.27, False), ("2", "~", P, 0, -3.81, 90, 1.27, False)],
    [("rect", -1.016, 2.54, 1.016, -2.54, False)], "Resistor", False, False)
sym("C", "C", [("1", "~", P, 0, 3.81, 270, 3.048, False), ("2", "~", P, 0, -3.81, 90, 3.048, False)],
    [("line", [(-2.032, 0.762), (2.032, 0.762)], 0.508), ("line", [(-2.032, -0.762), (2.032, -0.762)], 0.508)],
    "Capacitor", False, False)
sym("CP", "C", [("1", "~", P, 0, 3.81, 270, 2.794, False), ("2", "~", P, 0, -3.81, 90, 3.048, False)],
    [("rect", -2.286, 1.016, 2.286, 0.508, False), ("rect", -2.286, -0.508, 2.286, -1.016, True),
     ("line", [(-1.778, 2.286), (-0.762, 2.286)], 0.15), ("line", [(-1.27, 2.794), (-1.27, 1.778)], 0.15)],
    "Polarized capacitor (pin 1 = +)", False, False)
sym("L", "L", [("1", "1", P, 0, 3.81, 270, 1.27, False), ("2", "2", P, 0, -3.81, 90, 1.27, False)],
    [("arc", (0, 2.54), (0.635, 1.905), (0, 1.27)), ("arc", (0, 1.27), (0.635, 0.635), (0, 0)),
     ("arc", (0, 0), (0.635, -0.635), (0, -1.27)), ("arc", (0, -1.27), (0.635, -1.905), (0, -2.54))],
    "Inductor", False, False)
sym("Fuse", "F", [("1", "~", P, 0, 3.81, 270, 1.27, False), ("2", "~", P, 0, -3.81, 90, 1.27, False)],
    [("rect", -0.762, 2.54, 0.762, -2.54, False), ("line", [(0, 2.54), (0, -2.54)], 0.15)],
    "Fuse", False, False)
TRI = [(-1.27, -1.016), (1.27, -1.016), (0, 1.016), (-1.27, -1.016)]
sym("D", "D", [("1", "K", P, 0, 3.81, 270, 2.794, False), ("2", "A", P, 0, -3.81, 90, 2.794, False)],
    [("line", TRI, 0.2), ("line", [(-1.27, 1.016), (1.27, 1.016)], 0.2)], "Diode (pin1 K)", False, False)
sym("D_Zener", "D", [("1", "K", P, 0, 3.81, 270, 2.794, False), ("2", "A", P, 0, -3.81, 90, 2.794, False)],
    [("line", TRI, 0.2), ("line", [(-1.778, 1.524), (-1.27, 1.016), (1.27, 1.016), (1.778, 0.508)], 0.2)],
    "Zener diode (pin1 K)", False, False)
sym("D_TVS", "D", [("1", "K", P, 0, 3.81, 270, 2.794, False), ("2", "A", P, 0, -3.81, 90, 2.794, False)],
    [("line", TRI, 0.2), ("line", [(-1.778, 0.508), (-1.27, 1.016), (1.27, 1.016), (1.778, 1.524)], 0.2)],
    "Unidirectional TVS (pin1 K)", False, False)
sym("LED", "D", [("1", "K", P, 0, 3.81, 270, 2.794, False), ("2", "A", P, 0, -3.81, 90, 2.794, False)],
    [("line", TRI, 0.2), ("line", [(-1.27, 1.016), (1.27, 1.016)], 0.2),
     ("line", [(1.778, -0.254), (3.048, 1.016)], 0.15), ("line", [(1.778, -1.27), (3.048, 0)], 0.15)],
    "LED (pin1 K)", False, False)
# BAS21 SOT-23: pin 1 = A (bottom), pin 3 = K (top)
sym("D_SOT23_A1K3", "D", [("3", "K", P, 0, 3.81, 270, 2.794, False), ("1", "A", P, 0, -3.81, 90, 2.794, False),
                          ("2", "NC", "no_connect", 2.54, 0, 180, 1.27, True)],
    [("line", TRI, 0.2), ("line", [(-1.27, 1.016), (1.27, 1.016)], 0.2)], "Diode SOT-23 (1=A, 3=K)", False, True)

# ---- P-MOSFET G=1 D=2 S=3 (DPAK). Drawn with D at bottom, S at top (source toward load).
MOS_BODY = [("line", [(0.254, 1.905), (0.254, -1.905)], 0.254),
            ("line", [(0.762, 2.286), (0.762, 1.27)], 0.254), ("line", [(0.762, 0.508), (0.762, -0.508)], 0.254),
            ("line", [(0.762, -1.27), (0.762, -2.286)], 0.254),
            ("line", [(0.762, 1.778), (2.54, 1.778), (2.54, 2.54)], 0.15),
            ("line", [(0.762, -1.778), (2.54, -1.778), (2.54, -2.54)], 0.15),
            ("line", [(0.762, 0), (2.54, 0), (2.54, -1.778)], 0.15),
            ("circle", 1.524, 0, 2.794, False)]
sym("Q_PMOS_GDS", "Q", [("1", "G", "input", -5.08, 0, 0, 4.826, False),
                        ("3", "S", P, 2.54, 5.08, 270, 2.54, False),
                        ("2", "D", P, 2.54, -5.08, 90, 2.54, False)],
    MOS_BODY + [("line", [(2.032, 0.254), (1.27, 0), (2.032, -0.254)], 0.15)],
    "P-MOSFET, 1=G 2=D(tab) 3=S", False, True)
# ---- N-MOSFET PowerPAK SO-8: 1,2,3 = S, 4 = G, 5 = D
sym("Q_NMOS_PPAK", "Q", [("4", "G", "input", -5.08, 0, 0, 4.826, False),
                         ("5", "D", P, 2.54, 5.08, 270, 2.54, False),
                         ("1", "S", P, 2.54, -5.08, 90, 2.54, False),
                         ("2", "S", P, 2.54, -5.08, 90, 2.54, True),
                         ("3", "S", P, 2.54, -5.08, 90, 2.54, True)],
    MOS_BODY + [("line", [(1.27, 0.254), (2.032, 0), (1.27, -0.254)], 0.15)],
    "N-MOSFET PowerPAK SO-8, 1-3=S 4=G 5=D", False, True)

# ---- SM712 asymmetric TVS array, 1=A1 2=A2 3=common
sym("SM712", "D", [("1", "A1", P, -7.62, 2.54, 0, 2.54, False), ("2", "A2", P, -7.62, -2.54, 0, 2.54, False),
                   ("3", "COM", P, 7.62, 0, 180, 2.54, False)],
    [("rect", -5.08, 5.08, 5.08, -5.08, False), ("text", "SM712", 0, 3.6, 1.0)],
    "RS-485 TVS array", True, True)

# ---- LM5116 (HTSSOP-20 + EP)
LM_L = [("1", "VIN", "power_in"), ("2", "UVLO", "input"), ("3", "RT/SYNC", "input"), ("4", "EN", "input"),
        ("5", "RAMP", "passive"), ("6", "AGND", "power_in"), ("7", "SS", "passive"), ("8", "FB", "input"),
        ("9", "COMP", "output"), ("10", "VOUT", "input")]
LM_R = [("20", "SW", "passive"), ("19", "HO", "output"), ("18", "HB", "passive"), ("17", "VCCX", "power_in"),
        ("16", "VCC", "power_out"), ("15", "LO", "output"), ("14", "PGND", "power_in"), ("13", "CSG", "input"),
        ("12", "CS", "input"), ("11", "DEMB", "input"), ("21", "EP", "power_in")]
pins = []
for i, (n, nm, t) in enumerate(LM_L):
    pins.append((n, nm, t, -12.7, 12.7 - 2.54 * i, 0, 2.54, False))
for i, (n, nm, t) in enumerate(LM_R):
    pins.append((n, nm, t, 12.7, 12.7 - 2.54 * i, 180, 2.54, False))
sym("LM5116", "U", pins, [("rect", -10.16, 15.24, 10.16, -15.24, True), ("text", "LM5116", 0, 16.5, 1.27)],
    "Wide-range synchronous buck controller, HTSSOP-20")

# ---- L78L05 SOT-89: 1=OUT 2=GND 3=IN
sym("LDO_SOT89", "U", [("3", "IN", "power_in", -7.62, 0, 0, 2.54, False),
                       ("1", "OUT", "power_out", 7.62, 0, 180, 2.54, False),
                       ("2", "GND", "power_in", 0, -5.08, 90, 2.54, False)],
    [("rect", -5.08, 2.54, 5.08, -2.54, True)], "5 V linear regulator, SOT-89")

# ---- RS-485 transceiver SOIC-8
sym("RS485", "U", [("1", "RO", "output", -10.16, 3.81, 0, 2.54, False),
                   ("2", "~{RE}", "input", -10.16, 1.27, 0, 2.54, False),
                   ("3", "DE", "input", -10.16, -1.27, 0, 2.54, False),
                   ("4", "DI", "input", -10.16, -3.81, 0, 2.54, False),
                   ("8", "VCC", "power_in", 0, 8.89, 270, 2.54, False),
                   ("6", "A", "bidirectional", 10.16, 1.27, 180, 2.54, False),
                   ("7", "B", "bidirectional", 10.16, -1.27, 180, 2.54, False),
                   ("5", "GND", "power_in", 0, -8.89, 90, 2.54, False)],
    [("rect", -7.62, 6.35, 7.62, -6.35, True)], "RS-485 transceiver (THVD1450 SOIC-8)")

# ---- connectors (pins on the left, body to the right)
for n in (2, 3):
    pins = [(str(i + 1), f"Pin_{i + 1}", P, -5.08, 2.54 * (n - 1) / 2 * 1 - 2.54 * i, 0, 3.81, False) for i in range(n)]
    h = 1.27 + 2.54 * (n - 1) / 2
    gfx = [("rect", -1.27, h, 1.27, -h, False)]
    for i in range(n):
        y = 2.54 * (n - 1) / 2 - 2.54 * i
        gfx.append(("circle", 0, y, 0.635, False))
    sym(f"Screw_Terminal_01x0{n}", "J", pins, gfx, f"Screw terminal 1x{n}", False, True)

sym("SolderJumper_2", "JP", [("1", "A", P, -3.81, 0, 0, 2.54, False), ("2", "B", P, 3.81, 0, 180, 2.54, False)],
    [("rect", -1.27, 0.762, -0.254, -0.762, True), ("rect", 0.254, 0.762, 1.27, -0.762, True)],
    "Solder jumper, open", False, True)
sym("SolderJumper_3", "JP", [("1", "A", P, -5.08, 0, 0, 2.54, False), ("2", "C", P, 0, -3.81, 90, 2.794, False),
                             ("3", "B", P, 5.08, 0, 180, 2.54, False)],
    [("rect", -2.54, 0.762, -1.016, -0.762, True), ("rect", -0.762, 0.762, 0.762, -0.762, True),
     ("rect", 1.016, 0.762, 2.54, -0.762, True), ("line", [(-1.016, 0), (-0.762, 0)], 0.4)],
    "3-pad solder jumper, 1-2 bridged by default", False, True)
sym("MountingHole", "H", [], [("circle", 0, 0, 1.27, False)], "Mounting hole")


# ------------------------------------------------------------------ writers
def _eff(size=1.27, hide=False, justify=None):
    e = [Sym("effects"), [Sym("font"), [Sym("size"), size, size]]]
    if justify:
        e.append([Sym("justify")] + [Sym(j) for j in justify.split()])
    if hide:
        e.append([Sym("hide"), Sym("yes")])
    return e


def _gfx(g):
    st = lambda w: [Sym("stroke"), [Sym("width"), w], [Sym("type"), Sym("default")]]
    fl = lambda f: [Sym("fill"), [Sym("type"), Sym("background" if f else "none")]]
    if g[0] == "rect":
        return [Sym("rectangle"), [Sym("start"), g[1], g[2]], [Sym("end"), g[3], g[4]], st(0.254), fl(g[5])]
    if g[0] == "line":
        return [Sym("polyline"), [Sym("pts")] + [[Sym("xy"), x, y] for x, y in g[1]], st(g[2]), fl(False)]
    if g[0] == "circle":
        return [Sym("circle"), [Sym("center"), g[1], g[2]], [Sym("radius"), g[3]], st(0.254), fl(g[4])]
    if g[0] == "arc":
        return [Sym("arc"), [Sym("start"), *g[1]], [Sym("mid"), *g[2]], [Sym("end"), *g[3]], st(0.254), fl(False)]
    if g[0] == "text":
        return [Sym("text"), g[1], [Sym("at"), g[2], g[3], 0], _eff(g[4])]


def lib_symbol(name, libname="snb", props=None):
    s = S[name]
    full = f"{libname}:{name}" if libname else name
    node = [Sym("symbol"), full]
    if not s["pnum"]:
        node.append([Sym("pin_numbers"), [Sym("hide"), Sym("yes")]])
    pn = [Sym("pin_names"), [Sym("offset"), 0.508 if s["pn"] else 0]]
    if not s["pn"]:
        pn.append([Sym("hide"), Sym("yes")])
    node.append(pn)
    node += [[Sym("exclude_from_sim"), Sym("no")], [Sym("in_bom"), Sym("yes")], [Sym("on_board"), Sym("yes")]]
    p = dict(Reference=s["ref"], Value=name, Footprint="", Datasheet="", Description=s["desc"])
    if props:
        p.update(props)
    for i, (k, v) in enumerate(p.items()):
        node.append([Sym("property"), k, v, [Sym("at"), 0, 0, 0], _eff(1.27, hide=(k not in ("Reference", "Value")))])
    node.append([Sym("symbol"), f"{name}_0_1"] + [_gfx(g) for g in s["gfx"]])
    u = [Sym("symbol"), f"{name}_1_1"]
    for (n, nm, t, x, y, a, ln, hid) in s["pins"]:
        pin = [Sym("pin"), Sym(t), Sym("line"), [Sym("at"), x, y, a], [Sym("length"), ln]]
        if hid:
            pin.append([Sym("hide"), Sym("yes")])
        pin += [[Sym("name"), nm, _eff()], [Sym("number"), n, _eff()]]
        u.append(pin)
    node.append(u)
    node.append([Sym("embedded_fonts"), Sym("no")])
    return node


def write_lib(path):
    from sexpr import dump
    lib = [Sym("kicad_symbol_lib"), [Sym("version"), 20241209], [Sym("generator"), "snb_gen"],
           [Sym("generator_version"), "9.0"]]
    for name in S:
        lib.append(lib_symbol(name, libname=None))
    open(path, "w", encoding="utf-8", newline="\n").write(dump(lib) + "\n")
