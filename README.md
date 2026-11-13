# SNB-1 Segment Node Board

24 V Class 2 input -> 12 V / 6 A output (TI LM5116 synchronous buck), with an optional RS-485 pixel-data
receiver (TI THVD1450) for the first node of each WS2815 run.

**Status: Rev A prototype for review.** Not yet built. KiCad ERC/DRC have not been run (checked with the
scripts in `pcb/design` only). Not UL-listed.

- `pcb/kicad/` - KiCad project (opens in KiCad 9 and 10). Press **B** to fill zones, then run ERC/DRC.
- `pcb/kicad/snb_bom.csv` - bill of materials (node-variant column)
- `SNB-1_Segment_Node_Board_Design.pdf` - calculations, schematic, layout, BOM, verification and test plan
- `pcb/design/` - generators. `netlist.py` is the single source of truth; run `sh pcb/design/build.sh`
  (needs Python 3 + numpy + reportlab) to regenerate the schematic, routed PCB, checks and PDF.
  Do not hand-edit the generated `.kicad_*` files.
