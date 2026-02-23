from typing import List, Dict, Any
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks

from app.routers.auth import get_current_user
from app.core.database import fetch_all, fetch_one, fetch_one_returning, execute, SessionLocal 
from app.models.sql_models import (
    AuthUser, FriendAddRequest, FriendRequestItem, FriendAcceptRequest, FriendSummary,
    GroupCreateRequest, GroupSummary, GroupMemberInfo, GroupMessageModel, MessageCreateRequest,
    DMRequest, InviteRequest, KickRequest, RemoveFriendRequest
)
from app.services.planner import AutoPlannerService
from app.core.database import get_db
router = APIRouter(prefix="/social", tags=["social"])

async def run_ai_task_in_background(group_id: str, content: str):
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

# --- FRIENDS ---
@router.get("/friends", response_model=Dict[str, List[FriendSummary]])
def list_friends(u: AuthUser = Depends(get_current_user)):
    rows = fetch_all("SELECT u.id, u.username, u.user_code FROM friendships f JOIN users u ON f.friend_id = u.id WHERE f.user_id = %(me)s", {"me": u.id})
    return {"friends": [FriendSummary(**row) for row in rows]}

@router.post("/friends/add", response_model=Dict[str, Any])
def add_friend(p: FriendAddRequest, u: AuthUser = Depends(get_current_user)):
    # 🔴 支持 UserID 和 Username 双重搜索，并且忽略大小写
    search_term = p.friend_code.strip()
    
    target = fetch_one(
        """
        SELECT id, username 
        FROM users 
        WHERE LOWER(user_code) = LOWER(%(term)s) OR LOWER(username) = LOWER(%(term)s)
        """, 
        {"term": search_term}
    )
    
    if not target: 
        raise HTTPException(404, "User not found")
        
    if target["id"] == u.id: 
        raise HTTPException(400, "Cannot add self")
        
    existing = fetch_one(
        "SELECT id FROM friend_requests WHERE (from_user_id=%(me)s AND to_user_id=%(t)s) OR (from_user_id=%(t)s AND to_user_id=%(me)s)", 
        {"me": u.id, "t": target["id"]}
    )
    if existing: 
        return {"message": "Exists"}
        
    execute("INSERT INTO friend_requests (from_user_id, to_user_id, status) VALUES (%(me)s, %(t)s, 'pending')", 
            {"me": u.id, "t": target["id"]})
    return {"message": "Sent", "username": target["username"]}

@router.get("/friends/requests", response_model=Dict[str, List[FriendRequestItem]])
def get_friend_requests(u: AuthUser = Depends(get_current_user)):
    rows = fetch_all("SELECT r.id, r.from_user_id, u.username as from_username, u.user_code as from_user_code, r.created_at FROM friend_requests r JOIN users u ON r.from_user_id = u.id WHERE r.to_user_id = %(me)s AND r.status = 'pending'", {"me": u.id})
    return {"requests": [FriendRequestItem(**r) for r in rows]}

@router.post("/friends/accept", response_model=Dict[str, Any])
def accept_friend(p: FriendAcceptRequest, u: AuthUser = Depends(get_current_user)):
    rid = int(p.request_id)
    req = fetch_one("SELECT * FROM friend_requests WHERE id=%(rid)s AND to_user_id=%(me)s", {"rid": rid, "me": u.id})
    if not req: raise HTTPException(404, "Not found")
    
    # 🔴 分 3 次独立执行，彻底解决单向好友 Bug
    execute("UPDATE friend_requests SET status='accepted' WHERE id=%(rid)s", {"rid": rid})
    execute("INSERT INTO friendships (user_id, friend_id) VALUES (%(u)s, %(f)s) ON CONFLICT DO NOTHING", {"u": u.id, "f": req["from_user_id"]})
    execute("INSERT INTO friendships (user_id, friend_id) VALUES (%(f)s, %(u)s) ON CONFLICT DO NOTHING", {"u": u.id, "f": req["from_user_id"]})
    
    return {"message": "Accepted"}

# -----------------------------------------
# 新增：拒绝好友请求
# -----------------------------------------
@router.post("/friends/requests/{request_id}/reject", response_model=Dict[str, Any])
def reject_friend_request(request_id: int, u: AuthUser = Depends(get_current_user)):
    # 直接用原生 execute 封装更新状态
    execute(
        "UPDATE friend_requests SET status='rejected' WHERE id=%(rid)s AND to_user_id=%(uid)s", 
        {"rid": request_id, "uid": u.id}
    )
    return {"message": "Friend request rejected."}

