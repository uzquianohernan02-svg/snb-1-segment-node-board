"""
Segment Node Board (SNB-1) - single source of truth for schematic, PCB and BOM.

24 V Class 2 feed in  ->  4 A T fuse -> reverse-polarity P-FET -> TVS -> LM5116 sync buck
-> 12 V / 6 A out to WS2815 strip injection points.
Optional (node 1 of each run only): RS-485 receiver -> 5 V pixel data (DI) + BI handling.

Each component: ref -> dict(value, sym, fp, pins{pin_number: net}, mpn, desc, dnp_variant)
'variant' : "ALL"  = fitted on every node board
            "RX"   = fitted only on the first node of a run (RS-485 receiver section)
"""

GND = "GND"

C = {}

def part(ref, value, sym, fp, pins, mpn="", desc="", variant="ALL", block=""):
    C[ref] = dict(value=value, sym=sym, fp=fp, pins=pins, mpn=mpn, desc=desc,
                  variant=variant, block=block)

# ------------------------------------------------------------------ INPUT / PROTECTION
part("J1", "24V IN", "Screw_Terminal_01x02",
     "TerminalBlock_Phoenix:TerminalBlock_Phoenix_MKDS-3-2-5.08_1x02_P5.08mm_Horizontal",
     {"1": "VIN_RAW", "2": GND}, "Phoenix 1711026 (MKDS 3/2-5,08)",
     "Terminal block 2p 5.08 mm, 24-12 AWG, 24 A", block="input")
part("F1", "4A T", "Fuse",
     "Fuse:Fuseholder_Cylinder-5x20mm_Schurter_0031_8201_Horizontal_Open",
     {"1": "VIN_RAW", "2": "VIN_F"}, "Schurter 0031.8201 holder + 4 A time-lag 5x20 fuse, DC-rated >= 32 V",
     "Field-replaceable 4 A time-delay fuse (Spec Rev 5 item 10)", block="input")
part("Q1", "SQD50P06-15L", "Q_PMOS_GDS",
     "Package_TO_SOT_SMD:TO-252-2",
     {"1": "PG", "2": "VIN_F", "3": "VIN"}, "Vishay SQD50P06-15L",
     "P-MOSFET -60 V, reverse-polarity protection", block="input")
part("R1", "10k", "R", "Resistor_SMD:R_0805_2012Metric",
     {"1": "PG", "2": GND}, "", "P-FET gate pull-down", block="input")
part("D1", "BZT52C15", "D_Zener", "Diode_SMD:D_SOD-123",
     {"1": "VIN", "2": "PG"}, "Nexperia BZT52C15", "15 V gate-source clamp (K=VIN, A=gate)", block="input")
part("D2", "SMBJ33A", "D_TVS", "Diode_SMD:D_SMB",
     {"1": "VIN", "2": GND}, "Littelfuse SMBJ33A",
     "TVS 33 V standoff, ~53 V clamp (FETs rated 60 V)", block="input")
part("C1", "100uF 50V", "CP", "Capacitor_THT:CP_Radial_D10.0mm_P5.00mm",
     {"1": "VIN", "2": GND}, "Panasonic EEU-FR1H101",
     "Bulk input, damps cable-inductance ringing on hot-plug", block="input")
for i, ref in enumerate(["C2", "C3", "C4", "C5"]):
    part(ref, "2.2uF 100V", "C", "Capacitor_SMD:C_1812_4532Metric",
         {"1": "VIN", "2": GND}, "TDK C4532X7R2A225M", "Input ceramic X7R", block="buck")
part("C6", "100nF 100V", "C", "Capacitor_SMD:C_0805_2012Metric",
     {"1": "VIN", "2": GND}, "TDK C2012X7R2A104M", "VIN pin bypass", block="buck")

