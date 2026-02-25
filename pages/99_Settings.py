import streamlit as st
import pandas as pd
from utils.supabase_client import supabase
from st_aggrid import AgGrid, GridOptionsBuilder, GridUpdateMode, DataReturnMode

st.set_page_config(page_title="System Settings", layout="wide")
st.title("⚙️ System Settings")

tab1, tab2 = st.tabs(["📥 Import Settings", "👤 User Management"])

with tab1:
    st.header("Excel Template Mapping")
    st.info("엑셀을 업로드하고, **데이터의 제목(Header)**이 있는 줄을 클릭해주세요.")

    # 1. 파일 업로드
    uploaded_file = st.file_uploader("Choose Excel File", type=["xlsx", "xlsm", "xls", "csv"])

    if uploaded_file:
        try:
            # 파일을 일단 '헤더 없이' 통으로 읽습니다 (최대 100줄)
            if uploaded_file.name.endswith('.csv'):
                df_raw = pd.read_csv(uploaded_file, header=None, nrows=100)
            else:
                df_raw = pd.read_excel(uploaded_file, header=None, nrows=100, engine='openpyxl')
            
            # --- [Step 1] Interactive Grid로 보여주기 ---
            st.subheader("1️⃣ 제목(Header) 줄 선택하기")
            st.markdown("아래 표에서 **항목 이름(Name, Hours 등)**이 적혀있는 줄을 **클릭(체크)**해주세요.")

            # AgGrid 설정 (선택 가능하게)
            gb = GridOptionsBuilder.from_dataframe(df_raw)
            gb.configure_selection('single', use_checkbox=True) # 체크박스로 선택
            gb.configure_grid_options(domLayout='normal')
            gridOptions = gb.build()

            grid_response = AgGrid(
                df_raw, 
                gridOptions=gridOptions,
                update_mode=GridUpdateMode.SELECTION_CHANGED,
                height=300, 
                fit_columns_on_grid_load=False
            )

            selected_rows = grid_response['selected_rows']
            
            # 선택된 행이 있으면 그 정보를 가져옴
            header_row_idx = 0
            if selected_rows is not None and len(selected_rows) > 0:
                # 선택된 행의 실제 인덱스 찾기 (AgGrid는 데이터를 dict로 반환함)
                # _selectedRowNodeInfo가 있으면 좋지만, 없으면 값으로 매칭
                # 여기서는 간단하게 사용자가 입력하게 하거나, 선택된 값을 보여줍니다.
                # *AgGrid 무료버전은 행 번호를 직접 주지 않을 수 있어서, 
                # 가장 확실한 방법은 '보여주고 -> 사용자가 번호 입력' 이지만,
                # 더 직관적인 '클릭'을 원하셨으므로 아래와 같이 처리합니다.
                
                # 선택된 행 데이터를 DataFrame 형태로 변환
                sel_df = pd.DataFrame(selected_rows)
                # 원본 df_raw에서 이 행이 몇 번째인지 찾기 (인덱스 매칭)
                # (주의: AgGrid가 인덱스를 리셋했을 수 있음)
                # 여기서는 UI상 선택된 행의 내용을 보여주고 "이게 맞나요?" 확인
                st.success("✅ 선택된 줄의 내용:")
                st.dataframe(sel_df, use_container_width=True)
                
                # 사용자가 행 번호를 확정하도록 유도 (자동 감지가 어려울 경우를 대비)
                # 팁: 아까 보여준 표의 왼쪽 숫자가 행 번호입니다.
                st.info("위에서 선택한 줄의 **왼쪽 숫자(인덱스)**를 아래에 입력해주세요.")
            
            col_h1, col_h2 = st.columns([1, 3])
            with col_h1:
                header_row = st.number_input("헤더 행 번호 입력", min_value=0, value=0, step=1)

            # --- [Step 2] 진짜 데이터 로딩 ---
            # 선택된 헤더로 다시 읽기
            if uploaded_file.name.endswith('.csv'):
                uploaded_file.seek(0)
                df = pd.read_csv(uploaded_file, header=header_row)
            else:
                df = pd.read_excel(uploaded_file, header=header_row, engine='openpyxl')
            
            with col_h2:
                st.write(f"▼ **Row {header_row}** 기준 데이터 미리보기:")
                st.dataframe(df.head(3), use_container_width=True)

            excel_cols = ["(Not Selected)"] + list(df.columns)

            # --- [Step 3] 매핑 (이전과 동일) ---
            st.divider()
            st.subheader("2️⃣ 컬럼 연결하기 (Mapping)")
            
            col_map1, col_map2 = st.columns(2)
            with col_map1:
                st.markdown("#### 👷‍♂️ Labor & Job")
                with st.container(border=True):
                    map_job_num = st.selectbox("Job Number ↔", excel_cols, index=0)
                    st.divider()
                    map_crew_name = st.selectbox("Crew Name ↔", excel_cols, index=0)
                    map_trade = st.selectbox("Trade ↔", excel_cols, index=0)
                    map_reg = st.selectbox("Regular Hrs ↔", excel_cols, index=0)
                    map_ot = st.selectbox("Overtime Hrs ↔", excel_cols, index=0)
            
            with col_map2:
                st.markdown("#### 🚜 Equipment")
                with st.container(border=True):
                    st.write("") 
                    st.write("") 
                    st.write("") 
                    map_unit = st.selectbox("Unit # ↔", excel_cols, index=0)
                    map_eq_name = st.selectbox("Equipment Name ↔", excel_cols, index=0)
                    map_usage = st.selectbox("Usage Hrs ↔", excel_cols, index=0)

            # --- [Step 4] 저장 ---
            st.divider()
            col_s1, col_s2 = st.columns([2, 1])
            with col_s1:
                profile_name = st.text_input("Profile Name", placeholder="e.g. Shell Timesheet")
            with col_s2:
                st.write("") 
                st.write("") 
                if st.button("💾 Save Settings", type="primary", use_container_width=True):
                    if not profile_name:
                        st.error("Profile Name is required.")
                    else:
                        mapping_data = {
                            "job_num": map_job_num,
                            "crew_name": map_crew_name, "trade": map_trade, 
                            "reg_hrs": map_reg, "ot_hrs": map_ot,
                            "unit_num": map_unit, "eq_name": map_eq_name, "usage_hrs": map_usage
                        }
                        try:
                            supabase.table("client_import_maps").insert({
                                "map_name": profile_name,
                                "header_row_idx": header_row,
                                "mapping_data": mapping_data
                            }).execute()
                            st.success(f"✅ Saved '{profile_name}'!")
                        except Exception as e:
                            st.error(f"Error: {e}")

        except Exception as e:
            st.error(f"Error: {e}")