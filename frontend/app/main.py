import streamlit as st
import os
import sys
from datetime import datetime

# 1. 核心环境配置 (确保路径正确)
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# 2. 导入所有功能视图 (确保功能不丢失)
from app.core.state import init_state
from app.core.api import auth_request
from app.views.home import render_home_page
from app.views.friends import render_add_friend_page
from app.views.groups import render_groups_page
from app.views.chat import render_chat_page

# 3. 注入高级主题 CSS (找回精细的 UI 布局)
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

        .card {
            background: var(--card);
            border: 1px solid rgba(31,122,80,0.12);
            border-radius: 16px;
            padding: 24px;
            box-shadow: 0 8px 24px rgba(0,0,0,0.04);
            margin-bottom: 20px;
        }

        .stButton > button {
            border-radius: 10px;
            font-weight: 600;
            transition: all 0.2s ease;
        }

        .sidebar-user {
            padding: 1.5rem;
            background: rgba(31, 122, 80, 0.05);
            border-radius: 12px;
            margin-bottom: 2rem;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

# 4. 认证大门逻辑
def render_auth_gate() -> None:
    st.markdown("<h1 style='text-align: center;'>🥾 HikeBot</h1>", unsafe_allow_html=True)
    st.markdown("<p style='text-align: center; color: var(--muted);'>Your intelligent trail companion</p>", unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        login_tab, signup_tab = st.tabs(["Existing Hiker", "Join the Crew"])
        
        with login_tab:
            with st.form("login_form"):
                u = st.text_input("Username")
                p = st.text_input("Password", type="password")
                if st.form_submit_button("Start Hiking", use_container_width=True):
                    try:
                        auth_request("/auth/login", u, p)
                        st.success("Welcome back!")
                        st.rerun()
                    except Exception as e: st.error(f"Login Error: {e}")

        with signup_tab:
            with st.form("signup_form"):
                u = st.text_input("Choose Username")
                p = st.text_input("Create Password", type="password")
                c = st.text_input("User Code (Hike ID)")
                if st.form_submit_button("Create Profile", use_container_width=True):
                    try:
                        auth_request("/auth/signup", u, p, user_code=c)
                        st.success("Account created!")
                        st.rerun()
                    except Exception as e: st.error(f"Signup Error: {e}")

# 5. 主程序逻辑
def main() -> None:
    # 基础配置
    st.set_page_config(page_title="HikeBot | Digital Trailhead", page_icon="🥾", layout="wide")
    inject_theme()
    init_state()

    # 身份状态检查
    user = st.session_state.get("user")
    if not user:
        render_auth_gate()
        return

    # --- 侧边栏：找回复杂的导航与功能入口 ---
    with st.sidebar:
        st.markdown(f"<div class='sidebar-user'><strong>Hiker:</strong> {user}</div>", unsafe_allow_html=True)
        
        st.subheader("Explore")
        nav_choice = st.radio(
            "Navigate to",
            ["Home / Search", "Trail Partners", "Hiking Groups"],
            label_visibility="collapsed"
        )
        
        # 导航分发逻辑
        if nav_choice == "Home / Search":
            st.session_state.view_mode = "home"
        elif nav_choice == "Trail Partners":
            st.session_state.view_mode = "friends"
        elif nav_choice == "Hiking Groups":
            st.session_state.view_mode = "groups"

        st.divider()
        
        # 找回辅助功能按钮
        if st.button("⚙️ Profile Settings", use_container_width=True):
            st.info("Settings coming soon!")
            
        if st.button("🚪 Logout", use_container_width=True, type="secondary"):
            st.session_state.clear()
            st.rerun()
            
        # 底部版权信息 (找回原本的 117 行细节)
        st.markdown(f"<div style='position: fixed; bottom: 20px; font-size: 0.8rem; color: var(--muted);'>© {datetime.now().year} HikeBot v2.4</div>", unsafe_allow_html=True)

    # --- 视图渲染：确保各模块内容完整加载 ---
    view = st.session_state.get("view_mode", "home")

    if view == "home":
        # 加载包含搜索、推荐和地图的首页
        render_home_page(user)
    elif view == "friends":
        # 加载好友管理、添加和请求页面
        render_add_friend_page(user)
    elif view == "groups":
        # 加载群组列表及管理
        render_groups_page(user)
    elif view == "chat":
        # 加载实时聊天和 AI 规划界面
        render_chat_page()

if __name__ == "__main__":
    main()