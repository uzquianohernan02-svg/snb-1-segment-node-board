# SNB-1 Segment Node Board

24 V Class 2 input -> 12 V / 6 A output (TI LM5116 synchronous buck), with an optional RS-485 pixel-data
receiver (TI THVD1450) for the first node of each WS2815 run.

**Status: Rev A prototype for review.** Not yet built. KiCad 10 ERC and DRC (all severities, schematic
parity, zones refilled) report 0 errors / 0 warnings; reports in `pcb/kicad/snb-erc.json` and `snb-drc.json`.
Not UL-listed.

- `pcb/kicad/` - KiCad project (KiCad 10; the board is saved with filled zones). `snb.kicad_dru` holds one
  custom rule: 0.2 mm clearance at the LM5116 0.65 mm-pitch pads (Power netclass is 0.3 mm elsewhere).
- `pcb/kicad/snb_bom.csv` - bill of materials (node-variant column)
- `SNB-1_Segment_Node_Board_Design.pdf` - calculations, schematic, layout, BOM, verification and test plan
- `pcb/design/` - generators. `netlist.py` is the single source of truth; run `sh pcb/design/build.sh`
  (needs Python 3 + numpy + reportlab, and KiCad 10 for the kicad-cli ERC/DRC step) to regenerate the
  schematic, routed PCB, checks and PDF.
  Do not hand-edit the generated `.kicad_*` files.
