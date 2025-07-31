# app.py

import streamlit as st
import pandas as pd
import pdfplumber
import openpyxl
import re

# ---- Knowledge Bases ----

STANDARDS_KNOWLEDGE_BASE = {
    "IP Rating": "IEC 60529", "Short Circuit Protection": "AIS-156 / IEC 62133",
    "Overcharge Protection": "AIS-156 / ISO 12405-4", "Over-discharge Protection": "AIS-156 / ISO 12405-4",
    "Cell Balancing": "AIS-156", "Temperature Protection": "AIS-156 / ISO 12405-4",
    "Communication Interface (CAN)": "ISO 11898", "Vibration Test": "IEC 60068-2-6 / AIS-048",
    "Thermal Runaway Test": "AIS-156 Amendment 3", "Braking Performance Test": "EN 15194 / ISO 4210-2",
    "Frame Fatigue Test": "ISO 4210-6", "EMC Test": "IEC 61000 / EN 15194"
}

TEST_CASE_KNOWLEDGE_BASE = {
    "over-voltage test": {"requirement": "The DUT shall withstand a specified over-voltage condition without damage.", "equipment": ["Programmable DC Power Supply", "DMM", "Oscilloscope", "Load Bank"]},
    "short-circuit protection": {"requirement": "The DUT shall detect and safely interrupt a short-circuit condition within a specified time limit.", "equipment": ["High-Current Power Supply", "Oscilloscope with Current Probe", "Shorting Switch"]},
    "line regulation test": {"requirement": "Output voltage must remain within tolerance as input AC voltage varies.", "equipment": ["Programmable AC Source", "Precision DMM", "Electronic Load"]},
    "load regulation test": {"requirement": "Output voltage must remain within tolerance as the load varies from no-load to full-load.", "equipment": ["Power Source", "Precision DMM", "Programmable Electronic Load"]},
    "efficiency test": {"requirement": "The system must meet or exceed a specified efficiency percentage at various load points.", "equipment": ["Power Analyzer", "Power Source", "Electronic Load or Dynamometer"]},
    "insulation resistance test": {"requirement": "Resistance between live circuits and chassis/ground must be above a minimum value (e.g., >10 MΩ).", "equipment": ["Insulation Resistance Tester (Megohmmeter)"]},
    "dielectric withstand (hipot) test": {"requirement": "Insulation must withstand a high voltage between live parts and chassis without breakdown.", "equipment": ["Hipot Tester"]},
    "electromagnetic compatibility (emc) test": {"requirement": "The device must operate correctly in its EM environment and not emit interference.", "equipment": ["Anechoic Chamber", "Spectrum Analyzer", "LISN", "EMI Receiver"]},
    "thermal cycling": {"requirement": "The DUT must operate reliably across a specified temperature range over multiple cycles.", "equipment": ["Thermal Chamber", "Data Logger", "Power Supply"]},
    "vibration test": {"requirement": "The DUT must withstand vibrations simulating operational conditions without failure.", "equipment": ["Vibration Shaker Table", "Accelerometer", "Control System"]},
    "ip rating test": {"requirement": "The enclosure must provide protection against ingress of solids and water to its specified IP rating.", "equipment": ["Dust Chamber", "Water Jet/Spray Nozzles"]},
    "frame fatigue test": {"requirement": "The frame must endure a specified number of load cycles without cracks or structural failure.", "equipment": ["Fatigue Test Rig", "Strain Gauges", "Data Acquisition System"]},
    "braking performance test": {"requirement": "The braking system must stop the e-bike from a specified speed within a maximum distance.", "equipment": ["Brake Test Dynamometer or GPS System", "Load Cells"]},
    "salt spray test": {"requirement": "Coated components must resist corrosion after exposure to a salt spray environment.", "equipment": ["Salt Spray Chamber", "Saline Solution"]}
}