# ------------------------------------------------------------------ LM5116 BUCK CONTROLLER
part("U1", "LM5116MH", "LM5116",
     "Package_SO:HTSSOP-20-1EP_4.4x6.5mm_P0.65mm_EP2.85x4mm",
     {"1": "VIN", "2": "UVLO", "3": "RT", "4": "EN", "5": "RAMP", "6": GND, "7": "SS",
      "8": "FB", "9": "COMP", "10": "+12V", "11": "DEMB", "12": "CS", "13": GND,
      "14": GND, "15": "LO", "16": "VCC", "17": GND, "18": "HB", "19": "HO", "20": "SW",
      "21": GND},
     "TI LM5116MHX/NOPB", "Synchronous buck controller, 6-100 V", block="buck")
part("R2", "100k", "R", "Resistor_SMD:R_0603_1608Metric", {"1": "VIN", "2": "UVLO"},
     "", "UVLO top (RUV2 > 500 x 60 V)", block="buck")
part("R3", "7.87k", "R", "Resistor_SMD:R_0603_1608Metric", {"1": "UVLO", "2": GND},
     "", "UVLO bottom: shutdown at ~16 V", block="buck")
part("C7", "1nF", "C", "Capacitor_SMD:C_0603_1608Metric", {"1": "UVLO", "2": GND},
     "", "UVLO filter", block="buck")
part("R4", "12.4k", "R", "Resistor_SMD:R_0603_1608Metric", {"1": "RT", "2": GND},
     "", "RT: 250 kHz", block="buck")
part("R5", "100k", "R", "Resistor_SMD:R_0603_1608Metric", {"1": "VIN", "2": "EN"},
     "", "EN pull-up to VIN (EN rated 100 V)", block="buck")
part("C8", "470pF C0G", "C", "Capacitor_SMD:C_0603_1608Metric", {"1": "RAMP", "2": GND},
     "", "CRAMP, C0G 5%", block="buck")
part("R6", "464k", "R", "Resistor_SMD:R_0603_1608Metric", {"1": "VCC", "2": "RAMP"},
     "", "RRAMP to VCC (VOUT > 7.5 V slope comp)", block="buck")
part("C9", "100nF", "C", "Capacitor_SMD:C_0603_1608Metric", {"1": "SS", "2": GND},
     "", "Soft start ~12 ms", block="buck")
part("R7", "1.24k 1%", "R", "Resistor_SMD:R_0603_1608Metric", {"1": "FB", "2": GND},
     "", "RFB1", block="buck")
part("R8", "11.0k 1%", "R", "Resistor_SMD:R_0603_1608Metric", {"1": "+12V", "2": "FB"},
     "", "RFB2 -> VOUT = 11.99 V", block="buck")
part("R9", "26.1k", "R", "Resistor_SMD:R_0603_1608Metric", {"1": "COMP", "2": "CZ"},
     "", "RCOMP", block="buck")
part("C10", "3.9nF", "C", "Capacitor_SMD:C_0603_1608Metric", {"1": "CZ", "2": "FB"},
     "", "CCOMP (zero ~1.6 kHz)", block="buck")
part("C11", "56pF C0G", "C", "Capacitor_SMD:C_0603_1608Metric", {"1": "COMP", "2": "FB"},
     "", "CHF", block="buck")
part("R10", "10k", "R", "Resistor_SMD:R_0603_1608Metric", {"1": "DEMB", "2": GND},
     "", "RDEMB: fully synchronous after soft start", block="buck")
part("C12", "1uF 25V", "C", "Capacitor_SMD:C_0805_2012Metric", {"1": "VCC", "2": GND},
     "TDK C2012X7R1E105K", "VCC decoupling", block="buck")
part("D3", "BAS21", "D_SOT23_A1K3", "Package_TO_SOT_SMD:SOT-23",
     {"1": "VCC", "3": "HB"}, "Nexperia BAS21", "Bootstrap diode 250 V", block="buck")
