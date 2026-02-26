import streamlit as st

def require_login():
    """
    모든 페이지의 최상단에서 호출하여, 
    로그인되지 않은 사용자의 접근을 차단합니다.
    """
    if "user" not in st.session_state or st.session_state.user is None:
        st.set_page_config(page_title="Access Denied", layout="centered")
        
        st.error("⛔ Access Denied (접근 거부)")
        st.warning("로그인이 필요한 페이지입니다. (Please sign in to continue.)")
        
        # 로그인 페이지로 돌아가는 버튼
        if st.button("🏠 Go to Login Page", type="primary"):
            st.switch_page("Home.py")
            
        # 중요: 여기서 코드 실행을 강제로 중단시킵니다. 
        # 이 아래에 있는 어떤 코드도 실행되지 않고, 데이터도 보이지 않습니다.
        st.stop()
