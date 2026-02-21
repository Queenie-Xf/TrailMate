import re
import hashlib
from fastapi import APIRouter, HTTPException, Header

# ✅ 修正：使用完整路径导入
from app.models.sql_models import (
    SignupRequest,
    LoginRequest,
    AuthResponse,
    AuthUser,
)
# ✅ 修正：从数据库核心模块导入
from app.core.database import fetch_one, fetch_one_returning

router = APIRouter(prefix="/auth", tags=["auth"])

def _hash_password(password: str) -> str:
    return hashlib.sha256(password.encode("utf-8")).hexdigest()

# 你原本的正则校验逻辑
USER_CODE_REGEX = re.compile(r"^[A-Za-z0-9]{4,16}$")

def _validate_user_code(user_code: str) -> None:
    if not USER_CODE_REGEX.match(user_code):
        raise HTTPException(
            400,
            "user_code 必须是 4~16 位的字母和数字（不能有空格、符号）",
        )

@router.post("/signup", response_model=AuthResponse)
def signup(payload: SignupRequest) -> AuthResponse:
    username = payload.username.strip()
    user_code = payload.user_code.strip()
    password = payload.password

    if not username or not password or not user_code:
        raise HTTPException(400, "username、password、user_code 都是必填的")

    _validate_user_code(user_code)

    # 1. 检查 Username 是否存在
    existing_user = fetch_one("SELECT id FROM users WHERE LOWER(username) = LOWER(%(u)s)", {"u": username})
    if existing_user:
        raise HTTPException(400, "Username 已经存在")

    # 2. 🔴 核心新增：检查 user_code 是否已被占用 (解决 2001 重复问题)
    existing_code = fetch_one("SELECT id FROM users WHERE LOWER(user_code) = LOWER(%(c)s)", {"c": user_code})
    if existing_code:
        raise HTTPException(400, f"这个 user_code ({user_code}) 已被使用，请换一个")

    # 3. 插入数据
    row = fetch_one_returning(
        """
        INSERT INTO users (username, user_code, password_hash)
        VALUES (%(u)s, %(code)s, %(pwd)s)
        RETURNING id, username, user_code
        """,
        {
            "u": username,
            "code": user_code,
            "pwd": _hash_password(password),
        },
    )

    user = AuthUser(id=row["id"], username=row["username"], user_code=row["user_code"])
    return AuthResponse(user=user, message="Signup successful")

@router.post("/login", response_model=AuthResponse)
def login(payload: LoginRequest) -> AuthResponse:
    username = payload.username.strip()
    password = payload.password

    row = fetch_one(
        "SELECT id, username, user_code, password_hash FROM users WHERE username = %(u)s",
        {"u": username},
    )
    if not row or row["password_hash"] != _hash_password(password):
        raise HTTPException(400, "Invalid username or password")

    user = AuthUser(id=row["id"], username=row["username"], user_code=row["user_code"])
    return AuthResponse(user=user, message="Login successful")

def get_current_user(
    x_username: str = Header(..., alias="X-Username"),
    x_user_code: str = Header(..., alias="X-User-Code"),
) -> AuthUser:
    row = fetch_one(
        "SELECT id, username, user_code FROM users WHERE username = %(u)s AND user_code = %(c)s",
        {"u": x_username, "c": x_user_code},
    )
    if not row:
        raise HTTPException(401, "Invalid auth headers")
    return AuthUser(id=row["id"], username=row["username"], user_code=row["user_code"])