import streamlit as st
from streamlit_autorefresh import st_autorefresh

from app.views.chat import render_rich_message, normalize_group_message 
from app.core.api import (
    fetch_group_members_detailed, fetch_groups, leave_group, 
    ask_ai_recommend, remove_friend, kick_group_member, 
    invite_group_member, fetch_group_messages, send_group_message, join_group
)

def render_group_interface(group_id: str, username: str):
    """渲染详细的群聊 / 私聊视图"""
    
    st_autorefresh(interval=5000, key=f"chat_refresh_{group_id}")

    try:
        members = fetch_group_members_detailed(group_id)
        all_grps = fetch_groups()
    except Exception:
        members, all_grps = [], []

    is_dm = False
    group_name = "Chat"
    for g in all_grps:
        if str(g.get("id")) == str(group_id):
            group_name = g.get("name")
            if (group_name or "").startswith("DM:"):
                is_dm = True
                group_name = group_name.replace("DM: ", "💬 ")
            break
    
    head_left, head_right = st.columns([5, 1])
    with head_left: st.title(group_name)
    with head_right:
        if st.button("🚪 Leave", key=f"exit_{group_id}"):
            leave_group(group_id)
            st.session_state.active_group = None
            st.rerun()

    chat_col, info_col = st.columns([3, 1])

    with info_col:
        with st.container(border=True):
            st.markdown("#### ✨ AI Copilot")
            if st.button("🗺 Recommend Trail", use_container_width=True):
                ask_ai_recommend(group_id)
                st.toast("AI is generating route cards...")

        st.markdown("---")
        st.subheader("👥 Members")
        
        my_role = "member"
        current_uid = st.session_state.get("current_user_id")

        for m in members:
            if m.get("user_id") == current_uid:
                my_role = m.get("role")
            
            role_icon = "👑" if m.get("role") == "admin" else "👤"
            st.write(f"{role_icon} **{m.get('username')}**")
            
            if my_role == "admin" and m.get("user_id") != current_uid:
                if is_dm:
                    if st.button("Remove Friend", key=f"rem_f_{m.get('user_id')}"):
                        remove_friend(m.get("user_id"))
                        st.session_state.active_group = None
                        st.rerun()
                else:
                    if st.button("Kick", key=f"kick_{m.get('user_id')}"):
                        kick_group_member(group_id, m.get("user_id"))
                        st.rerun()
            st.caption(f"ID: {m.get('user_code')}")
            st.markdown("---")

    with chat_col:
        with st.container(border=True, height=550):
            try: raw_messages = fetch_group_messages(group_id)
            except: raw_messages = []
            
            if not raw_messages: 
                st.caption("No messages yet. Say hi to the group!")
            
            for raw in raw_messages:
                msg_obj = normalize_group_message(raw)
                render_rich_message(msg_obj)

        if chat_input := st.chat_input(f"Message {group_name}..."):
            send_group_message(group_id, chat_input)
            st.rerun()