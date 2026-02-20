import streamlit as st
from datetime import datetime as _dt
from streamlit_autorefresh import st_autorefresh

from app.views.chat import render_rich_message
from app.components.common import render_message_bubble
from app.core.api import send_planning_message

def render_ai_interface(username: str):
    """渲染 AI 个人助手聊天界面"""
    st.title("🤖 Trail Assistant")
    st.caption("Plan your next summit with real-time AI guidance.")
    
    st_autorefresh(interval=5000, key="ai_home_refresh")

    if "messages" not in st.session_state:
        st.session_state.messages = []

    with st.container(border=True, height=500):
        if not st.session_state.messages:
            st.info("Hello! Ask me to recommend a trail or check the weather for your next hike.")
        for msg in st.session_state.messages: 
            try:
                render_rich_message(msg)
            except Exception:
                render_message_bubble(msg)

    prompt = st.chat_input("Where should we hike next?", key="ai_chat_input")
    if prompt:
        st.session_state.messages.append({
            "sender": username, 
            "role": "user", 
            "content": prompt, 
            "timestamp": _dt.utcnow().isoformat()
        })
        with st.spinner("AI is analyzing trails..."):
            process_ai_response()
        st.rerun()

def process_ai_response():
    """处理并获取后端 AI 返回的结果"""
    msgs = st.session_state.messages
    if msgs and msgs[-1]["role"] == "user":
        try: 
            reply = send_planning_message(msgs[-1]["content"])
        except Exception as exc: 
            reply = f"⚠️ AI Assistant is currently offline: {exc}"
        
        msgs.append({
            "sender": "HikeBot", 
            "role": "assistant", 
            "content": reply, 
            "timestamp": _dt.utcnow().isoformat()
        })