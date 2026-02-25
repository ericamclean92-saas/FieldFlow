import streamlit as st
import pandas as pd
from utils.supabase_client import supabase
import io

st.set_page_config(page_title="System Settings", layout="wide")
st.title("⚙️ 시스템 설정 (Settings)")

tab1, tab2 = st.tabs(["📥 엑셀 가져오기 설정 (Import Templates)", "👤 사용자 관리 (추후 예정)"])

with tab1:
    st.header("엑셀 양식 매핑 설정")
    st.info("고객사마다 다른 엑셀 양식을 등록하는 곳입니다. 여기서 한 번만 설정하면, 티켓 입력 화면에서 바로 쓸 수 있습니다.")

    # 1. 샘플 파일 업로드
    st.subheader("1️⃣ 샘플 파일 업로드")
    st.markdown("설정하려는 고객사의 엑셀 파일을 아무거나 하나 올려주세요. (데이터 구조 파악용)")
    uploaded_file = st.file_uploader("엑셀 파일 선택 (.xlsx, .xlsm, .csv)", type=["xlsx", "xlsm", "xls", "csv"])

    if uploaded_file:
        try:
            # 파일 형식에 따라 읽기
            is_csv = uploaded_file.name.endswith('.csv')
            
            # --- [Step 1] 헤더 위치 찾기 ---
            st.divider()
            st.subheader("2️⃣ 제목 줄(Header) 찾기")
            
            col_h1, col_h2 = st.columns([1, 3])
            with col_h1:
                header_row = st.number_input(
                    "몇 번째 줄이 제목인가요? (0부터 시작)", 
                    min_value=0, value=0, step=1,
                    help="엑셀 맨 위에 로고나 결재란이 있다면, 실제 항목명(이름, 시간 등)이 시작되는 줄 번호를 입력하세요."
                )
            
            # 데이터 읽기
            if is_csv:
                df = pd.read_csv(uploaded_file, header=header_row)
            else:
                df = pd.read_excel(uploaded_file, header=header_row, engine='openpyxl')
            
            with col_h2:
                st.caption(f"▼ 선택한 {header_row}번째 줄을 제목으로 인식한 결과입니다. 항목명들이 제대로 보이나요?")
                st.dataframe(df.head(5), use_container_width=True)

            excel_cols = ["(선택 안 함)"] + list(df.columns)

            # --- [Step 2] 컬럼 연결하기 ---
            st.divider()
            st.subheader("3️⃣ 항목 연결하기 (Mapping)")
            st.markdown("우리 시스템의 항목과 엑셀의 항목을 짝지어주세요.")

            col_map1, col_map2 = st.columns(2)
            
            with col_map1:
                st.markdown("#### 👷‍♂️ 인력 (Labor) 정보")
                with st.container(border=True):
                    map_crew_name = st.selectbox("작업자 이름 (Name) ↔", excel_cols, index=0, help="필수 항목입니다.")
                    map_trade = st.selectbox("직종 (Trade) ↔", excel_cols, index=0)
                    map_reg = st.selectbox("정규 시간 (Regular Hrs) ↔", excel_cols, index=0)
                    map_ot = st.selectbox("OT 시간 (Overtime Hrs) ↔", excel_cols, index=0)
            
            with col_map2:
                st.markdown("#### 🚜 장비 (Equipment) 정보")
                with st.container(border=True):
                    map_unit = st.selectbox("장비 번호 (Unit #) ↔", excel_cols, index=0)
                    map_eq_name = st.selectbox("장비명 (Equip Name) ↔", excel_cols, index=0)
                    map_usage = st.selectbox("사용 시간 (Usage Hrs) ↔", excel_cols, index=0)

            # --- [Step 3] 저장하기 ---
            st.divider()
            st.subheader("4️⃣ 설정 저장")
            
            col_s1, col_s2 = st.columns([2, 1])
            with col_s1:
                profile_name = st.text_input("이 설정의 이름은 무엇인가요?", placeholder="예: Shell Standard 2026, CNRL 타임시트 등")
            with col_s2:
                st.write("") # 줄맞춤용
                st.write("") 
                if st.button("💾 설정 저장하기", type="primary", use_container_width=True):
                    if not profile_name:
                        st.error("설정 이름을 입력해주세요!")
                    elif map_crew_name == "(선택 안 함)" and map_unit == "(선택 안 함)":
                        st.error("적어도 하나 이상의 항목(이름 또는 장비번호)은 연결해야 합니다.")
                    else:
                        # 저장 데이터 구성
                        mapping_data = {
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
                            st.success(f"✅ '{profile_name}' 설정이 성공적으로 저장되었습니다!")
                            st.balloons()
                        except Exception as e:
                            st.error(f"저장 실패: {e}")

        except Exception as e:
            st.error(f"파일을 읽는 중 에러가 발생했습니다: {e}")