import streamlit as st

# 导入所有拆分出来的视图组件
from app.components.sidebar import render_social_sidebar
from app.components.dashboard import render_dashboard
from app.views.ai_chat import render_ai_interface
from app.views.group_chat import render_group_interface
from app.views.groups import render_create_group_page
from app.views.friends import render_add_friend_page

def render_home_page(username: str) -> None:
    """
    主路由中心 (Router)
    只负责判断当前状态，并调用对应的视图组件。
    """
    
    # 1. 始终渲染侧边栏
    render_social_sidebar(username)
    
    # 2. 判断子视图模式
    view_mode = st.session_state.get("view_mode", "home")
    
    if view_mode == "create_group":
        render_create_group_page(username)
        return
    elif view_mode == "add_friend":
        render_add_friend_page(username)
        return

    # 3. 处理核心内容区
    active_group = st.session_state.get("active_group")
    show_ai = st.session_state.get("show_ai_planning", False)

    if active_group:
        # 进入群聊/私聊视图
        render_group_interface(active_group, username)
        
    elif show_ai:
        # 进入 AI 智能规划视图
        col_back, _ = st.columns([1, 5])
        with col_back:
            if st.button("← Home"):
                st.session_state.show_ai_planning = False
                st.rerun()
        render_ai_interface(username)
        
    else:
        # 默认：渲染仪表盘看板
        render_dashboard(username)