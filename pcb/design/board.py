"""Board model: footprint loading, placement, copper primitives, hand-drawn power copper."""
import math, os
import numpy as np
import sexpr
from netlist import C

FPDIR = os.environ.get("KICAD_FP_DIR", "")
BW, BH = 125.0, 85.0          # board size (mm)
OX, OY = 100.0, 100.0         # board origin in KiCad sheet coordinates
CLR = 0.2                     # default copper clearance
EDGE = 0.5                    # copper-to-edge clearance
CLR_POWER = 0.3               # 'Power' netclass clearance (written to snb.kicad_pro)
POWER_NETS = ("VIN_RAW", "VIN_F", "VIN", "SW", "CS", "+12V")
FINE_PITCH = ("U1",)          # 0.65 mm pitch: pads of these parts use CLR (custom rule in snb.kicad_dru)


def clr_for(net, it):
    """Required clearance between copper of `net` and item `it` (mirrors netclasses + snb.kicad_dru)."""
    if it.kind == "pad" and it.ref in FINE_PITCH:
        return CLR
    return CLR_POWER if (net in POWER_NETS or it.net in POWER_NETS) else CLR


def clr_pair(a, b):
    return min(clr_for(a.net, b), clr_for(b.net, a))

# ------------------------------------------------------------------ placement: ref -> (x, y, rot)
PLACE = {
    # input chain
    "J1": (7, 22, 90), "F1": (16, 22, 0), "Q1": (47, 22, 180), "D1": (56, 22, 270), "R1": (56, 27, 270),
    "D2": (60.5, 22, 270), "C1": (65.5, 9.5, 0),
    "C2": (67, 21.75, 270), "C3": (71.5, 21.75, 270), "C4": (76, 21.75, 270), "C5": (80.5, 21.75, 270),
    # power stage
    "Q2": (88, 23, 180), "Q3": (88, 33.5, 0), "R11": (80.5, 33.5, 270), "L1": (101.5, 29, 0),
    "R12": (92, 38.6, 270), "C14": (92, 43, 270), "C13": (88, 39.5, 90),
    # controller
    "U1": (76, 46, 0),
    "C6": (66.5, 40.2, 180), "R3": (66.5, 42.2, 180), "C7": (66.5, 44.1, 180), "R4": (66.5, 46.0, 180),
    "R5": (66.5, 47.9, 0), "C8": (66.5, 49.8, 180), "C9": (66.5, 51.7, 180),
    "R2": (61.5, 43.15, 0), "R6": (61.5, 50.75, 0),
    "R7": (72.0, 54.0, 270), "R8": (74.2, 54.0, 90), "C11": (76.4, 54.0, 90), "R9": (78.6, 54.0, 90),
    "C10": (80.8, 54.0, 270),
    "D3": (82.4, 44.9, 90), "C12": (82.6, 48.0, 0), "R10": (82.6, 50.2, 0),
    # output
    "C15": (110, 22, 0), "C16": (110, 26, 0), "C17": (110, 30, 0), "C18": (110, 34, 0),
    "C19": (104.8, 42, 180), "J3": (118.5, 14, 270), "J4": (118.5, 26, 270),
    "R13": (114.5, 40, 0), "D4": (114.5, 43, 0),
    # RS-485 receiver
    "J2": (70, 79, 180), "J5": (110, 79, 180), "U3": (86, 70, 180), "D5": (76, 72.5, 0),
    "R14": (79.5, 67.5, 0), "JP1": (80.0, 71.5, 0), "C22": (82.6, 74.6, 0), "U2": (92, 62, 0),
    "C20": (97.2, 62, 90), "C21": (87.0, 62, 90), "R15": (92.5, 72, 0), "JP2": (100, 71.5, 0),
    # mechanical
    "H1": (4, 4, 0), "H2": (121, 4, 0), "H3": (4, 81, 0), "H4": (121, 81, 0),
}


def xf(px, py, x, y, rot):
    a = math.radians(rot)
    return (x + px * math.cos(a) + py * math.sin(a), y - px * math.sin(a) + py * math.cos(a))


# ------------------------------------------------------------------ copper primitives
# ("poly", [(x,y)...], r)  ("seg", (x1,y1), (x2,y2), r)  ("pt", (x,y), r)
def rect_prims(cx, cy, w, h, ang, rr=0.0):
    r = min(w, h) * rr if rr else 0.0
    hw, hh = w / 2 - r, h / 2 - r
    pts = [xf(dx, dy, cx, cy, ang) for dx, dy in ((-hw, -hh), (hw, -hh), (hw, hh), (-hw, hh))]
    return [("poly", pts, r)]


