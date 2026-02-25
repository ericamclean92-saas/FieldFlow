import streamlit as st
import pandas as pd
from utils.supabase_client import supabase
from datetime import datetime
import io

st.set_page_config(page_title="Time Ticket Entry", layout="wide")
st.title("⏱️ Time Ticket Entry (현장 타임 티켓)")

# --- 초기 데이터 로딩 함수 ---
def get_active_jobs():
    try:
        res = supabase.table("master_project").select("*").eq("status", "Active").execute()
        return res.data if res.data else []
    except: return []

jobs_data = get_active_jobs()
job_list = [j['job_number'] for j in jobs_data]

# --- [기능] 엑셀 템플릿 생성 함수 ---
def generate_excel_template():
    output = io.BytesIO()
    writer = pd.ExcelWriter(output, engine='xlsxwriter')
    
    # 1. 헤더 시트
    df_header = pd.DataFrame([{
        "Job Number": "25-001", "Date": "2026-02-25", "Ticket Number": "FT-Temp-01", 
        "Billing Type": "T&M", "AFE": "", "PO": "", "Description": "작업 내용..."
    }])
    df_header.to_excel(writer, sheet_name='Header', index=False)
    
    # 2. 인력 시트
    df_labor = pd.DataFrame(columns=["Crew Name", "Trade", "Reg Hrs", "OT Hrs", "Travel Hrs", "Subsistence"])
    df_labor.to_excel(writer, sheet_name='Labor', index=False)
    
    # 3. 장비 시트
    df_equip = pd.DataFrame(columns=["Unit #", "Equipment Name", "Operator", "Usage Hrs"])
    df_equip.to_excel(writer, sheet_name='Equipment', index=False)
    
    # 4. 자재 시트
    df_misc = pd.DataFrame(columns=["Description", "Qty", "Rate"])
    df_misc.to_excel(writer, sheet_name='Material', index=False)
    
    writer.close()
    processed_data = output.getvalue()
    return processed_data

# --- [상단] 입력 방식 선택 ---
entry_mode = st.radio("입력 방식 선택", ["Manual Entry (수동)", "Import from File (엑셀)"], horizontal=True)

# 세션 상태 초기화 (데이터 담을 그릇)
if "labour_df" not in st.session_state:
    st.session_state.labour_df = pd.DataFrame(columns=["Crew Name", "Trade", "Reg Hrs", "OT Hrs", "Travel Hrs", "Subsistence"])
if "equip_df" not in st.session_state:
    st.session_state.equip_df = pd.DataFrame(columns=["Unit #", "Equipment Name", "Operator", "Usage Hrs"])
if "misc_df" not in st.session_state:
    st.session_state.misc_df = pd.DataFrame(columns=["Description", "Qty", "Rate", "Total"])
if "header_info" not in st.session_state:
    st.session_state.header_info = {}

