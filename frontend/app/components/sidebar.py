import streamlit as st
from datetime import datetime as _dt

from app.core.api import (
    fetch_groups, fetch_friends, fetch_friend_requests, 
    get_or_create_dm, create_group, accept_friend_request, send_friend_request
)

def render_social_sidebar(username: str):
    """侧边栏组件：包含调试信息、群组过滤、好友管理"""
    
    active_group_id = st.session_state.get("active_group")
    st.sidebar.markdown(f"**DEBUG: Active Group ID:** `{active_group_id}`")
    
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

    st.sidebar.markdown("---")

    try: raw_groups = fetch_groups()
    except: raw_groups = []
    all_groups = raw_groups if isinstance(raw_groups, list) else []

    try:
        raw_friends = fetch_friends()
        friends = raw_friends.get("friends", []) if isinstance(raw_friends, dict) else (raw_friends if isinstance(raw_friends, list) else [])
    except: friends = []

    try:
        pending_reqs = fetch_friend_requests()
        if isinstance(pending_reqs, dict): pending_reqs = pending_reqs.get("requests", [])
    except: pending_reqs = []
    
    pending_count = len(pending_reqs)
    if pending_count > 0:
        st.sidebar.warning(f"🔔 {pending_count} New Friend Request(s)")

    display_groups = []
    for g in all_groups:
        if isinstance(g, dict) and not (g.get("name") or "").upper().startswith("DM:"):
            display_groups.append(g)
        elif isinstance(g, str) and not g.upper().startswith("DM:"):
            display_groups.append({"id": g, "name": g})

    st.sidebar.markdown("### 🏔 Groups")
    if st.sidebar.button("🤖 AI Personal Assistant", key="btn_home_ai", use_container_width=True):
        st.session_state.active_group = None
        st.session_state.show_ai_planning = True
        st.rerun()

    for g in display_groups:
        gid, name = g.get("id"), g.get("name") or "Unnamed Group"
        is_active = (str(gid) == str(active_group_id))
        
        btn_label = f"📍 {name}" if is_active else f"# {name}"
        if st.sidebar.button(btn_label, key=f"side_grp_{gid}", use_container_width=True, type="primary" if is_active else "secondary"):
            st.session_state.active_group = gid
            st.session_state.show_ai_planning = False
            st.session_state.view_mode = "chat"
            st.rerun()

    st.sidebar.markdown("---")

    st.sidebar.markdown("### 👥 Friends")
    if not friends:
        st.sidebar.caption("No friends found.")
    else:
        for f in friends:
            if isinstance(f, dict):
                fid, fname, fcode = f.get("id"), f.get("display_name") or f.get("username") or "Friend", f.get("user_code", "N/A")
            else:
                fid, fname, fcode = f, f, "N/A"

            if st.sidebar.button(f"👤 {fname}", key=f"side_dm_{fid}", use_container_width=True, help=f"ID: {fcode}"):
                try:
                    dm_res = get_or_create_dm(fid)
                    st.session_state.active_group = dm_res.get("group_id") if isinstance(dm_res, dict) else dm_res
                    st.session_state.show_ai_planning = False
                    st.session_state.view_mode = "chat"
                    st.rerun()
                except Exception as e:
                    st.sidebar.error(f"DM Error: {e}")

    st.sidebar.markdown("---")
    
    with st.sidebar.expander("➕ Create New Group"):
        new_name = st.text_input("Name", key="sidebar_new_grp_name")
        friend_opts = {f"{f['username']}": f['user_code'] for f in friends if isinstance(f, dict)}
        selected = st.multiselect("Invite", options=list(friend_opts.keys()))
        if st.button("Initialize Group", use_container_width=True):
            if new_name:
                res = create_group(new_name, [friend_opts[s] for s in selected])
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
            if not target_id:
                st.sidebar.warning("Please enter an ID.")
            else:
                try:
                    res = send_friend_request(target_id)
                    if isinstance(res, dict) and res.get("message") == "Exists":
                        # 🔴 优化提示
                        st.sidebar.info("⏳ Pending. Waiting for them to accept.")
                    else:
                        st.toast("Request Sent! 🚀")
                except Exception as e:
                    err_msg = str(e).lower()
                    if "404" in err_msg or "not found" in err_msg:
                        st.sidebar.error(f"❌ User ID '{target_id}' does not exist.")
                    elif "cannot add self" in err_msg:
                        st.sidebar.error("🚫 You cannot add yourself.")
                    else:
                        st.sidebar.error(f"Failed: {e}")