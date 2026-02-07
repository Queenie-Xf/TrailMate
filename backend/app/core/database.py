import os
import psycopg2
from psycopg2.extras import RealDictCursor
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from contextlib import contextmanager
from typing import Any, Dict, Iterable, Optional

# ==========================================
# 1. 配置与连接信息
# ==========================================
POSTGRES_USER = os.getenv("POSTGRES_USER", "hikebot")
POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD", "hikebot")
POSTGRES_HOST = os.getenv("POSTGRES_HOST", "postgres")
POSTGRES_PORT = os.getenv("POSTGRES_PORT", "5432")
POSTGRES_DB = os.getenv("POSTGRES_DB", "hikebot")

DATABASE_URL = f"postgresql://{POSTGRES_USER}:{POSTGRES_PASSWORD}@{POSTGRES_HOST}:{POSTGRES_PORT}/{POSTGRES_DB}"

# ==========================================
# 2. SQLAlchemy Setup (用于 ORM)
# ==========================================
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def get_db():
    """FastAPI 依赖注入使用的生成器"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# ==========================================
# 3. Raw SQL Helpers (用于高性能查询)
#    (迁移自原来的 pg_db.py)
# ==========================================

def _get_raw_conn():
    return psycopg2.connect(
        host=POSTGRES_HOST,
        dbname=POSTGRES_DB,
        user=POSTGRES_USER,
        password=POSTGRES_PASSWORD,
        cursor_factory=RealDictCursor,
    )

@contextmanager
def get_cursor():
    conn = _get_raw_conn()
    try:
        cur = conn.cursor()
        yield cur
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

def fetch_one(query: str, params: Optional[Dict[str, Any]] = None) -> Optional[Dict[str, Any]]:
    with get_cursor() as cur:
        cur.execute(query, params or {})
        row = cur.fetchone()
        return dict(row) if row else None

def fetch_all(query: str, params: Optional[Dict[str, Any]] = None) -> Iterable[Dict[str, Any]]:
    with get_cursor() as cur:
        cur.execute(query, params or {})
        rows = cur.fetchall()
        return [dict(r) for r in rows]

def execute(query: str, params: Optional[Dict[str, Any]] = None) -> None:
    with get_cursor() as cur:
        cur.execute(query, params or {})

def fetch_one_returning(query: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    with get_cursor() as cur:
        cur.execute(query, params or {})
        row = cur.fetchone()
        if not row:
            raise RuntimeError("No row returned from query")
        return dict(row)