COMPONENT_KNOWLEDGE_BASE = {
    "bq76952": {"manufacturer": "Texas Instruments", "function": "16-Series Battery Monitor & Protector", "voltage": "Up to 80V", "package": "TQFP-48"},
    "stm32g431": {"manufacturer": "STMicroelectronics", "function": "MCU for Motor Control", "voltage": "3.3V", "package": "LQFP-48"},
    "l6234": {"manufacturer": "STMicroelectronics", "function": "DMOS Driver for Brushless DC Motor", "voltage": "52V", "package": "PowerSO20"},
    "lm358": {"manufacturer": "Texas Instruments", "function": "Dual Op-Amp", "voltage": "3V to 32V", "package": "SOIC-8"},
    "tps54560": {"manufacturer": "Texas Instruments", "function": "60V, 5A Step-Down DC-DC Converter", "voltage": "4.5V to 60V Input", "package": "HTSSOP-8"},
    "irfb4110": {"manufacturer": "Infineon", "function": "N-Channel MOSFET", "voltage": "100V", "current": "180A", "package": "TO-220AB"},
    "irfz44n": {"manufacturer": "Vishay", "function": "N-Channel MOSFET", "voltage": "55V", "current": "49A", "package": "TO-220AB"},
    "bs170": {"manufacturer": "onsemi", "function": "N-Channel Small Signal MOSFET", "voltage": "60V", "current": "500mA", "package": "TO-92 (Leaded)"},
    "mmbt3904": {"manufacturer": "onsemi", "function": "NPN BJT", "voltage": "40V", "current": "200mA", "package": "SOT-23 (SMD)"},
    "1n4007": {"manufacturer": "Multiple", "function": "General Purpose Rectifier Diode", "voltage": "1000V", "current": "1A", "package": "DO-41 (Leaded)"},
    "1n4733a": {"manufacturer": "Vishay", "function": "5.1V Zener Diode", "voltage": "5.1V", "power": "1W", "package": "DO-41 (Leaded)"},
    "mbr20100ct": {"manufacturer": "onsemi", "function": "Dual Schottky Rectifier", "voltage": "100V", "current": "20A", "package": "TO-220AB"},
    "ss14": {"manufacturer": "Vishay", "function": "Schottky Rectifier Diode", "voltage": "40V", "current": "1A", "package": "SMA (SMD)"},
    "crcw120610k0fkea": {"manufacturer": "Vishay", "function": "Thick Film Chip Resistor", "value": "10 kΩ", "tolerance": "±1%", "package": "1206 (SMD)"},
    "cfr-25jb-52-1k": {"manufacturer": "Yageo", "function": "Carbon Film Resistor", "value": "1 kΩ", "tolerance": "±5%", "package": "Axial (Leaded)"},
    "c1206c104k5ractu": {"manufacturer": "KEMET", "function": "MLCC", "value": "100 nF (0.1µF)", "voltage": "50V", "package": "1206 (SMD)"},
    "eeufc1h101": {"manufacturer": "Panasonic", "function": "Aluminum Electrolytic Capacitor", "value": "100 µF", "voltage": "50V", "package": "Radial (Leaded)"}
}

# --- Helper Functions ---

def parse_report(uploaded_file):
    try:
        if uploaded_file.type == "application/pdf":
            with pdfplumber.open(uploaded_file) as pdf: text = "".join(page.extract_text() + "\n" for page in pdf.pages)
            return parse_report_custom(text)
    except Exception as e: st.error(f"Error parsing file: {e}")
    return None