class Item:
    def __init__(self, net, layers, prims, kind, ref=None, pad=None, width=None, drill=None, hole=None):
        self.net, self.layers, self.prims, self.kind = net, set(layers), prims, kind
        self.ref, self.pad, self.width, self.drill, self.hole = ref, pad, width, drill, hole
        self.conn = None              # copper a track end must land in (defaults to prims)
        xs, ys = [], []
        for p in prims:
            r = p[-1]
            pts = p[1] if p[0] == "poly" else ([p[1], p[2]] if p[0] == "seg" else [p[1]])
            for (x, y) in pts:
                xs += [x - r, x + r]
                ys += [y - r, y + r]
        self.bbox = (min(xs), min(ys), max(xs), max(ys))


# ------------------------------------------------------------------ footprints
_fp_cache = {}


def load_fp(libname):
    name = libname.split(":", 1)[1]
    if name not in _fp_cache:
        _fp_cache[name] = sexpr.parse(open(os.path.join(FPDIR, name + ".kicad_mod"), encoding="utf-8").read())
    return _fp_cache[name]


def pad_items(ref):
    p = C[ref]
    x, y, rot = PLACE[ref]
    t = load_fp(p["fp"])
    items, holes = [], []
    for pd in sexpr.findall(t, "pad"):
        num, ptype, shape = pd[1], str(pd[2]), str(pd[3])
        at = sexpr.find(pd, "at")
        px, py = float(at[1]), float(at[2])
        pang = float(at[3]) if len(at) > 3 else 0.0
        sz = sexpr.find(pd, "size")
        w, h = float(sz[1]), float(sz[2])
        cx, cy = xf(px, py, x, y, rot)
        ang = rot + pang
        lay = [str(l) for l in sexpr.find(pd, "layers")[1:]]
        cu = set()
        for l in lay:
            if l in ("*.Cu", "F&B.Cu"):
                cu |= {"F", "B"}
            elif l == "F.Cu":
                cu.add("F")
            elif l == "B.Cu":
                cu.add("B")
        conn = None
        dr = sexpr.find(pd, "drill")
        drill = float(dr[1]) if dr and len(dr) > 1 and not isinstance(dr[1], list) else None
        if ptype == "np_thru_hole":
            holes.append((cx, cy, drill or w))
            continue
        if shape == "circle":
            prims = [("pt", (cx, cy), w / 2)]
        elif shape == "oval":
            if w >= h:
                a = xf(-(w - h) / 2, 0, cx, cy, ang); b = xf((w - h) / 2, 0, cx, cy, ang)
            else:
                a = xf(0, -(h - w) / 2, cx, cy, ang); b = xf(0, (h - w) / 2, cx, cy, ang)
            prims = [("seg", a, b, min(w, h) / 2)]
        elif shape == "roundrect":
            rr = sexpr.find(pd, "roundrect_rratio")
            prims = rect_prims(cx, cy, w, h, ang, float(rr[1]) if rr else 0.25)
        elif shape == "custom":
            prims = rect_prims(cx, cy, w, h, ang)
            prs = sexpr.find(pd, "primitives")
            xs, ys = [-w / 2, w / 2], [-h / 2, h / 2]
            for g in prs[1:]:
                if g[0] == "gr_poly":
                    for xy in sexpr.findall(sexpr.find(g, "pts"), "xy"):
                        xs.append(float(xy[1])); ys.append(float(xy[2]))
                elif g[0] == "gr_circle":
                    c = sexpr.find(g, "center"); e = sexpr.find(g, "end")
                    r = math.hypot(float(e[1]) - float(c[1]), float(e[2]) - float(c[2]))
                    xs += [float(c[1]) - r, float(c[1]) + r]; ys += [float(c[2]) - r, float(c[2]) + r]
            if ref.startswith("U"):  # SOT-89 tab: anchor + extension rectangle
                ext = [(float(xy[1]), float(xy[2])) for g in prs[1:] if g[0] == "gr_poly"
                       for xy in sexpr.findall(sexpr.find(g, "pts"), "xy")]
                ex = [e[0] for e in ext]; ey = [e[1] for e in ext]
                ecx, ecy = (min(ex) + max(ex)) / 2, (min(ey) + max(ey)) / 2
                c2 = xf(px + ecx, py + ecy, x, y, rot)
                prims = rect_prims(cx, cy, w, h, ang) + rect_prims(c2[0], c2[1], max(ex) - min(ex),
                                                                    max(ey) - min(ey), ang)
            else:  # solder jumper half-moons: bounding rectangle
                bx = (min(xs) + max(xs)) / 2; by = (min(ys) + max(ys)) / 2
                c2 = xf(px + bx, py + by, x, y, rot)
                prims = rect_prims(c2[0], c2[1], max(xs) - min(xs), max(ys) - min(ys), ang)
                conn = rect_prims(cx, cy, w, h, ang)   # land tracks on the anchor, not the bbox
        else:  # rect / trapezoid
            prims = rect_prims(cx, cy, w, h, ang)
        net = p["pins"].get(num, "") if num else ""
        it = Item(net, cu, prims, "pad", ref=ref, pad=num, drill=drill)
        it.conn = conn
        items.append(it)
    return items, holes


