import streamlit as st
import pandas as pd
from utils.supabase_client import supabase
from datetime import datetime
import time
from utils.auth_req import require_login  # 보안 체크

st.set_page_config(page_title="Time Ticket Entry", layout="wide")

# 🔒 로그인 체크
require_login()

st.title("⏱️ Time Ticket Entry")

# --- 1. 기본 데이터 로딩 ---
def get_active_jobs():
    try:
        res = supabase.table("master_project").select("job_number, project_name").eq("status", "Active").execute()
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

# --- 2. 탭 구성 (생성 / 검토) ---
tab_create, tab_review = st.tabs(["📝 Create Ticket (생성)", "👀 Draft Review (검토)"])

# ==========================================
# [TAB 1] Create Ticket (Manual OR Import)
# ==========================================
with tab_create:
    # 입력 방식 선택
    entry_mode = st.radio("Entry Mode", ["Manual Entry (Single)", "Bulk Import (Excel)"], horizontal=True)
    st.divider()

    # ---------------------------------------------------------
    # MODE A: Manual Entry (수동 입력)
    # ---------------------------------------------------------
    if entry_mode == "Manual Entry (Single)":
        st.caption("Manually enter a single field ticket.")
        
        # 세션 초기화 (Manual용)
        if "man_labour" not in st.session_state:
            st.session_state.man_labour = pd.DataFrame(columns=["Crew Name", "Trade", "Reg Hrs", "OT Hrs", "Subsistence"])
        if "man_equip" not in st.session_state:
            st.session_state.man_equip = pd.DataFrame(columns=["Unit #", "Equipment Name", "Usage Hrs"])
        if "man_misc" not in st.session_state:
            st.session_state.man_misc = pd.DataFrame(columns=["Description", "Qty", "Rate"])

        with st.form("manual_form", clear_on_submit=False):
            # 1. Header
            c1, c2, c3, c4 = st.columns(4)
            with c1: m_job = st.selectbox("Job #", job_list, key="m_job")
            with c2: m_date = st.date_input("Date", datetime.now(), key="m_date")
            with c3: m_ticket = st.text_input("Ticket #", placeholder="FT-260225-01", key="m_ticket")
            with c4: m_billing = st.selectbox("Billing Type", ["T&M", "Lump Sum", "Unit Price"], key="m_billing")
            
            cc1, cc2, cc3 = st.columns(3)
            with cc1: m_afe = st.text_input("AFE #", key="m_afe")
            with cc2: m_po = st.text_input("PO #", key="m_po")
            with cc3: m_desc = st.text_input("Description", key="m_desc")
            
            st.divider()
            
            # 2. Details (Editors)
            st.markdown("##### 👷‍♂️ Labor")
            edit_lab = st.data_editor(st.session_state.man_labour, num_rows="dynamic", use_container_width=True, key="editor_man_lab")
            
            st.markdown("##### 🚜 Equipment")
            edit_eq = st.data_editor(st.session_state.man_equip, num_rows="dynamic", use_container_width=True, key="editor_man_eq")
            
            st.markdown("##### 📦 Material / Misc")
            edit_misc = st.data_editor(st.session_state.man_misc, num_rows="dynamic", use_container_width=True, key="editor_man_misc")
            
            # 3. Submit
            st.divider()
            submit_manual = st.form_submit_button("✅ Submit Ticket (Create)", type="primary", use_container_width=True)
            
            if submit_manual:
                if not m_ticket:
                    st.error("Ticket # is required.")
                else:
                    try:
                        # Header
                        h_data = {
                            "ticket_number": m_ticket, "job_number": m_job, "ticket_date": str(m_date),
                            "afe_number": m_afe, "po_number": m_po, "work_description": m_desc,
                            "status": "Ticket Created" # Manual은 바로 생성됨
                        }
                        supabase.table("field_tickets").insert(h_data).execute()
                        
                        # Labor
                        l_data = []
                        for _, r in edit_lab.iterrows():
                            if r.get("Crew Name"):
                                l_data.append({
                                    "ticket_number": m_ticket, "crew_name": r["Crew Name"], "trade": r.get("Trade", "Laborer"),
                                    "regular_hours": r.get("Reg Hrs", 0), "overtime_hours": r.get("OT Hrs", 0),
                                    "subsistence": r.get("Subsistence", False)
                                })
                        if l_data: supabase.table("field_labor").insert(l_data).execute()
                        
                        # Equip
                        e_data = []
                        for _, r in edit_eq.iterrows():
                            if r.get("Unit #"):
                                e_data.append({
                                    "ticket_number": m_ticket, "unit_number": r["Unit #"], 
                                    "equipment_name": r.get("Equipment Name", "Equip"), "usage_hours": r.get("Usage Hrs", 0)
                                })
                        if e_data: supabase.table("field_equipment").insert(e_data).execute()
                        
                        st.success(f"Ticket {m_ticket} Created Successfully!")
                        
                        # Reset Session
                        st.session_state.man_labour = pd.DataFrame(columns=["Crew Name", "Trade", "Reg Hrs", "OT Hrs", "Subsistence"])
                        st.session_state.man_equip = pd.DataFrame(columns=["Unit #", "Equipment Name", "Usage Hrs"])
                        st.session_state.man_misc = pd.DataFrame(columns=["Description", "Qty", "Rate"])
                        st.rerun()
                        
                    except Exception as e:
                        st.error(f"Error: {e}")

    # ---------------------------------------------------------
    # MODE B: Bulk Import (엑셀 일괄 업로드)
    # ---------------------------------------------------------
    elif entry_mode == "Bulk Import (Excel)":
        st.caption("Upload Excel files to generate multiple Draft tickets automatically.")
        
        c_imp1, c_imp2 = st.columns([1, 2])
        with c_imp1:
            map_options = {m['map_name']: m for m in saved_maps}
            if not map_options:
                st.warning("⚠️ No settings found. Go to 'Settings' to configure mapping.")
                selected_map = None
            else:
                selected_profile = st.selectbox("Select Import Profile", list(map_options.keys()))
                selected_map = map_options[selected_profile]

        with c_imp2:
            uploaded_file = st.file_uploader("Upload Excel File", type=["xlsx", "xlsm", "csv"], label_visibility="collapsed")

        if uploaded_file and selected_map and st.button("🚀 Process & Generate Drafts", type="primary"):
            try:
                # 1. Read File
                header_idx = selected_map['header_row_idx']
                if uploaded_file.name.endswith('.csv'):
                    df = pd.read_csv(uploaded_file, header=header_idx)
                else:
                    df = pd.read_excel(uploaded_file, header=header_idx, engine='openpyxl')
                
                # Mapping Info
                grp_cols = selected_map['mapping_data']['group_cols']
                dat_cols = selected_map['mapping_data']['data_cols']
                
                # Validate Grouping Keys
                t_col = grp_cols.get("ticket_num")
                j_col = grp_cols.get("job_num")
                d_col = grp_cols.get("date")
                
                if t_col == "(Not Selected)" and (j_col == "(Not Selected)" or d_col == "(Not Selected)"):
                    st.error("Grouping requires 'Ticket #' OR 'Job # + Date' mapped.")
                    st.stop()

                # 2. Create Group Key
                df['__GROUP_KEY__'] = ""
                for index, row in df.iterrows():
                    if t_col != "(Not Selected)" and t_col in df.columns and pd.notna(row[t_col]):
                        key = str(row[t_col]).strip()
                    else:
                        j_val = str(row[j_col]).strip() if j_col in df.columns else "UnknownJob"
                        d_val = str(row[d_col]).strip() if d_col in df.columns else datetime.now().strftime("%Y-%m-%d")
                        key = f"{j_val}_{d_val}"
                    df.at[index, '__GROUP_KEY__'] = key
                
                # 3. Process Groups
                grouped = df.groupby('__GROUP_KEY__')
                success_count = 0
                progress_bar = st.progress(0)
                total_groups = len(grouped)
                
                for i, (key, group) in enumerate(grouped):
                    first_row = group.iloc[0]
                    
                    # Generate Header Info
                    ticket_num = key if t_col != "(Not Selected)" else f"DRAFT-{key}-{int(time.time())}"
                    job_num = str(first_row[j_col]).strip() if j_col != "(Not Selected)" and j_col in df.columns else "Unknown"
                    try:
                        t_date = pd.to_datetime(first_row[d_col]).strftime("%Y-%m-%d") if d_col != "(Not Selected)" else datetime.now().strftime("%Y-%m-%d")
                    except: t_date = datetime.now().strftime("%Y-%m-%d")

                    # Insert Header (Draft Status)
                    try:
                        supabase.table("field_tickets").insert({
                            "ticket_number": ticket_num, "job_number": job_num, "ticket_date": t_date,
                            "status": "Draft", "work_description": f"Imported from {uploaded_file.name}"
                        }).execute()
                    except: pass # Ignore duplicates for now

                    # Insert Details
                    labor_list = []
                    equip_list = []
                    
                    for _, row in group.iterrows():
                        # Labor
                        if dat_cols["crew_name"] != "(Not Selected)" and pd.notna(row[dat_cols["crew_name"]]):
                            labor_list.append({
                                "ticket_number": ticket_num,
                                "crew_name": row[dat_cols["crew_name"]],
                                "trade": row[dat_cols["trade"]] if dat_cols["trade"] != "(Not Selected)" else "Laborer",
                                "regular_hours": row[dat_cols["reg_hrs"]] if dat_cols["reg_hrs"] != "(Not Selected)" else 0,
                                "overtime_hours": row[dat_cols["ot_hrs"]] if dat_cols["ot_hrs"] != "(Not Selected)" else 0
                            })
                        # Equip
                        if dat_cols["unit_num"] != "(Not Selected)" and pd.notna(row[dat_cols["unit_num"]]):
                            equip_list.append({
                                "ticket_number": ticket_num,
                                "unit_number": row[dat_cols["unit_num"]],
                                "equipment_name": row[dat_cols["eq_name"]] if dat_cols["eq_name"] != "(Not Selected)" else "Equip",
                                "usage_hours": row[dat_cols["usage_hrs"]] if dat_cols["usage_hrs"] != "(Not Selected)" else 0
                            })
                    
                    if labor_list: supabase.table("field_labor").insert(labor_list).execute()
                    if equip_list: supabase.table("field_equipment").insert(equip_list).execute()
                    
                    success_count += 1
                    progress_bar.progress((i + 1) / total_groups)

                st.success(f"🎉 Generated {success_count} Draft Tickets! Check 'Draft Review' tab.")
                
            except Exception as e:
                st.error(f"Import Failed: {e}")

