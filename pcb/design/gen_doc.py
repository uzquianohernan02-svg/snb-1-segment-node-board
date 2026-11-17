"""Build the SNB-1 design document PDF and BOM CSV."""
import csv, json, math, os, sys
from reportlab.lib import colors
from reportlab.lib.pagesizes import A3, A4, landscape
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (BaseDocTemplate, Frame, PageTemplate, Paragraph, Spacer, Table, TableStyle,
                                PageBreak, NextPageTemplate, Flowable, KeepTogether)
import board as B
import symbols as SY
import render as RD
from netlist import C

HERE = os.path.dirname(os.path.abspath(__file__))
OUTPDF = sys.argv[1]
BOMCSV = os.path.join(HERE, "..", "kicad", "snb_bom.csv")
VER = json.load(open(os.path.join(HERE, "verify.json")))

ss = getSampleStyleSheet()
H1 = ParagraphStyle("h1", parent=ss["Heading1"], fontSize=15, spaceAfter=6, spaceBefore=4)
H2 = ParagraphStyle("h2", parent=ss["Heading2"], fontSize=11.5, spaceAfter=4, spaceBefore=8)
BD = ParagraphStyle("b", parent=ss["Normal"], fontSize=9, leading=12)
SM = ParagraphStyle("s", parent=ss["Normal"], fontSize=7.6, leading=9.6)
SMB = ParagraphStyle("sb", parent=SM, fontName="Helvetica-Bold")
HD = ParagraphStyle("hd", parent=SM, fontName="Helvetica-Bold", textColor=colors.white)
NAVY = colors.HexColor("#1F3A5F")
WARN = colors.HexColor("#FDF0DC")


def tbl(rows, widths, head=True, zebra=True, fs=None):
    data = [[Paragraph(str(c), HD if (head and i == 0) else SM) for c in r] for i, r in enumerate(rows)]
    t = Table(data, colWidths=widths, repeatRows=1 if head else 0)
    st = [("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#9AA5B1")), ("VALIGN", (0, 0), (-1, -1), "TOP"),
          ("TOPPADDING", (0, 0), (-1, -1), 2.5), ("BOTTOMPADDING", (0, 0), (-1, -1), 2.5)]
    if head:
        st.append(("BACKGROUND", (0, 0), (-1, 0), NAVY))
    if zebra:
        for i in range(1, len(rows)):
            if i % 2 == 0:
                st.append(("BACKGROUND", (0, i), (-1, i), colors.HexColor("#EEF2F6")))
    t.setStyle(TableStyle(st))
    return t


def P(t, s=BD):
    return Paragraph(t, s)


