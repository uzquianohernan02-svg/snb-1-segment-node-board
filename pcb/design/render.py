"""Render routed board (from routed.pkl) to PDF/PNG-able vector drawing with reportlab."""
import math, os, pickle, sys
from reportlab.lib import colors
from reportlab.pdfgen import canvas
import board as B
from netlist import C

HERE = os.path.dirname(os.path.abspath(__file__))
COL = {"F": colors.Color(0.80, 0.15, 0.15, alpha=0.85), "B": colors.Color(0.15, 0.35, 0.85, alpha=0.75)}


def load():
    raw, holes = pickle.load(open(os.path.join(HERE, "routed.pkl"), "rb"))
    items = []
    for net, layers, prims, kind, ref, pad, width, drill in raw:
        items.append(B.Item(net, layers, prims, kind, ref=ref, pad=pad, width=width, drill=drill))
    return items, holes


def draw_board(c, items, holes, ox, oy, s, layers=("B", "F"), labels=True, netlabels=False, zone=True):
    """Draw at page offset (ox, oy) [points], scale s [points per mm]. Board y is down."""
    P = lambda x, y: (ox + x * s, oy + (B.BH - y) * s)
    c.saveState()
    c.setFillColor(colors.Color(0.93, 0.95, 0.90))
    c.setStrokeColor(colors.black)
    c.setLineWidth(0.8)
    c.rect(*P(0, B.BH), B.BW * s, B.BH * s, fill=1, stroke=1)
    if zone:
        c.setFillColor(colors.Color(0.15, 0.35, 0.85, alpha=0.08))
        c.rect(*P(0.3, B.BH - 0.3), (B.BW - 0.6) * s, (B.BH - 0.6) * s, fill=1, stroke=0)
    for L in layers:
        col = COL[L]
        for it in items:
            if L not in it.layers or it.kind == "via":
                continue
            if it.kind == "pad" and len(it.layers) == 2 and L == "B":
                continue
            c.setFillColor(col if it.kind != "pad" else (colors.Color(0.85, 0.6, 0.1) if L == "F" else col))
            c.setStrokeColor(col)
            for p in it.prims:
                prim(c, p, P, s)
    # courtyards + refs
    if labels:
        c.setStrokeColor(colors.Color(0.4, 0.4, 0.4))
        c.setLineWidth(0.25)
        for ref in C:
            cy = B.courtyard(ref)
            if cy:
                x0, y0 = P(cy[0], cy[3])
                c.rect(x0, y0, (cy[2] - cy[0]) * s, (cy[3] - cy[1]) * s, fill=0, stroke=1)
    for it in items:
        if it.kind == "via":
            x, y = P(*it.prims[0][1])
            c.setFillColor(colors.Color(0.55, 0.55, 0.55))
            c.circle(x, y, it.width / 2 * s, fill=1, stroke=0)
            c.setFillColor(colors.white)
            c.circle(x, y, it.drill / 2 * s, fill=1, stroke=0)
        if it.kind == "pad" and it.drill:
            p = it.prims[0]
            x, y = P(*(p[1] if p[0] == "pt" else ((p[1][0] + p[2][0]) / 2, (p[1][1] + p[2][1]) / 2)
                       if p[0] == "seg" else (sum(q[0] for q in p[1]) / 4, sum(q[1] for q in p[1]) / 4)))
            c.setFillColor(colors.white)
            c.circle(x, y, it.drill / 2 * s, fill=1, stroke=0)
    for hx, hy, hd in holes:
        x, y = P(hx, hy)
        c.setFillColor(colors.white); c.setStrokeColor(colors.black)
        c.circle(x, y, hd / 2 * s, fill=1, stroke=1)
    if labels:
        c.setFillColor(colors.black)
        for ref in C:
            cy = B.courtyard(ref)
            x, y, _ = B.PLACE[ref]
            if cy:
                x, y = (cy[0] + cy[2]) / 2, (cy[1] + cy[3]) / 2
            fs = max(3.0, min(7.0, s * 0.9))
            c.setFont("Helvetica-Bold", fs)
            c.drawCentredString(*P(x, y - 0.0), ref)
    if netlabels:
        c.setFont("Helvetica", max(2.5, s * 0.45))
        c.setFillColor(colors.Color(0.1, 0.1, 0.1))
        for it in items:
            if it.kind == "pad" and it.net:
                bx = it.bbox
                c.drawCentredString(*P((bx[0] + bx[2]) / 2, (bx[1] + bx[3]) / 2 + 0.15), it.net[:6])
    c.restoreState()


def prim(c, p, P, s):
    if p[0] == "pt":
        x, y = P(*p[1]); c.circle(x, y, p[2] * s, fill=1, stroke=0)
    elif p[0] == "seg":
        c.setLineWidth(max(p[3] * 2 * s, 0.1)); c.setLineCap(1)
        a = P(*p[1]); b = P(*p[2]); c.line(a[0], a[1], b[0], b[1])
    else:
        pts = [P(*q) for q in p[1]]
        path = c.beginPath(); path.moveTo(*pts[0])
        for q in pts[1:]:
            path.lineTo(*q)
        path.close()
        c.setLineWidth(max(p[2] * 2 * s, 0.01)); c.setLineJoin(1)
        c.drawPath(path, fill=1, stroke=1 if p[2] > 0 else 0)


if __name__ == "__main__":
    items, holes = load()
    out = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, "preview.pdf")
    zoom = sys.argv[2] if len(sys.argv) > 2 else None
    from reportlab.lib.pagesizes import A3, landscape
    W, H = landscape(A3)
    c = canvas.Canvas(out, pagesize=(W, H))
    if zoom:
        x0, y0, x1, y1 = map(float, zoom.split(","))
        s = min((W - 40) / (x1 - x0), (H - 40) / (y1 - y0))
        c.saveState()
        p = c.beginPath(); p.rect(20, 20, W - 40, H - 40); c.clipPath(p, stroke=0)
        draw_board(c, items, holes, 20 - x0 * s, 20 - (B.BH - y1) * s, s, netlabels=True)
        c.restoreState()
    else:
        s = min((W - 40) / B.BW, (H - 40) / B.BH)
        draw_board(c, items, holes, 20, 20, s)
    c.save()
    print("wrote", out)
