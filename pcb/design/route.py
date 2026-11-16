"""Grid maze router (A*, 2 layers) for signal nets + GND via fan-out. Produces routed item list."""
import heapq, math, sys, time
import numpy as np
import board as B
from netlist import C

G = 0.1
NX, NY = int(round(B.BW / G)) + 1, int(round(B.BH / G)) + 1
MARGIN = 0.035
VIA, VIA_DRILL = 0.6, 0.3
LAYERS = ("F", "B")
BOTTOM_COST = 6.0
VIA_COST = 30.0
TURN_COST = 0.6

# routing order: (net, width, extra options)
ROUTES = [
    ("SW", 0.3), ("HB", 0.3), ("VCC_L", 0.3), ("HO", 0.3), ("LO", 0.3),
    ("CS", 0.25), ("CSG_K", 0.25), ("DEMB", 0.25), ("SNB", 0.6),
    ("UVLO", 0.25), ("RT", 0.25), ("EN", 0.25), ("RAMP", 0.25), ("SS", 0.25), ("FB", 0.25), ("COMP", 0.25),
    ("CZ", 0.25), ("VSNS", 0.25), ("VCC", 0.3), ("VIN", 0.4), ("+12V", 0.5), ("LEDA", 0.25),
    ("+5V", 0.4), ("RS485_A", 0.3), ("RS485_B", 0.3), ("TERM", 0.3), ("RXO", 0.25), ("DO", 0.3), ("BI", 0.3),
]
# Kelvin sense: route U1.13 (CSG) to R11.2 as a dedicated GND track
VIRTUAL = {"CSG_K": ("GND", [("U1", "13"), ("R11", "2")]),
           "VCC_L": ("VCC", [("U1", "16"), ("D3", "1"), ("C12", "1")]),
           "VSNS": ("+12V", [("U1", "10"), ("R8", "1"), ("C19", "1")])}
GND_VIAS = {("C2", "2"): 2, ("C3", "2"): 2, ("C4", "2"): 2, ("C5", "2"): 2, ("D2", "2"): 2, ("R11", "2"): 3,
            ("C15", "2"): 2, ("C16", "2"): 2, ("C17", "2"): 2, ("C18", "2"): 2, ("U2", "2"): 2, ("C14", "2"): 2}


def grid_xy(i0, j0, i1, j1):
    xs = np.arange(i0, i1 + 1) * G
    ys = np.arange(j0, j1 + 1) * G
    return np.meshgrid(xs, ys)  # shapes (H, W)


