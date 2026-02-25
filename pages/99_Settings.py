import streamlit as st
import pandas as pd
from utils.supabase_client import supabase
import io

st.set_page_config(page_title="System Settings", layout="wide")
st.title("⚙️ System Settings")

tab1, tab2 = st.tabs(["📥 Import Settings", "👤 User Management (Coming Soon)"])

with tab1:
    st.header("Excel Template Mapping")
    st.info("Configure import templates for different clients here. Once set up, you can use them directly in the Ticket Entry page.")

    # 1. Upload Sample File
    st.subheader("1️⃣ Upload Sample File")
    st.markdown("Upload a sample Excel file from the client to analyze its structure.")
    uploaded_file = st.file_uploader("Choose Excel File (.xlsx, .xlsm, .csv)", type=["xlsx", "xlsm", "xls", "csv"])

    if uploaded_file:
        try:
            # Determine file type
            is_csv = uploaded_file.name.endswith('.csv')
            
            # --- [Step 1] Locate Header ---
            st.divider()
            st.subheader("2️⃣ Locate Header Row")
            
            col_h1, col_h2 = st.columns([1, 3])
            with col_h1:
                header_row = st.number_input(
                    "Header Row Number (Starts at 0)", 
                    min_value=0, value=0, step=1,
                    help="Enter the row number where the actual column names begin (skipping logos or titles)."
                )
            
            # Read Data
            if is_csv:
                df = pd.read_csv(uploaded_file, header=header_row)
            else:
                df = pd.read_excel(uploaded_file, header=header_row, engine='openpyxl')
            
            with col_h2:
                st.caption(f"▼ Preview based on Row {header_row}. Do the column names look correct?")
                st.dataframe(df.head(5), use_container_width=True)

            # Column Options
            excel_cols = ["(Not Selected)"] + list(df.columns)

            # --- [Step 2] Map Columns ---
            st.divider()
            st.subheader("3️⃣ Map Columns")
            st.markdown("Match your system fields with the Excel columns.")

            col_map1, col_map2 = st.columns(2)
            
            with col_map1:
                st.markdown("#### 👷‍♂️ Labor Information")
                with st.container(border=True):
                    map_crew_name = st.selectbox("Crew Name ↔", excel_cols, index=0, help="Required Field")
                    map_trade = st.selectbox("Trade ↔", excel_cols, index=0)
                    map_reg = st.selectbox("Regular Hrs ↔", excel_cols, index=0)
                    map_ot = st.selectbox("Overtime Hrs ↔", excel_cols, index=0)
            
            with col_map2:
                st.markdown("#### 🚜 Equipment Information")
                with st.container(border=True):
                    map_unit = st.selectbox("Unit # ↔", excel_cols, index=0)
                    map_eq_name = st.selectbox("Equipment Name ↔", excel_cols, index=0)
                    map_usage = st.selectbox("Usage Hrs ↔", excel_cols, index=0)

            # --- [Step 3] Save Settings ---
            st.divider()
            st.subheader("4️⃣ Save Configuration")
            
            col_s1, col_s2 = st.columns([2, 1])
            with col_s1:
                profile_name = st.text_input("Profile Name", placeholder="e.g., Shell Standard 2026, CNRL Timesheet")
            with col_s2:
                st.write("") # Spacer
                st.write("") 
                if st.button("💾 Save Settings", type="primary", use_container_width=True):
                    if not profile_name:
                        st.error("Please enter a Profile Name.")
                    elif map_crew_name == "(Not Selected)" and map_unit == "(Not Selected)":
                        st.error("You must map at least one field (Crew Name or Unit #).")
                    else:
                        # Prepare data for saving
                        mapping_data = {
                            "crew_name": map_crew_name, "trade": map_trade, 
                            "reg_hrs": map_reg, "ot_hrs": map_ot,
                            "unit_num": map_unit, "eq_name": map_eq_name, "usage_hrs": map_usage
                        }
                        
                        try:
                            supabase.table("client_import_maps").insert({
                                "map_name": profile_name,
                                "header_row_idx": header_row,
                                "mapping_data": mapping_data
                            }).execute()
                            st.success(f"✅ Configuration '{profile_name}' saved successfully!")
                            st.balloons()
                        except Exception as e:
                            st.error(f"Failed to save: {e}")

        except Exception as e:
            st.error(f"Error reading file: {e}")