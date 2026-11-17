#!/bin/sh
# Rebuild everything: schematic, routed PCB, checks, design PDF + BOM.
cd "$(dirname "$0")"
export KICAD_FP_DIR="$PWD/lib/footprints" KICAD_POWER_LIB="$PWD/lib/power.kicad_sym" KICAD_TEMPLATE_DIR="$PWD/lib"
python -X utf8 gen_sch.py && python -X utf8 check_sch.py && python -X utf8 build_pcb.py && \
python -X utf8 verify_all.py && python -X utf8 kicad_check.py && python -X utf8 kicad_fab.py && python -X utf8 gen_doc.py ../../SNB-1_Segment_Node_Board_Design.pdf
