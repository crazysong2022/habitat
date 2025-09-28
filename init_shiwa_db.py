# init_shiwa_db.py# 修正版：真正创建“成蛙池”而非“商品蛙池”，并补充后续细分所需池区
import os
import psycopg2
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()
DATABASE_URL = os.getenv("DATABASE_SHIWA_URL")
if not DATABASE_URL:
    raise ValueError("❌ DATABASE_SHIWA_URL 未设置")

# 兼容 Heroku 风格 URL
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)


def init_database():
    conn = psycopg2.connect(DATABASE_URL)
    cur = conn.cursor()

    try:
        # ========== 1. 清空所有业务数据表（保留字典表结构） ==========
        print("🗑️ 正在清空业务数据表...")
        tables_to_truncate = [
            "t_business_behavior_record",
            "t_batch_sorting_record",
            "t_incubation_batch",
            "t_incubation_pool",
            "t_frog_inventory",
            "t_material_inventory",
            "t_frog_pool",
        ]
        for table in tables_to_truncate:
            cur.execute(f"TRUNCATE TABLE {table} RESTART IDENTITY CASCADE;")
        print("✅ 业务数据已清空")

        # ========== 2. 插入基础字典数据（使用 True/False） ==========
        print("📚 正在初始化字典表...")

        # ===== 1. 蛙类型字典（按年限）=====
        frog_types = [
            ("SP",     "商品蛙",   "SP", True),
            ("SP_三年蛙",  "三年蛙",   "SP", True),
            ("SP_四年蛙",  "四年蛙",   "SP", True),
            ("SP_五年蛙",  "五年蛙",   "SP", True),
            ("ZB",     "种蛙",     "ZB", True),
            ("ZB_母种",  "母种蛙",   "ZB", True),
            ("ZB_公种",  "公种蛙",   "ZB", True),
            ("SY",     "试验蛙",   "SY", True),
            ("SY_对照组","试验对照组","SY", True),
        ]

        # ===== 2. 创建细分池（500只）=====
        fine_pools = [
            # 公共销售池：统一 pool_type 为 "商品蛙"，便于销售模块直接调用
            ("三年蛙池-001",  "三年蛙",  "通用", 500, "三年蛙专用细分池"),
            ("四年蛙池-001",  "四年蛙",  "通用", 500, "四年蛙专用细分池"),
            ("五年蛙池-001",  "五年蛙",  "通用", 500, "五年蛙专用细分池"),
            ("种蛙池-001",    "种蛙",    "通用", 500, "种蛙专用细分池"),
            ("试验蛙池-001",  "试验蛙",  "通用", 500, "试验蛙专用细分池"),
        ]
        for code, ptype, skin, cap, remark in fine_pools:
            cur.execute("""
                INSERT INTO t_frog_pool (pool_code, pool_type, skin_type, max_capacity, remark)
                VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT (pool_code) DO NOTHING
            """, (code, ptype, skin, cap, remark))

        # 物资类型字典
        material_types = [
            ("FEED_A", "蝌蚪饲料A", "kg"),
            ("FEED_B", "成蛙饲料B", "kg"),
            ("TADPOLE", "外购蝌蚪", "只"),
            ("YOUNG_FROG", "外购幼蛙", "只"),
            ("ADULT_FROG", "外购成蛙", "只"),
        ]
        for code, name, unit in material_types:
            cur.execute("""
                INSERT INTO t_material_type_dict (type_code, name, unit, is_active)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (type_code) DO NOTHING
            """, (code, name, unit, True))

        print("✅ 字典数据初始化完成")

        # ========== 3. 初始化孵化池（10 个空闲池） ==========
        print("🧪 正在创建孵化池...")
        for i in range(1, 11):
            pool_no = f"INC-{i:02d}"
            location = f"孵化区-A排-{i}号"
            cur.execute("""
                INSERT INTO t_incubation_pool (pool_no, location_info, current_status, current_batch_no)
                VALUES (%s, %s, '空闲', NULL)
                ON CONFLICT (pool_no) DO NOTHING
            """, (pool_no, location))
        print("✅ 10 个孵化池已创建")

        # ========== 4. 初始化成蛙池（四来源 × 皮型） ==========
        print("🐸 正在创建成蛙池（分拣首站）...")
        sources = ["自养卵", "外购蝌蚪", "外购幼蛙", "外购成蛙"]
        skin_types = ["细皮", "粗皮"]
        for src in sources:
            for skin in skin_types:
                pool_code = f"{src}{skin}成蛙池-001"  # ✅ 关键：成蛙池，不是商品蛙池
                cur.execute("""
                    INSERT INTO t_frog_pool (pool_code, pool_type, skin_type, max_capacity, remark)
                    VALUES (%s, %s, %s, 500, %s)
                    ON CONFLICT (pool_code) DO NOTHING
                """, (pool_code, src, skin, f"{src}{skin}专用成蛙池"))
        print("✅ 成蛙池初始化完成")

        # ========== 5. 初始化后续细分池（商品/种/试验） ==========
        print("🎯 正在创建细分池...")
        # ① 来源+皮型商品蛙池（再分类后才进入）
        for src in sources:
            for skin in skin_types:
                pool_code = f"{src}{skin}商品蛙池-001"
                cur.execute("""
                    INSERT INTO t_frog_pool (pool_code, pool_type, skin_type, max_capacity, remark)
                    VALUES (%s, %s, %s, 500, %s)
                    ON CONFLICT (pool_code) DO NOTHING
                """, (pool_code, src, skin, f"{src}{skin}专用商品蛙池"))

        # ② 通用池
        generic_pools = [
            ("种蛙池", "通用", "通用", 200),
            ("试验蛙池", "通用", "通用", 100),
            # 若需一个“兜底”商品池，可保留：
            ("商品蛙池", "通用", "通用", 500),
        ]
        for code, ptype, skin, cap in generic_pools:
            cur.execute("""
                INSERT INTO t_frog_pool (pool_code, pool_type, skin_type, max_capacity, remark)
                VALUES (%s, %s, %s, %s, '通用池')
                ON CONFLICT (pool_code) DO NOTHING
            """, (code, ptype, skin, cap))
        print("✅ 细分池初始化完成")

        conn.commit()
        print("🎉 数据库初始化成功！现在可以开始测试了。")

    except Exception as e:
        conn.rollback()
        print(f"❌ 初始化失败: {e}")
        raise
    finally:
        cur.close()
        conn.close()


if __name__ == "__main__":
    init_database()