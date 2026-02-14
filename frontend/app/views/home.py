import streamlit as st
from datetime import datetime as _dt
from streamlit_autorefresh import st_autorefresh
import json
import re

# ✅ Precise Imports
from app.views.chat import render_rich_message, normalize_group_message 
from app.views.groups import render_create_group_page
from app.views.friends import render_add_friend_page
from app.components.common import render_message_bubble
from app.core.api import (
    fetch_groups, create_group, join_group, leave_group, 
    fetch_group_messages, send_group_message, fetch_group_members_detailed,
    ask_ai_recommend, fetch_friends, fetch_friend_requests, 
    send_friend_request, accept_friend_request, get_or_create_dm,
    send_planning_message, invite_group_member, kick_group_member, remove_friend
)

# --- SIDEBAR COMPONENT ---
def render_social_sidebar(username: str):
    """Detailed sidebar with Debug info, Group filtering, and Friend management"""
    
    # 🐞 DEBUG SECTION
    active_group_id = st.session_state.get("active_group")
    st.sidebar.markdown(f"**DEBUG: Active Group ID:** `{active_group_id}`")
    
    col_refresh, col_status = st.sidebar.columns([1, 3])
    with col_refresh:
        if st.button("🔄", help="Force Refresh Data"): 
            st.rerun()
    with col_status: 
        st.caption(f"Last sync: {_dt.now().strftime('%H:%M:%S')}")

    # User Identity Card
    my_code = st.session_state.get("user_code", "Loading...")
    with st.sidebar.container(border=True):
        st.markdown(f"**👤 {username}**")
        st.code(my_code, language="text")
        st.caption("Share your Hike ID with others.")

    st.sidebar.markdown("---")

    # 1. Data Fetching with Safety Checks
    try:
        raw_groups = fetch_groups()
        all_groups = raw_groups if isinstance(raw_groups, list) else []
    except Exception:
        all_groups = []

    try:
        raw_friends = fetch_friends()
        if isinstance(raw_friends, dict):
            friends = raw_friends.get("friends", [])
        else:
            friends = raw_friends if isinstance(raw_friends, list) else []
    except Exception:
        friends = []

    try:
        pending_reqs = fetch_friend_requests()
        # Handle dict or list return types
        if isinstance(pending_reqs, dict):
            pending_reqs = pending_reqs.get("requests", [])
    except Exception:
        pending_reqs = []
    
    pending_count = len(pending_reqs)
    if pending_count > 0:
        st.sidebar.warning(f"🔔 {pending_count} New Friend Request(s)")

    # 2. Group Filtering (DM vs Group)
    display_groups = []
    for g in all_groups:
        if isinstance(g, dict):
            name = (g.get("name") or "").upper()
            if not name.startswith("DM:"):
                display_groups.append(g)
        elif isinstance(g, str): # Fallback for string-only returns
            if not g.upper().startswith("DM:"):
                display_groups.append({"id": g, "name": g})

    st.sidebar.markdown("### 🏔 Groups")
    if st.sidebar.button("🤖 AI Personal Assistant", key="btn_home_ai", use_container_width=True):
        st.session_state.active_group = None
        st.session_state.show_ai_planning = True
        st.rerun()

    for g in display_groups:
        gid = g.get("id")
        name = g.get("name") or "Unnamed Group"
        is_active = (str(gid) == str(active_group_id))
        
        btn_label = f"📍 {name}" if is_active else f"# {name}"
        if st.sidebar.button(
            btn_label, 
            key=f"side_grp_{gid}", 
            use_container_width=True,
            type="primary" if is_active else "secondary"
        ):
            st.session_state.active_group = gid
            st.session_state.show_ai_planning = False
            st.session_state.view_mode = "chat"
            st.rerun()

    st.sidebar.markdown("---")

    # 3. Friend List Rendering
    st.sidebar.markdown("### 👥 Friends")
    if not friends:
        st.sidebar.caption("No friends found.")
    else:
        for f in friends:
            if isinstance(f, dict):
                fid = f.get("id")
                fname = f.get("display_name") or f.get("username") or "Friend"
                fcode = f.get("user_code", "N/A")
            else:
                fid, fname, fcode = f, f, "N/A"

            if st.sidebar.button(f"👤 {fname}", key=f"side_dm_{fid}", use_container_width=True, help=f"ID: {fcode}"):
                try:
                    dm_res = get_or_create_dm(fid)
                    # Support both raw ID string or dict response
                    st.session_state.active_group = dm_res.get("group_id") if isinstance(dm_res, dict) else dm_res
                    st.session_state.show_ai_planning = False
                    st.session_state.view_mode = "chat"
                    st.rerun()
                except Exception as e:
                    st.sidebar.error(f"DM Error: {e}")

    st.sidebar.markdown("---")
    
    # 4. Action Expanders
    with st.sidebar.expander("➕ Create New Group"):
        new_name = st.text_input("Name", key="sidebar_new_grp_name")
        friend_opts = {f"{f['username']}": f['user_code'] for f in friends if isinstance(f, dict)}
        selected = st.multiselect("Invite", options=list(friend_opts.keys()))
        if st.button("Initialize Group", use_container_width=True):
            if new_name:
                codes = [friend_opts[s] for s in selected]
                res = create_group(new_name, codes)
                st.session_state.active_group = res.get("group_id")
                st.rerun()

    add_btn_label = f"👋 Add Friend ({pending_count})" if pending_count > 0 else "👋 Add Friend"
    with st.sidebar.expander(add_btn_label):
        if pending_reqs:
            for r in pending_reqs:
                st.write(f"**{r.get('from_username')}**")
                if st.button("Accept", key=f"sidebar_acc_{r.get('id')}"):
                    accept_friend_request(r.get('id'))
                    st.rerun()
            st.divider()
        
        target_id = st.text_input("Enter Hike ID")
        if st.button("Send Request", use_container_width=True):
            send_friend_request(target_id)
            st.toast("Request Sent!")

