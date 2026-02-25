import streamlit as st
import pandas as pd
from utils.supabase_client import supabase
from datetime import datetime

st.set_page_config(page_title="Rate Master", layout="wide")
st.title("💰 Rate Sheet (단가표) 관리")

tab1, tab2 = st.tabs(["1. 단가표 생성 (Header)", "2. 항목 추가 (Details)"])

# --- TAB 1: 단가표(Rate Sheet) 이름 만들기 ---
with tab1:
    st.subheader("새로운 단가표 만들기")
    with st.form("rate_list_form"):
        col1, col2 = st.columns(2)
        with col1:
            rate_list_name = st.text_input("단가표 이름 (필수)", placeholder="예: 2026 Standard Rates")
            effective_date = st.date_input("적용 시작일")
        with col2:
            rate_type = st.selectbox("유형", ["Standard", "Discounted", "Premium"])
            expiry_date = st.date_input("만료일")
        
        submitted_header = st.form_submit_button("단가표 생성")
        
        if submitted_header:
            if not rate_list_name:
                st.error("단가표 이름을 입력하세요.")
            else:
                try:
                    data = {
                        "rate_list_name": rate_list_name,
                        "rate_type": rate_type,
                        "effective_date": str(effective_date),
                        "expiry_date": str(expiry_date)
                    }
                    supabase.table("master_rate_list").insert(data).execute()
                    st.success(f"✅ [{rate_list_name}] 단가표가 생성되었습니다!")
                except Exception as e:
                    st.error(f"생성 실패 (중복된 이름일 수 있음): {e}")

    # 생성된 단가표 목록
    st.divider()
    try:
        res = supabase.table("master_rate_list").select("*").execute()
        if res.data:
            st.dataframe(pd.DataFrame(res.data)[["rate_list_name", "rate_type", "effective_date"]], use_container_width=True)
    except:
        pass

# --- TAB 2: 단가표에 항목(아이템) 추가하기 ---
with tab2:
    st.subheader("단가표에 상세 항목 추가")
    
    # 1. 단가표 선택하기
    try:
        res_list = supabase.table("master_rate_list").select("rate_list_name").execute()
        rate_lists = [i['rate_list_name'] for i in res_list.data] if res_list.data else []
    except:
        rate_lists = []
    
    if not rate_lists:
        st.warning("먼저 '탭 1'에서 단가표를 생성하세요.")
    else:
        selected_sheet = st.selectbox("어떤 단가표에 추가할까요?", rate_lists)
        
        st.divider()
        
        # 2. 항목 입력 폼
        with st.form("rate_item_form"):
            c1, c2, c3 = st.columns(3)
            with c1:
                item_type = st.selectbox("항목 유형", ["Labor", "Equipment", "Material", "Subcontractor"])
                item_name = st.text_input("항목명 (Item Name)", placeholder="예: Supervisor, Crew Truck")
            with c2:
                unit = st.selectbox("단위", ["Hr", "Day", "Km", "Ea", "Ls"])
                regular_rate = st.number_input("기본 단가 ($)", min_value=0.0, step=1.0)
            with c3:
                ot_rate = st.number_input("OT 단가 ($)", min_value=0.0, step=1.0)
                gl_code = st.text_input("GL Code (매출)", placeholder="4000-01")
            
            submitted_item = st.form_submit_button("항목 추가하기")
            
            if submitted_item:
                if not item_name:
                    st.error("항목명을 입력하세요.")
                else:
                    try:
                        detail_data = {
                            "rate_list_name": selected_sheet,
                            "item_type": item_type,
                            "item_name": item_name,
                            "unit": unit,
                            "regular_rate": regular_rate,
                            "ot_rate": ot_rate,
                            "gl_code_revenue": gl_code
                        }
                        supabase.table("master_rate_details").insert(detail_data).execute()
                        st.success(f"✅ {item_name} ($ {regular_rate}) 추가 완료!")
                    except Exception as e:
                        st.error(f"추가 실패: {e}")

        # 3. 현재 선택된 단가표의 항목들 보여주기
        st.write(f"📊 **[{selected_sheet}]** 포함된 항목들:")
        try:
            res_items = supabase.table("master_rate_details").select("*").eq("rate_list_name", selected_sheet).execute()
            if res_items.data:
                df_items = pd.DataFrame(res_items.data)
                st.dataframe(df_items[["item_type", "item_name", "unit", "regular_rate", "ot_rate"]], use_container_width=True)
            else:
                st.info("아직 추가된 항목이 없습니다.")
        except:
            pass