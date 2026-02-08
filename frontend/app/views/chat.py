from __future__ import annotations
import json
import re
import datetime
import streamlit as st
from typing import Dict, Any
from streamlit_autorefresh import st_autorefresh

# ✅ 修正引用路径
from app.core.api import (
    fetch_group_messages,
    send_group_message,
    fetch_group_members,
    join_group,
    leave_group,
)
from app.core.state import ensure_members_cached, in_group
from app.components.common import render_message_bubble

# --- 新增：对接 main.py 的入口函数 ---
def render_chat_page():
    """这是对齐 main.py 第 15 行导入需求的关键入口"""
    active_group = st.session_state.get("active_group")
    username = st.session_state.get("user")
    
    if not active_group:
        st.info("💡 请在侧边栏选择一个群组或好友开始聊天。")
        if st.button("返回首页"):
            st.session_state.view_mode = "home"
            st.rerun()
        return

    # 调用 home.py 中你已经写好的渲染逻辑
    from app.views.home import render_group_interface
    render_group_interface(active_group, username)

def normalize_group_message(raw: Dict[str, Any]) -> Dict[str, Any]:
    """Normalize backend group message payload."""
    sender = raw.get("sender") or raw.get("sender_display") or "Unknown"
    content = raw.get("content", "")
    ts = raw.get("timestamp") or raw.get("created_at")
    role = raw.get("role", "user")
    msg_id = raw.get("id") or str(ts)
    return {"id": msg_id, "sender": sender, "content": content, "timestamp": ts, "role": role}

def render_rich_message(msg: Dict[str, Any]) -> None:
    sender = msg.get("sender", "Unknown")
    content = msg.get("content", "")
    
    is_card = False
    data = {}

    if content:
        try:
            match = re.search(r"\{.*\}", content, re.DOTALL)
            if match:
                json_str = match.group(0)
                parsed = json.loads(json_str)
                if isinstance(parsed, dict) and "title" in parsed and "stats" in parsed:
                    data = parsed
                    is_card = True
        except (json.JSONDecodeError, AttributeError):
            pass

    if is_card:
        with st.chat_message("assistant", avatar="🏔️"):
            with st.container(border=True):
                st.markdown(f"### {data.get('title')}")
                st.caption(f"📢 Trip Announcement via {sender}")
                st.write(data.get('summary', ''))
                st.divider()

                stats = data.get('stats', {})
                dist = stats.get('dist', 'N/A')
                elev = stats.get('elev', 'N/A')
                
                st.markdown(
                    f"""
                    | 📏 Distance | ⛰️ Elevation |
                    | :---: | :---: |
                    | **{dist}** | **{elev}** |
                    """
                )
                
                st.divider()
                
                if data.get('weather_warning'):
                    st.info(f"🌤 {data.get('weather_warning')}")
                
                if data.get('fun_fact'):
                    st.markdown(f"> 💡 **Fun Fact:** *{data.get('fun_fact')}*")
                
                gear = data.get('gear_required', [])
                if gear:
                    with st.expander("🎒 Gear List", expanded=False):
                        for item in gear:
                            st.checkbox(str(item), value=True, key=f"{msg.get('id')}_{item}", disabled=True)
    else:
        render_message_bubble(msg)

def render_members_panel() -> None:
    st.subheader("Group Members")
    group_id = st.session_state.get("active_group")
    if not group_id: return
    
    username = st.session_state.get("user")
    members = ensure_members_cached(group_id, fetch_group_members)
    
    if members:
        for m in members:
            st.markdown(f"- **{m}**" + (" (you)" if m == username else ""))
    
    st.markdown("---")
    if in_group(group_id, username, fetch_group_members):
        if st.button("Quit Group", key="quit_grp_chat"):
             try: leave_group(group_id); st.session_state.active_group = None; st.rerun()
             except: pass