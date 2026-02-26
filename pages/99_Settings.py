import streamlit as st
import pandas as pd
from utils.supabase_client import supabase
from st_aggrid import AgGrid, GridOptionsBuilder, GridUpdateMode

st.set_page_config(page_title="System Settings", layout="wide")
st.title("⚙️ System Settings (Bulk Import Setup)")

tab1, tab2 = st.tabs(["📥 Bulk Import Mapping", "👤 User Management"])

with tab1:
    st.info("엑셀 파일의 각 열(Column)을 시스템 항목과 연결합니다. 한 번만 설정하면 대량 업로드가 가능합니다.")

    # 1. 샘플 파일 업로드
    uploaded_file = st.file_uploader("샘플 엑셀 파일 업로드", type=["xlsx", "xlsm", "xls", "csv"])

    if uploaded_file:
        try:
            # 헤더 찾기용으로 50줄만 읽기
            if uploaded_file.name.endswith('.csv'):
                df_raw = pd.read_csv(uploaded_file, header=None, nrows=50)
            else:
                df_raw = pd.read_excel(uploaded_file, header=None, nrows=50, engine='openpyxl')
            
            st.subheader("1️⃣ 헤더(제목) 줄 찾기")
            
            # AgGrid로 보여주고 선택 유도
            gb = GridOptionsBuilder.from_dataframe(df_raw)
            gb.configure_selection('single', use_checkbox=True)
            gridOptions = gb.build()
            
            AgGrid(df_raw, gridOptions=gridOptions, height=250, fit_columns_on_grid_load=False)
            
            header_row = st.number_input("헤더 행 번호 입력 (왼쪽 숫자)", min_value=0, value=0, step=1)

            # 헤더 적용해서 다시 읽기
            if uploaded_file.name.endswith('.csv'):
                uploaded_file.seek(0)
                df = pd.read_csv(uploaded_file, header=header_row)
            else:
                df = pd.read_excel(uploaded_file, header=header_row, engine='openpyxl')
            
            st.write(f"▼ **Row {header_row}** 기준 데이터 미리보기:")
            st.dataframe(df.head(3), use_container_width=True)
            
            excel_cols = ["(Not Selected)"] + list(df.columns)

            # --- 매핑 설정 ---
            st.divider()
            st.subheader("2️⃣ 컬럼 연결 (Mapping)")
            st.caption("❗ Job Number, Date, Ticket Number를 연결하면 자동으로 그룹화하여 Draft 티켓을 생성합니다.")

            c1, c2, c3 = st.columns(3)
            
            with c1:
                st.markdown("##### 🔑 그룹핑 기준 (Grouping Keys)")
                with st.container(border=True):
                    map_ticket_num = st.selectbox("Ticket # (티켓번호) ↔", excel_cols, index=0)
                    map_job_num = st.selectbox("Job # (프로젝트) ↔", excel_cols, index=0)
                    map_date = st.selectbox("Date (날짜) ↔", excel_cols, index=0)

            with c2:
                st.markdown("##### 👷‍♂️ 인력 (Labor)")
                with st.container(border=True):
                    map_crew_name = st.selectbox("Name (이름) ↔", excel_cols, index=0)
                    map_trade = st.selectbox("Trade (직종) ↔", excel_cols, index=0)
                    map_reg = st.selectbox("Reg Hrs ↔", excel_cols, index=0)
                    map_ot = st.selectbox("OT Hrs ↔", excel_cols, index=0)

            with c3:
                st.markdown("##### 🚜 장비 (Equipment)")
                with st.container(border=True):
                    map_unit = st.selectbox("Unit # (장비번호) ↔", excel_cols, index=0)
                    map_eq_name = st.selectbox("Eq Name (장비명) ↔", excel_cols, index=0)
                    map_usage = st.selectbox("Usage Hrs ↔", excel_cols, index=0)

            # --- 저장 ---
            st.divider()
            col_s1, col_s2 = st.columns([2, 1])
            with col_s1:
                profile_name = st.text_input("설정 이름 (예: Shell Timesheet Bulk)", placeholder="Profile Name")
            with col_s2:
                st.write("") 
                st.write("") 
                if st.button("💾 설정 저장하기", type="primary", use_container_width=True):
                    if not profile_name:
                        st.error("설정 이름을 입력하세요.")
                    elif map_crew_name == "(Not Selected)" and map_unit == "(Not Selected)":
                        st.error("최소한 이름이나 장비번호 중 하나는 매핑해야 합니다.")
                    else:
                        mapping_data = {
                            "group_cols": { # 그룹핑 기준
                                "ticket_num": map_ticket_num,
                                "job_num": map_job_num,
                                "date": map_date
                            },
                            "data_cols": { # 데이터
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
