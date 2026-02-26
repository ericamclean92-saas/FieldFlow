import streamlit as st
import time

def require_login():
    """
    로그인 상태인지 확인합니다.
    로그인이 되어 있으면 -> 아무 일도 안 함 (그냥 통과)
    로그인이 안 되어 있으면 -> 경고 메시지 띄우고 Home으로 강제 이동
    """
    # 세션에 'user' 정보가 없으면 (로그인 안 한 상태)
    if "user" not in st.session_state or st.session_state.user is None:
        st.warning("🔒 Please log in to access this page.")
        time.sleep(1)
        
        try:
            # 1. Home.py로 이동 시도
            st.switch_page("Home.py")
        except Exception:
            # 2. 만약 파일명이 달라서 이동 실패하면 수동 링크 제공
            # (Streamlit Cloud에서는 메인 페이지 경로가 '/' 입니다)
            st.error("⚠️ Redirect failed. Please click the link below.")
            st.markdown(
                """<a href="/" target="_self" style="
                    display: inline-block;
                    padding: 0.5em 1em;
                    color: white;
                    background-color: #ff4b4b;
                    border-radius: 5px;
                    text-decoration: none;">
                    🏠 Go to Login Page
                </a>""", 
                unsafe_allow_html=True
            )
        
        st.stop() # 밑에 코드 실행 중지
