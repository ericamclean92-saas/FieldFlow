import streamlit as st
import pandas as pd
from utils.supabase_client import supabase
from st_aggrid import AgGrid, GridOptionsBuilder, GridUpdateMode

st.set_page_config(page_title="System Settings", layout="wide")
st.title("⚙️ System Settings")

# 탭 구성
tab_import, tab_users = st.tabs(["📥 Import Settings (엑셀 매핑)", "👤 User Management (사용자 관리)"])

# ==========================================
# [TAB 1] Excel Import Settings (기존 기능 유지)
# ==========================================
with tab_import:
    st.header("Excel Template Mapping")
    st.info("Configure import templates here. Map columns for bulk processing.")

    # 1. Upload Sample File
    uploaded_file = st.file_uploader("Upload Sample Excel File", type=["xlsx", "xlsm", "xls", "csv"])

    if uploaded_file:
        try:
            if uploaded_file.name.endswith('.csv'):
                df_raw = pd.read_csv(uploaded_file, header=None, nrows=50)
            else:
                df_raw = pd.read_excel(uploaded_file, header=None, nrows=50, engine='openpyxl')
            
            st.subheader("1️⃣ Locate Header Row")
            
            gb = GridOptionsBuilder.from_dataframe(df_raw)
            gb.configure_selection('single', use_checkbox=True)
            gridOptions = gb.build()
            
            AgGrid(df_raw, gridOptions=gridOptions, height=250, fit_columns_on_grid_load=False)
            
            header_row = st.number_input("Header Row Index (See number on left)", min_value=0, value=0, step=1)

            # Reload with header
            if uploaded_file.name.endswith('.csv'):
                uploaded_file.seek(0)
                df = pd.read_csv(uploaded_file, header=header_row)
            else:
                df = pd.read_excel(uploaded_file, header=header_row, engine='openpyxl')
            
            st.write(f"▼ Preview (Row {header_row}):")
            st.dataframe(df.head(3), use_container_width=True)
            
            excel_cols = ["(Not Selected)"] + list(df.columns)

            # --- Mapping ---
            st.divider()
            st.subheader("2️⃣ Map Columns")

            c1, c2, c3 = st.columns(3)
            
            with c1:
                st.markdown("##### 🔑 Grouping Keys")
                with st.container(border=True):
                    map_ticket_num = st.selectbox("Ticket # ↔", excel_cols, index=0)
                    map_job_num = st.selectbox("Job # ↔", excel_cols, index=0)
                    map_date = st.selectbox("Date ↔", excel_cols, index=0)

            with c2:
                st.markdown("##### 👷‍♂️ Labor")
                with st.container(border=True):
                    map_crew_name = st.selectbox("Name ↔", excel_cols, index=0)
                    map_trade = st.selectbox("Trade ↔", excel_cols, index=0)
                    map_reg = st.selectbox("Reg Hrs ↔", excel_cols, index=0)
                    map_ot = st.selectbox("OT Hrs ↔", excel_cols, index=0)

            with c3:
                st.markdown("##### 🚜 Equipment")
                with st.container(border=True):
                    map_unit = st.selectbox("Unit # ↔", excel_cols, index=0)
                    map_eq_name = st.selectbox("Eq Name ↔", excel_cols, index=0)
                    map_usage = st.selectbox("Usage Hrs ↔", excel_cols, index=0)

            # --- Save ---
            st.divider()
            col_s1, col_s2 = st.columns([2, 1])
            with col_s1:
                profile_name = st.text_input("Profile Name", placeholder="e.g. Shell Timesheet Bulk")
            with col_s2:
                st.write("") 
                st.write("") 
                if st.button("💾 Save Settings", type="primary", use_container_width=True):
                    if not profile_name:
                        st.error("Enter Profile Name.")
                    else:
                        mapping_data = {
                            "group_cols": { "ticket_num": map_ticket_num, "job_num": map_job_num, "date": map_date },
                            "data_cols": { 
                                "crew_name": map_crew_name, "trade": map_trade, "reg_hrs": map_reg, "ot_hrs": map_ot,
                                "unit_num": map_unit, "eq_name": map_eq_name, "usage_hrs": map_usage
                            }
                        }
                        try:
                            supabase.table("client_import_maps").insert({
                                "map_name": profile_name, "header_row_idx": header_row, "mapping_data": mapping_data
                            }).execute()
                            st.success(f"✅ Saved '{profile_name}'!")
                        except Exception as e:
                            st.error(f"Error: {e}")

        except Exception as e:
            st.error(f"Error: {e}")


# ==========================================
# [TAB 2] User Management (New Feature!)
# ==========================================
with tab_users:
    st.header("👤 User Management")
    st.caption("Manage system users and their access roles.")

    # 1. Create New User Form
    with st.expander("➕ Register New User", expanded=True):
        with st.form("create_user"):
            c_u1, c_u2 = st.columns(2)
            with c_u1:
                new_email = st.text_input("Email Address")
                new_password = st.text_input("Password", type="password", help="Min 6 characters")
            with c_u2:
                new_name = st.text_input("Full Name")
                new_role = st.selectbox("Role", ["Field User", "Admin"])
            
            submit_create = st.form_submit_button("Create User", type="primary")
            
            if submit_create:
                if len(new_password) < 6:
                    st.error("Password must be at least 6 characters.")
                else:
                    try:
                        # 1. Supabase Auth에 사용자 생성 (Sign Up)
                        # 주의: 기본 설정상 이메일 확인 메일이 발송됩니다.
                        auth_res = supabase.auth.sign_up({
                            "email": new_email, 
                            "password": new_password,
                            "options": {"data": {"full_name": new_name}}
                        })
                        
                        if auth_res.user:
                            # 2. DB에 역할(Role) 정보 저장
                            supabase.table("user_roles").insert({
                                "email": new_email,
                                "full_name": new_name,
                                "role": new_role
                            }).execute()
                            
                            st.success(f"✅ User '{new_name}' created successfully! Please ask them to verify email if required.")
                        else:
                            st.warning("User creation initiated, but no user object returned (Check email confirmation settings).")
                            
                    except Exception as e:
                        st.error(f"Failed to create user: {e}")

    st.divider()

    # 2. User List
    st.subheader("📋 Registered Users")
    try:
        # role 테이블 조회
        users_res = supabase.table("user_roles").select("*").order("created_at", desc=True).execute()
        users = users_res.data if users_res.data else []
        
        if users:
            df_users = pd.DataFrame(users)
            
            # 테이블 보여주기 (비밀번호 제외)
            edited_users = st.data_editor(
                df_users[["email", "full_name", "role", "created_at"]],
                column_config={
                    "email": "Email",
                    "full_name": "Name",
                    "role": st.column_config.SelectboxColumn("Role", options=["Admin", "Field User"], required=True),
                    "created_at": "Joined Date"
                },
                use_container_width=True,
                hide_index=True,
                key="user_editor"
            )
            
            # (옵션) 역할 변경 기능은 추후 'Save Changes' 버튼과 연동하여 구현 가능
            
        else:
            st.info("No users found.")
            
    except Exception as e:
        st.error(f"Error loading users: {e}")