class Router:
    def __init__(self):
        self.items, self.holes = B.all_pads()
        self.items += B.hand_copper()
        self.log = []

    # ---------------------------------------------------------- helpers
    def net_items(self, net):
        return [it for it in self.items if it.net == net]

    def components(self, items):
        n = len(items)
        par = list(range(n))

        def f(a):
            while par[a] != a:
                par[a] = par[par[a]]
                a = par[a]
            return a
        for i in range(n):
            for j in range(i + 1, n):
                if items[i].layers & items[j].layers and B.item_dist(items[i], items[j]) <= 1e-3:
                    par[f(i)] = f(j)
        comps = {}
        for i in range(n):
            comps.setdefault(f(i), []).append(items[i])
        return list(comps.values())

    def maps(self, net, w, roi, extra_same=()):
        i0, j0, i1, j1 = roi
        X, Y = grid_xy(i0, j0, i1, j1)
        H, W = X.shape
        blk = {L: np.zeros((H, W), bool) for L in LAYERS}
        vblk = np.zeros((H, W), bool)
        x0, y0, x1, y1 = i0 * G, j0 * G, i1 * G, j1 * G
        for it in self.items:
            if it.net == net or id(it) in extra_same:
                continue
            c = B.clr_for(net, it)
            inf_t = c + w / 2 + MARGIN
            inf_v = c + VIA / 2 + MARGIN
            bx = it.bbox
            if bx[0] > x1 + 1 or bx[2] < x0 - 1 or bx[1] > y1 + 1 or bx[3] < y0 - 1:
                continue
            # sub-window
            si0 = max(0, int((bx[0] - inf_v - 0.2 - x0) / G)); si1 = min(W - 1, int((bx[2] + inf_v + 0.2 - x0) / G) + 1)
            sj0 = max(0, int((bx[1] - inf_v - 0.2 - y0) / G)); sj1 = min(H - 1, int((bx[3] + inf_v + 0.2 - y0) / G) + 1)
            if si1 < si0 or sj1 < sj0:
                continue
            xs, ys = X[sj0:sj1 + 1, si0:si1 + 1], Y[sj0:sj1 + 1, si0:si1 + 1]
            d = np.min([B.vdist(p, xs, ys) for p in it.prims], axis=0)
            for L in it.layers:
                blk[L][sj0:sj1 + 1, si0:si1 + 1] |= d < inf_t
            vblk[sj0:sj1 + 1, si0:si1 + 1] |= d < inf_v
        # board edge and holes
        e_t = B.EDGE + w / 2
        e_v = B.EDGE + VIA / 2
        edge_d = np.minimum(np.minimum(X, B.BW - X), np.minimum(Y, B.BH - Y))
        for L in LAYERS:
            blk[L] |= edge_d < e_t
        vblk |= edge_d < e_v
        for hx, hy, hd in self.holes:
            d = np.hypot(X - hx, Y - hy) - hd / 2
            for L in LAYERS:
                blk[L] |= d < 0.3 + w / 2
            vblk |= d < 0.3 + VIA / 2
        vblk |= blk["F"] | blk["B"]
        return X, Y, blk, vblk

    def cells_of(self, items, X, Y, blk, roi):
        out = set()
        i0, j0 = roi[0], roi[1]
        for it in items:
            m = np.min([B.vdist(p, X, Y) for p in (it.conn or it.prims)], axis=0) <= -0.0
            for L in it.layers:
                ok = m & ~blk[L]
                js, is_ = np.nonzero(ok)
                for j, i in zip(js.tolist(), is_.tolist()):
                    out.add((L, i, j))
        return out

    # ---------------------------------------------------------- A*
    def astar(self, src, dst, blk, vblk, W, H):
        INF = float("inf")
        bl = {L: blk[L].ravel().tolist() for L in LAYERS}
        vb = vblk.ravel().tolist()
        dst_set = dst
        tx = [c[1] for c in dst]; ty = [c[2] for c in dst]
        tbx0, tbx1, tby0, tby1 = min(tx), max(tx), min(ty), max(ty)

        def h(i, j):
            dx = max(tbx0 - i, 0, i - tbx1); dy = max(tby0 - j, 0, j - tby1)
            return max(dx, dy) + 0.414 * min(dx, dy)
        g = {}
        came = {}
        pq = []
        for (L, i, j) in src:
            k = (L, i, j)
            g[k] = 0.0
            came[k] = (None, -1)
            heapq.heappush(pq, (h(i, j), 0.0, L, i, j, -1))
        dirs = [(1, 0, 1.0), (-1, 0, 1.0), (0, 1, 1.0), (0, -1, 1.0),
                (1, 1, 1.414), (1, -1, 1.414), (-1, 1, 1.414), (-1, -1, 1.414)]
        n = 0
        while pq:
            f, gc, L, i, j, d = heapq.heappop(pq)
            if gc > g.get((L, i, j), INF) + 1e-9:
                continue
            n += 1
            if (L, i, j) in dst_set:
                path = [(L, i, j)]
                k = (L, i, j)
                while came[k][0] is not None:
                    k = came[k][0]
                    path.append(k)
                return path[::-1], n
            mult = BOTTOM_COST if L == "B" else 1.0
            for di, (dx, dy, c) in enumerate(dirs):
                ni, nj = i + dx, j + dy
                if ni < 0 or nj < 0 or ni >= W or nj >= H:
                    continue
                if bl[L][nj * W + ni]:
                    continue
                if dx and dy and (bl[L][j * W + ni] or bl[L][nj * W + i]):
                    continue
                ng = gc + c * mult + (TURN_COST if (d >= 0 and d != di) else 0.0)
                k = (L, ni, nj)
                if ng < g.get(k, INF):
                    g[k] = ng
                    came[k] = ((L, i, j), di)
                    heapq.heappush(pq, (ng + h(ni, nj), ng, L, ni, nj, di))
            if not vb[j * W + i]:
                L2 = "B" if L == "F" else "F"
                k = (L2, i, j)
                ng = gc + VIA_COST
                if ng < g.get(k, INF):
                    g[k] = ng
                    came[k] = ((L, i, j), -1)
                    heapq.heappush(pq, (ng + h(i, j), ng, L2, i, j, -1))
        return None, n

    def path_items(self, net, w, path, roi):
        i0, j0 = roi[0], roi[1]
        pts = [(L, (i + i0) * G, (j + j0) * G) for (L, i, j) in path]
        out = []
        run = [pts[0]]
        for p in pts[1:]:
            if p[0] != run[-1][0]:
                out += self._run_to_segs(net, w, run)
                out.append(B.via(net, p[1], p[2], VIA, VIA_DRILL))
                run = [p]
            else:
                run.append(p)
        out += self._run_to_segs(net, w, run)
        return out

    def _run_to_segs(self, net, w, run):
        if len(run) < 2:
            return []
        pts = [(round(r[1], 4), round(r[2], 4)) for r in run]
        simp = [pts[0]]
        for k in range(1, len(pts) - 1):
            a, b, c = simp[-1], pts[k], pts[k + 1]
            cross = (b[0] - a[0]) * (c[1] - b[1]) - (b[1] - a[1]) * (c[0] - b[0])
            if abs(cross) > 1e-9:
                simp.append(b)
        simp.append(pts[-1])
        return B.seg(net, simp, w, run[0][0])

    # ---------------------------------------------------------- net routing
    def roi_for(self, items, margin):
        x0 = min(it.bbox[0] for it in items) - margin; y0 = min(it.bbox[1] for it in items) - margin
        x1 = max(it.bbox[2] for it in items) + margin; y1 = max(it.bbox[3] for it in items) + margin
        return (max(0, int(x0 / G)), max(0, int(y0 / G)), min(NX - 1, int(x1 / G) + 1), min(NY - 1, int(y1 / G) + 1))

    def route_net(self, name, w):
        if name in VIRTUAL:
            net, terms = VIRTUAL[name]
            items = [it for it in self.items if it.kind == "pad" and (it.ref, it.pad) in terms]
            comps = [[it] for it in items]
        else:
            net = name
            comps = self.components(self.net_items(net))
        if len(comps) <= 1:
            self.log.append(f"{name}: already connected")
            return True
        t0 = time.time()
        comps.sort(key=lambda c: -sum(1 for _ in c))
        tree = list(comps[0])
        rest = comps[1:]
        while rest:
            done = False
            for margin in (4.0, 9.0, 40.0):
                roi = self.roi_for(tree + [it for c in rest for it in c], margin)
                X, Y, blk, vblk = self.maps(net, w, roi)
                H, W = X.shape
                src = self.cells_of(tree, X, Y, blk, roi)
                dst_map = {}
                for ci, c in enumerate(rest):
                    for cell in self.cells_of(c, X, Y, blk, roi):
                        dst_map[cell] = ci
                if not src or not dst_map:
                    self.log.append(f"  {name}: no free start/end cells (src={len(src)}, dst={len(dst_map)}) margin={margin}")
                    print(self.log[-1])
                    continue
                path, n = self.astar(src, set(dst_map), blk, vblk, W, H)
                if path:
                    ci = dst_map[path[-1]]
                    new = self.path_items(net, w, path, roi)
                    self.items += new
                    tree += new + rest[ci]
                    rest.pop(ci)
                    done = True
                    break
            if not done:
                self.log.append(f"{name}: FAILED with {len(rest)} unconnected group(s)")
                return False
        self.log.append(f"{name}: routed ({time.time() - t0:.1f}s)")
        return True

    # ---------------------------------------------------------- GND via fan-out
    def gnd_fanout(self):
        plane = [it for it in self.items if it.net == "GND" and "B" in it.layers]
        pads = [it for it in self.items if it.net == "GND" and it.kind == "pad" and it.layers == {"F"}]
        placed = 0
        for pad in pads:
            need = GND_VIAS.get((pad.ref, pad.pad), 1)
            # already connected to plane?
            comp = self.components([it for it in self.items if it.net == "GND"])
            mine = next(c for c in comp if pad in c)
            have = sum(1 for it in mine if it.kind == "via" and B.item_dist(it, pad) < 3.0)
            plane_ok = any("B" in it.layers for it in mine)
            need = max(0, need - have) if need > 1 else (0 if plane_ok else 1)
            for _ in range(need):
                if not self._one_via(pad):
                    self.log.append(f"GND fan-out failed at {pad.ref}.{pad.pad}")
                    break
                placed += 1
        self.log.append(f"GND fan-out: {placed} vias")

    def _one_via(self, pad, w=0.5):
        roi = self.roi_for([pad], 3.5)
        X, Y, blk, vblk = self.maps("GND", w, roi)
        # no via-in-pad and keep vias 0.25 mm apart
        i0, j0 = roi[0], roi[1]
        for it in self.items:
            if it.kind in ("pad", "via"):
                bx = it.bbox
                if bx[0] > X.max() + 1 or bx[2] < X.min() - 1 or bx[1] > Y.max() + 1 or bx[3] < Y.min() - 1:
                    continue
                d = np.min([B.vdist(p, X, Y) for p in it.prims], axis=0)
                vblk |= d < VIA / 2 + (0.25 if it.kind == "via" else 0.15)
        src = self.cells_of([pad], X, Y, blk, roi)
        H, W = X.shape
        best = None
        # BFS on F layer to nearest via-able cell
        from collections import deque
        q = deque()
        seen = {}
        for (L, i, j) in src:
            if L == "F":
                q.append((i, j)); seen[(i, j)] = None
        bl = blk["F"]
        while q:
            i, j = q.popleft()
            if not vblk[j, i]:
                best = (i, j)
                break
            for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1), (1, 1), (1, -1), (-1, 1), (-1, -1)):
                ni, nj = i + dx, j + dy
                if 0 <= ni < W and 0 <= nj < H and (ni, nj) not in seen and not bl[nj, ni]:
                    if dx and dy and (bl[j, ni] or bl[nj, i]):
                        continue
                    seen[(ni, nj)] = (i, j)
                    q.append((ni, nj))
        if not best:
            return False
        path = [best]
        while seen[path[-1]] is not None:
            path.append(seen[path[-1]])
        path = path[::-1]
        cells = [("F", i, j) for i, j in path]
        new = self.path_items("GND", w, cells, roi) if len(cells) > 1 else []
        vx, vy = (best[0] + i0) * G, (best[1] + j0) * G
        new.append(B.via("GND", round(vx, 4), round(vy, 4), VIA, VIA_DRILL))
        self.items += new
        return True

    def run(self):
        ok = True
        for name, w in ROUTES:
            ok &= self.route_net(name, w)
            print(self.log[-1], flush=True)
        self.gnd_fanout()
        print(self.log[-1], flush=True)
        return ok
