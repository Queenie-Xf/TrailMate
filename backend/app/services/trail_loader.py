import os
import logging
import pandas as pd
import osmnx as ox
from sqlalchemy import create_engine
from geoalchemy2 import Geometry
from dotenv import load_dotenv

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

load_dotenv()

# 数据库配置
DB_USER = os.getenv("POSTGRES_USER", "hikebot")
DB_PASS = os.getenv("POSTGRES_PASSWORD", "hikebot")
DB_HOST = os.getenv("POSTGRES_HOST", "localhost")
DB_PORT = os.getenv("POSTGRES_PORT", "5432")
DB_NAME = os.getenv("POSTGRES_DB", "hikebot")

DATABASE_URL = f"postgresql://{DB_USER}:{DB_PASS}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

def get_db_engine():
    return create_engine(DATABASE_URL)

def fetch_trails_from_point(lat: float, lon: float, dist: int = 2000):
    logger.info(f"🌍 [1/3] 正在强制抓取坐标 ({lat}, {lon}) 周围 {dist}米 的数据...")
    try:
        G = ox.graph_from_point((lat, lon), dist=dist, network_type='all', simplify=True)
        logger.info(f"✅ [2/3] 下载成功! 抓取到 {len(G.edges)} 条路段")
        return G
    except Exception as e:
        logger.error(f"❌ OSM 坐标下载出错: {e}")
        return None

def fetch_trails_from_osm(place_name: str):
    try:
        G = ox.graph_from_place(place_name, network_type='all', simplify=True)
        return G
    except Exception:
        return None

def add_elevation_data(G, raster_path=None):
    return G

def process_and_save_to_db(G, table_name="trails"):
    if not G or len(G.edges) == 0:
        logger.warning("⚠️  图形为空，无法保存！")
        return

    logger.info("💾 [3/3] 正在转换并存入数据库 (V7: 全字段独立列)...")
    try:
        gdf_nodes, gdf_edges = ox.graph_to_gdfs(G)
        gdf_edges = gdf_edges.reset_index()
        
        # 1. 基础清理：处理 List 类型
        for col in gdf_edges.columns:
            if gdf_edges[col].apply(lambda x: isinstance(x, list)).any():
                gdf_edges[col] = gdf_edges[col].apply(lambda x: ', '.join(map(str, x)) if isinstance(x, list) else x)
        
        # 2. 确保名字和长度存在
        if 'name' not in gdf_edges.columns:
            gdf_edges['name'] = "Unnamed Trail"
        gdf_edges['name'] = gdf_edges['name'].fillna("Unnamed Trail")

        if 'length' in gdf_edges.columns:
            gdf_edges['length_km'] = gdf_edges['length'] / 1000.0
        else:
            gdf_edges['length_km'] = 0.0

        # 🎯 3. 定义你指定的所有目标列 (不包含 ref 和 symbol)
        target_columns = [
            # 难度
            'sac_scale',        # 难度分级
            'trail_visibility', # 路径清晰度
            'smoothness',       # 路面平整度
            
            # 路况
            'surface',          # 物理路面材质
            'tracktype',        # 道路硬化等级
            'width',            # 宽度
            'incline',          # 坡度
            
            # 设施/描述
            'description',      # 文字描述
            
            # 权限
            'access',           # 总体权限
            'foot',             # 行人
            'dog',              # 狗
            'bicycle',          # 自行车
            'horse',            # 马
            
            # 景色/地标 (独立存，不合并)
            'tourism',          # 观景点
            'natural',          # 山峰/自然特征
            'landmark'          # 地标
        ]

        # 4. 循环检查：如果 OSM 数据里没有这一列，就创建一个全空的列
        # 这样能保证数据库表结构永远包含这些字段
        for col in target_columns:
            if col not in gdf_edges.columns:
                gdf_edges[col] = None  # 填充空值

        # 5. 组装最终要存的列名
        # 基础列 + 你的目标列 + 地理形状
        final_column_list = ['name', 'length_km'] + target_columns + ['geometry']
        
        # 提取数据
        db_gdf = gdf_edges[final_column_list].copy()
        
        # 6. 存入数据库
        engine = get_db_engine()
        db_gdf.to_postgis(
            name=table_name,
            con=engine,
            if_exists='replace', # 覆盖重建表
            index=False,
            dtype={'geometry': Geometry('LINESTRING', srid=4326)}
        )
        logger.info(f"🚀 写入成功! 表结构已更新，包含所有指定字段。")
        
    except Exception as e:
        logger.error(f"❌ 数据库写入失败: {e}")
        import traceback
        traceback.print_exc()