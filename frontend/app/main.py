import streamlit as st
import os
import sys
import time
from datetime import datetime

# ⚠️ 必须是第一个 Streamlit 命令
st.set_page_config(page_title="HikeBot | Summit Together", page_icon="🏔️", layout="wide")

# 1. 核心环境配置
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# 2. 导入所有功能视图
from app.core.state import init_state
from app.core.api import auth_request
from app.views.home import render_home_page
from app.views.friends import render_add_friend_page
from app.views.groups import render_groups_page 
from app.views.chat import render_chat_page     

import extra_streamlit_components as stx

# 初始化 Cookie 管理器 (使用全新 Key 强制隔离旧缓存)
cookie_manager = stx.CookieManager(key="hikebot_v2_final_lock")

# 3. 注入高级主题 CSS
def inject_theme() -> None:
    st.markdown(
        """
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@300;400;500;600;700&display=swap');
        
        :root {
            --bg: #f6f3ea; --panel: #f0eddf; --card: #ffffff;
            --accent: #1f7a50; --text: #123124; --muted: #5e7a68;
        }

        .stApp {
            background: radial-gradient(140% 140% at 10% 10%, #ffffff 0%, #f6f3ea 50%, #eef3eb 100%);
            color: var(--text);
            font-family: 'Space Grotesk', sans-serif;
        }
        
        [data-testid="stSidebarNav"] {display: none;}
        
        .stButton>button {
            border-radius: 12px;
            transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

def render_auth_gate():
    """认证大门：确保注册和登录逻辑完全隔离"""
    st.markdown("<h1 style='text-align: center; color: var(--accent);'>🏔 HikeBot</h1>", unsafe_allow_html=True)
    
    tab_login, tab_signup = st.tabs(["Login", "Create Account"])
    
    with tab_login:
        with st.form("login_form"):
            u = st.text_input("Username")
            p = st.text_input("Password", type="password")
            if st.form_submit_button("Sign In", use_container_width=True):
                try:
                    auth_request("/auth/login", u, p)
                    if st.session_state.get("authenticated"):
                        cookie_manager.set("saved_username", st.session_state.user, max_age=30*24*60*60, key="login_set_u")
                        cookie_manager.set("saved_usercode", st.session_state.user_code, max_age=30*24*60*60, key="login_set_c")
                        st.success("Welcome back!")
                        st.rerun()
                except Exception as e:
                    st.error(f"Login Failed: {str(e)}")

    with tab_signup:
        with st.form("signup_form"):
            u = st.text_input("Choose Username")
            p = st.text_input("Choose Password", type="password")
            c = st.text_input("User Code (e.g. 2001)")
            if st.form_submit_button("Join the Community", use_container_width=True):
                try:
                    # 仅发送注册请求，不触发自动登录
                    auth_request("/auth/signup", u, p, c)
                    st.success("Account created! Please switch to Login tab to sign in.")
                    st.balloons()
                except Exception as e:
                    st.error(f"Signup Failed: {str(e)}")
                    st.session_state.authenticated = False

def main() -> None:
    inject_theme()
    init_state()

    cookies = cookie_manager.get_all()

    # 从 Cookie 恢复状态 (带严格的非空拦截)
    if not st.session_state.get("authenticated"):
        saved_user = cookies.get("saved_username")
        saved_code = cookies.get("saved_usercode")
        if saved_user and saved_code and saved_user != "None" and saved_user.strip() != "":
            st.session_state.user = saved_user
            st.session_state.user_code = saved_code
            st.session_state.authenticated = True

    user = st.session_state.get("user")
    if not st.session_state.get("authenticated") or not user:
        render_auth_gate()
        return

    # --- 侧边栏导航 (极简版) ---
    with st.sidebar:
        st.markdown(f"### 🌲 Welcome, {user}")
        st.subheader("Explore")
        
        def on_nav_change():
            choice = st.session_state.sidebar_nav_radio
            if choice == "Home / Search":
                st.session_state.view_mode = "home"
            elif choice == "Social Bar":
                st.session_state.view_mode = "friends"
            elif choice == "Hiking Groups":
                st.session_state.view_mode = "groups"

        # 状态同步
        current_view = st.session_state.get("view_mode", "home")
        if current_view == "home":
            st.session_state.sidebar_nav_radio = "Home / Search"
        elif current_view == "friends":
            st.session_state.sidebar_nav_radio = "Social Bar"
        elif current_view == "groups":
            st.session_state.sidebar_nav_radio = "Hiking Groups"
        elif current_view == "chat":
            pass 

        st.radio(
            "Navigate to",
            ["Home / Search", "Social Bar", "Hiking Groups"],
            key="sidebar_nav_radio",
            label_visibility="collapsed",
            on_change=on_nav_change
        )

        st.divider()
        
        # 终极登出逻辑
        if st.button("🚪 Logout", use_container_width=True, type="secondary"):
            cookie_manager.set("saved_username", "", max_age=0, key="logout_clear_u")
            cookie_manager.set("saved_usercode", "", max_age=0, key="logout_clear_c")
            for k in list(st.session_state.keys()):
                del st.session_state[k]
            time.sleep(0.5)
            st.rerun()
            
        st.markdown(
            f"<div style='position: fixed; bottom: 20px; font-size: 0.8rem; color: var(--muted);'>© {datetime.now().year} HikeBot</div>", 
            unsafe_allow_html=True
        )

    # --- 路由渲染 ---
    view = st.session_state.get("view_mode", "home")

    if view == "home":
        render_home_page(user)
    elif view == "friends":
        render_add_friend_page(user)
    elif view == "groups":
        render_groups_page(user) 
    elif view == "chat":
        render_chat_page()       

if __name__ == "__main__":
    main()