import streamlit as st
import pandas as pd
from utils.supabase_client import supabase
from datetime import datetime
import io

st.set_page_config(page_title="Time Ticket Entry", layout="wide")
st.title("⏱️ Time Ticket Entry")

# --- Load Basic Data ---
def get_active_jobs():
    try:
        res = supabase.table("master_project").select("*").eq("status", "Active").execute()
        return res.data if res.data else []
    except: return []

def get_saved_maps():
    try:
        res = supabase.table("client_import_maps").select("*").order("created_at", desc=True).execute()
        return res.data if res.data else []
    except: return []

jobs_data = get_active_jobs()
job_list = [j['job_number'] for j in jobs_data]
saved_maps = get_saved_maps()

# --- Initialize Session State ---
if "labour_df" not in st.session_state:
    st.session_state.labour_df = pd.DataFrame(columns=["Crew Name", "Trade", "Reg Hrs", "OT Hrs", "Travel Hrs", "Subsistence"])
if "equip_df" not in st.session_state:
    st.session_state.equip_df = pd.DataFrame(columns=["Unit #", "Equipment Name", "Operator", "Usage Hrs"])
if "misc_df" not in st.session_state:
    st.session_state.misc_df = pd.DataFrame(columns=["Description", "Qty", "Rate", "Total"])

# ==========================================
# Entry Mode Selection
# ==========================================
entry_mode = st.radio("Entry Mode", ["Manual Entry", "Import from Excel"], horizontal=True)

# 1. Header Section (Moved up to be selected BEFORE import)
st.divider()
st.subheader("1️⃣ Ticket Details")
c1, c2, c3, c4 = st.columns(4)
with c1: 
    # Capture the selected Job Number to filter data
    selected_job_num = st.selectbox("Job #", job_list)
with c2: ticket_date = st.date_input("Ticket Date", datetime.now())
with c3: ticket_number = st.text_input("Ticket #", placeholder="FT-260225-01")
with c4: billing_type = st.selectbox("Billing", ["T&M", "Lump Sum", "Unit Price"])

cc1, cc2, cc3 = st.columns(3)
with cc1: afe = st.text_input("AFE #")
with cc2: po = st.text_input("PO #")
with cc3: desc = st.text_input("Description")


# ==========================================
# Import Logic
# ==========================================
if entry_mode == "Import from Excel":
    st.divider()
    st.subheader("📂 Excel Import")
    
    # Select Map Settings
    map_options = {m['map_name']: m for m in saved_maps}
    
    if not map_options:
        st.warning("⚠️ No import templates found. Please configure them in 'Settings'.")
    else:
        c_imp1, c_imp2 = st.columns([1, 2])
        with c_imp1:
            selected_profile_name = st.selectbox("Select Profile", list(map_options.keys()))
            selected_map = map_options[selected_profile_name]
        
        with c_imp2:
            uploaded_file = st.file_uploader("Upload Excel File", type=["xlsx", "xlsm", "xls", "csv"], label_visibility="collapsed")

        if uploaded_file and st.button("🚀 Process & Apply Data", type="primary"):
            try:
                # 1. Read File
                header_idx = selected_map['header_row_idx']
                if uploaded_file.name.endswith('.csv'):
                    df = pd.read_csv(uploaded_file, header=header_idx)
                else:
                    df = pd.read_excel(uploaded_file, header=header_idx, engine='openpyxl')
                
                # 2. Filter by Job Number (Multi-job sheet support)
                mapping = selected_map['mapping_data']
                job_col_map = mapping.get("job_num")
                
                # If a Job Number column is mapped, filter the dataframe
                if job_col_map and job_col_map != "(Not Selected)" and job_col_map in df.columns:
                    # Convert to string for safe comparison
                    df[job_col_map] = df[job_col_map].astype(str).str.strip()
                    original_count = len(df)
                    
                    # Keep rows where Job # matches the selected job
                    df = df[df[job_col_map] == str(selected_job_num)]
                    filtered_count = len(df)
                    
                    if filtered_count < original_count:
                        st.info(f"ℹ️ Filtered data: Found {filtered_count} rows matching Job '{selected_job_num}' (out of {original_count}).")
                
                # 3. Transform Data
                
                # (1) Labor Transformation
                if mapping.get("crew_name") != "(Not Selected)":
                    new_labor = pd.DataFrame()
                    if mapping["crew_name"] in df.columns:
                        new_labor["Crew Name"] = df[mapping["crew_name"]]
                        
                        # Trade
                        if mapping.get("trade") != "(Not Selected)" and mapping["trade"] in df.columns:
                            new_labor["Trade"] = df[mapping["trade"]]
                        else:
                            new_labor["Trade"] = "Laborer"
                            
                        # Hours
                        if mapping.get("reg_hrs") != "(Not Selected)" and mapping["reg_hrs"] in df.columns:
                            new_labor["Reg Hrs"] = pd.to_numeric(df[mapping["reg_hrs"]], errors='coerce').fillna(0)
                        else: new_labor["Reg Hrs"] = 0
                        
                        if mapping.get("ot_hrs") != "(Not Selected)" and mapping["ot_hrs"] in df.columns:
                            new_labor["OT Hrs"] = pd.to_numeric(df[mapping["ot_hrs"]], errors='coerce').fillna(0)
                        else: new_labor["OT Hrs"] = 0
                        
                        new_labor["Subsistence"] = False
                        
                        # Remove empty rows
                        new_labor = new_labor[new_labor["Crew Name"].notna()]
                        st.session_state.labour_df = new_labor
                
                # (2) Equipment Transformation
                if mapping.get("unit_num") != "(Not Selected)":
                    new_equip = pd.DataFrame()
                    if mapping["unit_num"] in df.columns:
                        new_equip["Unit #"] = df[mapping["unit_num"]]
                        
                        if mapping.get("eq_name") != "(Not Selected)" and mapping["eq_name"] in df.columns:
                            new_equip["Equipment Name"] = df[mapping["eq_name"]]
                        else: new_equip["Equipment Name"] = "Equipment"
                        
                        if mapping.get("usage_hrs") != "(Not Selected)" and mapping["usage_hrs"] in df.columns:
                            new_equip["Usage Hrs"] = pd.to_numeric(df[mapping["usage_hrs"]], errors='coerce').fillna(0)
                        else: new_equip["Usage Hrs"] = 0
                        
                        new_equip = new_equip[new_equip["Unit #"].notna()]
                        st.session_state.equip_df = new_equip

                st.success("✅ Data applied below!")
                st.rerun()
                
            except Exception as e:
                st.error(f"Data processing failed: {e}")


