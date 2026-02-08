import logging
# ✅ 从你现有的 database.py 导入 get_cursor 工具
from app.core.database import get_cursor 

logger = logging.getLogger("uvicorn")

def init_tables():
    """
    初始化数据库表。
    使用 CREATE TABLE IF NOT EXISTS 确保即使容器重启，数据也会保留在 Volume 中而不会报错。
    """
    logger.info("Checking database tables...")
    
    # 按照依赖顺序排列建表语句
    queries = [
        # 1. Users (基础表)
        """
        CREATE TABLE IF NOT EXISTS users (
            id SERIAL PRIMARY KEY,
            username VARCHAR(50) UNIQUE NOT NULL,
            user_code VARCHAR(20) UNIQUE NOT NULL,
            password_hash VARCHAR(128) NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """,
        # 2. Friend Requests (依赖 users)
        """
        CREATE TABLE IF NOT EXISTS friend_requests (
            id SERIAL PRIMARY KEY,
            from_user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
            to_user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
            status VARCHAR(20) DEFAULT 'pending',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(from_user_id, to_user_id)
        );
        """,
        # 3. Friendships (依赖 users)
        """
        CREATE TABLE IF NOT EXISTS friendships (
            user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
            friend_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (user_id, friend_id)
        );
        """,
        # 4. Groups (依赖 users)
        """
        CREATE TABLE IF NOT EXISTS groups (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            name VARCHAR(100) NOT NULL,
            description TEXT,
            created_by INTEGER REFERENCES users(id) ON DELETE SET NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """,
        # 5. Group Members (依赖 groups 和 users)
        """
        CREATE TABLE IF NOT EXISTS group_members (
            group_id UUID REFERENCES groups(id) ON DELETE CASCADE,
            user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
            role VARCHAR(20) DEFAULT 'member', 
            joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (group_id, user_id)
        );
        """,
        # 6. Group Messages (依赖 groups 和 users)
        """
        CREATE TABLE IF NOT EXISTS group_messages (
            id SERIAL PRIMARY KEY,
            group_id UUID REFERENCES groups(id) ON DELETE CASCADE,
            user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
            sender_display VARCHAR(50),
            role VARCHAR(20) DEFAULT 'user',
            content TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """
    ]

    try:
        with get_cursor() as cur:
            # ✅ 如果你的 Postgres 镜像版本较低，可能需要手动开启 UUID 扩展
            cur.execute('CREATE EXTENSION IF NOT EXISTS "pgcrypto";')
            
            for q in queries:
                cur.execute(q)
        logger.info("Database tables verified/initialized successfully.")
    except Exception as e:
        logger.error(f"Failed to initialize database tables: {e}")
        raise e