@router.post("/friends/remove", response_model=Dict[str, Any])
def remove_friend(p: RemoveFriendRequest, u: AuthUser = Depends(get_current_user)):
    execute("DELETE FROM friendships WHERE (user_id=%(u)s AND friend_id=%(f)s) OR (user_id=%(f)s AND friend_id=%(u)s)", {"u": u.id, "f": p.friend_id})
    return {"message": "Friend removed"}

@router.post("/friends/dm", response_model=Dict[str, Any])
def get_or_create_dm(p: DMRequest, u: AuthUser = Depends(get_current_user)):
    if p.friend_id == u.id: raise HTTPException(400, "Cannot DM self")
    existing = fetch_one("""SELECT g.id FROM groups g JOIN group_members gm1 ON g.id=gm1.group_id JOIN group_members gm2 ON g.id=gm2.group_id WHERE gm1.user_id=%(me)s AND gm2.user_id=%(f)s AND g.name LIKE 'DM:%%' LIMIT 1""", {"me": u.id, "f": p.friend_id})
    if existing: return {"group_id": existing["id"], "new": False}
    friend = fetch_one("SELECT username FROM users WHERE id=%(id)s", {"id": p.friend_id})
    if not friend: raise HTTPException(404, "Friend not found")
    dm_name = f"DM: {u.username} & {friend['username']}"
    gid = fetch_one_returning("INSERT INTO groups (name, description, created_by) VALUES (%(n)s, 'DM', %(u)s) RETURNING id", {"n": dm_name, "u": u.id})["id"]
    execute("INSERT INTO group_members (group_id, user_id, role) VALUES (%(gid)s, %(u)s, 'admin')", {"gid": gid, "u": u.id})
    execute("INSERT INTO group_members (group_id, user_id, role) VALUES (%(gid)s, %(u)s, 'admin')", {"gid": gid, "u": p.friend_id})
    return {"group_id": gid, "new": True}

# --- GROUPS ---
@router.get("/groups", response_model=Dict[str, List[GroupSummary]])
def list_groups(u: AuthUser = Depends(get_current_user)):
    rows = fetch_all("SELECT g.id, g.name, g.description, g.created_at FROM groups g JOIN group_members gm ON g.id=gm.group_id WHERE gm.user_id=%(u)s ORDER BY g.created_at DESC", {"u": u.id})
    return {"groups": [GroupSummary(**r) for r in rows]}

@router.post("/groups", response_model=Dict[str, Any])
def create_group(p: GroupCreateRequest, u: AuthUser = Depends(get_current_user)):
    # 1. 创建群组
    gid = fetch_one_returning("INSERT INTO groups (name, description, created_by) VALUES (%(n)s, %(d)s, %(u)s) RETURNING id", {"n": p.name, "d": p.description, "u": u.id})["id"]
    
    # 2. 把创建者自己加进去
    execute("INSERT INTO group_members (group_id, user_id, role) VALUES (%(gid)s, %(u)s, 'admin')", {"gid": gid, "u": u.id})
    
    # 3. 给其他人发送邀请 (不再是直接拉入群)
    if p.member_codes:
        codes = list(set(p.member_codes))
        plc = ",".join(["%s"]*len(codes))
        users = fetch_all(f"SELECT id FROM users WHERE user_code IN ({plc})", codes)
        for user in users:
            if user["id"] != u.id:
                execute(
                    "INSERT INTO group_invitations (group_id, inviter_id, invitee_id, status) VALUES (%(gid)s, %(me)s, %(invitee)s, 'pending')", 
                    {"gid": str(gid), "me": u.id, "invitee": user["id"]}
                )
    return {"message": "Created", "group_id": gid}

@router.get("/groups/{group_id}/members", response_model=Dict[str, List[GroupMemberInfo]])
def get_members(group_id: UUID, u: AuthUser = Depends(get_current_user)):
    rows = fetch_all("SELECT u.id as user_id, u.username, u.user_code, gm.role FROM group_members gm JOIN users u ON gm.user_id=u.id WHERE gm.group_id=%(gid)s", {"gid": str(group_id)})
    return {"members": [GroupMemberInfo(**r) for r in rows]}

@router.post("/groups/{group_id}/invite")
def invite_member(group_id: UUID, p: InviteRequest, u: AuthUser = Depends(get_current_user)):
    execute("INSERT INTO group_members (group_id, user_id, role) VALUES (%(gid)s, (SELECT id FROM users WHERE user_code=%(c)s), 'member') ON CONFLICT DO NOTHING", {"gid": str(group_id), "c": p.friend_code})
    return {"message": "Invited"}

