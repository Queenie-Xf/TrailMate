import streamlit as st
from app.core.api import api_get, api_post
from app.components.common import card_container

# ✅ 对齐 home.py 的导入需求，提供 render_add_friend_page 入口
def render_add_friend_page():
    """
    这是 home.py 调用的入口函数。
    它将渲染完整的好友管理界面。
    """
    render_friends_page()

def render_friends_page():
    st.header("🤝 Social Hub")
    
    # 创建三个 Tab 分别处理：好友列表、待处理请求、添加好友
    list_tab, requests_tab, add_tab = st.tabs([
        "My Friends", 
        "Friend Requests", 
        "Add by Code"
    ])

    # --- 1. 好友列表 ---
    with list_tab:
        try:
            # 这里的 endpoint 需对应 backend/app/routers/social.py 的 @router.get("/friends")
            res = api_get("/social/friends")
            friends = res.get("friends", [])
            
            if not friends:
                st.info("You haven't added any friends yet.")
            else:
                for f in friends:
                    with st.container():
                        col1, col2 = st.columns([3, 1])
                        with col1:
                            st.markdown(f"**{f['username']}** (Code: `{f['user_code']}`)")
                        with col2:
                            # 点击 Chat 跳转到 DM
                            if st.button("💬 Chat", key=f"chat_{f['id']}"):
                                try:
                                    # 对接 /social/friends/dm
                                    dm_res = api_post("/social/friends/dm", {"friend_id": f['id']})
                                    st.session_state.current_group_id = dm_res.get("group_id")
                                    st.success("Redirecting to chat...")
                                    st.rerun()
                                except Exception as e:
                                    st.error(f"Failed to start DM: {e}")
                        st.divider()
        except Exception as e:
            st.error(f"Could not load friends: {e}")

    # --- 2. 待处理请求 (对接 /social/friends/accept) ---
    with requests_tab:
        try:
            req_res = api_get("/social/friends/requests")
            requests = req_res.get("requests", [])
            
            if not requests:
                st.write("No pending requests.")
            else:
                for r in requests:
                    with card_container():
                        st.write(f"**{r['from_username']}** wants to be your friend!")
                        st.caption(f"Code: {r['from_user_code']}")
                        
                        c1, c2 = st.columns(2)
                        with c1:
                            if st.button("✅ Accept", key=f"acc_{r['id']}", use_container_width=True):
                                api_post("/social/friends/accept", {"request_id": r['id']})
                                st.success(f"Accepted {r['from_username']}!")
                                st.rerun()
                        with c2:
                            # 这里可以保留，后续增加拒绝逻辑
                            st.button("❌ Ignore", key=f"ign_{r['id']}", use_container_width=True)
        except Exception as e:
            st.error(f"Error loading requests: {e}")

    # --- 3. 添加好友 (对接 /social/friends/add) ---
    with add_tab:
        st.subheader("Add a new friend")
        friend_code = st.text_input("Enter Friend Code", placeholder="e.g. USER-1234")
        if st.button("Send Request", type="primary"):
            if not friend_code:
                st.warning("Please enter a code.")
            else:
                try:
                    res = api_post("/social/friends/add", {"friend_code": friend_code})
                    if res.get("message") == "Exists":
                        st.info("Request already sent or you are already friends.")
                    else:
                        st.success(f"Request sent to {res.get('username', 'user')}!")
                except Exception as e:
                    st.error(f"Failed to add: {e}")