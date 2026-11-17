# SNB-1 Segment Node Board

24 V Class 2 input -> 12 V / 6 A output (TI LM5116 synchronous buck), with an optional RS-485 pixel-data
receiver (TI THVD1450) for the first node of each WS2815 run.

**Status: Rev B prototype, ready for a first prototype order.** Not yet built or bench-tested. KiCad 10 ERC and
DRC (all severities, schematic parity, zones refilled) report 0 errors / 0 warnings; reports in
`pcb/kicad/snb-erc.json` and `snb-drc.json`. Not UL-listed.

Rev B (2026-11-17): added R16, a 2.2 Ohm HO gate resistor at Q2, to damp the long gate-drive trace. Also added
manufacturing outputs in `pcb/fab/`.

- `pcb/kicad/` - KiCad project (KiCad 10; the board is saved with filled zones). `snb.kicad_dru` holds one
  custom rule: 0.2 mm clearance at the LM5116 0.65 mm-pitch pads (Power netclass is 0.3 mm elsewhere).
- `pcb/kicad/snb_bom.csv` - bill of materials (node-variant column)
- `pcb/fab/` - manufacturing package: `snb-gerbers.zip` (Gerber X2 + Excellon, origin at the bottom-left board
  corner), pick-and-place and assembly BOM per variant (`node1` = with RS-485 receiver, `node2-4` = power only),
  `snb.step` for the enclosure fit check, `snb-top.png` render.
  Order: 125 x 85 mm, 2 layers, 1.6 mm FR-4, **2 oz copper**, HASL lead-free or ENIG.
- `SNB-1_Segment_Node_Board_Design.pdf` - calculations, schematic, layout, BOM, verification and test plan
- `pcb/design/` - generators. `netlist.py` is the single source of truth; run `sh pcb/design/build.sh`
  (needs Python 3 + numpy + reportlab, and KiCad 10 for the kicad-cli ERC/DRC and fab-export steps) to
  regenerate the schematic, routed PCB, checks, manufacturing files and PDF.
  Do not hand-edit the generated `.kicad_*` files.
