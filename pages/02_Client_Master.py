import streamlit as st
import pandas as pd
from utils.supabase_client import supabase
from datetime import datetime

st.set_page_config(page_title="Client Master", layout="wide")
st.title("🏢 Client (고객사) 관리")

# --- 1. 고객사 등록 폼 ---
with st.expander("➕ 새로운 고객사 등록하기", expanded=True):
    with st.form("client_form"):
        col1, col2 = st.columns(2)
        
        with col1:
            client_name = st.text_input("고객사 이름 (필수)", placeholder="예: Shell Canada")
            email = st.text_input("이메일", placeholder="billing@shell.com")
            phone = st.text_input("전화번호", placeholder="403-123-4567")
        
        with col2:
            address = st.text_area("주소", placeholder="캘거리 본사 주소...")
            billing_terms = st.selectbox("결제 조건", ["Net 30", "Net 60", "Due on Receipt"])
            
        submitted = st.form_submit_button("고객사 저장하기", use_container_width=True)

        if submitted:
            if not client_name:
                st.error("⚠️ 고객사 이름은 필수입니다!")
            else:
                try:
                    new_client = {
                        "client_name": client_name,
                        "email": email,
                        "phone": phone,
                        "address": address,
                        "billing_terms": billing_terms,
                        "created_at": datetime.now().isoformat()
                    }
                    
                    # master_client 테이블에 저장
                    supabase.table("master_client").insert(new_client).execute()
                    st.success(f"✅ [{client_name}] 등록이 완료되었습니다!")
                    
                except Exception as e:
                    st.error(f"저장 중 오류 발생 (중복된 이름일 수 있습니다): {e}")

# --- 2. 등록된 고객사 목록 ---
st.divider()
st.subheader("📋 등록된 고객사 목록")

try:
    response = supabase.table("master_client").select("*").order("created_at", desc=True).execute()
    
    if response.data:
        df = pd.DataFrame(response.data)
        
        # 보여줄 컬럼 선택
        display_cols = ["client_name", "email", "phone", "billing_terms", "created_at"]
        available_cols = [c for c in display_cols if c in df.columns]
        
        st.dataframe(
            df[available_cols], 
            use_container_width=True,
            hide_index=True
        )
    else:
        st.info("아직 등록된 고객사가 없습니다.")

except Exception as e:
    st.error(f"데이터 로딩 실패: {e}")