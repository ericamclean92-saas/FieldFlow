import streamlit as st
import pandas as pd
from utils.supabase_client import supabase
from datetime import datetime

st.set_page_config(page_title="Job Management", layout="wide")
st.title("📂 Job (프로젝트) 관리")

# --- 1. Job 등록 폼 ---
with st.expander("➕ 새로운 Job 등록하기", expanded=True):
    with st.form("project_form"):
        col1, col2, col3 = st.columns(3)
        
        with col1:
            job_number = st.text_input("Job Number (필수)", placeholder="예: 25-001")
            client_name = st.text_input("Client Name", placeholder="예: Shell Canada")
            assigned_pm = st.text_input("Project Manager", placeholder="담당 PM 이름")
            
        with col2:
            project_name = st.text_input("Project Name", placeholder="프로젝트명")
            location_name = st.text_input("Location / Field", placeholder="현장 위치")
            lsd = st.text_input("LSD (Location)", placeholder="예: 01-02-003-04 W5M")
            
        with col3:
            afe_number = st.text_input("AFE Number", placeholder="예: AFE-12345")
            po_number = st.text_input("PO Number", placeholder="예: PO-98765")
            status = st.selectbox("Status", ["Active", "Completed", "Pending"])

        submitted = st.form_submit_button("Job 저장하기", use_container_width=True)

        if submitted:
            if not job_number:
                st.error("⚠️ Job Number는 필수 항목입니다!")
            else:
                try:
                    # 데이터 준비
                    new_project = {
                        "job_number": job_number,
                        "project_name": project_name,
                        "client_name": client_name,
                        "location_name": location_name,
                        "lsd": lsd,
                        "afe_number": afe_number,
                        "po_number": po_number,
                        "assigned_pm": assigned_pm,
                        "status": status,
                        "last_modified": datetime.now().isoformat()
                    }
                    
                    # Supabase에 넣기 (테이블 이름: master_project)
                    supabase.table("master_project").insert(new_project).execute()
                    
                    st.success(f"✅ Job [{job_number}] 등록 완료!")
                    # 페이지 새로고침은 사용자가 원할 때 하도록 둡니다.
                except Exception as e:
                    st.error(f"저장 중 오류 발생: {e}")

# --- 2. 등록된 Job 목록 (데이터 그리드) ---
st.divider()
st.subheader("📋 전체 프로젝트 목록")

try:
    # 데이터 가져오기
    response = supabase.table("master_project").select("*").order("created_at", desc=True).execute()
    
    if response.data:
        df = pd.DataFrame(response.data)
        
        # 보고 싶은 컬럼만 추려서 순서대로 보여주기
        display_cols = [
            "job_number", "client_name", "project_name", 
            "location_name", "afe_number", "status", "created_at"
        ]
        # 데이터프레임에 해당 컬럼이 있는지 확인 후 출력
        available_cols = [c for c in display_cols if c in df.columns]
        
        st.dataframe(
            df[available_cols], 
            use_container_width=True,
            hide_index=True
        )
    else:
        st.info("등록된 데이터가 없습니다.")
        
except Exception as e:
    st.error(f"데이터 로딩 실패: {e}")