# ------------------------------------------------------------------ schematic drawing flowable
class SchematicDrawing(Flowable):
    def __init__(self, w, h):
        super().__init__()
        self.width, self.height = w, h
        self.d = json.load(open(os.path.join(HERE, "sch_draw.json")))

    def draw(self):
        c = self.canv
        xs, ys = [], []
        for it in self.d["draw"]:
            if it[0] == "wire":
                xs += [it[1][0], it[2][0]]; ys += [it[1][1], it[2][1]]
            elif it[0] in ("sym",):
                xs.append(it[4]); ys.append(it[5])
            elif it[0] in ("title", "note"):
                xs.append(it[2]); ys.append(it[3])
        x0, x1, y0, y1 = min(xs) - 8, max(xs) + 22, min(ys) - 6, max(ys) + 6
        s = min(self.width / (x1 - x0), self.height / (y1 - y0))
        T = lambda x, y: ((x - x0) * s, self.height - (y - y0) * s)
        c.setStrokeColor(colors.HexColor("#8B0000"))
        c.setLineWidth(0.5)
        c.rect(0, self.height - (y1 - y0) * s, (x1 - x0) * s, (y1 - y0) * s)
        for item in self.d["draw"]:
            k = item[0]
            if k == "wire":
                c.setStrokeColor(colors.HexColor("#007A00")); c.setLineWidth(0.6)
                a, b = T(*item[1]), T(*item[2]); c.line(a[0], a[1], b[0], b[1])
            elif k == "label":
                net, at, ang = item[1], item[2], item[3]
                x, y = T(*at)
                c.setFillColor(colors.black); c.setFont("Helvetica", 1.25 * s * 1.0 + 1.2)
                c.saveState(); c.translate(x, y); c.rotate(ang if ang in (0, 90) else ang - 180)
                if ang in (0, 90):
                    c.drawString(0.6, 0.8, net)
                else:
                    c.drawRightString(-0.6, 0.8, net)
                c.restoreState()
            elif k == "power":
                net, at, d = item[1], item[2], item[3]
                x, y = T(*at)
                c.setStrokeColor(colors.black); c.setFillColor(colors.black); c.setLineWidth(0.6)
                ux, uy = d[0], -d[1]
                if net == "GND":
                    px, py = -uy, ux
                    for k2, wd in ((0, 2.0), (0.7, 1.3), (1.4, 0.6)):
                        cx, cy = x + ux * (k2 * s), y + uy * (k2 * s)
                        c.line(cx - px * wd * s, cy - py * wd * s, cx + px * wd * s, cy + py * wd * s)
                else:
                    ex, ey = x + ux * 1.6 * s, y + uy * 1.6 * s
                    c.line(x, y, ex, ey)
                    px, py = -uy, ux
                    c.line(ex - px * 1.3 * s, ey - py * 1.3 * s, ex + px * 1.3 * s, ey + py * 1.3 * s)
                    c.setFont("Helvetica-Bold", 1.2 * s + 1)
                    c.drawCentredString(ex + ux * 2.6 * s, ey + uy * 2.6 * s - 1.5, net)
            elif k == "flag":
                x, y = T(*item[1])
                c.setStrokeColor(colors.HexColor("#8B0000"))
                c.line(x, y, x, y + 1.3 * s)
                c.setFont("Helvetica", 1.1 * s + 0.8); c.setFillColor(colors.HexColor("#8B0000"))
                c.drawCentredString(x, y + 1.8 * s, "PWR_FLAG")
            elif k == "sym":
                name, ref, val, X, Y = item[1:]
                self.sym(c, name, ref, val, X, Y, T, s)
            elif k == "title":
                x, y = T(item[2], item[3])
                c.setFillColor(NAVY); c.setFont("Helvetica-Bold", 2.0 * s + 2)
                c.drawString(x, y, item[1])
            elif k == "note":
                x, y = T(item[2], item[3])
                c.setFillColor(colors.black); c.setFont("Helvetica", 1.6 * s + 0.5)
                c.drawString(x, y, item[1])

    def sym(self, c, name, ref, val, X, Y, T, s):
        S = SY.S[name]
        L = lambda x, y: T(X + x, Y - y)
        c.setStrokeColor(colors.HexColor("#8B0000")); c.setLineWidth(0.7)
        for g in S["gfx"]:
            if g[0] == "rect":
                a, b = L(g[1], g[2]), L(g[3], g[4])
                if g[5]:
                    c.setFillColor(colors.HexColor("#FFFFC2"))
                c.rect(min(a[0], b[0]), min(a[1], b[1]), abs(b[0] - a[0]), abs(b[1] - a[1]),
                       fill=1 if g[5] else 0)
            elif g[0] == "line":
                pts = [L(*p) for p in g[1]]
                for p, q in zip(pts, pts[1:]):
                    c.line(p[0], p[1], q[0], q[1])
            elif g[0] == "circle":
                x, y = L(g[1], g[2]); c.circle(x, y, g[3] * s, fill=0)
            elif g[0] == "arc":
                pts = [L(*g[1]), L(*g[2]), L(*g[3])]
                p = c.beginPath(); p.moveTo(*pts[0]); p.curveTo(*pts[1], *pts[1], *pts[2]); c.drawPath(p)
            elif g[0] == "text":
                x, y = L(g[2], g[3]); c.setFillColor(colors.HexColor("#8B0000"))
                c.setFont("Helvetica-Bold", g[4] * s + 0.5); c.drawCentredString(x, y, g[1])
        for (n, nm, t, x, y, a, ln, hid) in S["pins"]:
            if hid:
                continue
            d = {0: (1, 0), 180: (-1, 0), 90: (0, 1), 270: (0, -1)}[a]
            p0 = L(x, y); p1 = L(x + d[0] * ln, y + d[1] * ln)
            c.setStrokeColor(colors.HexColor("#8B0000")); c.line(p0[0], p0[1], p1[0], p1[1])
            fs = 1.0 * s + 0.6
            if S["pn"] and nm not in ("~",):
                c.setFillColor(colors.HexColor("#006D6D")); c.setFont("Helvetica", fs)
                q = L(x + d[0] * (ln + 0.5), y + d[1] * (ln + 0.5))
                label = nm.replace("~{", "/").replace("}", "")
                if a == 0:
                    c.drawString(q[0], q[1] - fs / 3, label)
                elif a == 180:
                    c.drawRightString(q[0], q[1] - fs / 3, label)
                else:
                    c.drawCentredString(q[0], q[1] - fs / 3 + (1.5 if a == 270 else -2.5), label)
            if S["pnum"]:
                c.setFillColor(colors.HexColor("#8B0000")); c.setFont("Helvetica", fs * 0.85)
                q = L(x + d[0] * ln / 2, y + d[1] * ln / 2)
                c.drawCentredString(q[0] + (0 if a in (0, 180) else 2.2), q[1] + (0.8 if a in (0, 180) else 0), n)
        c.setFillColor(colors.black)
        fs = 1.3 * s + 0.6
        c.setFont("Helvetica-Bold", fs)
        if name in ("LM5116", "RS485", "LDO_SOT89", "SM712"):
            top = max([pp[4] for pp in S["pins"]] + [0]) + 3.5
            c.drawCentredString(*L(0, top + 2.5), ref)
            c.setFont("Helvetica", fs); c.drawCentredString(*L(0, top), val)
        elif name.startswith("Screw") or name == "MountingHole":
            c.drawCentredString(*L(0, 6.5), ref); c.setFont("Helvetica", fs); c.drawCentredString(*L(0, -8.2), val)
        elif name.startswith("SolderJumper"):
            c.drawCentredString(*L(0, 2.5), ref); c.setFont("Helvetica", fs); c.drawCentredString(*L(0, -6.5), val)
        else:
            c.drawString(*L(2.5, 0.6), ref); c.setFont("Helvetica", fs * 0.95); c.drawString(*L(2.5, -2.4), val)


