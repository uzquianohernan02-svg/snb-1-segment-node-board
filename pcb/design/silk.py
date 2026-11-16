"""Silkscreen layout: place reference designators and board labels clear of mask openings,
other silkscreen and the board edge (what KiCad DRC checks as silk_over_copper / silk_overlap /
silk_edge_clearance). Works on axis-aligned rectangles in board coordinates (mm)."""
import math
import sexpr
import board as B
from netlist import C

MASK_GAP = 0.15     # silk to pad (mask opening) gap
SILK_GAP = 0.15     # silk to silk gap
EDGE_GAP = 0.6      # silk to board edge
SIZES = (1.0, 0.8)  # try nominal text height, then a smaller one
STROKE = 0.15


def text_box(s, cx, cy, size, ang):
    w = len(s) * size * 0.9 + STROKE        # KiCad stroke font: conservative advance
    h = size * 1.15 + STROKE
    if ang % 180:
        w, h = h, w
    return (cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2)


def overlap(a, b, gap):
    return not (a[2] + gap <= b[0] or b[2] + gap <= a[0] or a[3] + gap <= b[1] or b[3] + gap <= a[1])


def fp_silk(ref):
    """Rectangles of the footprint's own F.SilkS graphics (board coords)."""
    p = C[ref]
    x, y, rot = B.PLACE[ref]
    out = []
    for g in B.load_fp(p["fp"]):
        if not (isinstance(g, list) and g[0] in ("fp_line", "fp_rect", "fp_poly", "fp_circle", "fp_arc")):
            continue
        ly = sexpr.find(g, "layer")
        if not ly or ly[1] != "F.SilkS":
            continue
        st = sexpr.find(g, "stroke")
        wd = float(sexpr.find(st, "width")[1]) / 2 if st else 0.06
        pts = []
        if g[0] == "fp_circle":   # outline ring: many small boxes, so the inside stays usable
            c = sexpr.find(g, "center"); e = sexpr.find(g, "end")
            cx, cy = float(c[1]), float(c[2])
            r = math.hypot(float(e[1]) - cx, float(e[2]) - cy)
            n = max(12, int(2 * math.pi * r / 0.3))
            for i in range(n):
                px, py = B.xf(cx + r * math.cos(2 * math.pi * i / n), cy + r * math.sin(2 * math.pi * i / n), x, y, rot)
                out.append((px - wd, py - wd, px + wd, py + wd))
            continue
        for k in ("start", "end", "mid"):
            e = sexpr.find(g, k)
            if e:
                pts.append((float(e[1]), float(e[2])))
        pp = sexpr.find(g, "pts")
        if pp:
            pts += [(float(q[1]), float(q[2])) for q in sexpr.findall(pp, "xy")]
        bp = [B.xf(a, b, x, y, rot) for a, b in pts]
        if g[0] in ("fp_line",) and len(bp) == 2 and abs(bp[0][0] - bp[1][0]) > 0.05 and abs(bp[0][1] - bp[1][1]) > 0.05:
            # diagonal line: split into small boxes so it does not block its whole bounding box
            n = max(2, int(math.dist(*bp) / 0.3))
            for i in range(n + 1):
                t = i / n
                px = bp[0][0] + t * (bp[1][0] - bp[0][0]); py = bp[0][1] + t * (bp[1][1] - bp[0][1])
                out.append((px - wd, py - wd, px + wd, py + wd))
            continue
        out.append((min(q[0] for q in bp) - wd, min(q[1] for q in bp) - wd,
                    max(q[0] for q in bp) + wd, max(q[1] for q in bp) + wd))
    return out


class Layout:
    def __init__(self):
        pads, _ = B.all_pads()
        self.mask = [it.bbox for it in pads]
        self.silk = [r for ref in C for r in fp_silk(ref)]
        self.placed = []

    def free(self, box):
        if box[0] < EDGE_GAP or box[1] < EDGE_GAP or box[2] > B.BW - EDGE_GAP or box[3] > B.BH - EDGE_GAP:
            return False
        if any(overlap(box, m, MASK_GAP) for m in self.mask):
            return False
        return not any(overlap(box, s, SILK_GAP) for s in self.silk + self.placed)

    def take(self, box):
        self.placed.append(box)

    def label(self, s, x, y, size):
        """Board text: keep nominal spot if clear, else nearest clear spot within 4 mm."""
        for r in [0] + [k * 0.25 for k in range(1, 17)]:
            steps = 1 if r == 0 else 16
            for i in range(steps):
                a = 2 * math.pi * i / steps
                cx, cy = x + r * math.cos(a), y + r * math.sin(a)
                box = text_box(s, cx, cy, size, 0)
                if self.free(box):
                    self.take(box)
                    return round(cx, 3), round(cy, 3)
        print(f"silk: no clear spot for label '{s}', left at nominal position")
        return x, y

    def reference(self, ref):
        """Return (x, y, angle, size, layer) in board coords for the Reference field."""
        cy_ = B.courtyard(ref)
        x, y, rot = B.PLACE[ref]
        if cy_ is None:
            cy_ = (x - 1, y - 1, x + 1, y + 1)
        x0, y0, x1, y1 = cy_
        mx, my = (x0 + x1) / 2, (y0 + y1) / 2
        for size in SIZES:
            for ang in (0, 90):
                tw, th = (text_box(ref, 0, 0, size, ang)[2] * 2, text_box(ref, 0, 0, size, ang)[3] * 2)
                cands = [(mx, y0 - th / 2 - 0.05), (mx, y1 + th / 2 + 0.05),
                         (x0 - tw / 2 - 0.05, my), (x1 + tw / 2 + 0.05, my)]
                # slide along each side as well
                for k in (1, -1, 2, -2, 3, -3):
                    d = k * 0.6
                    cands += [(mx + d, y0 - th / 2 - 0.05), (mx + d, y1 + th / 2 + 0.05),
                              (x0 - tw / 2 - 0.05, my + d), (x1 + tw / 2 + 0.05, my + d)]
                for cx, cy in cands:
                    box = text_box(ref, cx, cy, size, ang)
                    if self.free(box):
                        self.take(box)
                        return round(cx, 3), round(cy, 3), ang, size, "F.SilkS"
        # large parts: inside the body outline, between the pads
        for size in SIZES:
            for ang in (0, 90):
                for dx, dy in [(0, 0)] + [(a * 0.5, b * 0.5) for a in range(-4, 5) for b in range(-4, 5)]:
                    box = text_box(ref, mx + dx, my + dy, size, ang)
                    if self.free(box):
                        self.take(box)
                        return round(mx + dx, 3), round(my + dy, 3), ang, size, "F.SilkS"
        return x, y, 0, 1.0, "F.Fab"     # too dense: designator on the assembly (Fab) drawing only


def board_coords_to_local(ref, bx, by):
    x, y, rot = B.PLACE[ref]
    a = math.radians(rot)
    dx, dy = bx - x, by - y
    return round(dx * math.cos(a) - dy * math.sin(a), 4), round(dx * math.sin(a) + dy * math.cos(a), 4)