# ==========================================
# [Common] Data Review Section
# ==========================================
st.divider()
st.subheader("2️⃣ Review & Submit")

# Data Editors
st.markdown("##### 👷‍♂️ Labor")
edited_labour = st.data_editor(st.session_state.labour_df, num_rows="dynamic", use_container_width=True, key="ed_labour")

st.markdown("##### 🚜 Equipment")
edited_equip = st.data_editor(st.session_state.equip_df, num_rows="dynamic", use_container_width=True, key="ed_equip")

st.markdown("##### 📦 Material / Misc")
edited_misc = st.data_editor(st.session_state.misc_df, num_rows="dynamic", use_container_width=True, key="ed_misc")

# Submit Button
submit_btn = st.button("✅ Final Submit", type="primary", use_container_width=True)

if submit_btn:
    if not ticket_number:
        st.error("Ticket # is required!")
    else:
        try:
            # Save Header
            header_data = {
                "ticket_number": ticket_number, "job_number": selected_job_num,
                "ticket_date": str(ticket_date), "afe_number": afe, "po_number": po,
                "work_description": desc, "status": "Ticket Created"
            }
            supabase.table("field_tickets").insert(header_data).execute()

            # Save Labor
            labor_data = []
            for _, row in edited_labour.iterrows():
                if row.get("Crew Name"):
                    labor_data.append({
                        "ticket_number": ticket_number, "crew_name": row["Crew Name"],
                        "trade": row.get("Trade"), "regular_hours": row.get("Reg Hrs"),
                        "overtime_hours": row.get("OT Hrs"), "subsistence": row.get("Subsistence")
                    })
            if labor_data: supabase.table("field_labor").insert(labor_data).execute()

            # Save Equipment
            equip_data = []
            for _, row in edited_equip.iterrows():
                if row.get("Unit #"):
                    equip_data.append({
                        "ticket_number": ticket_number, "unit_number": row["Unit #"],
                        "equipment_name": row.get("Equipment Name"), "usage_hours": row.get("Usage Hrs")
                    })
            if equip_data: supabase.table("field_equipment").insert(equip_data).execute()

            st.success(f"🎉 Ticket [{ticket_number}] saved successfully!")
            
            # Reset Session
            st.session_state.labour_df = pd.DataFrame(columns=["Crew Name", "Trade", "Reg Hrs", "OT Hrs", "Travel Hrs", "Subsistence"])
            st.session_state.equip_df = pd.DataFrame(columns=["Unit #", "Equipment Name", "Operator", "Usage Hrs"])
            st.rerun()

        except Exception as e:
            st.error(f"Error saving ticket: {e}")