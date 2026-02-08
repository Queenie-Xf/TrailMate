from typing import List, Dict, Any
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks

# ✅ 修正引用路径
from app.routers.auth import get_current_user
from app.core.database import fetch_all, fetch_one, fetch_one_returning, execute, get_cursor, SessionLocal 
from app.models.sql_models import (
    AuthUser, FriendAddRequest, FriendRequestItem, FriendAcceptRequest, FriendSummary,
    GroupCreateRequest, GroupSummary, GroupMemberInfo, GroupMessageModel, MessageCreateRequest,
    DMRequest, InviteRequest, KickRequest, RemoveFriendRequest
)
# ✅ 确保 AI 服务引用正确
from app.services.planner import AutoPlannerService

router = APIRouter(prefix="/social", tags=["social"])

# --- AI 背景任务处理函数 (补齐) ---
async def run_ai_task_in_background(group_id: str, content: str):
    """在后台运行 AI 徒步规划流水线"""
    print(f"🔄 [Background] Starting AI task for Group {group_id}...")
    db = SessionLocal()
    try:
        service = AutoPlannerService(db)
        await service.run_pipeline(chat_id=group_id, user_message=content)
        print(f"✅ [Background] AI task finished for Group {group_id}")
    except Exception as e:
        print(f"❌ [Background] AI task failed: {e}")
    finally:
        db.close()

# --- FRIENDS (好友系统) ---

@router.get("/friends", response_model=Dict[str, List[FriendSummary]])
def list_friends(u: AuthUser = Depends(get_current_user)):
    """获取已建立好友关系的用户列表"""
    rows = fetch_all("""
        SELECT u.id, u.username, u.user_code 
        FROM friendships f 
        JOIN users u ON f.friend_id = u.id 
        WHERE f.user_id = %(me)s
    """, {"me": u.id})
    return {"friends": [FriendSummary(**row) for row in rows]}

@router.post("/friends/add", response_model=Dict[str, Any])
def add_friend(p: FriendAddRequest, u: AuthUser = Depends(get_current_user)):
    """补齐：发送好友请求接口"""
    target = fetch_one("SELECT id, username FROM users WHERE user_code = %(code)s", {"code": p.friend_code})
    if not target: 
        raise HTTPException(404, "User not found")
    if target["id"] == u.id: 
        raise HTTPException(400, "Cannot add self")
    
    # 检查是否已存在请求（双向检查）
    existing = fetch_one("""
        SELECT id FROM friend_requests 
        WHERE (from_user_id=%(me)s AND to_user_id=%(t)s) 
           OR (from_user_id=%(t)s AND to_user_id=%(me)s)
    """, {"me": u.id, "t": target["id"]})
    
    if existing: 
        return {"message": "Exists"}
    
    execute("INSERT INTO friend_requests (from_user_id, to_user_id, status) VALUES (%(me)s, %(t)s, 'pending')", 
            {"me": u.id, "t": target["id"]})
    return {"message": "Sent", "username": target["username"]}

@router.get("/friends/requests", response_model=Dict[str, List[FriendRequestItem]])
def get_friend_requests(u: AuthUser = Depends(get_current_user)):
    """获取收到的待处理好友请求"""
    rows = fetch_all("""
        SELECT r.id, r.from_user_id, u.username as from_username, u.user_code as from_user_code, r.created_at 
        FROM friend_requests r 
        JOIN users u ON r.from_user_id = u.id 
        WHERE r.to_user_id = %(me)s AND r.status = 'pending'
    """, {"me": u.id})
    return {"requests": [FriendRequestItem(**r) for r in rows]}

@router.post("/friends/accept", response_model=Dict[str, Any])
def accept_friend(p: FriendAcceptRequest, u: AuthUser = Depends(get_current_user)):
    """接受好友请求并建立双向关系"""
    rid = int(p.request_id)
    req = fetch_one("SELECT * FROM friend_requests WHERE id=%(rid)s AND to_user_id=%(me)s", {"rid": rid, "me": u.id})
    if not req: 
        raise HTTPException(404, "Request not found")
    
    with get_cursor() as cur:
        cur.execute("UPDATE friend_requests SET status='accepted' WHERE id=%(rid)s", {"rid": rid})
        # 建立双向好友关系
        cur.execute("INSERT INTO friendships (user_id, friend_id) VALUES (%(u)s, %(f)s) ON CONFLICT DO NOTHING", {"u": u.id, "f": req["from_user_id"]})
        cur.execute("INSERT INTO friendships (user_id, friend_id) VALUES (%(f)s, %(u)s) ON CONFLICT DO NOTHING", {"u": req["from_user_id"], "f": u.id})
    return {"message": "Accepted"}

