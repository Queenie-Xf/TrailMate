import sys
import os
import asyncio

# 确保能导入父目录的 app
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services.trail_loader import fetch_trails_from_osm, add_elevation_data, process_and_save_to_db

def seed_initial_data():
    print("🌱 Starting Database Seeding Process...")
    # 目标区域
    target_areas = ["Griffith Park, Los Angeles, USA"]
    
    for area in target_areas:
        print(f"\n📍 Processing Area: {area}")
        graph = fetch_trails_from_osm(area)
        if graph:
            # 这里的 None 表示没有 .tif 文件，使用模拟海拔
            graph = add_elevation_data(graph, None) 
            process_and_save_to_db(graph)
        else:
            print(f"⚠️ Could not fetch data for {area}")

    print("\n✅ Seeding Complete!")

if __name__ == "__main__":
    seed_initial_data()