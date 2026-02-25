import streamlit as st
import pandas as pd
from utils.supabase_client import supabase
from datetime import datetime

st.set_page_config(page_title="Ticket Entry", layout="wide")
st.title("🎫 Field Ticket (작업 티켓) 입력")

# --- 1. 기초 데이터 로딩 (Job & Rate Sheet) ---
def get_jobs():
    try:
        res = supabase.table("master_project").select("job_number", "project_name", "client_name").eq("status", "Active").execute()
        return res.data if res.data else []
    except: return []

def get_rate_sheets():
    try:
        res = supabase.table("master_rate_list").select("rate_list_name").execute()
        return [i['rate_list_name'] for i in res.data] if res.data else []
    except: return []

# Job 목록 가져오기
jobs_data = get_jobs()
job_options = [j['job_number'] for j in jobs_data]
rate_sheet_options = get_rate_sheets()

# --- 2. 티켓 헤더 입력 (위쪽) ---
with st.container():
    col1, col2, col3 = st.columns(3)
    
    with col1:
        selected_job = st.selectbox("Job Number 선택", job_options if job_options else ["Job을 먼저 등록하세요"])
        # 선택된 Job의 정보 보여주기
        if jobs_data and selected_job:
            job_info = next((item for item in jobs_data if item["job_number"] == selected_job), None)
            if job_info:
                st.info(f"📍 {job_info['client_name']} / {job_info['project_name']}")
    
    with col2:
        ticket_date = st.date_input("작업 날짜 (Date)", datetime.now())
        ticket_number = st.text_input("티켓 번호 (Unique)", placeholder="예: T-1001")
        
    with col3:
        # 단가표 선택 (이걸 선택해야 아래 아이템을 불러옴)
        selected_rate_sheet = st.selectbox("적용할 단가표 (Rate Sheet)", rate_sheet_options)

# --- 3. 라인 아이템 입력 (엑셀 같은 에디터) ---
st.subheader("🛠️ 작업 항목 입력 (Line Items)")

# 선택된 단가표의 아이템 목록 가져오기 (Dropdown용)
rate_items = []
rate_dict = {} # { "Supervisor": 120, "Laborer": 80 } 형태로 가격 저장
if selected_rate_sheet:
    try:
        res = supabase.table("master_rate_details").select("item_name", "regular_rate", "unit", "item_type").eq("rate_list_name", selected_rate_sheet).execute()
        if res.data:
            rate_items = [i['item_name'] for i in res.data]
            # 아이템 이름을 키로, 상세 정보를 값으로 저장
            rate_dict = {i['item_name']: {'rate': i['regular_rate'], 'unit': i['unit'], 'type': i['item_type']} for i in res.data}
    except Exception as e:
        st.error(f"단가표 로딩 실패: {e}")

# 에디터 초기 데이터 (빈 깡통)
if "ticket_df" not in st.session_state:
    st.session_state.ticket_df = pd.DataFrame(columns=["Type", "Item Name", "Qty", "Unit", "Rate", "Total"])

# 데이터 에디터 설정
edited_df = st.data_editor(
    st.session_state.ticket_df,
    num_rows="dynamic", # 행 추가/삭제 가능하게
    use_container_width=True,
    column_config={
        "Item Name": st.column_config.SelectboxColumn(
            "항목 선택",
            help="단가표에 있는 항목을 선택하세요",
            width="medium",
            options=rate_items, # 단가표 아이템들이 드롭다운으로 뜸!
            required=True
        ),
        "Qty": st.column_config.NumberColumn("수량", min_value=0.0, step=0.5, format="%.1f"),
        "Rate": st.column_config.NumberColumn("단가($)", format="$%.2f"),
        "Total": st.column_config.NumberColumn("합계($)", format="$%.2f", disabled=True), # 자동계산 결과 (눈으로만 봄)
    },
    hide_index=True
)

# --- 4. 자동 계산 및 저장 로직 ---
# 사용자가 항목을 선택하면 자동으로 단가(Rate)와 단위(Unit) 채워주기
# (참고: Streamlit 에디터 한계상, '저장' 버튼 누를 때 최종 계산해서 DB에 넣는 게 가장 안정적입니다)

save_col, _ = st.columns([1, 4])
if save_col.button("💾 티켓 저장하기 (Save Ticket)", type="primary"):
    if not ticket_number:
        st.error("티켓 번호를 입력해주세요!")
    elif edited_df.empty:
        st.error("입력된 항목이 없습니다.")
    else:
        try:
            # 1. 티켓 헤더 저장
            header_data = {
                "ticket_number": ticket_number,
                "job_number": selected_job,
                "ticket_date": str(ticket_date),
                "status": "Submitted"
            }
            supabase.table("tickets").insert(header_data).execute()
            
            # 2. 티켓 아이템 저장 (루프 돌면서 처리)
            items_to_insert = []
            for index, row in edited_df.iterrows():
                item_name = row["Item Name"]
                qty = float(row["Qty"]) if row["Qty"] else 0.0
                
                # 단가가 비어있으면 단가표에서 찾아오기
                rate = float(row["Rate"]) if pd.notnull(row["Rate"]) else 0.0
                if rate == 0.0 and item_name in rate_dict:
                     rate = rate_dict[item_name]['rate']
                
                unit = row["Unit"] if pd.notnull(row["Unit"]) else ""
                if not unit and item_name in rate_dict:
                    unit = rate_dict[item_name]['unit']
                
                item_type = row["Type"] if pd.notnull(row["Type"]) else ""
                if not item_type and item_name in rate_dict:
                    item_type = rate_dict[item_name]['type']

                items_to_insert.append({
                    "ticket_number": ticket_number,
                    "item_type": item_type,
                    "description": item_name,
                    "quantity": qty,
                    "unit": unit,
                    "unit_rate": rate
                })
            
            if items_to_insert:
                supabase.table("ticket_items").insert(items_to_insert).execute()
                st.success(f"✅ 티켓 {ticket_number} 저장이 완료되었습니다!")
                
                # 입력창 초기화
                st.session_state.ticket_df = pd.DataFrame(columns=["Type", "Item Name", "Qty", "Unit", "Rate", "Total"])
                # st.rerun()
                
        except Exception as e:
            st.error(f"저장 중 에러 발생: {e}")

# --- 5. 최근 생성된 티켓 확인 ---
st.divider()
st.caption("최근 생성된 티켓 목록")
try:
    res = supabase.table("tickets").select("*").order("created_at", desc=True).limit(5).execute()
    if res.data:
        st.dataframe(pd.DataFrame(res.data)[["ticket_number", "job_number", "ticket_date", "status"]])
except:
    pass