def courtyard(ref):
    """Return courtyard rectangle (x1,y1,x2,y2) in board coords (axis aligned after rotation)."""
    p = C[ref]
    x, y, rot = PLACE[ref]
    t = load_fp(p["fp"])
    pts = []
    for g in t:
        if isinstance(g, list) and g[0] in ("fp_line", "fp_rect", "fp_poly", "fp_circle", "fp_arc"):
            ly = sexpr.find(g, "layer")
            if not ly or ly[1] != "F.CrtYd":
                continue
            if g[0] == "fp_circle":
                c = sexpr.find(g, "center"); e = sexpr.find(g, "end")
                r = math.hypot(float(e[1]) - float(c[1]), float(e[2]) - float(c[2]))
                pts += [(float(c[1]) - r, float(c[2]) - r), (float(c[1]) + r, float(c[2]) + r)]
            for k in ("start", "end", "mid"):
                e = sexpr.find(g, k)
                if e:
                    pts.append((float(e[1]), float(e[2])))
            pp = sexpr.find(g, "pts")
            if pp:
                pts += [(float(q[1]), float(q[2])) for q in sexpr.findall(pp, "xy")]
    if not pts:
        return None
    bx = [xf(a, b, x, y, rot) for a, b in pts]
    return (min(q[0] for q in bx), min(q[1] for q in bx), max(q[0] for q in bx), max(q[1] for q in bx))


# ------------------------------------------------------------------ hand-drawn power copper
def seg(net, pts, w, layer="F"):
    return [Item(net, {layer}, [("seg", a, b, w / 2)], "track", width=w) for a, b in zip(pts, pts[1:])]


def poly(net, pts, layer="F"):
    return Item(net, {layer}, [("poly", pts, 0.0)], "poly")


def via(net, x, y, size=0.6, drill=0.3):
    return Item(net, {"F", "B"}, [("pt", (x, y), size / 2)], "via", width=size, drill=drill)


def hand_copper():
    it = []
    it += seg("VIN_RAW", [(7, 22), (16, 22)], 2.5)
    it += seg("VIN_F", [(38.5, 22), (44.0, 22)], 2.5)
    it += seg("VIN", [(52.04, 19.72), (86.5, 19.72)], 3.0)
    it += seg("VIN", [(65.5, 9.5), (65.5, 19.72)], 1.5)
    it += seg("PG", [(52.04, 24.28), (56, 24.28), (56, 26.175)], 0.6)
    it.append(poly("SW", [(89.75, 21.85), (97.6, 21.85), (97.6, 37.0), (86.5, 37.0), (86.5, 25.5), (89.75, 25.5)]))
    it += seg("SW", [(88, 38.55), (88, 36.4)], 1.0)
    it.append(poly("CS", [(79.2, 30.4), (86.1, 30.4), (86.1, 34.5), (83.0, 34.5), (83.0, 31.95), (79.2, 31.95)]))
    it.append(poly("+12V", [(103.3, 20.0), (109.4, 20.0), (109.4, 36.0), (103.3, 36.0)]))
    it += seg("+12V", [(104.8, 36.0), (104.8, 42.0)], 2.0)
    it += seg("+12V", [(108.5, 20.0), (108.5, 14.0), (118.5, 14.0)], 2.5)
    it += seg("+12V", [(118.5, 14.0), (121.8, 17.3), (121.8, 22.7), (118.5, 26.0)], 2.0)
    # LM5116 AGND / PGND / VCCX to exposed pad, EP thermal vias
    it += seg("GND", [(73.14, 46.325), (74.8, 46.325)], 0.3)
    it += seg("GND", [(78.86, 46.975), (77.2, 46.975)], 0.3)
    it += seg("GND", [(78.86, 45.025), (77.2, 45.025)], 0.3)
    for vx in (75.3, 76.7):
        for vy in (44.8, 46.0, 47.2):
            it.append(via("GND", vx, vy))
    return it


# ------------------------------------------------------------------ geometry
def _pt_seg(p, a, b):
    ax, ay = a; bx, by = b; px, py = p
    dx, dy = bx - ax, by - ay
    L = dx * dx + dy * dy
    t = 0.0 if L == 0 else max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / L))
    return math.hypot(px - ax - t * dx, py - ay - t * dy)