def parse_report_custom(text):
    lines, parsed_tests, current_test = text.split('\n'), [], None
    for line in lines:
        line = line.strip()
        if not line: continue
        if match := re.match(r'^\d+\.\s+(.*)', line):
            if current_test: parsed_tests.append(current_test)
            test_name = match.group(1).strip().replace(':', '')
            standard = STANDARDS_KNOWLEDGE_BASE.get(test_name, "N/A")
            current_test = {'Name': test_name, 'Standard': standard, 'Result': 'N/A', 'Expected': 'N/A', 'Actual': 'N/A'}
            continue
        if current_test:
            if match := re.match(r'-\s*Result\s*:\s*(.*)', line, re.I): current_test['Result'] = match.group(1).strip()
            elif match := re.match(r'-\s*(?:Requirement|Required|Limit)\s*:\s*(.*)', line, re.I): current_test['Expected'] = match.group(1).strip()
            elif match := re.match(r'-\s*(?:Triggered at|Cut-off at|Maximum Deviation:)\s*(.*)', line, re.I): current_test['Actual'] = match.group(1).strip()
            elif not line.startswith('-') and current_test['Actual'] == 'N/A' and not re.match(r'^\d+$', line): current_test['Actual'] = line
    if current_test: parsed_tests.append(current_test)
    return parsed_tests

def verify_report(parsed_data):
    return [f"Test Failed: {test.get('Name', 'Unknown')}" for test in parsed_data if isinstance(parsed_data, list) and 'FAIL' in test.get('Result', '').upper()]

def generate_requirements(test_cases):
    reqs, default_info = [], {"requirement": "Generic requirement.", "equipment": ["Not specified."]}
    for i, user_input_line in enumerate(test_cases):
        found_match = False
        for known_test, details in TEST_CASE_KNOWLEDGE_BASE.items():
            if known_test.replace(" test", "") in user_input_line.lower():
                reqs.append({"Test Case": known_test.title(), "Requirement ID": f"REQ_{i+1:03d}", "Requirement Description": details["requirement"], "Required Equipment": ", ".join(details["equipment"])})
                found_match = True
        if not found_match: reqs.append({"Test Case": user_input_line, "Requirement ID": f"REQ_{i+1:03d}", **default_info})
    return pd.DataFrame(reqs)

# ---- Streamlit App Layout----

st.set_page_config(page_title="E-Bike Compliance & Safety Tool", layout="wide")
st.title("E-Bike Compliance & Safety Verification Tool")

option = st.sidebar.radio("Select a Module", (
    "Upload & Verify Test Report", "Test Requirement Generation", "Component Lookup & Database", "Dashboard & Analytics"))

if option == "Upload & Verify Test Report":
    st.header("Upload & Verify Test Report")
    uploaded_file = st.file_uploader("Choose a report file (.pdf)", type=['pdf'])
    if uploaded_file:
        parsed_data = parse_report(uploaded_file)
        if isinstance(parsed_data, list) and parsed_data:
            st.subheader("Parsed Report Summary")
            for r in parsed_data:
                st.markdown(
                    f"**🧪 Test:** {r.get('Name', 'N/A')}\n"
                    f"**📘 Standard:** {r.get('Standard', 'N/A')}\n"
                    f"**📊 Result:** {r.get('Result', 'N/A')}\n"
                    f"**🎯 Expected:** {r.get('Expected', 'N/A')}\n"
                    f"**📌 Actual:** {r.get('Actual', 'N/A')}\n---"
                )
        if parsed_data and st.button("Verify Report"):
            issues = verify_report(parsed_data)
            if issues:
                st.error(f"Verification Complete - {len(issues)} Issues Found:")
                for i in issues:
                    st.write(f"- {i}")
            else:
                st.success("Verification Complete: Report complies with all checks.")

elif option == "Test Requirement Generation":
    st.header("Generate Test Requirements from Test Cases")
    st.info("Enter test cases below. The system will generate detailed requirements in a readable format.")
    default_test_cases = "line and load regulation\nframe fatigue test\nemc test"
    test_case_text = st.text_area("Enter test cases", default_test_cases, height=150)
    if st.button("Generate Requirements"):
        test_cases = [line.strip() for line in test_case_text.split('\n') if line.strip()]
        if test_cases:
            requirements_df = generate_requirements(test_cases)
            st.subheader("Generated Requirements & Equipment")
            for _, row in requirements_df.iterrows():
                st.markdown(
                    f"**📝 Test Case:** {row['Test Case']}\n"
                    f"**🆔 Requirement ID:** {row['Requirement ID']}\n"
                    f"**📋 Requirement Description:**"
                )
                st.info(row['Requirement Description'])
                st.markdown(f"**🛠️ Required Equipment:** {row['Required Equipment']}\n---")
            csv = requirements_df.to_csv(index=False).encode('utf-8')
            st.download_button("Download as CSV", data=csv, file_name="requirements.csv", mime="text/csv")

