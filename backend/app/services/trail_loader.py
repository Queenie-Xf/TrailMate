import os
import sys
import logging
import osmnx as ox
import networkx as nx
import geopandas as gpd
import pandas as pd
from sqlalchemy import create_engine
from geoalchemy2 import Geometry
from dotenv import load_dotenv

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 加载环境变量
load_dotenv()

# 数据库连接配置
DB_USER = os.getenv("POSTGRES_USER", "postgres")
DB_PASS = os.getenv("POSTGRES_PASSWORD", "password")
DB_HOST = os.getenv("POSTGRES_HOST", "localhost")
DB_PORT = os.getenv("POSTGRES_PORT", "5432")
DB_NAME = os.getenv("POSTGRES_DB", "hikebot")

DATABASE_URL = f"postgresql://{DB_USER}:{DB_PASS}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

# 🎯 核心过滤器：只抓取真正的徒步路线
# 排除掉普通的城市人行道 (sidewalk) 和服务道路 (service road)
CUSTOM_FILTER = (
    '["highway"~"path|track|footway"]'
    '["foot"!~"no"]'
    '["service"!~"alley|driveway"]'
    '["surface"!~"paved|asphalt"]'  # 可选：如果你只想要土路/自然路面
)

def get_db_engine():
    return create_engine(DATABASE_URL)

def fetch_trails_from_osm(place_name: str, dist: int = None):
    """
    从 OpenStreetMap 获取指定区域的徒步路网。
    :param place_name: 地点名称 (e.g., "Griffith Park, Los Angeles")
    :param dist: 如果是按坐标点搜索，可以传距离范围 (米)
    """
    logger.info(f"🌍 正在从 OSM 获取数据: {place_name}...")
    
    try:
        # 下载路网图 (Graph)
        G = ox.graph_from_place(
            place_name, 
            network_type='walk', 
            simplify=True, 
            custom_filter=CUSTOM_FILTER
        )
        logger.info(f"✅ 下载成功! 包含 {len(G.nodes)} 个节点和 {len(G.edges)} 条路段。")
        return G
    except Exception as e:
        logger.error(f"❌ OSM 下载失败: {e}")
        return None

def add_elevation_data(G, raster_path: str = None):
    """
    为路线添加海拔数据 (2D -> 3D)。
    如果 raster_path 存在，使用真实 DEM 数据；否则使用模拟数据。
    """
    if raster_path and os.path.exists(raster_path):
        logger.info(f"🏔️ 正在从文件读取海拔数据: {raster_path}")
        try:
            G = ox.elevation.add_node_elevations_raster(G, raster_path)
            G = ox.elevation.add_edge_grades(G)
            logger.info("✅ 海拔数据添加成功。")
        except Exception as e:
            logger.warning(f"⚠️ 海拔数据处理失败: {e}")
    else:
        logger.warning("⚠️ 未提供 DEM 文件，正在生成模拟海拔数据 (仅供测试)...")
        # 模拟海拔：简单的波浪函数
        for i, (node, data) in enumerate(G.nodes(data=True)):
            data['elevation'] = 100 + (i % 50) * 10
            
    return G

def process_and_save_to_db(G, table_name="trails"):
    """
    将 NetworkX 图转换为 GeoDataFrame 并存入 PostGIS。
    """
    logger.info("💾 正在处理数据并存入数据库...")
    
    # 1. 转为 GeoDataFrame
    # nodes 是点，edges 是线（我们主要存 edges）
    gdf_nodes, gdf_edges = ox.graph_to_gdfs(G)
    
    # 2. 数据清洗
    # Reset index to allow saving ID
    gdf_edges = gdf_edges.reset_index()
    
    # 处理 OSM 返回的 List 类型数据 (Postgres 不能直接存 List)
    # 例如: highway=['path', 'track'] -> "path, track"
    for col in gdf_edges.columns:
        if gdf_edges[col].apply(lambda x: isinstance(x, list)).any():
            gdf_edges[col] = gdf_edges[col].apply(lambda x: ', '.join(map(str, x)) if isinstance(x, list) else x)
            
    # 填充缺失名称
    if 'name' not in gdf_edges.columns:
        gdf_edges['name'] = "Unnamed Trail"
    gdf_edges['name'] = gdf_edges['name'].fillna("Unnamed Trail")

    # 3. 筛选需要的列
    # 根据你的 models.py 调整，这里保留核心字段
    columns_to_keep = ['name', 'length', 'geometry']
    if 'grade' in gdf_edges.columns:
        columns_to_keep.append('grade')
        
    # 确保只保留存在的列
    final_cols = [c for c in columns_to_keep if c in gdf_edges.columns]
    db_gdf = gdf_edges[final_cols].copy()
    
    # 重命名 length -> length_km (可选)
    # db_gdf['length_km'] = db_gdf['length'] / 1000.0

    # 4. 存入 PostGIS
    engine = get_db_engine()
    try:
        # 使用 GeoPandas 的 to_postgis 方法 (需安装 geoalchemy2)
        db_gdf.to_postgis(
            name=table_name,
            con=engine,
            if_exists='replace', # 开发阶段用 replace，生产环境用 append
            index=False,
            dtype={'geometry': Geometry('LINESTRING', srid=4326)}
        )
        logger.info(f"🚀 成功! 已将 {len(db_gdf)} 条路线存入表 '{table_name}'")
    except Exception as e:
        logger.error(f"❌ 数据库写入错误: {e}")

# --- 如果直接运行此文件 (用于测试) ---
if __name__ == "__main__":
    # 测试区域：洛杉矶格里菲斯公园
    AREA = "Griffith Park, Los Angeles, USA"
    
    print(f"Testing loader for: {AREA}")
    graph = fetch_trails_from_osm(AREA)
    
    if graph:
        # 如果你有 .tif 文件，填在这里
        # graph = add_elevation_data(graph, "./backend/data/srtm.tif")
        graph = add_elevation_data(graph, None) 
        process_and_save_to_db(graph)