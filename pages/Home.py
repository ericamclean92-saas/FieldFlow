import streamlit as st
import pandas as pd
import plotly.express as px
from utils.supabase_client import supabase
from datetime import datetime, timedelta

st.set_page_config(
    page_title="FieldFlow Dashboard",
    page_icon="🏗️",
    layout="wide",
)

st.title("🏗️ FieldFlow Executive Dashboard")
st.markdown("Overview of active jobs, field tickets, and LEM status.")

# --- 1. 데이터 가져오기 (Data Fetching) ---
@st.cache_data(ttl=60) # 1분마다 캐시 갱신
def load_dashboard_data():
    data = {}
    try:
        # 1. Active Jobs Count
        jobs_res = supabase.table("master_project").select("job_number", count="exact").eq("status", "Active").execute()
        data['active_jobs'] = jobs_res.count if jobs_res.count else 0

        # 2. Tickets (This Month)
        today = datetime.now()
        first_day = today.replace(day=1).strftime('%Y-%m-%d')
        
        # 이번 달 생성된 티켓 수
        tickets_res = supabase.table("field_tickets").select("id", count="exact").gte("ticket_date", first_day).execute()
        data['month_tickets'] = tickets_res.count if tickets_res.count else 0
        
        # 3. Pending (Draft) Tickets
        draft_res = supabase.table("field_tickets").select("id", count="exact").eq("status", "Draft").execute()
        data['pending_tickets'] = draft_res.count if draft_res.count else 0

        # 4. Recent LEMs
        lem_res = supabase.table("lems").select("*").order("created_at", desc=True).limit(5).execute()
        data['recent_lems'] = pd.DataFrame(lem_res.data) if lem_res.data else pd.DataFrame()

        # 5. Labor Hours (Recent 30 Days) for Chart
        thirty_days_ago = (today - timedelta(days=30)).strftime('%Y-%m-%d')
        
        # 조인이 복잡하므로, 단순하게 Ticket Header와 Labor를 가져와서 Python에서 병합 (데이터량이 적을 때 유효)
        # 실제 운영시에는 Supabase View나 RPC를 쓰는 게 좋음
        tickets_30d = supabase.table("field_tickets").select("ticket_number, ticket_date").gte("ticket_date", thirty_days_ago).execute()
        labor_30d = supabase.table("field_labor").select("ticket_number, regular_hours, overtime_hours").execute()
        
        if tickets_30d.data and labor_30d.data:
            df_t = pd.DataFrame(tickets_30d.data)
            df_l = pd.DataFrame(labor_30d.data)
            
            # Merge
            df_merged = pd.merge(df_t, df_l, on="ticket_number", how="inner")
            # Calculate Total Hours
            df_merged["total_hours"] = df_merged["regular_hours"] + df_merged["overtime_hours"]
            data['chart_data'] = df_merged
        else:
            data['chart_data'] = pd.DataFrame()

    except Exception as e:
        st.error(f"Data loading failed: {e}")
    
    return data

dashboard_data = load_dashboard_data()

# --- 2. KPI Metrics (상단 지표) ---
st.divider()
kpi1, kpi2, kpi3, kpi4 = st.columns(4)

with kpi1:
    st.metric(label="🚧 Active Jobs", value=dashboard_data.get('active_jobs', 0))

with kpi2:
    st.metric(label="🎫 Tickets (This Month)", value=dashboard_data.get('month_tickets', 0))

with kpi3:
    st.metric(label="⏳ Pending Drafts", value=dashboard_data.get('pending_tickets', 0), delta_color="inverse")

with kpi4:
    # LEM Count (Generated)
    lem_count = len(dashboard_data.get('recent_lems', []))
    st.metric(label="📑 Recent LEMs", value=lem_count)

# --- 3. Charts & Activity (중간 시각화) ---
st.divider()

col_chart, col_list = st.columns([2, 1])

with col_chart:
    st.subheader("📈 Daily Man-Hours (Last 30 Days)")
    
    df_chart = dashboard_data.get('chart_data', pd.DataFrame())
    
    if not df_chart.empty:
        # 날짜별 그룹핑
        df_daily = df_chart.groupby("ticket_date")["total_hours"].sum().reset_index()
        
        fig = px.bar(
            df_daily, 
            x="ticket_date", 
            y="total_hours", 
            labels={"ticket_date": "Date", "total_hours": "Total Man-Hours"},
            color_discrete_sequence=["#0068C9"]
        )
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("No labor data available for the chart.")

with col_list:
    st.subheader("🕒 Recent Activity (LEMs)")
    
    df_lem = dashboard_data.get('recent_lems', pd.DataFrame())
    if not df_lem.empty:
        # 보기 좋게 컬럼 선택 및 이름 변경
        display_df = df_lem[["lem_number", "job_number", "status", "lem_date"]]
        st.dataframe(
            display_df, 
            use_container_width=True, 
            hide_index=True,
            column_config={
                "lem_number": "LEM #",
                "job_number": "Job",
                "status": "Status",
                "lem_date": "Date"
            }
        )
    else:
        st.caption("No recent LEMs generated.")

# --- 4. Quick Actions (바로가기) ---
st.divider()
st.subheader("⚡ Quick Actions")

qa1, qa2, qa3, qa4 = st.columns(4)
with qa1:
    if st.button("➕ New Time Ticket", use_container_width=True):
        st.switch_page("pages/04_Time_Ticket_Entry.py")
with qa2:
    if st.button("📂 Create LEM", use_container_width=True):
        st.switch_page("pages/05_LEM_Management.py")
with qa3:
    if st.button("⚙️ Import Settings", use_container_width=True):
        st.switch_page("pages/99_Settings.py")
with qa4:
    if st.button("💰 Rate Master", use_container_width=True):
        st.switch_page("pages/03_Rate_Master.py")
