from __future__ import annotations
from typing import List, Dict, Any
import streamlit as st

from app.core.api import (
    fetch_friends,
    send_friend_request,
    fetch_friend_requests,
    accept_friend_request,
    get_or_create_dm,
)

def render_add_friend_page(username: str) -> None:
    # 顶部标题与手动刷新按钮
    col_t, col_r = st.columns([4, 1])
    with col_t:
        st.markdown("### Add & manage friends")
    with col_r:
        if st.button("🔄 Refresh"):
            st.rerun()

    if st.button("← Back to home", key="back_from_add_friend"):
        st.session_state.view_mode = "home"
        st.rerun()

    # 添加好友卡片
    st.markdown("<div class='card'>", unsafe_allow_html=True)
    friend_code = st.text_input("Friend code (Hike ID)", placeholder="Enter Hike ID", key="add_friend_code")
    if st.button("Send friend request", type="primary"):
        if friend_code.strip():
            try:
                send_friend_request(friend_code.strip())
                st.success("Request sent!")
                st.rerun()
            except Exception as e:
                st.error(f"Error: {e}")
    st.markdown("</div>", unsafe_allow_html=True)

    # 待处理请求 (解析逻辑对齐后端)
    try:
        raw_reqs = fetch_friend_requests()
        requests = raw_reqs.get("requests", []) if isinstance(raw_reqs, dict) else []
    except:
        requests = []

    if requests:
        st.markdown("### Incoming requests")
        for req in requests:
            rid = req.get("id")
            from_name = req.get("from_username", "Unknown")
            col1, col2 = st.columns([3, 1])
            with col1:
                st.write(f"🤝 **{from_name}** wants to add you.")
            with col2:
                if st.button("Accept", key=f"acc_{rid}"):
                    try:
                        accept_friend_request(rid)
                        st.success("Accepted!")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Failed: {e}")

    # 好友列表 (解析逻辑对齐后端)
    st.markdown("### Your friends")
    try:
        raw_friends = fetch_friends()
        friends = raw_friends.get("friends", []) if isinstance(raw_friends, dict) else []
    except:
        friends = []

    if not friends:
        st.caption("No friends yet.")
    else:
        for f in friends:
            fid = f.get("id")
            fname = f.get("username", "Friend")
            c1, c2 = st.columns([3, 1])
            with c1:
                st.write(f"**{fname}**")
            with c2:
                if st.button("💬 Chat", key=f"chat_{fid}"):
                    try:
                        dm_res = get_or_create_dm(fid)
                        # 支持后端返回 {"group_id": "..."} 的结构
                        st.session_state.active_group = dm_res.get("group_id") if isinstance(dm_res, dict) else dm_res
                        st.session_state.view_mode = "chat"
                        st.rerun()
                    except Exception as e:
                        st.error(f"Chat failed: {e}")