import streamlit as st
import pandas as pd
from utils.supabase_client import supabase
from datetime import datetime, date
import io

st.set_page_config(page_title="LEM Management", layout="wide")
st.title("📑 LEM Management (작업 확인서)")

# --- 1. 사이드바 필터 (LEM 만들 대상 찾기) ---
st.sidebar.header("🔍 LEM 대상 찾기")

# Job 목록 가져오기
try:
    jobs_res = supabase.table("master_project").select("job_number, project_name").eq("status", "Active").execute()
    jobs = jobs_res.data if jobs_res.data else []
    job_opts = [j['job_number'] for j in jobs]
except:
    jobs = []
    job_opts = []

selected_job = st.sidebar.selectbox("Job # 선택", job_opts)

# 날짜 범위 (기간 설정)
today = date.today()
start_date = st.sidebar.date_input("시작일", date(today.year, today.month, 1))
end_date = st.sidebar.date_input("종료일", today)

# --- 2. 아직 LEM으로 안 묶인 티켓(Unassigned Tickets) 조회 ---
st.subheader(f"📋 LEM 미생성 티켓 목록 [{selected_job}]")

if selected_job:
    try:
        # 조건: 해당 Job + LEM ID가 없음(NULL) + 기간 내
        tickets_res = supabase.table("field_tickets")\
            .select("*")\
            .eq("job_number", selected_job)\
            .is_("lem_id", "null")\
            .gte("ticket_date", str(start_date))\
            .lte("ticket_date", str(end_date))\
            .order("ticket_date", desc=True)\
            .execute()
        
        tickets = tickets_res.data if tickets_res.data else []
    except Exception as e:
        st.error(f"티켓 로딩 실패: {e}")
        tickets = []

    if not tickets:
        st.info("선택한 기간에 LEM을 생성할 티켓이 없습니다.")
    else:
        # 데이터프레임 변환
        df_tickets = pd.DataFrame(tickets)
        df_tickets['Select'] = True  # 기본 선택
        
        # 편집 가능한 테이블로 보여주기
        edited_df = st.data_editor(
            df_tickets[["Select", "ticket_number", "ticket_date", "work_description", "status"]],
            column_config={
                "Select": st.column_config.CheckboxColumn("포함?", default=True),
                "ticket_number": "Ticket #",
                "ticket_date": "Date",
                "work_description": "Description"
            },
            hide_index=True,
            use_container_width=True
        )

        # 선택된 티켓만 추출
        selected_rows = edited_df[edited_df["Select"] == True]
        
        st.divider()

        # --- 3. LEM 생성 액션 ---
        if not selected_rows.empty:
            st.subheader("⚙️ Create LEM (LEM 생성)")
            
            c1, c2 = st.columns([2, 1])
            with c1:
                # LEM 번호 자동 제안 (Job번호 + 오늘날짜)
                suggestion = f"LEM-{selected_job}-{datetime.now().strftime('%y%m%d')}"
                lem_number_input = st.text_input("LEM Number", value=suggestion)
            
            with c2:
                st.write("")
                st.write("")
                create_btn = st.button("🚀 LEM 생성하기", type="primary", use_container_width=True)

            if create_btn:
                try:
                    # 1. LEM 헤더 생성
                    lem_data = {
                        "lem_number": lem_number_input,
                        "job_number": selected_job,
                        "lem_date": str(date.today()),
                        "period_start": str(start_date),
                        "period_end": str(end_date),
                        "status": "Generated"
                    }
                    lem_res = supabase.table("lems").insert(lem_data).execute()
                    new_lem_id = lem_res.data[0]['id']

                    # 2. 티켓들에 LEM ID 업데이트
                    # 선택된 티켓 번호 리스트 추출
                    target_ticket_nums = selected_rows['ticket_number'].tolist()
                    
                    supabase.table("field_tickets")\
                        .update({"lem_id": new_lem_id})\
                        .in_("ticket_number", target_ticket_nums)\
                        .execute()

                    st.success(f"✅ LEM [{lem_number_input}] 생성이 완료되었습니다!")
                    st.rerun()

                except Exception as e:
                    st.error(f"생성 중 오류 발생: {e}")

# --- 4. 생성된 LEM 목록 및 내보내기 (Export) ---
st.divider()
st.subheader("📂 LEM History & Export")

try:
    # 최근 생성된 LEM 조회
    lem_list_res = supabase.table("lems").select("*").order("created_at", desc=True).limit(10).execute()
    lems = lem_list_res.data if lem_list_res.data else []

    if lems:
        for lem in lems:
            with st.expander(f"📄 {lem['lem_number']} ({lem['lem_date']}) - {lem['status']}"):
                col_info, col_export = st.columns([3, 1])
                
                with col_info:
                    st.write(f"**Job:** {lem['job_number']}")
                    st.caption(f"Period: {lem['period_start']} ~ {lem['period_end']}")
                    
                    # 이 LEM에 포함된 티켓들 보여주기
                    linked_tickets = supabase.table("field_tickets").select("ticket_number, ticket_date, work_description").eq("lem_id", lem['id']).execute()
                    if linked_tickets.data:
                        st.dataframe(pd.DataFrame(linked_tickets.data), hide_index=True)

                with col_export:
                    st.write("📤 **Export Options**")
                    
                    # [기능] 엑셀 다운로드 생성 로직
                    def to_excel(lem_data, tickets_data):
                        output = io.BytesIO()
                        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                            # 시트 1: LEM Summary
                            pd.DataFrame([lem_data]).to_excel(writer, sheet_name='LEM Summary', index=False)
                            # 시트 2: 상세 티켓
                            if tickets_data:
                                pd.DataFrame(tickets_data).to_excel(writer, sheet_name='Tickets', index=False)
                        return output.getvalue()

                    excel_data = to_excel(lem, linked_tickets.data)
                    
                    st.download_button(
                        label="Download Excel (LEM)",
                        data=excel_data,
                        file_name=f"{lem['lem_number']}.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        key=f"btn_xls_{lem['id']}"
                    )
                    
                    st.caption("For Sage/QuickBooks import, use this Excel.")

    else:
        st.info("생성된 LEM이 없습니다.")

except Exception as e:
    st.error(f"목록 로딩 실패: {e}")
