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
        st.switch_page("Home.py") # 바로 로그인 화면으로 쫓아냄
        st.stop() # 밑에 코드 실행 중지
