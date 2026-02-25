import streamlit as st
import pandas as pd
from utils.supabase_client import supabase
from datetime import datetime
import io
import json

st.set_page_config(page_title="Time Ticket Entry", layout="wide")
st.title("⏱️ Time Ticket Entry (Smart Import)")

# --- 초기 데이터 로딩 ---
def get_active_jobs():
    try:
        res = supabase.table("master_project").select("*").eq("status", "Active").execute()
        return res.data if res.data else []
    except: return []

# [NEW] 저장된 매핑 설정 가져오기
def get_saved_maps():
    try:
        res = supabase.table("client_import_maps").select("*").order("created_at", desc=True).execute()
        return res.data if res.data else []
    except: return []

jobs_data = get_active_jobs()
job_list = [j['job_number'] for j in jobs_data]
saved_maps = get_saved_maps() # 저장된 설정 로딩

# --- 세션 상태 초기화 ---
if "labour_df" not in st.session_state:
    st.session_state.labour_df = pd.DataFrame(columns=["Crew Name", "Trade", "Reg Hrs", "OT Hrs", "Travel Hrs", "Subsistence"])
if "equip_df" not in st.session_state:
    st.session_state.equip_df = pd.DataFrame(columns=["Unit #", "Equipment Name", "Operator", "Usage Hrs"])
if "misc_df" not in st.session_state:
    st.session_state.misc_df = pd.DataFrame(columns=["Description", "Qty", "Rate", "Total"])

# --- [입력 방식 선택] ---
entry_mode = st.radio("입력 방식 선택", ["Manual Entry (수동)", "Import Custom Excel (스마트 업로드)"], horizontal=True)

