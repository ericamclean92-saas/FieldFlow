import streamlit as st
import pandas as pd
import plotly.express as px
from utils.supabase_client import supabase
from datetime import datetime, timedelta
import time

st.set_page_config(
    page_title="FieldFlow",
    page_icon="🏗️",
    layout="wide",
)

# --- 세션 상태 초기화 (로그인 여부 확인) ---
if "user" not in st.session_state:
    st.session_state.user = None

# ==========================================
# [기능 1] 로그인 화면 (Login Form)
# ==========================================
def login_form():
    st.markdown("<h1 style='text-align: center;'>🏗️ FieldFlow Login</h1>", unsafe_allow_html=True)
    st.markdown("<p style='text-align: center;'>Enter your credentials to access the Field Service Management System.</p>", unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns([1, 1, 1])
    with col2:
        with st.form("login"):
            email = st.text_input("Email")
            password = st.text_input("Password", type="password")
            submit = st.form_submit_button("Sign In", type="primary", use_container_width=True)
            
            if submit:
                try:
                    # Supabase Auth 로그인 시도
                    res = supabase.auth.sign_in_with_password({"email": email, "password": password})
                    
                    if res.user:
                        st.session_state.user = res.user
                        st.success("Login Successful! Redirecting...")
                        time.sleep(1)
                        st.rerun()
                except Exception as e:
                    st.error(f"Login failed: {e}")
        
        st.caption("Don't have an account? Contact your Administrator.")

# ==========================================
# [기능 2] 메인 대시보드 (로그인 성공 시 보임)
# ==========================================
def show_dashboard():
    # 사이드바에 로그아웃 버튼 추가
    with st.sidebar:
        st.write(f"👤 Signed in as: **{st.session_state.user.email}**")
        if st.button("Log Out"):
            supabase.auth.sign_out()
            st.session_state.user = None
            st.rerun()
            
    st.title("🏗️ FieldFlow Executive Dashboard")
    st.markdown("Overview of active jobs, field tickets, and LEM status.")

    # --- 데이터 가져오기 (Data Fetching) ---
    @st.cache_data(ttl=60)
    def load_dashboard_data():
        data = {}
        try:
            # 1. Active Jobs
            jobs_res = supabase.table("master_project").select("job_number", count="exact").eq("status", "Active").execute()
            data['active_jobs'] = jobs_res.count if jobs_res.count else 0

            # 2. Tickets (This Month)
            today = datetime.now()
            first_day = today.replace(day=1).strftime('%Y-%m-%d')
            tickets_res = supabase.table("field_tickets").select("id", count="exact").gte("ticket_date", first_day).execute()
            data['month_tickets'] = tickets_res.count if tickets_res.count else 0
            
            # 3. Pending Drafts
            draft_res = supabase.table("field_tickets").select("id", count="exact").eq("status", "Draft").execute()
            data['pending_tickets'] = draft_res.count if draft_res.count else 0

            # 4. Recent LEMs
            lem_res = supabase.table("lems").select("*").order("created_at", desc=True).limit(5).execute()
            data['recent_lems'] = pd.DataFrame(lem_res.data) if lem_res.data else pd.DataFrame()

            # 5. Chart Data (30 days)
            thirty_days_ago = (today - timedelta(days=30)).strftime('%Y-%m-%d')
            tickets_30d = supabase.table("field_tickets").select("ticket_number, ticket_date").gte("ticket_date", thirty_days_ago).execute()
            labor_30d = supabase.table("field_labor").select("ticket_number, regular_hours, overtime_hours").execute()
            
            if tickets_30d.data and labor_30d.data:
                df_t = pd.DataFrame(tickets_30d.data)
                df_l = pd.DataFrame(labor_30d.data)
                df_merged = pd.merge(df_t, df_l, on="ticket_number", how="inner")
                df_merged["total_hours"] = df_merged["regular_hours"] + df_merged["overtime_hours"]
                data['chart_data'] = df_merged
            else:
                data['chart_data'] = pd.DataFrame()

        except Exception as e:
            # 에러나면 그냥 0으로 처리 (로그인 직후 DB권한 문제 등 방지)
            return {'active_jobs': 0, 'month_tickets': 0, 'pending_tickets': 0, 'recent_lems': pd.DataFrame(), 'chart_data': pd.DataFrame()}
        
        return data

    dashboard_data = load_dashboard_data()

    # --- KPI Metrics ---
    st.divider()
    kpi1, kpi2, kpi3, kpi4 = st.columns(4)
    kpi1.metric("🚧 Active Jobs", dashboard_data.get('active_jobs', 0))
    kpi2.metric("🎫 Tickets (This Month)", dashboard_data.get('month_tickets', 0))
    kpi3.metric("⏳ Pending Drafts", dashboard_data.get('pending_tickets', 0), delta_color="inverse")
    kpi4.metric("📑 Recent LEMs", len(dashboard_data.get('recent_lems', [])))

    # --- Charts & Lists ---
    st.divider()
    col_chart, col_list = st.columns([2, 1])

    with col_chart:
        st.subheader("📈 Daily Man-Hours (30 Days)")
        df_chart = dashboard_data.get('chart_data', pd.DataFrame())
        if not df_chart.empty:
            df_daily = df_chart.groupby("ticket_date")["total_hours"].sum().reset_index()
            fig = px.bar(df_daily, x="ticket_date", y="total_hours", labels={"ticket_date": "Date", "total_hours": "Hours"})
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No data for chart.")

    with col_list:
        st.subheader("🕒 Recent Activity")
        df_lem = dashboard_data.get('recent_lems', pd.DataFrame())
        if not df_lem.empty:
            st.dataframe(df_lem[["lem_number", "status", "lem_date"]], use_container_width=True, hide_index=True)
        else:
            st.caption("No recent LEMs.")

    # --- Quick Actions ---
    st.divider()
    st.subheader("⚡ Quick Actions")
    qa1, qa2, qa3, qa4 = st.columns(4)
    if qa1.button("➕ New Ticket", use_container_width=True): st.switch_page("pages/04_Time_Ticket_Entry.py")
    if qa2.button("📂 Create LEM", use_container_width=True): st.switch_page("pages/05_LEM_Management.py")
    if qa3.button("⚙️ Import Settings", use_container_width=True): st.switch_page("pages/99_Settings.py")
    if qa4.button("💰 Rate Master", use_container_width=True): st.switch_page("pages/03_Rate_Master.py")

# ==========================================
# [Main Flow]
# ==========================================
if st.session_state.user:
    show_dashboard()
else:
    login_form()