# --- Option 2: Import 모드일 때 로직 ---
if entry_mode == "Import from File (엑셀)":
    st.info("💡 지정된 엑셀 템플릿을 업로드하면 아래 양식에 자동으로 채워집니다.")
    
    col_u1, col_u2 = st.columns([2, 1])
    with col_u1:
        uploaded_file = st.file_uploader("엑셀 파일 업로드 (.xlsx)", type=["xlsx"])
    with col_u2:
        st.write("양식이 없으신가요?")
        st.download_button(
            label="📥 기본 템플릿 다운로드",
            data=generate_excel_template(),
            file_name="FieldFlow_Ticket_Template.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

    if uploaded_file:
        try:
            # 엑셀 읽기
            xls = pd.ExcelFile(uploaded_file)
            
            # 1. 헤더 정보 읽기
            if 'Header' in xls.sheet_names:
                df_h = pd.read_excel(xls, 'Header')
                if not df_h.empty:
                    # 세션에 저장 (아래 폼에 채우기 위함)
                    row = df_h.iloc[0]
                    st.session_state.header_info = {
                        "job": str(row.get("Job Number", "")),
                        "date": row.get("Date", datetime.now()),
                        "ticket": str(row.get("Ticket Number", "")),
                        "billing": str(row.get("Billing Type", "T&M")),
                        "afe": str(row.get("AFE", "")),
                        "po": str(row.get("PO", "")),
                        "desc": str(row.get("Description", ""))
                    }

            # 2. 상세 정보 읽기 & 세션 업데이트
            if 'Labor' in xls.sheet_names:
                st.session_state.labour_df = pd.read_excel(xls, 'Labor')
            if 'Equipment' in xls.sheet_names:
                st.session_state.equip_df = pd.read_excel(xls, 'Equipment')
            if 'Material' in xls.sheet_names:
                st.session_state.misc_df = pd.read_excel(xls, 'Material')
                # Total 컬럼이 없으면 계산
                if "Total" not in st.session_state.misc_df.columns:
                     st.session_state.misc_df["Total"] = st.session_state.misc_df["Qty"] * st.session_state.misc_df["Rate"]

            st.success("✅ 파일 로딩 성공! 아래 내용을 검토하고 Submit 버튼을 누르세요.")
            
        except Exception as e:
            st.error(f"파일 읽기 실패: {e}")

# --- 공통 입력 폼 (Manual & Import 둘 다 여기서 보여줌) ---
st.divider()

with st.form("ticket_form", clear_on_submit=False):
    st.subheader("1️⃣ Section 1: Ticket Details")
    
    # Import된 데이터가 있으면 기본값으로 사용
    defaults = st.session_state.get("header_info", {})
    
    # Job 번호 매칭
    default_job_index = 0
    if defaults.get("job") and defaults.get("job") in job_list:
        default_job_index = job_list.index(defaults.get("job"))

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        selected_job_num = st.selectbox("Job #", job_list, index=default_job_index)
    with c2:
        # 날짜 처리
        d_date = defaults.get("date", datetime.now())
        if isinstance(d_date, str): 
            try: d_date = datetime.strptime(d_date, "%Y-%m-%d")
            except: d_date = datetime.now()
        ticket_date = st.date_input("Ticket Date", d_date)
    with c3:
        ticket_number = st.text_input("Ticket # (Unique)", value=defaults.get("ticket", ""), placeholder="FT-260225-01")
    with c4:
        # Billing Type 처리
        b_opts = ["T&M", "Lump Sum", "Unit Price"]
        b_idx = b_opts.index(defaults.get("billing")) if defaults.get("billing") in b_opts else 0
        billing_type = st.selectbox("Billing Type", b_opts, index=b_idx)

    # 코딩 디테일
    st.caption("Coding Details & Description")
    cc1, cc2, cc3 = st.columns(3)
    with cc1:
        afe = st.text_input("AFE #", value=defaults.get("afe", ""))
    with cc2:
        po = st.text_input("PO #", value=defaults.get("po", ""))
    with cc3:
        desc = st.text_input("Work Description", value=defaults.get("desc", ""))

    st.divider()

    # --- Section 2: Labour ---
    st.subheader("2️⃣ Section 2: Labour (인력)")
    edited_labour = st.data_editor(
        st.session_state.labour_df,
        num_rows="dynamic",
        use_container_width=True,
        column_config={
            "Crew Name": st.column_config.TextColumn("이름", required=True),
            "Trade": st.column_config.SelectboxColumn("직종", options=["Supervisor", "Foreman", "Pipefitter", "Welder", "Laborer", "Operator"], required=True),
            "Reg Hrs": st.column_config.NumberColumn("정규 시간", min_value=0.0, step=0.5),
            "OT Hrs": st.column_config.NumberColumn("OT 시간", min_value=0.0, step=0.5),
            "Subsistence": st.column_config.CheckboxColumn("식대/숙박(Sub)", default=False)
        },
        key="labour_editor"
    )

    # --- Section 3: Equipment ---
    st.subheader("3️⃣ Section 3: Equipment (장비)")
    edited_equip = st.data_editor(
        st.session_state.equip_df,
        num_rows="dynamic",
        use_container_width=True,
        column_config={
            "Unit #": st.column_config.TextColumn("장비 번호", required=True),
            "Equipment Name": st.column_config.TextColumn("장비명", required=True),
            "Usage Hrs": st.column_config.NumberColumn("사용 시간", min_value=0.0, step=0.5)
        },
        key="equip_editor"
    )

    # --- Section 4: Material ---
    st.subheader("4️⃣ Section 4: Miscellaneous (자재/기타)")
    edited_misc = st.data_editor(
        st.session_state.misc_df,
        num_rows="dynamic",
        use_container_width=True,
        column_config={
            "Description": st.column_config.TextColumn("항목 설명", required=True),
            "Qty": st.column_config.NumberColumn("수량", min_value=0.0, step=1.0),
            "Rate": st.column_config.NumberColumn("단가($)", min_value=0.0, format="$%.2f")
        },
        key="misc_editor"
    )

    st.divider()

    # --- Submit 버튼 (Import 모드든 Manual 모드든 똑같이 여기서 저장) ---
    submit_btn = st.form_submit_button("✅ Submit Ticket (검토 완료 및 저장)", type="primary", use_container_width=True)

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
                    "work_description": desc,
                    "status": "Ticket Created" # 생성 완료 상태
                }
                supabase.table("field_tickets").insert(header_data).execute()

                # 2. Labour 저장
                labour_list = []
                for _, row in edited_labour.iterrows():
                    if row.get("Crew Name"):
                        labour_list.append({
                            "ticket_number": ticket_number,
                            "crew_name": row["Crew Name"],
                            "trade": row["Trade"],
                            "regular_hours": row.get("Reg Hrs", 0),
                            "overtime_hours": row.get("OT Hrs", 0),
                            "subsistence": row.get("Subsistence", False)
                        })
                if labour_list:
                    supabase.table("field_labor").insert(labour_list).execute()

                # 3. Equipment 저장
                equip_list = []
                for _, row in edited_equip.iterrows():
                    if row.get("Unit #"):
                        equip_list.append({
                            "ticket_number": ticket_number,
                            "unit_number": row["Unit #"],
                            "equipment_name": row["Equipment Name"],
                            "operator_name": row.get("Operator", ""),
                            "usage_hours": row.get("Usage Hrs", 0)
                        })
                if equip_list:
                    supabase.table("field_equipment").insert(equip_list).execute()

                # 4. Material 저장
                misc_list = []
                for _, row in edited_misc.iterrows():
                    if row.get("Description"):
                        misc_list.append({
                            "ticket_number": ticket_number,
                            "item_description": row["Description"],
                            "quantity": row.get("Qty", 0),
                            "rate": row.get("Rate", 0)
                        })
                if misc_list:
                    supabase.table("field_material").insert(misc_list).execute()

                st.success(f"🎉 티켓 [{ticket_number}] 생성이 완료되었습니다!")
                
                # 세션 초기화 (다음 입력을 위해)
                for key in ["labour_df", "equip_df", "misc_df", "header_info"]:
                    if key in st.session_state:
                        del st.session_state[key]
                st.rerun()

            except Exception as e:
                st.error(f"저장 중 오류 발생: {e}")