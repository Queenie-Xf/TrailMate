import streamlit as st

def render_dashboard(username: str):
    """渲染默认的主页看板"""
    st.title("🥾 HikeBot Dashboard")
    st.markdown(f"Welcome back, **{username}**! Ready for the next peak?")
    
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