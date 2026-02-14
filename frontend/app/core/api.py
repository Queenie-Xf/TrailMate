from __future__ import annotations
import os
import requests
from datetime import datetime
from typing import Any, Dict, List
import streamlit as st

# 1. 确保 BACKEND_URL 正确，增加从 st.session_state 获取的备选方案
BACKEND_URL = os.getenv("BACKEND_URL", st.session_state.get("BACKEND_URL", "http://api:8000"))

def _auth_headers() -> Dict[str, str]:
    u = st.session_state.get("user")
    c = st.session_state.get("user_code")
    return {"X-Username": str(u), "X-User-Code": str(c)} if u and c else {}

def auth_request(path: str, username: str, password: str, user_code: str | None = None) -> str:
    payload = {"username": username, "password": password}
    if path == "/auth/signup": payload["user_code"] = user_code or ""
    r = requests.post(f"{BACKEND_URL}{path}", json=payload, timeout=15)
    if r.status_code != 200: 
        raise RuntimeError(r.json().get("detail", "认证失败"))
    data = r.json()
    user_data = data.get("user", {})
    st.session_state.user = user_data.get("username")
    st.session_state.user_code = user_data.get("user_code")
    st.session_state.current_user_id = user_data.get("id")
    st.session_state.authenticated = True
    return data.get("message", "OK")

# --- 社交功能 ---
def fetch_friends():
    r = requests.get(f"{BACKEND_URL}/social/friends", headers=_auth_headers())
    return r.json().get("friends", [])

def fetch_friend_requests():
    return requests.get(f"{BACKEND_URL}/social/friends/requests", headers=_auth_headers()).json().get("requests", [])

def send_friend_request(fc: str):
    return requests.post(f"{BACKEND_URL}/social/friends/add", json={"friend_code": fc}, headers=_auth_headers()).json()

def accept_friend_request(rid: int):
    return requests.post(f"{BACKEND_URL}/social/friends/accept", json={"request_id": rid}, headers=_auth_headers()).json()

def remove_friend(friend_id: int):
    return requests.post(f"{BACKEND_URL}/social/friends/remove", json={"friend_id": friend_id}, headers=_auth_headers()).json()

def get_or_create_dm(fid: int):
    res = requests.post(f"{BACKEND_URL}/social/friends/dm", json={"friend_id": fid}, headers=_auth_headers()).json()
    return res.get("group_id")

# --- 群组与聊天 ---
def fetch_groups():
    r = requests.get(f"{BACKEND_URL}/social/groups", headers=_auth_headers())
    return r.json().get("groups", [])

def create_group(name: str, member_codes: List[str]):
    return requests.post(f"{BACKEND_URL}/social/groups", json={"name": name, "member_codes": member_codes}, headers=_auth_headers()).json()

def fetch_group_messages(gid: str):
    return requests.get(f"{BACKEND_URL}/social/groups/{gid}/messages", headers=_auth_headers()).json().get("messages", [])

def send_group_message(gid: str, content: str):
    return requests.post(f"{BACKEND_URL}/social/groups/{gid}/messages", json={"content": content}, headers=_auth_headers())

def fetch_group_members_detailed(group_id: str):
    return requests.get(f"{BACKEND_URL}/social/groups/{group_id}/members", headers=_auth_headers()).json().get("members", [])

def fetch_group_members(group_id: str) -> List[str]:
    members = fetch_group_members_detailed(group_id)
    return [m["username"] for m in members]

def join_group(gid: str):
    return requests.post(f"{BACKEND_URL}/social/groups/{gid}/join", headers=_auth_headers())

def leave_group(gid: str):
    return requests.post(f"{BACKEND_URL}/social/groups/{gid}/leave", headers=_auth_headers())

def invite_group_member(gid: str, c: str):
    return requests.post(f"{BACKEND_URL}/social/groups/{gid}/invite", json={"friend_code": c}, headers=_auth_headers())

def kick_group_member(gid: str, uid: int):
    return requests.post(f"{BACKEND_URL}/social/groups/{gid}/kick", json={"user_id": uid}, headers=_auth_headers())

# --- 首页搜索与 AI ---
def search_trails(query: str):
    r = requests.get(f"{BACKEND_URL}/trails/search", params={"q": query}, headers=_auth_headers())
    return r.json()

def ask_ai_recommend(gid: str):
    return requests.post(f"{BACKEND_URL}/social/groups/{gid}/ai/recommend_routes", headers=_auth_headers())

def send_planning_message(message: str) -> str:
    r = requests.post(f"{BACKEND_URL}/chat", json={"user_message": message}, timeout=15)
    r.raise_for_status()
    return r.json().get("reply", "")

def api_get(endpoint: str, params: dict = None):
    r = requests.get(f"{BACKEND_URL}{endpoint}", params=params, headers=_auth_headers())
    if r.status_code != 200:
        raise RuntimeError(r.json().get("detail", f"GET {endpoint} failed"))
    return r.json()

def api_post(endpoint: str, json_data: dict = None):
    r = requests.post(f"{BACKEND_URL}{endpoint}", json=json_data, headers=_auth_headers())
    if r.status_code != 200:
        raise RuntimeError(r.json().get("detail", f"POST {endpoint} failed"))
    return r.json()