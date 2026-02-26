import streamlit as st
import pandas as pd
from utils.supabase_client import supabase
from datetime import datetime
import time

st.set_page_config(page_title="Bulk Ticket Import", layout="wide")
st.title("🚀 Bulk Ticket Import & Review")

# --- 1. 저장된 매핑 설정 가져오기 ---
def get_saved_maps():
    try:
        res = supabase.table("client_import_maps").select("*").order("created_at", desc=True).execute()
        return res.data if res.data else []
    except: return []

saved_maps = get_saved_maps()

# --- 2. 탭 구성 (업로드 / 검토) ---
tab_import, tab_review = st.tabs(["📤 Bulk Upload (일괄 업로드)", "📝 Draft Review (검토 및 승인)"])

# ==========================================
# [TAB 1] Bulk Upload Logic
# ==========================================
with tab_import:
    st.info("파일을 업로드하면 자동으로 그룹화하여 'Draft(임시)' 티켓들을 생성합니다.")
    
    col_u1, col_u2 = st.columns([1, 2])
    with col_u1:
        map_options = {m['map_name']: m for m in saved_maps}
        if not map_options:
            st.warning("⚠️ Settings 메뉴에서 매핑 설정을 먼저 등록하세요.")
            selected_map = None
        else:
            selected_profile = st.selectbox("매핑 설정 선택", list(map_options.keys()))
            selected_map = map_options[selected_profile]

    with col_u2:
        uploaded_file = st.file_uploader("엑셀 파일 업로드", type=["xlsx", "xlsm", "csv"])

    if uploaded_file and selected_map and st.button("🚀 일괄 생성 시작 (Generate Drafts)", type="primary"):
        try:
            # 1. 파일 읽기
            header_idx = selected_map['header_row_idx']
            if uploaded_file.name.endswith('.csv'):
                df = pd.read_csv(uploaded_file, header=header_idx)
            else:
                df = pd.read_excel(uploaded_file, header=header_idx, engine='openpyxl')
            
            # 매핑 정보
            grp_cols = selected_map['mapping_data']['group_cols']
            dat_cols = selected_map['mapping_data']['data_cols']
            
            # 2. 필수 컬럼 확인 (Ticket#, Job#, Date 중 하나라도 있어야 그룹핑 가능)
            t_col = grp_cols.get("ticket_num")
            j_col = grp_cols.get("job_num")
            d_col = grp_cols.get("date")
            
            if t_col == "(Not Selected)" and (j_col == "(Not Selected)" or d_col == "(Not Selected)"):
                st.error("그룹핑을 위해 'Ticket #' 또는 'Job # + Date'가 매핑되어야 합니다.")
                st.stop()

            # 3. 그룹핑 키 생성 (Key = Ticket# 혹은 Job+Date)
            # 데이터프레임에 임시 그룹키 컬럼 추가
            df['__GROUP_KEY__'] = ""
            
            for index, row in df.iterrows():
                # Ticket 번호가 있으면 그걸 최우선으로 씀
                if t_col != "(Not Selected)" and t_col in df.columns and pd.notna(row[t_col]):
                    key = str(row[t_col]).strip()
                else:
                    # 없으면 Job + Date 조합
                    j_val = str(row[j_col]).strip() if j_col in df.columns else "UnknownJob"
                    d_val = str(row[d_col]).strip() if d_col in df.columns else datetime.now().strftime("%Y-%m-%d")
                    key = f"{j_val}_{d_val}"
                df.at[index, '__GROUP_KEY__'] = key
            
            # 4. 그룹별로 순회하며 DB 저장
            grouped = df.groupby('__GROUP_KEY__')
            success_count = 0
            
            progress_bar = st.progress(0)
            total_groups = len(grouped)
            
            for i, (key, group) in enumerate(grouped):
                # (1) 헤더 정보 추출 (그룹의 첫 번째 행 기준)
                first_row = group.iloc[0]
                
                # 티켓 번호 (없으면 자동 생성)
                ticket_num = key if t_col != "(Not Selected)" else f"DRAFT-{key}-{int(time.time())}"
                
                # Job 번호
                job_num = str(first_row[j_col]).strip() if j_col != "(Not Selected)" and j_col in df.columns else "Unknown"
                
                # 날짜
                try:
                    t_date = pd.to_datetime(first_row[d_col]).strftime("%Y-%m-%d") if d_col != "(Not Selected)" else datetime.now().strftime("%Y-%m-%d")
                except: t_date = datetime.now().strftime("%Y-%m-%d")

                # DB Insert: Field Ticket Header
                header_data = {
                    "ticket_number": ticket_number,
                    "job_number": job_num,
                    "ticket_date": t_date,
                    "status": "Draft",  # 중요: Draft 상태로 저장
                    "work_description": f"Imported from {uploaded_file.name}"
                }
                # 중복 방지 (Upsert 유사 효과) -> 여기선 에러 무시하고 진행하거나, 기존거 삭제 후 생성 정책 필요
                # 일단 간단하게 try-except
                try:
                    supabase.table("field_tickets").insert(header_data).execute()
                except:
                    # 이미 존재하면 넘어감 (혹은 업데이트 로직 추가 가능)
                    pass

                # DB Insert: Labor Items
                labor_list = []
                for _, row in group.iterrows():
                    if dat_cols["crew_name"] != "(Not Selected)" and pd.notna(row[dat_cols["crew_name"]]):
                        labor_list.append({
                            "ticket_number": ticket_number,
                            "crew_name": row[dat_cols["crew_name"]],
                            "trade": row[dat_cols["trade"]] if dat_cols["trade"] != "(Not Selected)" else "Laborer",
                            "regular_hours": row[dat_cols["reg_hrs"]] if dat_cols["reg_hrs"] != "(Not Selected)" else 0,
                            "overtime_hours": row[dat_cols["ot_hrs"]] if dat_cols["ot_hrs"] != "(Not Selected)" else 0
                        })
                if labor_list:
                    supabase.table("field_labor").insert(labor_list).execute()

                # DB Insert: Equipment Items
                equip_list = []
                for _, row in group.iterrows():
                    if dat_cols["unit_num"] != "(Not Selected)" and pd.notna(row[dat_cols["unit_num"]]):
                        equip_list.append({
                            "ticket_number": ticket_number,
                            "unit_number": row[dat_cols["unit_num"]],
                            "equipment_name": row[dat_cols["eq_name"]] if dat_cols["eq_name"] != "(Not Selected)" else "Equipment",
                            "usage_hours": row[dat_cols["usage_hrs"]] if dat_cols["usage_hrs"] != "(Not Selected)" else 0
                        })
                if equip_list:
                    supabase.table("field_equipment").insert(equip_list).execute()
                
                success_count += 1
                progress_bar.progress((i + 1) / total_groups)

            st.success(f"🎉 총 {success_count}개의 Draft 티켓이 생성되었습니다! 'Draft Review' 탭에서 확인하세요.")
            
        except Exception as e:
            st.error(f"처리 중 오류 발생: {e}")


