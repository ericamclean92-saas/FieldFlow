import streamlit as st
import pandas as pd
from utils.supabase_client import supabase
from datetime import datetime
import io

st.set_page_config(page_title="Time Ticket Entry", layout="wide")
st.title("⏱️ Time Ticket Entry")

# --- 기본 데이터 로딩 ---
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

# --- 세션 초기화 ---
if "labour_df" not in st.session_state:
    st.session_state.labour_df = pd.DataFrame(columns=["Crew Name", "Trade", "Reg Hrs", "OT Hrs", "Travel Hrs", "Subsistence"])
if "equip_df" not in st.session_state:
    st.session_state.equip_df = pd.DataFrame(columns=["Unit #", "Equipment Name", "Operator", "Usage Hrs"])
if "misc_df" not in st.session_state:
    st.session_state.misc_df = pd.DataFrame(columns=["Description", "Qty", "Rate", "Total"])

# ==========================================
# [심플해진 상단] 입력 방식 선택
# ==========================================
entry_mode = st.radio("작업 방식", ["수동 입력 (Manual)", "엑셀 불러오기 (Import)"], horizontal=True)

if entry_mode == "엑셀 불러오기 (Import)":
    # 1. 설정 선택
    map_options = {m['map_name']: m for m in saved_maps}
    
    if not map_options:
        st.warning("⚠️ 등록된 엑셀 양식이 없습니다. 'Settings' 메뉴에서 양식을 먼저 등록해주세요.")
    else:
        st.info("💡 미리 설정된 양식을 선택하고 엑셀 파일을 업로드하세요.")
        
        c1, c2 = st.columns([1, 2])
        with c1:
            selected_profile_name = st.selectbox("📂 양식 선택 (Profile)", list(map_options.keys()))
            selected_map = map_options[selected_profile_name]
        
        with c2:
            uploaded_file = st.file_uploader("엑셀 파일 업로드", type=["xlsx", "xlsm", "xls", "csv"], label_visibility="collapsed")

        if uploaded_file and st.button("🚀 데이터 적용하기 (Process)", type="primary"):
            try:
                # 1. 파일 읽기 (저장된 헤더 위치 사용)
                header_idx = selected_map['header_row_idx']
                if uploaded_file.name.endswith('.csv'):
                    df = pd.read_csv(uploaded_file, header=header_idx)
                else:
                    df = pd.read_excel(uploaded_file, header=header_idx, engine='openpyxl')
                
                # 2. 매핑 정보로 데이터 변환
                mapping = selected_map['mapping_data']
                
                # (1) Labor 변환
                if mapping.get("crew_name") != "(선택 안 함)":
                    new_labor = pd.DataFrame()
                    # 컬럼이 실제 엑셀에 있는지 확인
                    if mapping["crew_name"] in df.columns:
                        new_labor["Crew Name"] = df[mapping["crew_name"]]
                        
                        # Trade
                        if mapping.get("trade") != "(선택 안 함)" and mapping["trade"] in df.columns:
                            new_labor["Trade"] = df[mapping["trade"]]
                        else:
                            new_labor["Trade"] = "Laborer" # 기본값
                            
                        # Hours
                        if mapping.get("reg_hrs") != "(선택 안 함)" and mapping["reg_hrs"] in df.columns:
                            new_labor["Reg Hrs"] = pd.to_numeric(df[mapping["reg_hrs"]], errors='coerce').fillna(0)
                        else: new_labor["Reg Hrs"] = 0
                        
                        if mapping.get("ot_hrs") != "(선택 안 함)" and mapping["ot_hrs"] in df.columns:
                            new_labor["OT Hrs"] = pd.to_numeric(df[mapping["ot_hrs"]], errors='coerce').fillna(0)
                        else: new_labor["OT Hrs"] = 0
                        
                        new_labor["Subsistence"] = False
                        
                        # 빈 행 제거 및 적용
                        new_labor = new_labor[new_labor["Crew Name"].notna()]
                        st.session_state.labour_df = new_labor
                
                # (2) Equipment 변환
                if mapping.get("unit_num") != "(선택 안 함)":
                    new_equip = pd.DataFrame()
                    if mapping["unit_num"] in df.columns:
                        new_equip["Unit #"] = df[mapping["unit_num"]]
                        
                        if mapping.get("eq_name") != "(선택 안 함)" and mapping["eq_name"] in df.columns:
                            new_equip["Equipment Name"] = df[mapping["eq_name"]]
                        else: new_equip["Equipment Name"] = "Equipment"
                        
                        if mapping.get("usage_hrs") != "(선택 안 함)" and mapping["usage_hrs"] in df.columns:
                            new_equip["Usage Hrs"] = pd.to_numeric(df[mapping["usage_hrs"]], errors='coerce').fillna(0)
                        else: new_equip["Usage Hrs"] = 0
                        
                        new_equip = new_equip[new_equip["Unit #"].notna()]
                        st.session_state.equip_df = new_equip

                st.success("✅ 데이터가 아래 입력폼에 채워졌습니다! 내용을 검토하고 Submit 하세요.")
                st.rerun()
                
            except Exception as e:
                st.error(f"데이터 처리 실패: {e}")


# ==========================================
# [공통] 입력 폼 (검토 및 수정)
# ==========================================
st.divider()

with st.form("ticket_form", clear_on_submit=False):
    st.subheader("📝 티켓 내용 검토 및 저장 (Ticket Review)")
    
    # 1. 헤더 (Job, Date 등)
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
    st.markdown("##### 👷‍♂️ 인력 (Labour)")
    edited_labour = st.data_editor(st.session_state.labour_df, num_rows="dynamic", use_container_width=True, key="ed_labour")

    st.markdown("##### 🚜 장비 (Equipment)")
    edited_equip = st.data_editor(st.session_state.equip_df, num_rows="dynamic", use_container_width=True, key="ed_equip")
    
    st.markdown("##### 📦 자재/기타 (Material)")
    edited_misc = st.data_editor(st.session_state.misc_df, num_rows="dynamic", use_container_width=True, key="ed_misc")

    # 3. 저장 버튼
    submit_btn = st.form_submit_button("✅ 최종 저장 (Final Submit)", type="primary", use_container_width=True)

    if submit_btn:
        if not ticket_number:
            st.error("티켓 번호(Ticket #)는 필수입니다!")
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

                st.success(f"🎉 티켓 [{ticket_number}] 저장이 완료되었습니다!")
                
                # 초기화
                st.session_state.labour_df = pd.DataFrame(columns=["Crew Name", "Trade", "Reg Hrs", "OT Hrs", "Travel Hrs", "Subsistence"])
                st.session_state.equip_df = pd.DataFrame(columns=["Unit #", "Equipment Name", "Operator", "Usage Hrs"])
                st.rerun()

            except Exception as e:
                st.error(f"저장 중 오류 발생: {e}")