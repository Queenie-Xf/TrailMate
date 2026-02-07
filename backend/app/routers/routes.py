from fastapi import APIRouter, HTTPException, Query
from typing import List, Dict, Any

from app.core.database import fetch_all

router = APIRouter(prefix="/routes", tags=["routes"])

@router.get("/", response_model=List[Dict[str, Any]])
def get_routes(limit: int = 50):
    """
    获取数据库里的路线列表
    """
    try:
        # ✅ 修正：改用 length_km
        # 注意：location 字段在爬虫数据里可能叫 'addr:city' 或者可能为空，
        # 为了防止报错，我们暂时只取 name, length_km 和 id
        query = "SELECT id, name, length_km FROM trails LIMIT %(limit)s"
        trails = fetch_all(query, {"limit": limit})
        return trails
    except Exception as e:
        print(f"Error fetching routes: {e}")
        return []

@router.get("/search")
def search_routes(q: str):
    """
    名称搜索
    """
    if not q: return []
    
    try:
        # ✅ 修正：改用 length_km
        query = "SELECT id, name, length_km FROM trails WHERE name ILIKE %(q)s LIMIT 10"
        trails = fetch_all(query, {"q": f"%{q}%"})
        return trails
    except Exception as e:
        print(f"Search error: {e}")
        return []