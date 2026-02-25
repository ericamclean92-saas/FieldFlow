import streamlit as st
import pandas as pd
from utils.supabase_client import supabase
from datetime import datetime

st.set_page_config(page_title="Time Ticket Entry", layout="wide")
st.title("⏱️ Time Ticket Entry (현장 타임 티켓)")

# --- 초기 데이터 로딩 함수 ---
def get_active_jobs():
    try:
        # Job 정보와 함께 기본값(AFE, PO 등)도 가져옴
        res = supabase.table("master_project").select("*").eq("status", "Active").execute()
        return res.data if res.data else []
    except: return []

jobs_data = get_active_jobs()
job_list = [j['job_number'] for j in jobs_data]

# --- [상단] 입력 방식 선택 (Manual vs Import) ---
entry_mode = st.radio("입력 방식 선택", ["Manual Entry (수동)", "Import from File (엑셀)"], horizontal=True)

if entry_mode == "Manual Entry (수동)":
    
    with st.form("manual_ticket_form", clear_on_submit=False):
        st.subheader("1️⃣ Section 1: Ticket Details")
        
        # --- Section 1: 헤더 정보 ---
        c1, c2, c3, c4 = st.columns(4)
        with c1:
            selected_job_num = st.selectbox("Job #", job_list)
        with c2:
            ticket_date = st.date_input("Ticket Date", datetime.now())
        with c3:
            ticket_number = st.text_input("Ticket # (Unique)", placeholder="FT-260225-01")
        with c4:
            billing_type = st.selectbox("Billing Type", ["T&M", "Lump Sum", "Unit Price"])

        # 선택된 Job의 기본 정보 가져오기 (Default Value 채우기용)
        selected_job_data = next((j for j in jobs_data if j['job_number'] == selected_job_num), {})
        
        # 코딩 디테일 (Job 마스터에서 가져오되 수정 가능)
        st.caption("Coding Details (Editable)")
        cc1, cc2, cc3, cc4 = st.columns(4)
        with cc1:
            afe = st.text_input("AFE #", value=selected_job_data.get('afe_number', ''))
        with cc2:
            po = st.text_input("PO #", value=selected_job_data.get('po_number', ''))
        with cc3:
            major = st.text_input("Major Code", value=selected_job_data.get('major', ''))
        with cc4:
            minor = st.text_input("Minor Code", value=selected_job_data.get('minor', ''))

        desc = st.text_area("Work Description", height=80, placeholder="오늘 수행한 작업 내용 상세 기술...")
        comments = st.text_input("Internal Comments (관리자용)", placeholder="특이사항...")

        st.divider()

        # --- Section 2: Labour (인력) ---
        st.subheader("2️⃣ Section 2: Labour (인력)")
        
        # 초기 빈 데이터프레임 생성
        if "labour_df" not in st.session_state:
            st.session_state.labour_df = pd.DataFrame(columns=["Crew Name", "Trade", "Reg Hrs", "OT Hrs", "Travel Hrs", "Subsistence"])

        edited_labour = st.data_editor(
            st.session_state.labour_df,
            num_rows="dynamic",
            use_container_width=True,
            column_config={
                "Crew Name": st.column_config.TextColumn("이름", required=True),
                "Trade": st.column_config.SelectboxColumn("직종", options=["Supervisor", "Foreman", "Pipefitter", "Welder", "Laborer", "Operator"], required=True),
                "Reg Hrs": st.column_config.NumberColumn("정규 시간", min_value=0.0, step=0.5),
                "OT Hrs": st.column_config.NumberColumn("OT 시간", min_value=0.0, step=0.5),
                "Travel Hrs": st.column_config.NumberColumn("이동 시간", min_value=0.0, step=0.5),
                "Subsistence": st.column_config.CheckboxColumn("식대/숙박(Sub)", default=False)
            },
            key="labour_editor"
        )

        st.divider()

        # --- Section 3: Equipment (장비) ---
        st.subheader("3️⃣ Section 3: Equipment (장비)")
        
        if "equip_df" not in st.session_state:
            st.session_state.equip_df = pd.DataFrame(columns=["Unit #", "Equipment Name", "Operator", "Usage Hrs"])

        edited_equip = st.data_editor(
            st.session_state.equip_df,
            num_rows="dynamic",
            use_container_width=True,
            column_config={
                "Unit #": st.column_config.TextColumn("장비 번호", required=True),
                "Equipment Name": st.column_config.TextColumn("장비명", required=True),
                "Operator": st.column_config.TextColumn("운전원 (Optional)"),
                "Usage Hrs": st.column_config.NumberColumn("사용 시간", min_value=0.0, step=0.5)
            },
            key="equip_editor"
        )

        st.divider()

        # --- Section 4: Miscellaneous (자재/기타) ---
        st.subheader("4️⃣ Section 4: Miscellaneous (자재/기타)")
        
        if "misc_df" not in st.session_state:
            st.session_state.misc_df = pd.DataFrame(columns=["Description", "Qty", "Rate", "Total"])

        edited_misc = st.data_editor(
            st.session_state.misc_df,
            num_rows="dynamic",
            use_container_width=True,
            column_config={
                "Description": st.column_config.TextColumn("항목 설명", required=True),
                "Qty": st.column_config.NumberColumn("수량", min_value=0.0, step=1.0),
                "Rate": st.column_config.NumberColumn("단가($)", min_value=0.0, format="$%.2f"),
                "Total": st.column_config.NumberColumn("합계($)", disabled=True) # UI상 보여주기용
            },
            key="misc_editor"
        )

        st.divider()

        # --- Submit 버튼 ---
        submit_btn = st.form_submit_button("✅ Submit Ticket (티켓 생성)", type="primary", use_container_width=True)

        if submit_btn:
            if not ticket_number:
                st.error("티켓 번호(Ticket #)는 필수입니다!")
            else:
                try:
                    # 1. 헤더 저장
                    header_data = {
                        "ticket_number": ticket_number,
                        "job_number": selected_job_num,
                        "ticket_date": str(ticket_date),
                        "afe_number": afe,
                        "po_number": po,
                        "major_code": major,
                        "minor_code": minor,
                        "work_description": desc,
                        "internal_comments": comments,
                        "status": "Ticket Created" # 바로 생성 상태로
                    }
                    supabase.table("field_tickets").insert(header_data).execute()

                    # 2. Labour 저장
                    labour_list = []
                    for _, row in edited_labour.iterrows():
                        if row["Crew Name"]: # 이름이 있는 행만 저장
                            labour_list.append({
                                "ticket_number": ticket_number,
                                "crew_name": row["Crew Name"],
                                "trade": row["Trade"],
                                "regular_hours": row["Reg Hrs"],
                                "overtime_hours": row["OT Hrs"],
                                "travel_hours": row["Travel Hrs"],
                                "subsistence": row["Subsistence"]
                            })
                    if labour_list:
                        supabase.table("field_labor").insert(labour_list).execute()

                    # 3. Equipment 저장
                    equip_list = []
                    for _, row in edited_equip.iterrows():
                        if row["Unit #"]:
                            equip_list.append({
                                "ticket_number": ticket_number,
                                "unit_number": row["Unit #"],
                                "equipment_name": row["Equipment Name"],
                                "operator_name": row["Operator"],
                                "usage_hours": row["Usage Hrs"]
                            })
                    if equip_list:
                        supabase.table("field_equipment").insert(equip_list).execute()

                    # 4. Material 저장
                    misc_list = []
                    for _, row in edited_misc.iterrows():
                        if row["Description"]:
                            misc_list.append({
                                "ticket_number": ticket_number,
                                "item_description": row["Description"],
                                "quantity": row["Qty"],
                                "rate": row["Rate"]
                            })
                    if misc_list:
                        supabase.table("field_material").insert(misc_list).execute()

                    st.success(f"🎉 티켓 [{ticket_number}] 생성이 완료되었습니다!")
                    
                except Exception as e:
                    st.error(f"저장 중 오류 발생: {e}")

elif entry_mode == "Import from File (엑셀)":
    st.info("🚧 엑셀/CSV 업로드 기능은 곧 구현될 예정입니다. (Option 2)")
    # 여기에 파일 업로더 구현 예정