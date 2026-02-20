from __future__ import annotations
from datetime import datetime
from html import escape
from textwrap import dedent
from typing import Dict, Any
import streamlit as st

def card_container():
    """卡片样式容器"""
    return st.container(border=True)

def render_message_bubble(msg: Dict[str, Any]) -> None:
    """还原精美 HTML/CSS 气泡逻辑"""
    sender = msg.get("sender") or "User"
    content = msg.get("content", "")
    ts = msg.get("created_at") or msg.get("timestamp")
    is_me = sender == st.session_state.get("user")

    align = "flex-end" if is_me else "flex-start"
    bubble_color = "#e8f4ec" if is_me else "#ffffff"
    border = "1px solid rgba(31,122,80,0.35)" if is_me else "1px solid rgba(31,122,80,0.12)"
    text_color = "#123124"

    time_str = ""
    if ts:
        try:
            if isinstance(ts, str):
                time_str = datetime.fromisoformat(ts.replace("Z", "+00:00")).strftime("%H:%M")
            else:
                time_str = ts.strftime("%H:%M")
        except Exception:
            time_str = str(ts)

    s_sender = escape(sender)
    s_content = escape(content).replace("\n", "<br>")

    html = dedent(
        f"""
        <div style="display:flex;justify-content:{align};margin-bottom:10px;">
          <div style="max-width:75%;font-size:14px;">
            <div style="color:#5e7a68;font-size:12px;margin-bottom:2px;">
              {s_sender} · {time_str}
            </div>
            <div style="
                        background:{bubble_color};
                        padding:10px 14px;
                        border-radius:14px;
                        border:{border};
                        color:{text_color};
                        box-shadow:0 8px 18px rgba(0,0,0,0.08);">
              {s_content}
            </div>
          </div>
        </div>
        """
    ).strip()
    st.markdown(html, unsafe_allow_html=True)