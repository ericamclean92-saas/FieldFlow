import streamlit as st
import pandas as pd
from utils.supabase_client import supabase
from st_aggrid import AgGrid, GridOptionsBuilder, GridUpdateMode

st.set_page_config(page_title="System Settings", layout="wide")
st.title("⚙️ System Settings")

tab1, tab2 = st.tabs(["📥 Import Settings", "👤 User Management"])

with tab1:
    st.header("Excel Template Mapping")
    st.info("엑셀 파일의 **헤더(제목)** 위치와 **Job 번호(특정 셀)** 위치를 설정합니다.")

    # 1. 파일 업로드
    uploaded_file = st.file_uploader("설정할 엑셀 파일 업로드", type=["xlsx", "xlsm", "xls", "csv"])

    if uploaded_file:
        try:
            # 파일을 '헤더 없이' 읽어서 좌표 찾기용으로 보여줌
            if uploaded_file.name.endswith('.csv'):
                df_raw = pd.read_csv(uploaded_file, header=None, nrows=50)
            else:
                df_raw = pd.read_excel(uploaded_file, header=None, nrows=50, engine='openpyxl')
            
            # --- [Step 1] 전체 구조 확인 (AgGrid) ---
            st.subheader("1️⃣ 엑셀 구조 확인 및 좌표 찾기")
            st.markdown("""
            * **헤더(제목) 행:** 항목 이름(Name, Hours)이 있는 줄
            * **Job 번호 셀:** Job 번호가 적혀 있는 칸 (예: B2)
            """)

            # AgGrid 설정
            gb = GridOptionsBuilder.from_dataframe(df_raw)
            gb.configure_grid_options(domLayout='normal')
            gb.configure_selection('single', use_checkbox=True)
            gridOptions = gb.build()

            AgGrid(df_raw, gridOptions=gridOptions, height=300, fit_columns_on_grid_load=False)
            
            st.caption("👆 위 표를 보고 행 번호(왼쪽 숫자)와 열 이름(알파벳)을 확인하세요.")

            # --- [Step 2] 위치 정보 입력 ---
            st.divider()
            st.subheader("2️⃣ 위치 정보 입력 (Header & Cells)")
            
            c_loc1, c_loc2 = st.columns(2)
            
            with c_loc1:
                st.markdown("##### 📌 표 시작 위치 (Header)")
                header_row = st.number_input("헤더(제목) 행 번호 (0부터 시작)", min_value=0, value=0, step=1)
                
            with c_loc2:
                st.markdown("##### 📌 고정 정보 위치 (Fixed Cells)")
                st.caption("헤더 위에 Job 번호나 날짜가 따로 적혀 있다면 셀 주소를 입력하세요.")
                cell_job = st.text_input("Job 번호 셀 주소 (예: C3)", help="비워두면 나중에 직접 선택합니다.")
                cell_date = st.text_input("날짜 셀 주소 (예: H3)", help="비워두면 오늘 날짜를 씁니다.")

            # --- [Step 3] 데이터 미리보기 ---
            # 선택된 헤더로 다시 읽기
            if uploaded_file.name.endswith('.csv'):
                uploaded_file.seek(0)
                df = pd.read_csv(uploaded_file, header=header_row)
            else:
                df = pd.read_excel(uploaded_file, header=header_row, engine='openpyxl')
            
            st.write(f"▼ **Row {header_row}** 기준 데이터 미리보기 (컬럼 확인용):")
            st.dataframe(df.head(3), use_container_width=True)

            excel_cols = ["(Not Selected)"] + list(df.columns)

            # --- [Step 4] 컬럼 매핑 ---
            st.divider()
            st.subheader("3️⃣ 컬럼 연결하기 (Mapping)")
            
            col_map1, col_map2 = st.columns(2)
            with col_map1:
                st.markdown("#### 👷‍♂️ Labor (인력)")
                with st.container(border=True):
                    map_crew_name = st.selectbox("Crew Name ↔", excel_cols, index=0)
                    map_trade = st.selectbox("Trade ↔", excel_cols, index=0)
                    map_reg = st.selectbox("Regular Hrs ↔", excel_cols, index=0, help="여러 Job이 있다면, 해당 Job의 시간 컬럼을 선택하세요.")
                    map_ot = st.selectbox("Overtime Hrs ↔", excel_cols, index=0)
            
            with col_map2:
                st.markdown("#### 🚜 Equipment (장비)")
                with st.container(border=True):
                    map_unit = st.selectbox("Unit # ↔", excel_cols, index=0)
                    map_eq_name = st.selectbox("Equipment Name ↔", excel_cols, index=0)
                    map_usage = st.selectbox("Usage Hrs ↔", excel_cols, index=0)

            # --- [Step 5] 저장 ---
            st.divider()
            col_s1, col_s2 = st.columns([2, 1])
            with col_s1:
                profile_name = st.text_input("설정 이름 (Profile Name)", placeholder="예: Shell - Job A 컬럼")
            with col_s2:
                st.write("") 
                st.write("") 
                if st.button("💾 설정 저장하기", type="primary", use_container_width=True):
                    if not profile_name:
                        st.error("설정 이름을 입력해주세요.")
                    else:
                        mapping_data = {
                            "fixed_cells": { # 고정 셀 주소 저장
                                "job_num": cell_job,
                                "date": cell_date
                            },
                            "cols": {
                                "crew_name": map_crew_name, "trade": map_trade, 
                                "reg_hrs": map_reg, "ot_hrs": map_ot,
                                "unit_num": map_unit, "eq_name": map_eq_name, "usage_hrs": map_usage
                            }
                        }
                        try:
                            supabase.table("client_import_maps").insert({
                                "map_name": profile_name,
                                "header_row_idx": header_row,
                                "mapping_data": mapping_data
                            }).execute()
                            st.success(f"✅ 설정 '{profile_name}' 저장 완료!")
                        except Exception as e:
                            st.error(f"저장 실패: {e}")

        except Exception as e:
            st.error(f"Error: {e}")