part("C13", "1uF 25V", "C", "Capacitor_SMD:C_0805_2012Metric", {"1": "HB", "2": "SW"},
     "TDK C2012X7R1E105K", "Bootstrap capacitor", block="buck")

# ------------------------------------------------------------------ POWER STAGE
part("Q2", "Si7850DP", "Q_NMOS_PPAK",
     "Package_SO:PowerPAK_SO-8_Single",
     {"1": "SW", "2": "SW", "3": "SW", "4": "HOG", "5": "VIN"}, "Vishay Si7850DP", "High-side N-MOSFET 60 V", block="power")
part("R16", "2.2", "R", "Resistor_SMD:R_0603_1608Metric", {"1": "HOG", "2": "HO"},
     "", "HO gate resistor at Q2 (damps long gate trace; 0-4.7 Ohm, tune on bench)", block="power")
part("Q3", "Si7850DP", "Q_NMOS_PPAK",
     "Package_SO:PowerPAK_SO-8_Single",
     {"1": "CS", "2": "CS", "3": "CS", "4": "LO", "5": "SW"}, "Vishay Si7850DP", "Low-side N-MOSFET 60 V", block="power")
part("R11", "10m 1%", "R", "Resistor_SMD:R_2010_5025Metric", {"1": "CS", "2": GND},
     "IRC LRC-LRF2010-01-R010-F", "Current sense RS: limit 6.2 A min / 7.8 A typ", block="power")
part("L1", "15uH", "L", "Inductor_SMD:L_Coilcraft_XAL1010-XXX",
     {"1": "SW", "2": "+12V"}, "Coilcraft XAL1010-153ME",
     "15 uH, Isat >= 13 A, shielded", block="power")
part("R12", "4.7", "R", "Resistor_SMD:R_1206_3216Metric", {"1": "SW", "2": "SNB"},
     "", "Snubber R (tune on bench)", block="power")
part("C14", "1nF 100V", "C", "Capacitor_SMD:C_0805_2012Metric", {"1": "SNB", "2": GND},
     "", "Snubber C (tune on bench)", block="power")
for ref in ["C15", "C16", "C17", "C18"]:
    part(ref, "22uF 25V", "C", "Capacitor_SMD:C_1210_3225Metric",
         {"1": "+12V", "2": GND}, "Murata GRM32ER71E226KE15", "Output ceramic X7R", block="output")
part("C19", "220uF 25V", "CP", "Capacitor_THT:CP_Radial_D8.0mm_P3.50mm",
     {"1": "+12V", "2": GND}, "Panasonic 25SVPF220M (OS-CON) or equiv. polymer",
     "Output bulk polymer, ESR ~20 mOhm", block="output")

# ------------------------------------------------------------------ 12 V OUTPUTS + LED
part("J3", "12V OUT A", "Screw_Terminal_01x02",
     "TerminalBlock_Phoenix:TerminalBlock_Phoenix_MKDS-3-2-5.08_1x02_P5.08mm_Horizontal",
     {"1": "+12V", "2": GND}, "Phoenix 1711026", "12 V to strip injection (start)", block="output")
part("J4", "12V OUT B", "Screw_Terminal_01x02",
     "TerminalBlock_Phoenix:TerminalBlock_Phoenix_MKDS-3-2-5.08_1x02_P5.08mm_Horizontal",
     {"1": "+12V", "2": GND}, "Phoenix 1711026", "12 V to strip injection (mid/end)", block="output")
part("R13", "4.7k", "R", "Resistor_SMD:R_0805_2012Metric", {"1": "+12V", "2": "LEDA"},
     "", "LED resistor (~2 mA)", block="output")
part("D4", "GRN", "LED", "LED_SMD:LED_0805_2012Metric", {"1": GND, "2": "LEDA"},
     "", "12 V present", block="output")

