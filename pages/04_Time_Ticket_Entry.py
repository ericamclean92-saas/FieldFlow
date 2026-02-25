import streamlit as st
import pandas as pd
from utils.supabase_client import supabase
from datetime import datetime
import io

st.set_page_config(page_title="Time Ticket Entry", layout="wide")
st.title("⏱️ Time Ticket Entry (Universal Import)")

# --- 초기 데이터 로딩 ---
def get_active_jobs():
    try:
        res = supabase.table("master_project").select("*").eq("status", "Active").execute()
        return res.data if res.data else []
    except: return []

jobs_data = get_active_jobs()
job_list = [j['job_number'] for j in jobs_data]

# --- 세션 상태 초기화 ---
if "labour_df" not in st.session_state:
    st.session_state.labour_df = pd.DataFrame(columns=["Crew Name", "Trade", "Reg Hrs", "OT Hrs", "Travel Hrs", "Subsistence"])
if "equip_df" not in st.session_state:
    st.session_state.equip_df = pd.DataFrame(columns=["Unit #", "Equipment Name", "Operator", "Usage Hrs"])
if "misc_df" not in st.session_state:
    st.session_state.misc_df = pd.DataFrame(columns=["Description", "Qty", "Rate", "Total"])

# --- [입력 방식 선택] ---
entry_mode = st.radio("입력 방식 선택", ["Manual Entry (수동)", "Import Custom Excel (고객사 양식 매핑)"], horizontal=True)

# ==========================================
# [기능 2] 고객사 엑셀 매핑 (Universal Import)
# ==========================================
if entry_mode == "Import Custom Excel (고객사 양식 매핑)":
    st.info("💡 고객사마다 다른 엑셀 양식(.xlsx, .xlsm, .csv)을 업로드하고, 컬럼을 연결(Mapping)해주세요.")
    
    # [수정됨] xlsm 확장자 추가!
    uploaded_file = st.file_uploader("고객사 엑셀 파일 업로드", type=["xlsx", "xlsm", "xls", "csv"])
    
    if uploaded_file:
        try:
            # 1. 파일 읽기 (헤더 위치를 찾기 위해 일단 읽음)
            if uploaded_file.name.endswith('.csv'):
                raw_df = pd.read_csv(uploaded_file)
            else:
                # engine='openpyxl'은 xlsm도 잘 읽습니다.
                raw_df = pd.read_excel(uploaded_file, engine='openpyxl')
            
            st.write("---")
            col_set1, col_set2 = st.columns([1, 2])
            
            with col_set1:
                st.subheader("1. 데이터 위치 설정")
                # 헤더가 몇 번째 줄에 있는지 선택 (0부터 시작)
                header_row_idx = st.number_input("헤더(제목) 행 번호 (0 = 첫째줄)", min_value=0, value=0, step=1)
                
                # 다시 읽기 (헤더 위치 적용)
                if uploaded_file.name.endswith('.csv'):
                    df = pd.read_csv(uploaded_file, header=header_row_idx)
                else:
                    df = pd.read_excel(uploaded_file, header=header_row_idx, engine='openpyxl')
                
                # 데이터 미리보기
                st.caption("엑셀 데이터 미리보기 (상위 3행):")
                st.dataframe(df.head(3), use_container_width=True)
                
                # 엑셀의 컬럼 목록
                excel_columns = ["(선택 안 함)"] + list(df.columns)

            with col_set2:
                st.subheader("2. 컬럼 매핑 (Mapping)")
                st.caption("엑셀의 어떤 칸이 시스템의 어떤 칸으로 들어갈지 짝을 지어주세요.")
                
                with st.expander("👷‍♂️ 인력 (Labor) 매핑", expanded=True):
                    l_c1, l_c2 = st.columns(2)
                    with l_c1:
                        map_name = st.selectbox("Crew Name (이름) ↔", excel_columns, index=0, key="map_name")
                        map_trade = st.selectbox("Trade (직종) ↔", excel_columns, index=0, key="map_trade")
                    with l_c2:
                        map_reg = st.selectbox("Regular Hrs ↔", excel_columns, index=0, key="map_reg")
                        map_ot = st.selectbox("Overtime Hrs ↔", excel_columns, index=0, key="map_ot")
                
                with st.expander("🚜 장비 (Equipment) 매핑"):
                    e_c1, e_c2 = st.columns(2)
                    with e_c1:
                        map_unit = st.selectbox("Unit # (장비번호) ↔", excel_columns, index=0, key="map_unit")
                        map_eq_name = st.selectbox("Equipment Name ↔", excel_columns, index=0, key="map_eq_name")
                    with e_c2:
                        map_usage = st.selectbox("Usage Hrs ↔", excel_columns, index=0, key="map_usage")

            # 3. 변환 및 적용 버튼
            if st.button("🔄 데이터 가져오기 (Apply Mapping)", type="primary"):
                # [인력 데이터 변환]
                if map_name != "(선택 안 함)":
                    new_labor = pd.DataFrame()
                    new_labor["Crew Name"] = df[map_name]
                    # Trade가 없으면 Laborer로 기본 설정
                    if map_trade != "(선택 안 함)":
                        new_labor["Trade"] = df[map_trade]
                    else:
                        new_labor["Trade"] = "Laborer"
                        
                    new_labor["Reg Hrs"] = pd.to_numeric(df[map_reg], errors='coerce').fillna(0) if map_reg != "(선택 안 함)" else 0
                    new_labor["OT Hrs"] = pd.to_numeric(df[map_ot], errors='coerce').fillna(0) if map_ot != "(선택 안 함)" else 0
                    new_labor["Travel Hrs"] = 0
                    new_labor["Subsistence"] = False
                    
                    # 빈 행 제거 (이름 없는 줄 삭제)
                    new_labor = new_labor[new_labor["Crew Name"].notna()]
                    st.session_state.labour_df = new_labor
                
                # [장비 데이터 변환]
                if map_unit != "(선택 안 함)":
                    new_equip = pd.DataFrame()
                    new_equip["Unit #"] = df[map_unit]
                    new_equip["Equipment Name"] = df[map_eq_name] if map_eq_name != "(선택 안 함)" else "Equipment"
                    new_equip["Operator"] = ""
                    new_equip["Usage Hrs"] = pd.to_numeric(df[map_usage], errors='coerce').fillna(0) if map_usage != "(선택 안 함)" else 0
                    
                    new_equip = new_equip[new_equip["Unit #"].notna()]
                    st.session_state.equip_df = new_equip

                st.success("데이터가 성공적으로 입력폼에 채워졌습니다! 아래 내용을 검토하고 Submit 하세요.")
                st.rerun()

        except Exception as e:
            st.error(f"파일 처리 중 오류: {e}")

# ==========================================
# [공통] 데이터 검토 및 Submit (Manual과 동일)
# ==========================================
st.divider()

with st.form("ticket_form", clear_on_submit=False):
    st.subheader("📝 Ticket Details & Review")
    
    # 1. 헤더 (Manual 입력 필요)
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

    # 2. 데이터 에디터 (매핑된 데이터가 여기에 뜸)
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
                # 세션 초기화
                st.session_state.labour_df = pd.DataFrame(columns=["Crew Name", "Trade", "Reg Hrs", "OT Hrs", "Travel Hrs", "Subsistence"])
                st.session_state.equip_df = pd.DataFrame(columns=["Unit #", "Equipment Name", "Operator", "Usage Hrs"])
                st.rerun()

            except Exception as e:
                st.error(f"저장 실패: {e}")