# --- AI ASSISTANT INTERFACE ---
def render_ai_interface(username: str):
    """Global AI Assistant interface with card support and response processing"""
    st.title("🤖 Trail Assistant")
    st.caption("Plan your next summit with real-time AI guidance.")
    
    st_autorefresh(interval=5000, key="ai_home_refresh")

    # Message History Container
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

    # Chat Input
    prompt = st.chat_input("Where should we hike next?", key="ai_chat_input")
    if prompt:
        st.session_state.messages.append({
            "sender": username, 
            "role": "user", 
            "content": prompt, 
            "timestamp": _dt.utcnow().isoformat()
        })
        # Process the AI response immediately
        with st.spinner("AI is analyzing trails..."):
            process_ai_response()
        st.rerun()

def process_ai_response():
    """Trigger the backend AI pipeline for planning messages"""
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

# --- CHAT & GROUP INTERFACE ---
def render_group_interface(group_id: str, username: str):
    """Detailed Chat Interface with Member Panel and AI Copilot actions"""
    
    st_autorefresh(interval=5000, key=f"chat_refresh_{group_id}")

    # Load Data
    try:
        members = fetch_group_members_detailed(group_id)
        all_grps = fetch_groups()
    except Exception:
        members, all_grps = [], []

    # Identify Group Metadata
    is_dm = False
    group_name = "Chat"
    for g in all_grps:
        if str(g.get("id")) == str(group_id):
            group_name = g.get("name")
            if (group_name or "").startswith("DM:"):
                is_dm = True
                group_name = group_name.replace("DM: ", "💬 ")
            break
    
    # Header UI
    head_left, head_right = st.columns([5, 1])
    with head_left: st.title(group_name)
    with head_right:
        if st.button("🚪 Leave", key=f"exit_{group_id}"):
            leave_group(group_id)
            st.session_state.active_group = None
            st.rerun()

    chat_col, info_col = st.columns([3, 1])

    with info_col:
        # AI Actions Panel
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
            
            # Admin Controls
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
        # Chat History
        with st.container(border=True, height=550):
            try: 
                raw_messages = fetch_group_messages(group_id)
            except Exception: 
                raw_messages = []
            
            if not raw_messages: 
                st.caption("No messages yet. Say hi to the group!")
            
            for raw in raw_messages:
                msg_obj = normalize_group_message(raw)
                render_rich_message(msg_obj)

        # Message Input
        if chat_input := st.chat_input(f"Message {group_name}..."):
            send_group_message(group_id, chat_input)
            st.rerun()

# --- MAIN ROUTING LOGIC ---
def render_home_page(username: str) -> None:
    """Main routing entry point for the Home view"""
    
    # Always render sidebar
    render_social_sidebar(username)
    
    # Handle Sub-Views (Navigation from Sidebar/Buttons)
    view_mode = st.session_state.get("view_mode", "home")
    
    if view_mode == "create_group":
        render_create_group_page(username)
        return
    elif view_mode == "add_friend":
        render_add_friend_page(username)
        return

    # Handle Active Contexts (Chat vs Assistant vs Home)
    active_group = st.session_state.get("active_group")
    show_ai = st.session_state.get("show_ai_planning", False)

    if active_group:
        render_group_interface(active_group, username)
    elif show_ai:
        col_back, _ = st.columns([1, 5])
        with col_back:
            if st.button("← Home"):
                st.session_state.show_ai_planning = False
                st.rerun()
        render_ai_interface(username)
    else:
        # DEFAULT DASHBOARD (The "Home" Content)
        st.title("🥾 HikeBot Dashboard")
        st.markdown(f"Welcome back, **{username}**! Ready for the next peak?")
        
        # Quick Stats or Welcome Cards
        card_l, card_r = st.columns(2)
        with card_l:
            with st.container(border=True):
                st.subheader("Explore Trails")
                st.write("Find new paths and check elevation data.")
                if st.button("Start Search"):
                    st.session_state.show_ai_planning = True
                    st.rerun()
        with card_r:
            with st.container(border=True):
                st.subheader("Manage Crew")
                st.write("Connect with partners for your next trip.")
                if st.button("Partners List"):
                    st.session_state.view_mode = "friends"
                    st.rerun()
        
        st.markdown("---")
        st.subheader("Recent Activity")
        st.caption("Stay tuned for upcoming hiking events in your groups.")