# ==========================================
# [TAB 2] Draft Review (검토 및 승인)
# ==========================================
with tab_review:
    st.markdown("### 📝 Draft Tickets Review")
    st.caption("Review tickets generated via Import. Approve them to make them available for LEMs.")
    
    try:
        res = supabase.table("field_tickets").select("*").eq("status", "Draft").order("created_at", desc=True).execute()
        drafts = res.data if res.data else []
    except: drafts = []
    
    if not drafts:
        st.info("No draft tickets pending review.")
    else:
        for ticket in drafts:
            with st.expander(f"📍 {ticket['ticket_number']} | Job: {ticket['job_number']} | Date: {ticket['ticket_date']}"):
                
                # Fetch details
                lab_res = supabase.table("field_labor").select("*").eq("ticket_number", ticket['ticket_number']).execute()
                eq_res = supabase.table("field_equipment").select("*").eq("ticket_number", ticket['ticket_number']).execute()
                
                df_lab = pd.DataFrame(lab_res.data) if lab_res.data else pd.DataFrame()
                df_eq = pd.DataFrame(eq_res.data) if eq_res.data else pd.DataFrame()

                c1, c2 = st.columns(2)
                with c1:
                    st.caption("Labor Details")
                    if not df_lab.empty: st.dataframe(df_lab[["crew_name", "trade", "regular_hours", "overtime_hours"]], use_container_width=True, hide_index=True)
                    else: st.write("-")
                with c2:
                    st.caption("Equipment Details")
                    if not df_eq.empty: st.dataframe(df_eq[["unit_number", "equipment_name", "usage_hours"]], use_container_width=True, hide_index=True)
                    else: st.write("-")
                
                # Buttons
                btn1, btn2, spacer = st.columns([1, 1, 4])
                with btn1:
                    if st.button("✅ Approve", key=f"app_{ticket['id']}"):
                        supabase.table("field_tickets").update({"status": "Ticket Created"}).eq("id", ticket['id']).execute()
                        st.success("Approved!")
                        st.rerun()
                with btn2:
                    if st.button("🗑️ Delete", key=f"del_{ticket['id']}", type="secondary"):
                        # Delete header (Cascade delete should handle items if configured, otherwise delete items first)
                        # For now assume cascade or simple delete header
                        supabase.table("field_tickets").delete().eq("id", ticket['id']).execute()
                        st.warning("Deleted.")
                        st.rerun()
