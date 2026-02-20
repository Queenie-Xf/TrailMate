import streamlit as st

# ⚠️ 必须放在所有 Streamlit 命令的最前面！
st.set_page_config(page_title="HikeBot | Summit Together", page_icon="🏔️", layout="wide")

import os
import sys
from datetime import datetime

# 1. 核心环境配置 (确保路径正确)
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# 2. 导入所有功能视图 
from app.core.state import init_state
from app.core.api import auth_request
from app.views.home import render_home_page
from app.views.friends import render_add_friend_page
from app.views.groups import render_groups_page 
from app.views.chat import render_chat_page     

import extra_streamlit_components as stx

# 初始化 Cookie 管理器 (适配最新版 Streamlit，直接调用即可)
cookie_manager = stx.CookieManager(key="cookie_manager")

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
        
        /* 隐藏默认侧边栏导航，使用我们自定义的导航 */
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
    """认证大门：处理登录与注册"""
    st.markdown("<h1 style='text-align: center; color: var(--accent);'>🏔 HikeBot</h1>", unsafe_allow_html=True)
    
    tab_login, tab_signup = st.tabs(["Login", "Create Account"])
    
    with tab_login:
        with st.form("login_form"):
            u = st.text_input("Username")
            p = st.text_input("Password", type="password")
            if st.form_submit_button("Sign In", use_container_width=True):
                try:
                    auth_request("/auth/login", u, p)
                    # 📍 记录点 1：登录成功，写入 Cookie (加上独立 key)
                    if st.session_state.get("user") and st.session_state.get("user_code"):
                        cookie_manager.set("saved_username", st.session_state.user, max_age=30*24*60*60, key="login_set_user")
                        cookie_manager.set("saved_usercode", st.session_state.user_code, max_age=30*24*60*60, key="login_set_code")
                    st.success("Welcome back!")
                    st.rerun()
                except Exception as e:
                    st.error(str(e))

    with tab_signup:
        with st.form("signup_form"):
            u = st.text_input("Choose Username")
            p = st.text_input("Choose Password", type="password")
            c = st.text_input("User Code (e.g. @hiking_fan)")
            if st.form_submit_button("Join the Community", use_container_width=True):
                try:
                    auth_request("/auth/signup", u, p, c)
                    # 📍 记录点 2：注册成功，写入 Cookie (加上独立 key)
                    if st.session_state.get("user") and st.session_state.get("user_code"):
                        cookie_manager.set("saved_username", st.session_state.user, max_age=30*24*60*60, key="signup_set_user")
                        cookie_manager.set("saved_usercode", st.session_state.user_code, max_age=30*24*60*60, key="signup_set_code")
                    st.success("Account created!")
                    st.rerun()
                except Exception as e:
                    st.error(str(e))

def main() -> None:
    inject_theme()
    
    # 初始化全局状态
    init_state()

    # 📍 记录点 3：页面刷新时，优先从 Cookie 读取账号信息
    if not st.session_state.get("authenticated"):
        saved_user = cookie_manager.get("saved_username")
        saved_code = cookie_manager.get("saved_usercode")
        
        if saved_user and saved_code:
            st.session_state.user = saved_user
            st.session_state.user_code = saved_code
            st.session_state.authenticated = True

    # 身份检查
    user = st.session_state.get("user")
    if not st.session_state.get("authenticated") or not user:
        render_auth_gate()
        return

    # --- 侧边栏导航 ---
    with st.sidebar:
        st.markdown(f"### 🌲 Welcome, {user}")
        st.subheader("Explore")
        
        # 导航选项
        nav_choice = st.radio(
            "Navigate to",
            ["Home / Search", "Trail Partners", "Hiking Groups"],
            label_visibility="collapsed"
        )
        
        if nav_choice == "Home / Search":
            st.session_state.view_mode = "home"
        elif nav_choice == "Trail Partners":
            st.session_state.view_mode = "friends"
        elif nav_choice == "Hiking Groups":
            st.session_state.view_mode = "groups"

        st.divider()
        
        if st.button("⚙️ Profile Settings", use_container_width=True):
            st.info("Settings coming soon!")
            
        if st.button("🚪 Logout", use_container_width=True, type="secondary"):
            # 📍 记录点 4：退出登录时，彻底清除 Cookie (加上独立 key)
            cookie_manager.delete("saved_username", key="logout_del_user")
            cookie_manager.delete("saved_usercode", key="logout_del_code")
            st.session_state.clear()
            st.rerun()
            
        st.markdown(
            f"<div style='position: fixed; bottom: 20px; font-size: 0.8rem; color: var(--muted);'>© {datetime.now().year} HikeBot v2.4</div>", 
            unsafe_allow_html=True
        )

    # --- 核心路由渲染 ---
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