class BoardDrawing(Flowable):
    def __init__(self, w, h, layers, labels=True, title=""):
        super().__init__()
        self.width, self.height, self.layers, self.labels, self.title = w, h, layers, labels, title

    def draw(self):
        items, holes = RD.load()
        s = min(self.width / B.BW, (self.height - 14) / B.BH)
        RD.draw_board(self.canv, items, holes, 0, 0, s, layers=self.layers, labels=self.labels)
        self.canv.setFont("Helvetica-Bold", 9); self.canv.setFillColor(NAVY)
        self.canv.drawString(0, B.BH * s + 4, self.title)


class BlockDiagram(Flowable):
    def __init__(self, w, h):
        super().__init__(); self.width, self.height = w, h

    def draw(self):
        c = self.canv
        boxes = [("24 V Class 2 feed\n(2.5 A, J1)", 0), ("Fuse 4 A T\nF1", 1), ("Reverse-polarity\nP-FET Q1 + TVS D2", 2),
                 ("Input filter\nC1 100 uF + 4x2.2 uF", 3), ("LM5116 sync buck\nQ2/Q3, L1 15 uH, 252 kHz", 4),
                 ("12 V / 6 A out\nJ3, J4 to strip", 5)]
        bw, bh, gap = (self.width - 5 * 14) / 6, 34, 14
        y = self.height - bh - 4
        for txt, i in boxes:
            x = i * (bw + gap)
            c.setFillColor(colors.HexColor("#E8EEF5")); c.setStrokeColor(NAVY); c.setLineWidth(0.8)
            c.roundRect(x, y, bw, bh, 4, fill=1)
            c.setFillColor(colors.black); c.setFont("Helvetica", 7)
            for k, line in enumerate(txt.split("\n")):
                c.drawCentredString(x + bw / 2, y + bh - 13 - k * 9, line)
            if i < 5:
                c.setStrokeColor(colors.HexColor("#B03030")); c.setLineWidth(1.6)
                c.line(x + bw + 1, y + bh / 2, x + bw + gap - 3, y + bh / 2)
                c.line(x + bw + gap - 7, y + bh / 2 + 3, x + bw + gap - 3, y + bh / 2)
                c.line(x + bw + gap - 7, y + bh / 2 - 3, x + bw + gap - 3, y + bh / 2)
        rx = [("RS-485 pair in (J2)\nSM712 TVS, 120R term.", 0), ("THVD1450 receiver\nU3 @ 5 V (U2 78L05)", 1),
              ("33 R series\nR15", 2), ("WS2815 DI / BI / GND\nJ5 (BI via JP2)", 3)]
        y2 = y - bh - 22
        for txt, i in rx:
            x = i * (bw + gap) + (bw + gap)
            c.setFillColor(colors.HexColor("#F3EEF9")); c.setStrokeColor(colors.HexColor("#5B3F8C")); c.setLineWidth(0.8)
            c.roundRect(x, y2, bw, bh, 4, fill=1)
            c.setFillColor(colors.black); c.setFont("Helvetica", 7)
            for k, line in enumerate(txt.split("\n")):
                c.drawCentredString(x + bw / 2, y2 + bh - 13 - k * 9, line)
            if i < 3:
                c.setStrokeColor(colors.HexColor("#5B3F8C")); c.setLineWidth(1.2)
                c.line(x + bw + 1, y2 + bh / 2, x + bw + gap - 3, y2 + bh / 2)
        c.setFont("Helvetica-Oblique", 7); c.setFillColor(colors.HexColor("#5B3F8C"))
        c.drawString(0, y2 + bh / 2 - 3, "Node 1 only:")
        c.setStrokeColor(colors.HexColor("#5B3F8C")); c.setDash(2, 2)
        c.line(5 * (bw + gap) + bw / 2, y, 5 * (bw + gap) + bw / 2, y2 + bh / 2)
        c.line(5 * (bw + gap) + bw / 2, y2 + bh / 2, 4 * (bw + gap) + bw, y2 + bh / 2)
        c.setDash()
        c.setFont("Helvetica", 6.5); c.setFillColor(colors.black)
        c.drawString(4 * (bw + gap) + bw + 4, y2 + bh / 2 + 3, "+12 V feeds U2")


