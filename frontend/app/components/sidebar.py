import streamlit as st
from datetime import datetime as _dt
from streamlit_autorefresh import st_autorefresh

from app.core.api import (
    fetch_groups, fetch_friends, fetch_friend_requests, 
    get_or_create_dm
)

# ==========================================
# 🧩 Helper Components (拆分的子组件模块)
# ==========================================

def _render_user_profile(username: str):
    """渲染顶部：刷新按钮、同步时间与个人名片"""
    col_refresh, col_status = st.sidebar.columns([1, 3])
    with col_refresh:
        if st.sidebar.button("🔄", help="Force Refresh Data"): 
            st.rerun()
    with col_status: 
        st.sidebar.caption(f"Last sync: {_dt.now().strftime('%H:%M:%S')}")

    my_code = st.session_state.get("user_code", "Loading...")
    with st.sidebar.container(border=True):
        st.markdown(f"**👤 {username}**")
        st.code(my_code, language="text")
        st.caption("Share your Hike ID with others.")


def _render_notifications(pending_reqs: list):
    """渲染醒目的：新好友申请红色通知弹窗"""
    pending_count = len(pending_reqs)
    if pending_count > 0:
        st.sidebar.error(f"🔔 You have {pending_count} new friend request(s)!")
        if st.sidebar.button("👉 View Requests", use_container_width=True):
            st.session_state.view_mode = "friends"
            st.rerun()


def _render_group_list(all_groups: list, active_group_id: str):
    """渲染：AI 助手入口与群组列表"""
    st.sidebar.markdown("### 🏔 Groups")
    
    # AI 助手固定在群组最上方
    if st.sidebar.button("🤖 AI Personal Assistant", key="btn_home_ai", use_container_width=True):
        st.session_state.active_group = None
        st.session_state.show_ai_planning = True
        st.rerun()

    # 过滤出非私聊(DM)的正常群组
    display_groups = [
        g for g in all_groups 
        if (isinstance(g, dict) and not (g.get("name") or "").upper().startswith("DM:")) 
        or (isinstance(g, str) and not g.upper().startswith("DM:"))
    ]
    
    for g in display_groups:
        gid = g.get("id") if isinstance(g, dict) else g
        name = (g.get("name") or "Unnamed Group") if isinstance(g, dict) else g
        is_active = (str(gid) == str(active_group_id))
        
        btn_label = f"📍 {name}" if is_active else f"# {name}"
        if st.sidebar.button(btn_label, key=f"side_grp_{gid}", use_container_width=True, type="primary" if is_active else "secondary"):
            st.session_state.active_group = gid
            st.session_state.show_ai_planning = False
            st.session_state.view_mode = "chat"
            st.rerun()


def _render_friend_list(friends: list):
    """渲染：私聊好友列表"""
    st.sidebar.markdown("### 👥 Friends")
    if not friends:
        st.sidebar.caption("No friends found.")
    else:
        for f in friends:
            fid = f.get("id") if isinstance(f, dict) else f
            fname = (f.get("display_name") or f.get("username") or "Friend") if isinstance(f, dict) else f
            fcode = f.get("user_code", "N/A") if isinstance(f, dict) else "N/A"

            if st.sidebar.button(f"👤 {fname}", key=f"side_dm_{fid}", use_container_width=True, help=f"ID: {fcode}"):
                try:
                    dm_res = get_or_create_dm(fid)
                    st.session_state.active_group = dm_res.get("group_id") if isinstance(dm_res, dict) else dm_res
                    st.session_state.show_ai_planning = False
                    st.session_state.view_mode = "chat"
                    st.rerun()
                except Exception as e:
                    st.sidebar.error(f"DM Error: {e}")




# ==========================================
# 🚀 Main Entry Function (主入口函数)
# ==========================================

def render_social_sidebar(username: str):
    """侧边栏主入口：集中获取数据，然后分配给各个子组件渲染"""
    
    # 每 10 秒自动同步数据，监听新的好友请求
    st_autorefresh(interval=10000, key="sidebar_auto_sync")
    active_group_id = st.session_state.get("active_group")

    # --- 1. 集中获取全局数据 (自带防报错处理) ---
    try:
        raw_groups = fetch_groups()
        all_groups = raw_groups if isinstance(raw_groups, list) else []
    except: all_groups = []

    try:
        raw_friends = fetch_friends()
        friends = raw_friends.get("friends", []) if isinstance(raw_friends, dict) else (raw_friends if isinstance(raw_friends, list) else [])
    except: friends = []

    try:
        pending_reqs = fetch_friend_requests()
        if isinstance(pending_reqs, dict): pending_reqs = pending_reqs.get("requests", [])
    except: pending_reqs = []


    # --- 2. 像搭积木一样调用子组件 ---
    _render_user_profile(username)
    st.sidebar.markdown("---")

    _render_notifications(pending_reqs)

    _render_group_list(all_groups, active_group_id)
    st.sidebar.markdown("---")

    _render_friend_list(friends)
    st.sidebar.markdown("---")

 
    
    