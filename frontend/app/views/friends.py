import streamlit as st
# 🔴 修复 1：去掉了末尾多余的逗号
from app.core.api import api_get, api_post, reject_friend_request
from app.components.common import card_container

def render_add_friend_page(username: str = ""):
    """主入口逻辑"""
    st.header("🤝 Social Hub")
    
    list_tab, requests_tab, add_tab = st.tabs([
        "My Friends", 
        "Friend Requests", 
        "Add by Code"
    ])

    # --- 1. 好友列表 (增加了删除功能) ---
    with list_tab:
        try:
            res = api_get("/social/friends")
            friends = res.get("friends", [])
            if not friends:
                st.info("You haven't added any friends yet.")
            else:
                for f in friends:
                    with st.container():
                        col1, col2, col3 = st.columns([3, 1, 1])
                        with col1:
                            st.markdown(f"**{f['username']}** (ID: `{f['user_code']}`)")
                        
                        with col2:
                            if st.button("💬 Chat", key=f"chat_{f['id']}", use_container_width=True):
                                try:
                                    dm_res = api_post("/social/friends/dm", {"friend_id": f['id']})
                                    st.session_state.active_group = dm_res.get("group_id")
                                    st.session_state.view_mode = "chat"
                                    st.rerun()
                                except Exception as e:
                                    st.error(f"Chat failed: {e}")
                        
                        with col3:
                            if st.button("❌ Remove", key=f"del_{f['id']}", type="secondary", use_container_width=True):
                                try:
                                    api_post("/social/friends/remove", {"friend_id": f['id']})
                                    st.toast(f"Removed {f['username']} from your friends list. 🗑️")
                                    st.rerun()
                                except Exception as e:
                                    st.error(f"Failed to remove friend: {e}")
                    st.divider()
        except Exception as e:
            st.error(f"Friends list error: {e}")

    # --- 2. 好友请求 (🔴 修复 2：加上了拒绝按钮排版) ---
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
                        
                        # 把下方分成两列，放两个按钮
                        col_acc, col_rej = st.columns(2)
                        
                        with col_acc:
                            if st.button("✅ Accept", key=f"acc_{r['id']}", use_container_width=True):
                                api_post("/social/friends/accept", {"request_id": r['id']})
                                st.success("Accepted!")
                                st.rerun()
                                
                        with col_rej:
                            if st.button("❌ Reject", key=f"rej_{r['id']}", type="secondary", use_container_width=True):
                                # 调用你刚刚写好的后端拒绝接口
                                api_post(f"/social/friends/requests/{r['id']}/reject", {})
                                st.warning("Request declined.")
                                st.rerun()
        except Exception as e:
            st.error(f"Requests error: {e}")

    # --- 3. 添加好友 ---
    with add_tab:
        st.subheader("Search by UserID or Username")
        st.caption("Enter the numeric UserID or exact username of your friend.")
        
        friend_code = st.text_input("Enter UserID / Username", placeholder="e.g. 1001 or Alice")
        
        if st.button("Send Request", type="primary"):
            if not friend_code.strip():
                st.warning("Please enter a UserID or Username.")
            else:
                try:
                    res = api_post("/social/friends/add", {"friend_code": friend_code.strip()})
                    if res.get("message") == "Exists":
                        st.info("⏳ Request is pending. Waiting for them to accept.")
                    else:
                        st.success(f"✅ Request sent to {res.get('username', 'user')}! They need to accept it.")
                
                except Exception as e:
                    err_msg = str(e).lower()
                    if "404" in err_msg or "not found" in err_msg:
                        st.error(f"❌ User '{friend_code.strip()}' does not exist.")
                    elif "cannot add self" in err_msg:
                        st.error("🚫 You cannot add yourself.")
                    else:
                        st.error(f"⚠️ Error: {str(e)}")