# ------------------------------------------------------------------ RS-485 RX (node 1 only)
part("U2", "L78L05", "LDO_SOT89", "Package_TO_SOT_SMD:SOT-89-3",
     {"1": "+5V", "2": GND, "3": "+12V"}, "ST L78L05ABUTR", "5 V LDO for receiver",
     variant="RX", block="rx")
part("C20", "1uF 25V", "C", "Capacitor_SMD:C_0805_2012Metric", {"1": "+12V", "2": GND},
     "", "LDO input", variant="RX", block="rx")
part("C21", "1uF 25V", "C", "Capacitor_SMD:C_0805_2012Metric", {"1": "+5V", "2": GND},
     "", "LDO output", variant="RX", block="rx")
part("U3", "THVD1450DR", "RS485", "Package_SO:SOIC-8_3.9x4.9mm_P1.27mm",
     {"1": "RXO", "2": GND, "3": GND, "4": GND, "5": GND, "6": "RS485_A", "7": "RS485_B",
      "8": "+5V"}, "TI THVD1450DR (SOIC-8)", "RS-485 transceiver 50 Mbps, receive-only", variant="RX", block="rx")
part("C22", "100nF", "C", "Capacitor_SMD:C_0603_1608Metric", {"1": "+5V", "2": GND},
     "", "U3 decoupling", variant="RX", block="rx")
part("J2", "RS485 IN", "Screw_Terminal_01x03",
     "TerminalBlock_Phoenix:TerminalBlock_Phoenix_MKDS-1,5-3-5.08_1x03_P5.08mm_Horizontal",
     {"1": "RS485_A", "2": "RS485_B", "3": GND}, "Phoenix 1715734",
     "Twisted-pair data from controller TX", variant="RX", block="rx")
part("D5", "SM712", "SM712", "Package_TO_SOT_SMD:SOT-23",
     {"1": "RS485_A", "2": "RS485_B", "3": GND}, "Semtech SM712.TCT", "RS-485 line TVS",
     variant="RX", block="rx")
part("R14", "120", "R", "Resistor_SMD:R_0805_2012Metric", {"1": "RS485_A", "2": "TERM"},
     "", "Line termination", variant="RX", block="rx")
part("JP1", "TERM", "SolderJumper_2",
     "Jumper:SolderJumper-2_P1.3mm_Open_RoundedPad1.0x1.5mm",
     {"1": "TERM", "2": "RS485_B"}, "", "Close to terminate (end of line)", variant="RX", block="rx")
part("R15", "33", "R", "Resistor_SMD:R_0603_1608Metric", {"1": "RXO", "2": "DO"},
     "", "Data series resistor", variant="RX", block="rx")
part("JP2", "BI SEL", "SolderJumper_3",
     "Jumper:SolderJumper-3_P1.3mm_Open_RoundedPad1.0x1.5mm",
     {"1": GND, "2": "BI", "3": "DO"}, "", "Bridge 1-2 at assembly: BI = GND (default); 2-3: BI = DI", variant="RX", block="rx")
part("J5", "DATA OUT", "Screw_Terminal_01x03",
     "TerminalBlock_Phoenix:TerminalBlock_Phoenix_MKDS-1,5-3-5.08_1x03_P5.08mm_Horizontal",
     {"1": "DO", "2": "BI", "3": GND}, "Phoenix 1715734", "To strip DI / BI / GND",
     variant="RX", block="rx")

# ------------------------------------------------------------------ MECHANICAL
for i in range(1, 5):
    part(f"H{i}", "M3", "MountingHole", "MountingHole:MountingHole_3.2mm_M3",
         {}, "", "Mounting hole, not bonded (Class 2 output not earthed)", block="mech")


def nets():
    n = {}
    for ref, p in C.items():
        for pin, net in p["pins"].items():
            n.setdefault(net, []).append((ref, pin))
    return n


if __name__ == "__main__":
    for net, conns in sorted(nets().items()):
        print(f"{net:10s} {len(conns):3d}  " + " ".join(f"{r}.{p}" for r, p in conns))
