import sys
import os
import logging

# 1. 强制配置日志，确保能看到 INFO 级别的输出
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')
logger = logging.getLogger(__name__)

# 2. 确保能引用 app 模块
sys.path.append(os.getcwd())

try:
    from app.services.trail_loader import fetch_trails_from_point, process_and_save_to_db
except ImportError as e:
    logger.error(f"❌ 导入失败，请检查 trail_loader.py 是否存在且正确: {e}")
    sys.exit(1)

def seed_initial_data():
    logger.info("🌱 === 开始运行数据库填充脚本 (V5: Metadata) ===\n")
    
    # 📍 格里菲斯天文台坐标 (Griffith Observatory)
    # 强制抓取这里的数据，确保一定有结果
    LAT = 34.1186
    LON = -118.3004
    RADIUS = 3000 # 3公里范围

    logger.info(f"📍 目标: 坐标 ({LAT}, {LON}), 半径 {RADIUS}m")

    # 1. 抓取
    graph = fetch_trails_from_point(LAT, LON, dist=RADIUS)
    
    if graph:
        # 2. 存库
        process_and_save_to_db(graph)
    else:
        logger.error("❌ 严重错误: 没有抓取到任何数据，请检查网络或坐标。")

    logger.info("\n✅ === 脚本运行结束 ===")

if __name__ == "__main__":
    # 这一行至关重要，没有它脚本就不会动
    seed_initial_data()