# ==========================================
# [TAB 2] Draft Review Logic
# ==========================================
with tab_review:
    st.markdown("### 📝 Draft Tickets (검토 대기)")
    
    # 1. Draft 상태인 티켓만 불러오기
    try:
        res = supabase.table("field_tickets").select("*").eq("status", "Draft").order("created_at", desc=True).execute()
        drafts = res.data if res.data else []
    except: drafts = []
    
    if not drafts:
        st.info("현재 검토할 Draft 티켓이 없습니다.")
    else:
        # 리스트 보여주기
        for ticket in drafts:
            with st.expander(f"📍 {ticket['ticket_number']} | Job: {ticket['job_number']} | Date: {ticket['ticket_date']}"):
                
                # 상세 데이터 로딩
                lab_res = supabase.table("field_labor").select("*").eq("ticket_number", ticket['ticket_number']).execute()
                eq_res = supabase.table("field_equipment").select("*").eq("ticket_number", ticket['ticket_number']).execute()
                
                df_lab = pd.DataFrame(lab_res.data) if lab_res.data else pd.DataFrame()
                df_eq = pd.DataFrame(eq_res.data) if eq_res.data else pd.DataFrame()

                c1, c2 = st.columns(2)
                with c1:
                    st.caption("Labor")
                    if not df_lab.empty: st.dataframe(df_lab[["crew_name", "trade", "regular_hours", "overtime_hours"]], use_container_width=True, hide_index=True)
                    else: st.write("-")
                with c2:
                    st.caption("Equipment")
                    if not df_eq.empty: st.dataframe(df_eq[["unit_number", "equipment_name", "usage_hours"]], use_container_width=True, hide_index=True)
                    else: st.write("-")
                
                # Action Buttons
                btn_col1, btn_col2, btn_col3 = st.columns([1, 1, 4])
                with btn_col1:
                    if st.button("✅ Approve", key=f"app_{ticket['id']}"):
                        supabase.table("field_tickets").update({"status": "Ticket Created"}).eq("id", ticket['id']).execute()
                        st.success("Approved!")
                        st.rerun()
                with btn_col2:
                    if st.button("🗑️ Delete", key=f"del_{ticket['id']}", type="secondary"):
                        # Cascading delete usually needed, but basic delete for header here
                        supabase.table("field_tickets").delete().eq("id", ticket['id']).execute()
                        st.warning("Deleted.")
                        st.rerun()