# ------------------------------------------------------------------ content
def bom_rows():
    groups = {}
    for ref, p in C.items():
        key = (p["value"], p["fp"].split(":")[1], p["mpn"], p["variant"], p["desc"])
        groups.setdefault(key, []).append(ref)
    def sk(r):
        import re
        m = re.match(r"([A-Z]+)(\d+)", r)
        return (m.group(1), int(m.group(2)))
    rows = []
    for (val, fp, mpn, var, desc), refs in groups.items():
        refs = sorted(refs, key=sk)
        rows.append((refs, val, fp, mpn, var, desc))
    rows.sort(key=lambda r: sk(r[0][0]))
    return rows


def generic(fp, val):
    import re
    m = re.match(r"(?:.*:)?(R|C|LED)_(\d{4})_", fp)
    if not m:
        return fp.split(":")[-1]
    kind, size = m.groups()
    if kind == "R":
        return f"Any {size} thick-film resistor, 1 %, 100 ppm/C"
    if kind == "LED":
        return f"Any {size} green LED (2 mA)"
    diel = "C0G" if ("C0G" in val or "pF" in val) else "X7R"
    v = "100 V" if "100V" in val else ("25 V" if "uF" in val else "50 V")
    return f"Any {size} {diel} ceramic, {v} min"


def write_bom(rows):
    with open(BOMCSV, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["Qty", "References", "Value", "Footprint", "Manufacturer part (or equivalent)", "Fitted", "Function"])
        for refs, val, fp, mpn, var, desc in rows:
            w.writerow([len(refs), " ".join(refs), val, fp, mpn or generic(fp, val),
                        "Node 1 only" if var == "RX" else ("Not a part (hole)" if refs[0].startswith("H") else "All nodes"),
                        desc])