@router.post("/groups/{group_id}/kick")
def kick_member(group_id: UUID, p: KickRequest, u: AuthUser = Depends(get_current_user)):
    me = fetch_one("SELECT role FROM group_members WHERE group_id=%(gid)s AND user_id=%(uid)s", {"gid": str(group_id), "uid": u.id})
    if not me or me["role"] != "admin": raise HTTPException(403, "Admin only")
    if p.user_id == u.id: raise HTTPException(400, "Cannot kick self")
    execute("DELETE FROM group_members WHERE group_id=%(gid)s AND user_id=%(uid)s", {"gid": str(group_id), "uid": p.user_id})
    return {"message": "Kicked"}

@router.post("/groups/{group_id}/leave")
def leave_group(group_id: UUID, u: AuthUser = Depends(get_current_user)):
    execute("DELETE FROM group_members WHERE group_id=%(gid)s AND user_id=%(u)s", {"gid": str(group_id), "u": u.id})
    return {"message": "Left"}

@router.post("/groups/{group_id}/join")
def join_group(group_id: UUID, u: AuthUser = Depends(get_current_user)):
    execute("INSERT INTO group_members (group_id, user_id, role) VALUES (%(gid)s, %(u)s, 'member') ON CONFLICT DO NOTHING", {"gid": str(group_id), "u": u.id})
    return {"message": "Joined"}

@router.get("/groups/{group_id}/messages", response_model=Dict[str, List[GroupMessageModel]])
def get_msgs(group_id: UUID, u: AuthUser = Depends(get_current_user)):
    rows = fetch_all("SELECT id, group_id, sender_display as sender, role, content, created_at FROM group_messages WHERE group_id=%(gid)s ORDER BY created_at ASC LIMIT 100", {"gid": str(group_id)})
    return {"messages": [GroupMessageModel(**r) for r in rows]}

@router.post("/groups/{group_id}/messages", response_model=GroupMessageModel)
def send_msg(group_id: UUID, p: MessageCreateRequest, background_tasks: BackgroundTasks, u: AuthUser = Depends(get_current_user)):
    r = fetch_one_returning(
        "INSERT INTO group_messages (group_id, user_id, sender_display, role, content) VALUES (%(gid)s, %(u)s, %(s)s, 'user', %(c)s) RETURNING id, group_id, sender_display as sender, role, content, created_at",
        {"gid": str(group_id), "u": u.id, "s": u.username, "c": p.content}
    )
    background_tasks.add_task(run_ai_task_in_background, group_id=str(group_id), content=p.content)
    return GroupMessageModel(**r)

# -----------------------------------------
# 新增：群组邀请相关接口
# -----------------------------------------
@router.get("/groups/invitations", response_model=Dict[str, Any])
def get_invitations(u: AuthUser = Depends(get_current_user)):
    # 联合查询获取群组名称和邀请人名称
    rows = fetch_all("""
        SELECT inv.id, inv.group_id, g.name AS group_name, u_inv.username AS invited_by_username
        FROM group_invitations inv
        JOIN groups g ON inv.group_id::varchar = g.id::varchar
        JOIN users u_inv ON inv.inviter_id = u_inv.id
        WHERE inv.invitee_id = %(uid)s AND inv.status = 'pending'
    """, {"uid": u.id})
    
    return {"invitations": [dict(r) for r in rows]}

@router.post("/groups/invitations/{invite_id}/accept", response_model=Dict[str, Any])
def accept_invite(invite_id: int, u: AuthUser = Depends(get_current_user)):
    # 1. 验证邀请是否存在
    inv = fetch_one("SELECT group_id FROM group_invitations WHERE id=%(id)s AND invitee_id=%(uid)s AND status='pending'", {"id": invite_id, "uid": u.id})
    if not inv: 
        raise HTTPException(404, "Invite not found or already processed")
        
    # 2. 更新状态
    execute("UPDATE group_invitations SET status='accepted' WHERE id=%(id)s", {"id": invite_id})
    
    # 3. 真正拉人进群
    execute("INSERT INTO group_members (group_id, user_id, role) VALUES (%(gid)s, %(uid)s, 'member') ON CONFLICT DO NOTHING", {"gid": str(inv["group_id"]), "uid": u.id})
    
    return {"message": "Joined"}

@router.post("/groups/invitations/{invite_id}/reject", response_model=Dict[str, Any])
def reject_invite(invite_id: int, u: AuthUser = Depends(get_current_user)):
    execute("UPDATE group_invitations SET status='rejected' WHERE id=%(id)s AND invitee_id=%(uid)s", {"id": invite_id, "uid": u.id})
    return {"message": "Rejected"}