@router.post("/friends/dm", response_model=Dict[str, Any])
def get_or_create_dm(p: DMRequest, u: AuthUser = Depends(get_current_user)):
    """补齐：获取或创建私信群组逻辑"""
    if p.friend_id == u.id: 
        raise HTTPException(400, "Cannot DM self")
    
    # 查找是否已有 DM 群组（通过成员判断）
    existing = fetch_one("""
        SELECT g.id FROM groups g 
        JOIN group_members gm1 ON g.id=gm1.group_id 
        JOIN group_members gm2 ON g.id=gm2.group_id 
        WHERE gm1.user_id=%(me)s AND gm2.user_id=%(f)s AND g.description = 'DM'
        LIMIT 1
    """, {"me": u.id, "f": p.friend_id})
    
    if existing: 
        return {"group_id": str(existing["id"]), "new": False}
    
    # 创建新 DM 群组
    friend = fetch_one("SELECT username FROM users WHERE id=%(id)s", {"id": p.friend_id})
    if not friend: 
        raise HTTPException(404, "Friend not found")
    
    dm_name = f"DM: {u.username} & {friend['username']}"
    gid = fetch_one_returning("INSERT INTO groups (name, description, created_by) VALUES (%(n)s, 'DM', %(u)s) RETURNING id", 
                               {"n": dm_name, "u": u.id})["id"]
    
    execute("INSERT INTO group_members (group_id, user_id, role) VALUES (%(gid)s, %(u)s, 'admin')", {"gid": gid, "u": u.id})
    execute("INSERT INTO group_members (group_id, user_id, role) VALUES (%(gid)s, %(u)s, 'admin')", {"gid": gid, "u": p.friend_id})
    
    return {"group_id": str(gid), "new": True}

# --- GROUPS (群组系统) ---

@router.get("/groups", response_model=Dict[str, List[GroupSummary]])
def list_groups(u: AuthUser = Depends(get_current_user)):
    """获取用户加入的所有群组"""
    rows = fetch_all("""
        SELECT g.id, g.name, g.description, g.created_at 
        FROM groups g 
        JOIN group_members gm ON g.id=gm.group_id 
        WHERE gm.user_id=%(u)s ORDER BY g.created_at DESC
    """, {"u": u.id})
    return {"groups": [GroupSummary(**r) for r in rows]}

@router.post("/groups", response_model=Dict[str, Any])
def create_group(p: GroupCreateRequest, u: AuthUser = Depends(get_current_user)):
    """创建新群组并邀请成员"""
    gid = fetch_one_returning("INSERT INTO groups (name, description, created_by) VALUES (%(n)s, %(d)s, %(u)s) RETURNING id", 
                               {"n": p.name, "d": p.description, "u": u.id})["id"]
    execute("INSERT INTO group_members (group_id, user_id, role) VALUES (%(gid)s, %(u)s, 'admin')", {"gid": gid, "u": u.id})
    
    if p.member_codes:
        for code in list(set(p.member_codes)):
            target = fetch_one("SELECT id FROM users WHERE user_code = %(c)s", {"c": code})
            if target and target["id"] != u.id:
                execute("INSERT INTO group_members (group_id, user_id, role) VALUES (%(gid)s, %(uid)s, 'member') ON CONFLICT DO NOTHING", 
                        {"gid": gid, "uid": target["id"]})
    return {"message": "Created", "group_id": str(gid)}

@router.get("/groups/{group_id}/messages", response_model=Dict[str, List[GroupMessageModel]])
def get_msgs(group_id: UUID, u: AuthUser = Depends(get_current_user)):
    """拉取群组聊天记录"""
    rows = fetch_all("""
        SELECT id, group_id, sender_display as sender, role, content, created_at 
        FROM group_messages WHERE group_id=%(gid)s ORDER BY created_at ASC LIMIT 100
    """, {"gid": str(group_id)})
    return {"messages": [GroupMessageModel(**r) for r in rows]}

@router.post("/groups/{group_id}/messages", response_model=GroupMessageModel)
def send_msg(group_id: UUID, p: MessageCreateRequest, background_tasks: BackgroundTasks, u: AuthUser = Depends(get_current_user)):
    """发送消息并触发 AI 任务"""
    r = fetch_one_returning("""
        INSERT INTO group_messages (group_id, user_id, sender_display, role, content) 
        VALUES (%(gid)s, %(u)s, %(s)s, 'user', %(c)s) 
        RETURNING id, group_id, sender_display as sender, role, content, created_at
    """, {"gid": str(group_id), "u": u.id, "s": u.username, "c": p.content})
    
    background_tasks.add_task(run_ai_task_in_background, group_id=str(group_id), content=p.content)
    return GroupMessageModel(**r)