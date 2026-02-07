import json
import asyncio
import logging
from pathlib import Path
from typing import Dict, Optional
from datetime import datetime

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware

from app.routers import auth, social, routes  # ✅ 引用 routes
from app.core.database import SessionLocal, fetch_one, fetch_one_returning, engine, Base
from app.models.sql_models import AuthUser
from app.services.planner import AutoPlannerService

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("uvicorn")

# 初始化数据库表
Base.metadata.create_all(bind=engine)

app = FastAPI(title="HikeBot Backend")

# 挂载静态文件
static_dir = Path(__file__).parent.parent / "static"
if static_dir.exists():
    app.mount("/static", StaticFiles(directory=static_dir), name="static")

# ✅ 注册所有路由
app.include_router(auth.router)
app.include_router(social.router)
app.include_router(routes.router)  # ✅ 现在可以安全地挂载它了

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ... (后面的 WebSocket 代码保持不变，不需要动) ...
# ...
# ...
# ==============================================================
#                 WebSocket Manager (Group Chat)
# ==============================================================

class GroupConnectionManager:
    def __init__(self) -> None:
        self.rooms: Dict[str, Dict[int, WebSocket]] = {}

    async def connect(self, group_id: str, user_id: int, websocket: WebSocket):
        await websocket.accept()
        self.rooms.setdefault(group_id, {})
        self.rooms[group_id][user_id] = websocket
        logger.info(f"User {user_id} connected to Group {group_id}")

    def disconnect(self, group_id: str, user_id: int):
        if group_id in self.rooms and user_id in self.rooms[group_id]:
            del self.rooms[group_id][user_id]
            if not self.rooms[group_id]:
                del self.rooms[group_id]

    async def broadcast_json(self, group_id: str, message: dict):
        data = json.dumps(message)
        room = self.rooms.get(group_id)
        if not room: return
        
        dead_users = []
        for uid, ws in list(room.items()):
            try:
                await ws.send_text(data)
            except RuntimeError:
                dead_users.append(uid)
        
        for uid in dead_users:
            self.disconnect(group_id, uid)

group_manager = GroupConnectionManager()

async def run_ai_pipeline_for_ws(group_id: str, user_content: str):
    db = SessionLocal()
    try:
        planner = AutoPlannerService(db)
        await planner.run_pipeline(chat_id=group_id, user_message=user_content)
        
        row = fetch_one(
            """
            SELECT id, group_id, sender_display, role, content, created_at 
            FROM group_messages 
            WHERE group_id = %(gid)s AND role = 'assistant' AND sender_display = 'HikeBot'
            ORDER BY created_at DESC LIMIT 1
            """,
            {"gid": group_id}
        )
        
        if row:
            time_diff = (datetime.utcnow() - row["created_at"]).total_seconds()
            if time_diff < 5:
                ai_msg = {
                    "id": row["id"],
                    "group_id": str(row["group_id"]),
                    "sender": row["sender_display"],
                    "role": row["role"],
                    "content": row["content"],
                    "created_at": row["created_at"].isoformat(),
                }
                await group_manager.broadcast_json(group_id, ai_msg)
    except Exception as e:
        logger.error(f"AI WebSocket Error: {e}")
    finally:
        db.close()

async def _get_user_for_ws(username: str, user_code: str) -> Optional[AuthUser]:
    row = fetch_one(
        "SELECT id, username, user_code FROM users WHERE username = %(u)s AND user_code = %(c)s",
        {"u": username, "c": user_code},
    )
    if not row: return None
    return AuthUser(id=row["id"], username=row["username"], user_code=row["user_code"])

@app.websocket("/ws/groups/{group_id}")
async def group_ws(websocket: WebSocket, group_id: str, username: str, user_code: str):
    user = await _get_user_for_ws(username, user_code)
    if not user:
        await websocket.close(code=4401)
        return

    membership = fetch_one(
        "SELECT 1 FROM group_members WHERE group_id = %(gid)s AND user_id = %(uid)s",
        {"gid": group_id, "uid": user.id},
    )
    if not membership:
        await websocket.close(code=4403)
        return

    await group_manager.connect(group_id, user.id, websocket)

    try:
        while True:
            text = await websocket.receive_text()
            row = fetch_one_returning(
                """
                INSERT INTO group_messages (group_id, user_id, sender_display, role, content)
                VALUES (%(gid)s, %(uid)s, %(s)s, 'user', %(c)s)
                RETURNING id, group_id, sender_display AS sender, role, content, created_at
                """,
                {
                    "gid": group_id,
                    "uid": user.id,
                    "s": user.username,
                    "c": text,
                },
            )

            msg_payload = {
                "id": row["id"],
                "group_id": str(row["group_id"]),
                "sender": row["sender"],
                "role": row["role"],
                "content": row["content"],
                "created_at": row["created_at"].isoformat(),
            }
            await group_manager.broadcast_json(group_id, msg_payload)
            asyncio.create_task(run_ai_pipeline_for_ws(group_id, text))

    except WebSocketDisconnect:
        group_manager.disconnect(group_id, user.id)

@app.get("/")
def read_root():
    return {"message": "HikeBot Backend V2 is Running!"}