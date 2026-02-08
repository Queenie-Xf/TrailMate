# frontend/app/core/api.py
from __future__ import annotations
import os
import requests
from datetime import datetime
from typing import Any, Dict, List
import streamlit as st

# 在 Docker 环境下指向 api 容器
BACKEND_URL = os.getenv("BACKEND_URL", "http://api:8000")

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
    # 统一设置 Session State
    st.session_state.user = user_data.get("username")
    st.session_state.user_code = user_data.get("user_code")
    st.session_state.current_user_id = user_data.get("id")
    st.session_state.authenticated = True
    return data.get("message", "OK")

# --- 社交与好友系统 (对齐 backend/app/routers/social.py) ---
def fetch_friends():
    return requests.get(f"{BACKEND_URL}/social/friends", headers=_auth_headers()).json()

def send_friend_request(fc: str):
    return requests.post(f"{BACKEND_URL}/social/friends/add", json={"friend_code": fc}, headers=_auth_headers()).json()

def fetch_friend_requests():
    return requests.get(f"{BACKEND_URL}/social/friends/requests", headers=_auth_headers()).json()

def accept_friend_request(rid: int):
    return requests.post(f"{BACKEND_URL}/social/friends/accept", json={"request_id": rid}, headers=_auth_headers()).json()

def remove_friend(friend_id: int):
    return requests.post(f"{BACKEND_URL}/social/friends/remove", json={"friend_id": friend_id}, headers=_auth_headers()).json()

def get_or_create_dm(fid: int):
    res = requests.post(f"{BACKEND_URL}/social/friends/dm", json={"friend_id": fid}, headers=_auth_headers()).json()
    return res.get("group_id")

# --- 群组与聊天功能 (修复 ImportError) ---
def fetch_groups():
    return requests.get(f"{BACKEND_URL}/social/groups", headers=_auth_headers()).json()

def create_group(name: str, member_codes: List[str]):
    return requests.post(f"{BACKEND_URL}/social/groups", json={"name": name, "member_codes": member_codes}, headers=_auth_headers()).json()

def fetch_group_messages(gid: str):
    # 修复 chat.py 的导入错误
    r = requests.get(f"{BACKEND_URL}/social/groups/{gid}/messages", headers=_auth_headers())
    return r.json().get("messages", [])

def send_group_message(gid: str, content: str):
    return requests.post(f"{BACKEND_URL}/social/groups/{gid}/messages", json={"content": content}, headers=_auth_headers())

def fetch_group_members_detailed(group_id: str):
    """找回获取群成员详情函数"""
    r = requests.get(f"{BACKEND_URL}/social/groups/{group_id}/members", headers=_auth_headers())
    return r.json().get("members", [])

# --- 首页搜索与 AI 规划 ---
def search_trails(query: str):
    # 调用 backend/app/routers/routes.py 的搜索接口
    r = requests.get(f"{BACKEND_URL}/trails/search", params={"q": query}, headers=_auth_headers())
    return r.json()

def ask_ai_recommend(gid: str):
    return requests.post(f"{BACKEND_URL}/social/groups/{gid}/ai/recommend_routes", headers=_auth_headers())

# --- 在你的 api.py 中添加这个函数以修复导入错误 ---

def fetch_groups():
    """修正：必须返回 .json().get("groups", [])，确保它是字典列表"""
    r = requests.get(f"{BACKEND_URL}/social/groups", headers=_auth_headers())
    # ✅ 确保返回的是 [{'id':..., 'name':...}, ...] 而不是字符串列表
    return r.json().get("groups", []) 

def fetch_group_members(group_id: str) -> List[str]:
    """这个函数才是返回字符串列表"""
    members = fetch_group_members_detailed(group_id)
    return [m["username"] for m in members]

# --- 同时也建议补全以下缺失的函数 (根据你之前的代码引用) ---

def join_group(gid: str):
    return requests.post(f"{BACKEND_URL}/social/groups/{gid}/join", headers=_auth_headers())

def leave_group(gid: str):
    return requests.post(f"{BACKEND_URL}/social/groups/{gid}/leave", headers=_auth_headers())

def invite_group_member(gid: str, c: str):
    return requests.post(f"{BACKEND_URL}/social/groups/{gid}/invite", json={"friend_code": c}, headers=_auth_headers())

def kick_group_member(gid: str, uid: int):
    return requests.post(f"{BACKEND_URL}/social/groups/{gid}/kick", json={"user_id": uid}, headers=_auth_headers())

def send_planning_message(message: str) -> str:
    """AI 助手使用的消息发送接口"""
    r = requests.post(f"{BACKEND_URL}/chat", json={"user_message": message}, timeout=15)
    r.raise_for_status()
    return r.json().get("reply", "")