elif option == "Component Lookup & Database":
    st.header("Component Lookup & Database")
    st.info(
        "Enter a full or partial component part number to search the internal knowledge base. "
        "If not found, you can use the web search buttons to quickly look up datasheet/spec info."
    )

    st.subheader("Component Lookup")
    part_number_to_find = st.text_input(
        "Enter Part Number to Look Up",
        help="Not case-sensitive. Partial matches work."
    ).lower().strip()

    if st.button("Find Component Info"):
        found_info, found_key = None, None
        if part_number_to_find:
            for key in COMPONENT_KNOWLEDGE_BASE:
                if key in part_number_to_find:
                    found_key, found_info = key, COMPONENT_KNOWLEDGE_BASE[key]
                    break
        if found_info:
            st.session_state.found_component = found_info
            st.session_state.found_component['part_number'] = part_number_to_find.upper()
            st.success(f"Found a match: '{found_key}' in your input '{part_number_to_find}'. Details below.")
        else:
            st.session_state.found_component = {}
            st.warning("Part number not found in knowledge base. You can add it manually below.")

            # --- Web Search Shortcuts ---
            if part_number_to_find:
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.markdown(
                        f"[🔎 Search Octopart](https://octopart.com/search?q={part_number_to_find})",
                        unsafe_allow_html=True)
                with col2:
                    st.markdown(
                        f"[🔎 Search Digi-Key](https://www.digikey.com/en/products/result?s={part_number_to_find})",
                        unsafe_allow_html=True)
                with col3:
                    st.markdown(
                        f"[🔎 Search Mouser](https://www.mouser.com/Search/Refine?Keyword={part_number_to_find})",
                        unsafe_allow_html=True)
                st.info(
                    "Click a web search link above to find datasheet/specs. "
                    "Copy the key datasheet fields back into the form to add a new part below."
                )
    st.markdown("---")
    st.subheader("Add Component to Project Database")
    default_data = st.session_state.get('found_component', {})
    with st.form("component_form", clear_on_submit=True):
        pn = st.text_input("Part Number", value=default_data.get("part_number", ""))
        mfg = st.text_input("Manufacturer", value=default_data.get("manufacturer", ""))
        func = st.text_input("Function", value=default_data.get("function", ""))
        p1_label = "Value" if "resistor" in func.lower() or "capacitor" in func.lower() else "Voltage"
        p1_val = default_data.get("value", default_data.get("voltage", ""))
        p1 = st.text_input(p1_label, value=p1_val)
        p2_label = "Package" if "resistor" in func.lower() or "capacitor" in func.lower() else "Current"
        p2_val = default_data.get("package", default_data.get("current", ""))
        p2 = st.text_input(p2_label, value=p2_val)
        if st.form_submit_button("Add Component"):
            if pn:
                if 'project_db' not in st.session_state: st.session_state.project_db = pd.DataFrame()
                new_row = pd.DataFrame([{
                    "Part Number": pn, "Manufacturer": mfg, "Function": func,
                    p1_label: p1, p2_label: p2
                }])
                st.session_state.project_db = pd.concat([st.session_state.project_db, new_row], ignore_index=True)
                st.success(f"Component '{pn}' added to your project database.")
    if 'project_db' in st.session_state and not st.session_state.project_db.empty:
        st.markdown("---")
        st.subheader("Project Component Database")
        st.dataframe(st.session_state.project_db.astype(str))
else: # Dashboard
    st.header("Dashboard & Analytics")
    col1, col2, col3 = st.columns(3)
    col1.metric("Reports Verified", "0")
    col2.metric("Requirements Generated", "0")
    col3.metric("Components in DB", len(st.session_state.get('project_db', [])))