def build():
    rows = bom_rows()
    write_bom(rows)
    PW, PH = landscape(A3)
    doc = BaseDocTemplate(OUTPDF, pagesize=landscape(A3), leftMargin=16 * mm, rightMargin=16 * mm,
                          topMargin=14 * mm, bottomMargin=14 * mm,
                          title="SNB-1 Segment Node Board - Design Package Rev B",
                          author="Engineering", subject="24 V to 12 V / 6 A node board with RS-485 receiver")
    fw, fh = PW - 32 * mm, PH - 28 * mm
    colw = (fw - 10 * mm) / 2

    def footer(c, d):
        c.saveState(); c.setFont("Helvetica", 7.5); c.setFillColor(colors.grey)
        c.drawString(16 * mm, 8 * mm, "SNB-1 Segment Node Board, Rev B (prototype design for review). Not PE-stamped, not UL-listed. "
                                      "Basis: Engineering Specification Rev 4 + Engineer's Assumptions, Nov 13, 2026.")
        c.drawRightString(PW - 16 * mm, 8 * mm, f"Page {d.page}")
        c.restoreState()

    two = PageTemplate("two", [Frame(16 * mm, 14 * mm, colw, fh, id="L"),
                               Frame(16 * mm + colw + 10 * mm, 14 * mm, colw, fh, id="R")], onPage=footer)
    one = PageTemplate("one", [Frame(16 * mm, 14 * mm, fw, fh, id="F")], onPage=footer)
    doc.addPageTemplates([two, one])
    st = []
    # ---------------- page 1-2: summary, requirements, calcs
    st.append(P("SNB-1 Segment Node Board: Design Package, Rev B", H1))
    st.append(P("Per-segment power and data node for the WS2815 architectural lighting system of Engineering Specification "
                "Rev 4. It replaces the separate fuse, 24 V-to-12 V converter and RS-485 pixel-data receiver at each segment "
                "with one board in an IP67 enclosure. Prepared Nov 13, 2026; KiCad ERC/DRC clean-up Nov 16, 2026; Rev B (HO gate resistor R16, manufacturing files) Nov 17, 2026.", BD))
    st.append(Spacer(1, 5))
    warn = Table([[P("<b>Status: prototype design for engineering review, not yet built or tested.</b> Schematic-to-netlist "
                     "parity, clearance and connectivity were checked with independent scripts, and KiCad's own ERC and DRC "
                     "(with schematic parity and zones refilled) report " + VER.get("kicad_erc", "n/a") + " and "
                     + VER.get("kicad_drc", "n/a") + " (Section 10). Review the layout and complete the bench tests in "
                     "Section 10 before ordering production quantities. A custom board is not UL-listed (open item 6 of Rev 4).", SM)]],
                 colWidths=[colw])
    warn.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), WARN), ("BOX", (0, 0), (-1, -1), 0.6, colors.HexColor("#D08A2E")),
                              ("LEFTPADDING", (0, 0), (-1, -1), 6), ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                              ("TOPPADDING", (0, 0), (-1, -1), 5), ("BOTTOMPADDING", (0, 0), (-1, -1), 5)]))
    st.append(warn)
    st.append(P("1. Function and block diagram", H2))
    st.append(BlockDiagram(colw, 120))
    st.append(P("2. Requirements traced to the specification", H2))
    st.append(tbl([
        ["Requirement", "Source", "SNB-1 implementation"],
        ["24 V DC Class 2 input, 2.5 A per segment", "Spec Sec. 1, 2 (approved 24 V)", "J1, sized for 12-14 AWG pigtail; UVLO off at 16 V"],
        ["4 A time-delay fuse at converter input", "Rev 4 open item 10 (approved)", "F1: 5x20 mm holder, 4 A T fuse, DC rating >= 32 V"],
        ["24 V to 12 V, >= 6 A / 72 W, IP67", "Spec Sec. 7", "LM5116 sync buck; 6.2 A min current limit; board in IP67 box"],
        ["Converter at the segment, 12 V injection start/mid/end", "Spec Sec. 5A", "Two 12 V output terminals (J3, J4), 14 AWG min wiring"],
        ["RS-485 receiver at first pixel; BI handling", "Spec Sec. 7", "U3 THVD1450 + JP2 (BI to GND default); node 1 only"],
        ["Remain Class 2; no paralleling; V+ isolated", "Spec Sec. 3", "One board per driver output; outputs never joined"],
        ["Common GND across segments, DC not earthed", "Spec Sec. 5", "GND continuous; mounting holes not connected"],
        ["Survive 150 ft feed (hot-plug ringing)", "Spec Sec. 4 (cable length)", "60 V-rated buck stage, SMBJ33A clamp, damped input (Sec. 3.7)"],
        ["Reverse-polarity field wiring", "Good practice", "Q1 P-MOSFET, 0.1 W loss at 2.5 A"],
    ], [0.30 * colw, 0.24 * colw, 0.46 * colw]))
    st.append(P("3. Design calculations (LM5116 datasheet SNVS499I equations)", H2))
    calc = [
        ["Item", "Equation / basis", "Result", "Part"],
        ["3.1 Switching frequency", "RT = (1/f - 450 ns) / 284 pF", "RT 12.4 k -> 252 kHz", "R4"],
        ["3.2 Inductor", "L = Vo(1 - Vo/Vin,max) / (Ipp f), Vin,max 30 V", "15 uH; ripple 1.6 A @24 V, 1.9 A @30 V", "L1"],
        ["3.3 Current limit", "Ilim = Vcs/RS - Vo T/L (Vcs 94/110/126 mV)", "RS 10 mOhm: 6.2 / 7.8 / 9.4 A", "R11"],
        ["3.4 Inductor saturation", "Peak in overload = Vcs,max / RS", ">= 12.6 A; specify Isat >= 13 A", "L1"],
        ["3.5 Ramp (VOUT > 7.5 V)", "IOS = Vo/3 x 10 uA/V; CRAMP = IOS L/(Vo A RS)", "IOS 40 uA; CRAMP 500 pF -> 470 pF C0G", "C8"],
        ["3.6 Ramp resistor", "RRAMP = (VCC - VRAMP)/(IOS - 25 uA), VCC 7.4 V", "VRAMP 0.42 V -> 464 k", "R6"],
        ["3.7 Input damping", "delta = 0.5[(Rin+ESR)/Zs + Zs/Zin], 150 ft ~30 uH", "Zs 0.53 Ohm, delta ~0.55 (well damped)", "C1"],
        ["3.8 Input ripple", "dV = Io / (4 f Cin), Cin eff. ~7 uF", "0.7 V p-p (C1 reduces further)", "C2-C5"],
        ["3.9 Output voltage", "Vo = 1.215 (1 + RFB2/RFB1)", "1.24 k / 11.0 k -> 11.99 V", "R7, R8"],
        ["3.10 UVLO", "Vmin = 1.215 (R2+R3)/R3 - 5 uA R2", "100 k / 7.87 k -> 16.2 V off", "R2, R3"],
        ["3.11 Soft start", "tss = CSS x 1.215 V / 10 uA", "100 nF -> ~12 ms", "C9"],
        ["3.12 Loop compensation", "fc ~ 15 kHz; zero = 1/(2 pi RCOMP CCOMP)", "26.1 k + 3.9 nF (1.6 kHz), CHF 56 pF (109 kHz)", "R9, C10, C11"],
        ["3.13 Gate drive", "IGC = 2 Qg f = 2 x 14 nC x 252 kHz", "7 mA < 15 mA VCC limit (VCCX at GND)", "U1"],
        ["3.13b HO gate resistor", "Damps trace L / Ciss ringing; t = Rg Qg / Vdrv", "2.2 Ohm adds ~5 ns; tune 0-4.7 Ohm", "R16"],
        ["3.14 Losses at 12 V / 5 A", "FETs 1.0 W, L1 0.5 W, RS 0.13 W, IC 0.2 W, Q1+F1 0.2 W", "~2.0 W total, ~96-97 % efficient", "-"],
        ["3.15 Output ripple", "Cout 4x22 uF + 220 uF polymer (~264 uF eff.)", "< 50 mV p-p (ESR dominated)", "C15-C19"],
    ]
    st.append(tbl(calc, [0.20 * colw, 0.38 * colw, 0.30 * colw, 0.12 * colw]))
    st.append(P("Values marked for bench tuning: R9/C10/C11 (loop), R12/C14 (snubber), R16 (HO gate). Confirm with TI WEBENCH or a Bode "
                "measurement before production.", SM))
    st.append(P("4. Key component choices", H2))
    st.append(tbl([
        ["Function", "Choice", "Why"],
        ["Controller", "TI LM5116 (6-100 V, HTSSOP-20)", "100 V rating covers 150 ft hot-plug ringing; external FETs spread heat"],
        ["Power FETs", "2x Vishay Si7850DP (60 V)", "TI's reference-design FET; Qg 14 nC within VCC limit"],
        ["Inductor", "Coilcraft XAL1010-153 (15 uH)", "Shielded, low DCR; confirm Isat >= 13 A on datasheet"],
        ["Input protection", "4 A T fuse, SQD50P06-15L, SMBJ33A", "Field-replaceable fuse; reverse polarity; clamp < 60 V FET rating"],
        ["Bulk input", "100 uF 50 V electrolytic (EEU-FR1H101)", "Its ESR damps the cable-inductance/ceramic resonance"],
        ["RS-485 receiver", "TI THVD1450 (50 Mbps, 5 V)", "Fast enough for 800 kHz WS2815 timing; 5 V logic out"],
        ["Line protection", "Semtech SM712", "Asymmetric -7/+12 V clamp matches the RS-485 common-mode range"],
    ], [0.18 * colw, 0.36 * colw, 0.46 * colw]))
    st.append(P("5. Variants and field configuration", H2))
    st.append(tbl([
        ["Item", "Node 1 of each run", "Nodes 2-4"],
        ["Power section (all parts not listed below)", "Fitted", "Fitted"],
        ["U2, U3, C20-C22, D5, R14, R15, J2, J5, JP1, JP2", "Fitted", "Not fitted (data runs in the strip)"],
        ["JP1 (RS-485 termination)", "Close on the last receiver on the line", "-"],
        ["JP2 (BI)", "Bridge 1-2: BI = GND (default)", "-"],
        ["F1", "4 A time-lag 5x20 mm, DC >= 32 V", "Same"],
    ], [0.42 * colw, 0.30 * colw, 0.28 * colw]))
    st.append(P("6. PCB construction", H2))
    st.append(tbl([
        ["Parameter", "Value"],
        ["Size / layers", f"{B.BW:.0f} x {B.BH:.0f} mm, 2 layers, 1.6 mm FR-4 (Tg >= 150 C)"],
        ["Copper", "2 oz (70 um) both layers; HASL lead-free or ENIG"],
        ["Rules", "0.2 mm clearance, 0.25 mm min signal track, 0.6/0.3 mm vias, 0.5 mm copper-to-edge"],
        ["Power copper", "VIN 3 mm, +12 V 2-2.5 mm + polygon, SW and CS polygons; solid GND plane on bottom"],
        ["Mounting", "4x M3, not connected to copper; fits an IP67 box with >= 130 x 90 mm inside"],
    ], [0.3 * colw, 0.7 * colw]))
    # ---------------- schematic page
    st.append(NextPageTemplate("one")); st.append(PageBreak())
    st.append(P("7. Schematic (generated from the KiCad file snb.kicad_sch; nets join by label name)", H2))
    st.append(SchematicDrawing(fw, fh - 45))
    # ---------------- layout pages
    st.append(PageBreak())
    st.append(P("8. PCB layout (top copper and assembly, scale ~2.7:1)", H2))
    st.append(BoardDrawing(fw, fh - 40, ("B", "F"), True, "Top view: red = top copper, blue = bottom copper (tracks), "
                                                         "light blue = GND pours, grey rings = vias. Boxes = courtyards."))
    st.append(PageBreak())
    st.append(P("8b. Bottom copper (tracks only; the rest of the bottom layer is a solid GND plane)", H2))
    st.append(BoardDrawing(fw, fh - 40, ("B",), False, "Bottom layer tracks seen from the top"))
    # ---------------- BOM + verification
    st.append(NextPageTemplate("two")); st.append(PageBreak())
    st.append(P("9. Bill of materials", H2))
    brow = [["Qty", "Refs", "Value", "Part (or equivalent)", "Fit"]]
    for refs, val, fp, mpn, var, desc in rows:
        if refs[0].startswith("H"):
            continue
        brow.append([len(refs), " ".join(refs), val, mpn or generic(fp, val), "N1" if var == "RX" else "All"])
    st.append(tbl(brow, [0.06 * colw, 0.22 * colw, 0.16 * colw, 0.48 * colw, 0.08 * colw]))
    st.append(P("N1 = node 1 of each run only. Full BOM with footprints: kicad/snb_bom.csv. Confirm the 4 A T fuse DC rating, "
                "the XAL1010-153 saturation current and the polymer capacitor ESR against current datasheets before ordering.", SM))
    st.append(P("10. Verification performed and still required", H2))
    v = VER
    st.append(tbl([
        ["Check", "Method", "Result"],
        ["Schematic matches netlist", "Connectivity re-derived from snb.kicad_sch (pins, wires, labels, power symbols)", v["sch"]],
        ["Schematic matches PCB", "Symbol UUID / value / footprint vs PCB footprint path / value / footprint", v["parity"]],
        ["Copper clearance 0.2 mm / Power 0.3 mm", "Exact geometry, all pads, tracks, vias, polygons, pairwise", v["clearance"]],
        ["Edge (0.5 mm) and hole clearance", "Exact geometry", v["edge"]],
        ["All nets connected", "Copper overlap graph; GND assumed joined by bottom plane", v["conn"]],
        ["Courtyards", "No overlaps between footprints", v["court"]],
        ["KiCad ERC", "kicad-cli " + VER.get("kicad_version", "") + " sch erc, all severities", VER.get("kicad_erc", "not run")],
        ["KiCad DRC", "kicad-cli pcb drc, all severities, schematic parity, zones refilled; custom rule snb.kicad_dru "
         "(0.2 mm at U1 0.65 mm pitch pads)", VER.get("kicad_drc", "not run")],
    ], [0.27 * colw, 0.50 * colw, 0.23 * colw]))
    st.append(P("Still required before production:", SMB))
    for t in [
        "Open kicad/snb.kicad_pro in KiCad 10 and review the layout. Re-run ERC/DRC after any manual change.",
        "Review the layout. Known compromises: (a) the HO gate-drive trace is about 36 mm long (U1 sits below the power stage). Rev B adds R16, a 2.2 Ohm "
        "gate resistor at the Q2 gate, to damp it. Moving U1 closer to Q2 is the Rev C option if HO ringing is seen on the bench; (b) the input-capacitor GND returns to R11 through the bottom plane (about 12 mm). Keep that plane unbroken.",
        "Bench: soft start, line 18-30 V and load 0-6 A regulation; current limit (expect 6.2-9.4 A); switch-node and HO gate ringing (tune R12/C14 and R16); "
        "step-load transient (tune R9/C10); 150 ft hot-plug VIN overshoot (must stay < 50 V).",
        "Thermal: 12 V / 5 A for 2 h in the sealed IP67 box at 60 C ambient. Keep L1, Q2, Q3 and U1 below 105 C (thermocouples).",
        "Data: 720 pixels at 45 fps through 300 ft of Cat5e. Check for no flicker, and check the BI behaviour with JP2.",
        "Compliance: a custom converter board is not UL-listed. Check with the AHJ (NEC 411.4) or plan UL recognition (Rev 4 items 6 and 13).",
    ]:
        st.append(P("&bull; " + t, SM))
    st.append(P("11. Files", H2))
    st.append(tbl([
        ["File", "Content"],
        ["pcb/kicad/snb.kicad_pro", "KiCad project (rules: 0.2 mm clearance, Power netclass 0.3 mm / 1.0 mm)"],
        ["pcb/kicad/snb.kicad_sch", "Schematic, 1 sheet A3, KiCad 9 format (opens in KiCad 9 and 10)"],
        ["pcb/kicad/snb.kicad_pcb", "PCB, 2 layers, zones filled, saved by KiCad 10 (needs KiCad 10)"],
        ["pcb/kicad/snb.kicad_dru", "Custom design rule: 0.2 mm clearance at the LM5116 fine-pitch pads"],
        ["pcb/kicad/snb-erc.json, snb-drc.json", "KiCad ERC and DRC reports"],
        ["pcb/kicad/snb.kicad_sym + sym-lib-table", "Project symbol library 'snb'"],
        ["pcb/kicad/snb_bom.csv", "Bill of materials with node-variant column"],
        ["pcb/fab/snb-gerbers.zip (+ gerbers/)", "Gerber X2 + Excellon drill files for the board house (drill map PDF in gerbers/)"],
        ["pcb/fab/snb-pos-*.csv, snb-bom-*.csv", "Pick-and-place and assembly BOM per variant (node1 / node2-4)"],
        ["pcb/fab/snb.step, snb-top.png", "3D model for the enclosure fit check; top render"],
        ["pcb/design/*.py", "Generator scripts: netlist (single source of truth), router, checks, this document"],
    ], [0.40 * colw, 0.60 * colw]))
    doc.build(st)


if __name__ == "__main__":
    build()
    print("wrote", OUTPDF, "and", BOMCSV)
