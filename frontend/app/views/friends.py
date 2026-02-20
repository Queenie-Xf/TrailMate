import streamlit as st
from app.core.api import api_get, api_post
from app.components.common import card_container

# 🔴 修复点：加上 username 参数接收
def render_add_friend_page(username: str = ""):
    """主入口逻辑"""
    st.header("🤝 Social Hub")
    
    list_tab, requests_tab, add_tab = st.tabs([
        "My Friends", 
        "Friend Requests", 
        "Add by Code"
    ])

    # --- 1. 好友列表 ---
    with list_tab:
        try:
            res = api_get("/social/friends")
            friends = res.get("friends", [])
            if not friends:
                st.info("You haven't added any friends yet.")
            else:
                for f in friends:
                    with st.container():
                        col1, col2 = st.columns([3, 1])
                        with col1:
                            st.markdown(f"**{f['username']}** (ID: `{f['user_code']}`)")
                        with col2:
                            if st.button("💬 Chat", key=f"chat_{f['id']}"):
                                try:
                                    dm_res = api_post("/social/friends/dm", {"friend_id": f['id']})
                                    st.session_state.active_group = dm_res.get("group_id")
                                    st.session_state.view_mode = "chat"
                                    st.rerun()
                                except Exception as e:
                                    st.error(f"Chat failed: {e}")
                        st.divider()
        except Exception as e:
            st.error(f"Friends list error: {e}")

    # --- 2. 好友请求 ---
    with requests_tab:
        try:
            req_res = api_get("/social/friends/requests")
            requests = req_res.get("requests", [])
            if not requests:
                st.write("No pending requests.")
            else:
                for r in requests:
                    with card_container():
                        st.write(f"**{r['from_username']}** sent you a request.")
                        if st.button("✅ Accept", key=f"acc_{r['id']}"):
                            api_post("/social/friends/accept", {"request_id": r['id']})
                            st.success("Accepted!")
                            st.rerun()
        except Exception as e:
            st.error(f"Requests error: {e}")

    # --- 3. 添加好友 ---
    with add_tab:
        st.subheader("Search by UserID")
        st.caption("Enter the numeric UserID of your friend.")
        
        friend_code = st.text_input("Enter UserID", placeholder="e.g. 1001")
        
        if st.button("Send Request", type="primary"):
            if not friend_code:
                st.warning("Please enter a UserID.")
            else:
                try:
                    res = api_post("/social/friends/add", {"friend_code": friend_code})
                    if res.get("message") == "Exists":
                        # 🔴 优化提示：明确告诉用户是对方还没同意
                        st.info("⏳ Request is pending. Waiting for them to accept.")
                    else:
                        st.success(f"✅ Request sent to {res.get('username', 'user')}! They need to accept it.")
                
                except Exception as e:
                    err_msg = str(e).lower()
                    if "404" in err_msg or "not found" in err_msg:
                        st.error(f"❌ User ID '{friend_code}' does not exist.")
                    elif "cannot add self" in err_msg:
                        st.error("🚫 You cannot add yourself.")
                    else:
                        st.error(f"⚠️ Error: {str(e)}")