def _seg_seg(a, b, c, d):
    def ccw(p, q, r):
        return (r[1] - p[1]) * (q[0] - p[0]) - (q[1] - p[1]) * (r[0] - p[0])
    d1, d2, d3, d4 = ccw(a, b, c), ccw(a, b, d), ccw(c, d, a), ccw(c, d, b)
    if ((d1 > 0) != (d2 > 0)) and ((d3 > 0) != (d4 > 0)) and d1 * d2 != 0 and d3 * d4 != 0:
        return 0.0
    return min(_pt_seg(a, c, d), _pt_seg(b, c, d), _pt_seg(c, a, b), _pt_seg(d, a, b))


def _in_poly(p, pts):
    x, y = p
    ins = False
    n = len(pts)
    for i in range(n):
        x1, y1 = pts[i]; x2, y2 = pts[(i + 1) % n]
        if (y1 > y) != (y2 > y) and x < x1 + (y - y1) * (x2 - x1) / (y2 - y1):
            ins = not ins
    return ins


def _edges(pts):
    return [(pts[i], pts[(i + 1) % len(pts)]) for i in range(len(pts))]


def prim_dist(a, b):
    """Edge-to-edge distance between two primitives (negative/zero = touching)."""
    def core(p):
        if p[0] == "pt":
            return ("pts", [p[1]])
        if p[0] == "seg":
            return ("segs", [(p[1], p[2])])
        return ("poly", p[1])
    ka, ga = core(a); kb, gb = core(b)
    ra, rb = a[-1], b[-1]
    if ka == "poly" and kb != "poly":
        ka, ga, kb, gb, ra, rb = kb, gb, ka, ga, rb, ra
    if kb == "poly":
        if ka == "poly":
            if any(_in_poly(p, gb) for p in ga) or any(_in_poly(p, ga) for p in gb):
                return -ra - rb
            d = min(_seg_seg(e1[0], e1[1], e2[0], e2[1]) for e1 in _edges(ga) for e2 in _edges(gb))
        elif ka == "pts":
            p = ga[0]
            if _in_poly(p, gb):
                return -ra - rb
            d = min(_pt_seg(p, e[0], e[1]) for e in _edges(gb))
        else:
            s = ga[0]
            if _in_poly(s[0], gb) or _in_poly(s[1], gb):
                return -ra - rb
            d = min(_seg_seg(s[0], s[1], e[0], e[1]) for e in _edges(gb))
        return d - ra - rb
    if ka == "pts" and kb == "pts":
        d = math.dist(ga[0], gb[0])
    elif ka == "pts":
        d = _pt_seg(ga[0], *gb[0])
    elif kb == "pts":
        d = _pt_seg(gb[0], *ga[0])
    else:
        d = _seg_seg(ga[0][0], ga[0][1], gb[0][0], gb[0][1])
    return d - ra - rb


def item_dist(A, B):
    if (A.bbox[0] > B.bbox[2] + 2 or B.bbox[0] > A.bbox[2] + 2 or
            A.bbox[1] > B.bbox[3] + 2 or B.bbox[1] > A.bbox[3] + 2):
        return 99.0
    return min(prim_dist(a, b) for a in A.prims for b in B.prims)


# vectorised distance (numpy) from grid points to a primitive
def vdist(prim, X, Y):
    if prim[0] == "pt":
        return np.hypot(X - prim[1][0], Y - prim[1][1]) - prim[2]
    if prim[0] == "seg":
        return _vseg(X, Y, prim[1], prim[2]) - prim[3]
    pts = prim[1]
    d = np.full(X.shape, np.inf)
    ins = np.zeros(X.shape, bool)
    n = len(pts)
    for i in range(n):
        a, b = pts[i], pts[(i + 1) % n]
        d = np.minimum(d, _vseg(X, Y, a, b))
        x1, y1 = a; x2, y2 = b
        if y1 != y2:
            cond = ((y1 > Y) != (y2 > Y)) & (X < x1 + (Y - y1) * (x2 - x1) / (y2 - y1))
            ins ^= cond
    d = np.where(ins, -d, d)
    return d - prim[2]


def _vseg(X, Y, a, b):
    ax, ay = a; bx, by = b
    dx, dy = bx - ax, by - ay
    L = dx * dx + dy * dy
    if L == 0:
        return np.hypot(X - ax, Y - ay)
    t = np.clip(((X - ax) * dx + (Y - ay) * dy) / L, 0, 1)
    return np.hypot(X - ax - t * dx, Y - ay - t * dy)


def all_pads():
    items, holes = [], []
    for ref in C:
        a, h = pad_items(ref)
        items += a
        holes += h
    return items, holes