# ==========================================
# [기능 2] 스마트 엑셀 업로드 (설정 저장 기능 포함)
# ==========================================
if entry_mode == "Import Custom Excel (스마트 업로드)":
    st.info("💡 엑셀을 업로드하고 [저장된 설정]을 선택하면 자동으로 매핑됩니다.")
    
    col_u1, col_u2 = st.columns([2, 1])
    with col_u1:
        uploaded_file = st.file_uploader("고객사 엑셀 파일 업로드", type=["xlsx", "xlsm", "xls", "csv"])
    
    with col_u2:
        # [NEW] 저장된 매핑 설정 선택 기능
        map_options = ["(직접 설정)"] + [m['map_name'] for m in saved_maps]
        selected_map_name = st.selectbox("📂 저장된 매핑 설정 불러오기", map_options)
        
        # 선택된 설정 데이터 찾기
        current_map_data = None
        if selected_map_name != "(직접 설정)":
            current_map_data = next((m for m in saved_maps if m['map_name'] == selected_map_name), None)

    if uploaded_file:
        try:
            # 1. 헤더 위치 결정 (저장된 값이 있으면 그거 쓰고, 없으면 0)
            default_header = current_map_data['header_row_idx'] if current_map_data else 0
            
            # 2. 파일 읽기
            if uploaded_file.name.endswith('.csv'):
                df = pd.read_csv(uploaded_file, header=default_header)
            else:
                df = pd.read_excel(uploaded_file, header=default_header, engine='openpyxl')
            
            # 엑셀 컬럼 목록
            excel_columns = ["(선택 안 함)"] + list(df.columns)

            st.write("---")
            col_set1, col_set2 = st.columns([1, 2])
            
            # [좌측] 데이터 미리보기
            with col_set1:
                st.subheader("1. 엑셀 미리보기")
                # 헤더 위치 수동 조절 (설정값 없을 때만 유용)
                if not current_map_data:
                    new_header = st.number_input("헤더 행 번호 수정", min_value=0, value=default_header, step=1)
                    if new_header != default_header:
                        st.caption("헤더 변경을 적용하려면 파일을 다시 업로드해주세요.")
                
                st.dataframe(df.head(3), use_container_width=True)

            # [우측] 컬럼 매핑 (자동 선택 로직 포함)
            with col_set2:
                st.subheader("2. 컬럼 매핑 (Mapping)")
                
                # 저장된 매핑 데이터가 있으면 가져오기
                saved_mapping = current_map_data['mapping_data'] if current_map_data else {}

                # --- 헬퍼 함수: 저장된 값이 엑셀 컬럼에 있으면 인덱스 반환 ---
                def get_idx(key, default_idx=0):
                    val = saved_mapping.get(key)
                    if val and val in excel_columns:
                        return excel_columns.index(val)
                    return default_idx

                with st.expander("👷‍♂️ 인력 (Labor) 매핑", expanded=True):
                    l_c1, l_c2 = st.columns(2)
                    with l_c1:
                        map_name = st.selectbox("Crew Name ↔", excel_columns, index=get_idx("crew_name"), key="m_name")
                        map_trade = st.selectbox("Trade ↔", excel_columns, index=get_idx("trade"), key="m_trade")
                    with l_c2:
                        map_reg = st.selectbox("Reg Hrs ↔", excel_columns, index=get_idx("reg_hrs"), key="m_reg")
                        map_ot = st.selectbox("OT Hrs ↔", excel_columns, index=get_idx("ot_hrs"), key="m_ot")
                
                with st.expander("🚜 장비 (Equipment) 매핑"):
                    e_c1, e_c2 = st.columns(2)
                    with e_c1:
                        map_unit = st.selectbox("Unit # ↔", excel_columns, index=get_idx("unit_num"), key="m_unit")
                        map_eq_name = st.selectbox("Eq Name ↔", excel_columns, index=get_idx("eq_name"), key="m_eqname")
                    with e_c2:
                        map_usage = st.selectbox("Usage Hrs ↔", excel_columns, index=get_idx("usage_hrs"), key="m_usage")

                # [NEW] 설정 저장하기 버튼
                with st.expander("💾 현재 매핑 설정 저장하기 (관리자용)"):
                    new_map_name = st.text_input("설정 이름 (예: Shell Standard)", placeholder="고객사 이름 + 양식")
                    if st.button("이 설정을 DB에 저장"):
                        if not new_map_name:
                            st.error("설정 이름을 입력하세요.")
                        else:
                            save_data = {
                                "crew_name": map_name, "trade": map_trade, "reg_hrs": map_reg, "ot_hrs": map_ot,
                                "unit_num": map_unit, "eq_name": map_eq_name, "usage_hrs": map_usage
                            }
                            supabase.table("client_import_maps").insert({
                                "map_name": new_map_name,
                                "header_row_idx": default_header, # 현재 보고있는 헤더 위치
                                "mapping_data": save_data
                            }).execute()
                            st.success(f"✅ '{new_map_name}' 설정이 저장되었습니다! 다음부터 불러올 수 있습니다.")
                            st.rerun()

            # 3. 변환 및 적용 버튼
            if st.button("🔄 데이터 변환 및 적용", type="primary"):
                # (이전과 동일한 변환 로직)
                if map_name != "(선택 안 함)":
                    new_labor = pd.DataFrame()
                    new_labor["Crew Name"] = df[map_name]
                    new_labor["Trade"] = df[map_trade] if map_trade != "(선택 안 함)" else "Laborer"
                    new_labor["Reg Hrs"] = pd.to_numeric(df[map_reg], errors='coerce').fillna(0) if map_reg != "(선택 안 함)" else 0
                    new_labor["OT Hrs"] = pd.to_numeric(df[map_ot], errors='coerce').fillna(0) if map_ot != "(선택 안 함)" else 0
                    new_labor["Travel Hrs"] = 0
                    new_labor["Subsistence"] = False
                    new_labor = new_labor[new_labor["Crew Name"].notna()]
                    st.session_state.labour_df = new_labor
                
                if map_unit != "(선택 안 함)":
                    new_equip = pd.DataFrame()
                    new_equip["Unit #"] = df[map_unit]
                    new_equip["Equipment Name"] = df[map_eq_name] if map_eq_name != "(선택 안 함)" else "Equipment"
                    new_equip["Operator"] = ""
                    new_equip["Usage Hrs"] = pd.to_numeric(df[map_usage], errors='coerce').fillna(0) if map_usage != "(선택 안 함)" else 0
                    new_equip = new_equip[new_equip["Unit #"].notna()]
                    st.session_state.equip_df = new_equip

                st.success("데이터 적용 완료! 아래에서 검토하세요.")
                st.rerun()

        except Exception as e:
            st.error(f"오류 발생: {e}")

