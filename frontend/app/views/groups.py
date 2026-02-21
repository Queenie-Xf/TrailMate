import streamlit as st
from typing import List, Dict, Any
from app.core.api import fetch_friends, create_group, fetch_groups

def render_groups_page(username: str) -> None:
    # --- 1. 还原你的头部 Hero 样式 ---
    st.markdown(
        """
        <div class="hero">
          <div class="pill">Summit together</div>
          <h3 style="margin:6px 0;">Your hiking groups</h3>
          <p style="margin:0;color:var(--muted);">Jump into existing groups or start a new one with your crew.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # 移除原本的 back_from_create_group 按钮，因为我们现在有全局侧边栏导航了

    # --- 2. 还原你的 My Groups Card，并加入 DM 过滤 ---
    st.markdown("<div class='card'>", unsafe_allow_html=True)
    st.markdown("### My groups")
    try:
        raw_groups = fetch_groups()
        # 兼容处理：确保拿到的是列表
        all_groups = raw_groups.get("groups", []) if isinstance(raw_groups, dict) else raw_groups
        
        # 🔴 核心修复：把 "DM:" 开头的私聊过滤掉，保持群组列表干净
        display_groups = [g for g in all_groups if isinstance(g, dict) and not (g.get("name") or "").upper().startswith("DM:")]
    except Exception as exc:
        display_groups = []
        st.error(f"Unable to load groups: {exc}")

    if not display_groups:
        st.caption("No groups yet.")
    else:
        for g in display_groups:
            gid = g.get("id")
            name = g.get("name") or "Group"
            desc = g.get("description") or ""
            col1, col2 = st.columns([3, 1])
            with col1:
                st.markdown(f"**{name}** \n{desc}")
            with col2:
                if st.button("Enter chat", key=f"enter_group_{gid}", use_container_width=True):
                    st.session_state.active_group = gid
                    st.session_state.view_mode = "chat"
                    st.rerun()
    st.markdown("</div>", unsafe_allow_html=True)

    # --- 3. 还原你的 Create Group Card，并加入数据格式安全检查 ---
    st.markdown("<div class='card'>", unsafe_allow_html=True)
    st.markdown("### Create a group")

    try:
        raw_friends = fetch_friends()
        # 🔴 核心修复：正确解析后端的 {"friends": [...]} 数据格式
        friends = raw_friends.get("friends", []) if isinstance(raw_friends, dict) else raw_friends
    except Exception as exc:
        friends = []
        st.error(f"Unable to load friends: {exc}")

    friend_labels: List[str] = []
    friend_map: Dict[str, Dict[str, Any]] = {}

    for f in friends:
        if isinstance(f, dict):
            fname = f.get("display_name") or f.get("username") or "Friend"
            code = f.get("user_code")
            label = f"{fname} ({code})"
            friend_labels.append(label)
            friend_map[label] = f

    name = st.text_input("Group name")
    selected_labels = st.multiselect(
        "Invite friends (optional)",
        friend_labels,
    )

    if st.button("Create Group", type="primary"):
        if not name.strip():
            st.error("Please enter a group name.")
        else:
            try:
                member_codes = [friend_map[l]["user_code"] for l in selected_labels]
                all_members = list(dict.fromkeys(member_codes))
                
                result = create_group(name.strip(), all_members)
                msg = result.get("message") or "Group created."
                group_id = result.get("group_id")

                st.success(f"{msg} (ID: {group_id})")

                st.session_state.active_group = group_id
                st.session_state.view_mode = "chat"
                st.rerun()

            except Exception as exc:
                st.error(f"Unable to create group: {exc}")

    st.markdown("</div>", unsafe_allow_html=True)
render_create_group_page = render_groups_page