# ==========================================
# [공통] 검토 및 저장 (이전과 동일)
# ==========================================
st.divider()

with st.form("ticket_form", clear_on_submit=False):
    st.subheader("📝 Ticket Details & Review")
    
    # 1. 헤더
    c1, c2, c3, c4 = st.columns(4)
    with c1: selected_job_num = st.selectbox("Job #", job_list)
    with c2: ticket_date = st.date_input("Ticket Date", datetime.now())
    with c3: ticket_number = st.text_input("Ticket #", placeholder="FT-260225-01")
    with c4: billing_type = st.selectbox("Billing", ["T&M", "Lump Sum", "Unit Price"])

    cc1, cc2, cc3 = st.columns(3)
    with cc1: afe = st.text_input("AFE #")
    with cc2: po = st.text_input("PO #")
    with cc3: desc = st.text_input("Description")

    st.divider()

    # 2. 데이터 에디터
    st.subheader("2️⃣ Section 2: Labour (검토)")
    edited_labour = st.data_editor(st.session_state.labour_df, num_rows="dynamic", use_container_width=True, key="ed_labour")

    st.subheader("3️⃣ Section 3: Equipment (검토)")
    edited_equip = st.data_editor(st.session_state.equip_df, num_rows="dynamic", use_container_width=True, key="ed_equip")
    
    st.subheader("4️⃣ Section 4: Material")
    edited_misc = st.data_editor(st.session_state.misc_df, num_rows="dynamic", use_container_width=True, key="ed_misc")

    # 3. 최종 저장
    submit_btn = st.form_submit_button("✅ Final Submit (저장)", type="primary", use_container_width=True)

    if submit_btn:
        if not ticket_number:
            st.error("티켓 번호는 필수입니다.")
        else:
            try:
                # 헤더 저장
                header_data = {
                    "ticket_number": ticket_number, "job_number": selected_job_num,
                    "ticket_date": str(ticket_date), "afe_number": afe, "po_number": po,
                    "work_description": desc, "status": "Ticket Created"
                }
                supabase.table("field_tickets").insert(header_data).execute()

                # Labor 저장
                labor_data = []
                for _, row in edited_labour.iterrows():
                    if row.get("Crew Name"):
                        labor_data.append({
                            "ticket_number": ticket_number, "crew_name": row["Crew Name"],
                            "trade": row.get("Trade"), "regular_hours": row.get("Reg Hrs"),
                            "overtime_hours": row.get("OT Hrs"), "subsistence": row.get("Subsistence")
                        })
                if labor_data: supabase.table("field_labor").insert(labor_data).execute()

                # Equipment 저장
                equip_data = []
                for _, row in edited_equip.iterrows():
                    if row.get("Unit #"):
                        equip_data.append({
                            "ticket_number": ticket_number, "unit_number": row["Unit #"],
                            "equipment_name": row.get("Equipment Name"), "usage_hours": row.get("Usage Hrs")
                        })
                if equip_data: supabase.table("field_equipment").insert(equip_data).execute()

                st.success(f"티켓 {ticket_number} 저장 완료!")
                st.session_state.labour_df = pd.DataFrame(columns=["Crew Name", "Trade", "Reg Hrs", "OT Hrs", "Travel Hrs", "Subsistence"])
                st.session_state.equip_df = pd.DataFrame(columns=["Unit #", "Equipment Name", "Operator", "Usage Hrs"])
                st.rerun()

            except Exception as e:
                st.error(f"저장 실패: {e}")