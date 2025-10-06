# projects/shiwa_farm/main.py
import streamlit as st
import os
from urllib.parse import urlparse
import psycopg2
from datetime import datetime, time
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
from dotenv import load_dotenv
# ================== ① AI 问答新增依赖 ==================
import json, tempfile, pandas as pd
from datetime import datetime
from openai import OpenAI
from sqlalchemy import create_engine, text, inspect
from sqlalchemy.exc import SQLAlchemyError
# =======================================================

# -----------------------------
# 加载环境变量
# -----------------------------
load_dotenv()

DATABASE_URL = os.getenv("DATABASE_SHIWA_URL")
if not DATABASE_URL:
    st.error("❌ DATABASE_SHIWA_URL 未在 .env 中设置！")
    st.stop()

# 解析数据库 URL
try:
    url = urlparse(DATABASE_URL)
    DB_CONFIG = {
        "host": url.hostname,
        "port": url.port or 5432,
        "database": url.path[1:],
        "user": url.username,
        "password": url.password,
    }
except Exception as e:
    st.error(f"❌ 数据库 URL 解析失败: {e}")
    st.stop()


# -----------------------------
# 数据库工具函数
# -----------------------------
def get_db_connection():
    return psycopg2.connect(**DB_CONFIG)


def table_exists(cursor, table_name):
    cursor.execute("""
        SELECT EXISTS (
            SELECT FROM information_schema.tables 
            WHERE table_schema = 'public' 
            AND table_name = %s
        );
    """, (table_name,))
    return cursor.fetchone()[0]

TRANSFER_PATH_RULES = {
    "种蛙池": ["商品蛙池","三年蛙池", "四年蛙池", "五年蛙池", "六年蛙池", "试验池"],
    "孵化池": ["养殖池", "试验池"],
    "养殖池": ["商品蛙池", "种蛙池", "试验池"],
    "商品蛙池": ["三年蛙池", "四年蛙池", "五年蛙池", "六年蛙池", "试验池"],
    # 试验池、销售周转池不允许转出（不在 keys 中）
}
# ============== 常用备注短语字典 ==============
COMMON_REMARKS = {
    "喂养备注": [
        "",
        "正常投喂",
        "加量投喂",
        "减量投喂",
        "蛙群活跃",
        "蛙群食欲一般",
        "剩料较多",
        "今日换水",
        "水温偏高，减料",
        "水温偏低，加料",
        "下雨延迟投喂"
    ],
    "每日观察": [
        "",
        "蛙群活跃，摄食正常",
        "发现个别浮头",
        "水面有泡沫",
        "池底粪便较多",
        "蝌蚪集群正常",
        "卵块增加",
        "发现有死亡个体",
        "活动力下降",
        "皮肤颜色正常",
        "换水后活跃"
    ],
    "操作描述": [
        "",
        "日常转池",
        "密度调整",
        "大小分级",
        "外购新苗",
        "自繁孵化",
        "病害隔离",
        "销售备货",
        "实验观察",
        "清池消毒",
        "暴雨后应急转移"
    ]
}
# ==========================================
# -----------------------------
# 初始化数据库（幂等）
# -----------------------------
def initialize_database():
    conn = psycopg2.connect(**DB_CONFIG)
    conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
    cur = conn.cursor()

    try:
        # 1. frog_type_shiwa
        if not table_exists(cur, 'frog_type_shiwa'):
            cur.execute("""
                CREATE TABLE frog_type_shiwa (
                    id SERIAL PRIMARY KEY,
                    name VARCHAR(20) NOT NULL UNIQUE CHECK (name IN ('细皮蛙', '粗皮蛙'))
                );
                INSERT INTO frog_type_shiwa (name) VALUES ('细皮蛙'), ('粗皮蛙');
            """)
            st.toast("✅ 创建蛙种类表", icon="🐸")

        # 2. pond_type_shiwa
        if not table_exists(cur, 'pond_type_shiwa'):
            cur.execute("""
                CREATE TABLE pond_type_shiwa (
                    id SERIAL PRIMARY KEY,
                    name VARCHAR(50) NOT NULL UNIQUE,
                    description TEXT
                );
            """)
            st.toast("✅ 创建池塘类型表", icon="🏞️")

        for name, desc in [
            ('种蛙池', '用于繁殖的成年种蛙'),
            ('孵化池', '用于孵化卵或外购蝌蚪'),
            ('养殖池', '幼蛙生长阶段'),
            ('商品蛙池', '准备销售的商品成蛙'),
            ('三年蛙池', '3年生销售周转池'),
            ('四年蛙池', '4年生销售周转池'),
            ('五年蛙池', '5年生销售周转池'),
            ('六年蛙池', '6年生销售周转池'),
            ('试验池', '用于实验或观察的特殊池'),
        ]:
            cur.execute(
                """INSERT INTO pond_type_shiwa (name, description)
                VALUES (%s, %s)
                ON CONFLICT (name) DO NOTHING;""",
                (name, desc)
            )

        # 3. pond_shiwa
        if not table_exists(cur, 'pond_shiwa'):
            cur.execute("""
                CREATE TABLE pond_shiwa (
                    id SERIAL PRIMARY KEY,
                    name VARCHAR(100) NOT NULL,
                    pond_type_id INT NOT NULL REFERENCES pond_type_shiwa(id) ON DELETE RESTRICT,
                    frog_type_id INT NOT NULL REFERENCES frog_type_shiwa(id) ON DELETE RESTRICT,
                    max_capacity INT NOT NULL DEFAULT 1000 CHECK (max_capacity > 0),
                    current_count INT NOT NULL DEFAULT 0 CHECK (current_count >= 0 AND current_count <= max_capacity),
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
                );
            """)
            st.toast("✅ 创建池塘实例表", icon="🏠")
            # 在 initialize_database() 的 pond_shiwa 创建之后加上：
            cur.execute("""
                DO $$
                BEGIN
                    IF NOT EXISTS (
                        SELECT 1
                        FROM information_schema.constraint_column_usage
                        WHERE table_name = 'pond_shiwa'
                        AND constraint_name = 'unique_pond_name'
                    ) THEN
                        ALTER TABLE pond_shiwa ADD CONSTRAINT unique_pond_name UNIQUE (name);
                    END IF;
                END $$;
            """)
        # 4. feed_type_shiwa
        if not table_exists(cur, 'feed_type_shiwa'):
            cur.execute("""
                CREATE TABLE feed_type_shiwa (
                    id SERIAL PRIMARY KEY,
                    name VARCHAR(50) NOT NULL UNIQUE,
                    unit_price DECIMAL(10,2) NOT NULL DEFAULT 0.00
                );
                INSERT INTO feed_type_shiwa (name, unit_price) VALUES
                ('饲料', 10.00),
                ('大面包虫', 30.00),
                ('小面包虫', 20.00);
            """)
            st.toast("✅ 创建饲料类型表", icon="🪱")

        # 5. feeding_record_shiwa
        if not table_exists(cur, 'feeding_record_shiwa'):
            cur.execute("""
                CREATE TABLE feeding_record_shiwa (
                    id SERIAL PRIMARY KEY,
                    pond_id INT NOT NULL REFERENCES pond_shiwa(id) ON DELETE CASCADE,
                    feed_type_id INT NOT NULL REFERENCES feed_type_shiwa(id) ON DELETE RESTRICT,
                    feed_weight_kg DECIMAL(8,3) NOT NULL CHECK (feed_weight_kg > 0),
                    unit_price_at_time DECIMAL(10,2) NOT NULL,
                    total_cost DECIMAL(12,2) GENERATED ALWAYS AS (feed_weight_kg * unit_price_at_time) STORED,
                    fed_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                    notes TEXT
                );
            """)
            st.toast("✅ 创建喂养记录表", icon="🍽️")

        # 6. stock_movement_shiwa 及枚举、约束、触发器
        cur.execute("SELECT 1 FROM pg_type WHERE typname = 'movement_type_shiwa';")
        if not cur.fetchone():
            cur.execute("CREATE TYPE movement_type_shiwa AS ENUM ('transfer', 'purchase', 'hatch');")
            cur.execute("ALTER TYPE movement_type_shiwa ADD VALUE IF NOT EXISTS 'sale';")

        if not table_exists(cur, 'stock_movement_shiwa'):
            cur.execute("""
                CREATE TABLE stock_movement_shiwa (
                    id SERIAL PRIMARY KEY,
                    movement_type movement_type_shiwa NOT NULL,
                    from_pond_id INT REFERENCES pond_shiwa(id) ON DELETE SET NULL,
                    to_pond_id   INT REFERENCES pond_shiwa(id) ON DELETE RESTRICT,
                    quantity INT NOT NULL CHECK (quantity > 0),
                    description TEXT,
                    moved_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                    unit_price DECIMAL(8,2)
                );
            """)
            st.toast("✅ 创建转池/外购/孵化记录表", icon="🔄")

        # -------------- 检查约束升级（hatch 合法）--------------
        cur.execute("""
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM pg_constraint
                       WHERE conname = 'chk_movement_from'
                         AND contype = 'c'
                         AND pg_get_constraintdef(oid) NOT LIKE '%hatch%') THEN
                ALTER TABLE stock_movement_shiwa DROP CONSTRAINT chk_movement_from;
            END IF;
            IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'chk_movement_from') THEN
                ALTER TABLE stock_movement_shiwa
                ADD CONSTRAINT chk_movement_from CHECK (
                    (movement_type = 'transfer' AND from_pond_id IS NOT NULL) OR
                    (movement_type = 'purchase' AND from_pond_id IS NULL) OR
                    (movement_type = 'hatch'    AND from_pond_id IS NULL)
                );
            END IF;
        END $$;
        """)

        # -------------- 触发器函数：对 hatch 完全放行 --------------
        cur.execute("""
        CREATE OR REPLACE FUNCTION check_same_frog_type_shiwa()
        RETURNS TRIGGER AS $$
        DECLARE
            from_frog INT;
            to_frog   INT;
        BEGIN
            /* 完全放行 */
            IF NEW.movement_type IN ('purchase','hatch','sale') THEN
                RETURN NEW;
            END IF;

            /* 以下仅对 transfer 检查蛙种一致性 */
            SELECT frog_type_id INTO from_frog FROM pond_shiwa WHERE id = NEW.from_pond_id;
            SELECT frog_type_id INTO to_frog   FROM pond_shiwa WHERE id = NEW.to_pond_id;

            IF from_frog IS NULL OR to_frog IS NULL THEN
                RAISE EXCEPTION '源池或目标池不存在';
            END IF;
            IF from_frog != to_frog THEN
                RAISE EXCEPTION '转池失败：源池与目标池蛙种不同（源:% → 目标:%）', from_frog, to_frog;
            END IF;

            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
        """)

        cur.execute("""
        DROP TRIGGER IF EXISTS trg_check_same_frog_type_shiwa ON stock_movement_shiwa;
        CREATE TRIGGER trg_check_same_frog_type_shiwa
        BEFORE INSERT OR UPDATE ON stock_movement_shiwa
        FOR EACH ROW EXECUTE FUNCTION check_same_frog_type_shiwa();
        """)
        st.toast("✅ 蛙种一致性触发器已升级（hatch 放行）", icon="🛡️")

        # 7. customer_shiwa
        if not table_exists(cur, 'customer_shiwa'):
            cur.execute("""
                CREATE TABLE customer_shiwa (
                    id          SERIAL PRIMARY KEY,
                    name        VARCHAR(100) NOT NULL,
                    phone       VARCHAR(50),
                    type        VARCHAR(10) CHECK (type IN ('零售','批发')),
                    created_at  TIMESTAMP WITH TIME ZONE DEFAULT NOW()
                );
            """)
            st.toast("✅ 创建客户表", icon="👤")

        # 8. sale_record_shiwa
        if not table_exists(cur, 'sale_record_shiwa'):
            cur.execute("""
                CREATE TABLE sale_record_shiwa (
                    id              SERIAL PRIMARY KEY,
                    pond_id         INT NOT NULL REFERENCES pond_shiwa(id) ON DELETE RESTRICT,
                    customer_id     INT NOT NULL REFERENCES customer_shiwa(id) ON DELETE RESTRICT,
                    sale_type       VARCHAR(10) CHECK (sale_type IN ('零售','批发')),
                    quantity        INT CHECK (quantity > 0),
                    unit_price      DECIMAL(8,2) NOT NULL,
                    total_amount    DECIMAL(10,2) GENERATED ALWAYS AS (quantity * unit_price) STORED,
                    sold_at         TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                    note            TEXT
                );
            """)
            st.toast("✅ 创建销售记录表", icon="💰")
        # 9. daily_log_shiwa（每日养殖日志）
        if not table_exists(cur, 'daily_log_shiwa'):
            cur.execute("""
                CREATE TABLE daily_log_shiwa (
                    id SERIAL PRIMARY KEY,
                    pond_id INT NOT NULL REFERENCES pond_shiwa(id) ON DELETE CASCADE,
                    log_date DATE NOT NULL,
                    water_temp DECIMAL(4,1),          -- 水温，如 22.5
                    ph_value DECIMAL(3,1),            -- pH值，如 7.0
                    light_condition VARCHAR(50),      -- 光照：散射光/直射光/阴暗 等
                    observation TEXT,                 -- 观察记录（支持多行）
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                    UNIQUE (pond_id, log_date)        -- 同一池塘同一天只允许一条日志
                );
            """)
            st.toast("✅ 创建每日养殖日志表", icon="📝")
        conn.commit()
    except Exception as e:
        st.error(f"❌ 数据库初始化失败: {e}")
        raise
    finally:
        cur.close()
        conn.close()

def get_recent_movements(limit=20):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT sm.id,
               CASE sm.movement_type
                   WHEN 'transfer' THEN '转池'
                   WHEN 'purchase' THEN '外购'
                   WHEN 'sale'     THEN '销售出库'
               END AS movement_type,
               fp.name   AS from_name,
               tp.name   AS to_name,
               sm.quantity,
               sm.description,
               sm.moved_at
        FROM stock_movement_shiwa sm
        LEFT JOIN pond_shiwa fp ON sm.from_pond_id = fp.id
        LEFT JOIN pond_shiwa tp ON sm.to_pond_id = tp.id
        ORDER BY sm.moved_at DESC
        LIMIT %s;
    """, (limit,))
    rows = cur.fetchall()
    cur.close(); conn.close()
    return rows
# -----------------------------
# 业务功能函数
# -----------------------------
def get_all_ponds():
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT p.id, p.name, pt.name AS pond_type, ft.name AS frog_type, 
               p.max_capacity, p.current_count
        FROM pond_shiwa p
        JOIN pond_type_shiwa pt ON p.pond_type_id = pt.id
        JOIN frog_type_shiwa ft ON p.frog_type_id = ft.id
        ORDER BY p.id;
    """)
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return rows


def add_feeding_record(pond_id, feed_type_id, weight_kg, unit_price, notes, fed_at=None):
    """fed_at 若留空则取 now()"""
    fed_at = fed_at or datetime.utcnow()
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO feeding_record_shiwa
        (pond_id, feed_type_id, feed_weight_kg, unit_price_at_time, notes, fed_at)
        VALUES (%s, %s, %s, %s, %s, %s);
    """, (pond_id, feed_type_id, weight_kg, unit_price, notes, fed_at))
    conn.commit()
    cur.close()
    conn.close()


def get_feed_types():
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT id, name, unit_price FROM feed_type_shiwa ORDER BY name;")
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return rows

def get_pond_types():
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT id, name FROM pond_type_shiwa ORDER BY id;")
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return rows

def get_frog_types():
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT id, name FROM frog_type_shiwa;")
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return rows

def create_pond(name, pond_type_id, frog_type_id, max_capacity, initial_count=0):
    initial_count = max(0, min(initial_count, max_capacity))
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        # 👇 先检查重名
        cur.execute("SELECT 1 FROM pond_shiwa WHERE name = %s;", (name.strip(),))
        if cur.fetchone():
            raise ValueError(f"池塘名称「{name}」已存在，请勿重复创建！")

        cur.execute("""
            INSERT INTO pond_shiwa (name, pond_type_id, frog_type_id, max_capacity, current_count)
            VALUES (%s, %s, %s, %s, %s);
        """, (name.strip(), pond_type_id, frog_type_id, max_capacity, initial_count))
        conn.commit()
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        cur.close()
        conn.close()


def delete_all_test_data():
    """⚠️ 清空所有池塘、转池记录、喂养记录，并复位序列（可选）"""
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        # 1. 先删子表
        cur.execute("TRUNCATE TABLE feeding_record_shiwa, stock_movement_shiwa RESTART IDENTITY CASCADE;")
        # 2. 再删主表
        cur.execute("TRUNCATE TABLE pond_shiwa RESTART IDENTITY CASCADE;")
        # 3. 序列号复位（如果还想保留 frog_type / pond_type / feed_type 可注释）
        # cur.execute("ALTER SEQUENCE pond_shiwa_id_seq RESTART WITH 1;")
        conn.commit()
        return True
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        cur.close()
        conn.close()
def get_pond_by_id(pond_id):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT id, name, frog_type_id, max_capacity, current_count
        FROM pond_shiwa WHERE id = %s;
    """, (pond_id,))
    row = cur.fetchone()
    cur.close()
    conn.close()
    return row  # (id, name, frog_type_id, max_capacity, current_count)

def add_stock_movement(movement_type, from_pond_id, to_pond_id, quantity, description, unit_price=None):
    """插入转池或外购记录，并自动更新池子 current_count"""
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        # 插入 movement 记录（现在支持 unit_price）
        cur.execute("""
            INSERT INTO stock_movement_shiwa 
            (movement_type, from_pond_id, to_pond_id, quantity, description, unit_price)
            VALUES (%s, %s, %s, %s, %s, %s);
        """, (movement_type, from_pond_id, to_pond_id, quantity, description, unit_price))

        # 更新目标池 current_count (+)
        cur.execute("""
            UPDATE pond_shiwa SET current_count = current_count + %s
            WHERE id = %s;
        """, (quantity, to_pond_id))

        # 如果是转池，更新源池 current_count (-)
        if from_pond_id is not None:
            cur.execute("""
                UPDATE pond_shiwa SET current_count = current_count - %s
                WHERE id = %s;
            """, (quantity, from_pond_id))

        conn.commit()
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        cur.close()
        conn.close()
def get_pond_type_id_by_name(name):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT id FROM pond_type_shiwa WHERE name = %s;", (name,))
    row = cur.fetchone()
    cur.close()
    conn.close()
    return row[0] if row else None
# 在 initialize_database() 之后、run() 之前定义（或在 run() 开头缓存到 session_state）
def get_pond_type_map():
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT id, name FROM pond_type_shiwa;")
    mapping = {row[1]: row[0] for row in cur.fetchall()}
    cur.close()
    conn.close()
    return mapping
# ---------- 客户 ----------
def get_customers():
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT id, name, phone, type FROM customer_shiwa ORDER BY id;")
    rows = cur.fetchall()
    cur.close(); conn.close()
    return rows

def add_customer(name, phone, ctype):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO customer_shiwa (name, phone, type) VALUES (%s,%s,%s) RETURNING id;",
        (name, phone, ctype)
    )
    cid = cur.fetchone()[0]
    conn.commit(); cur.close(); conn.close()
    return cid

# ---------- 销售 ----------
def do_sale(pond_id, customer_id, sale_type, qty, unit_price, note=""):
    """成交 + 扣库存 + 写 movement"""
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        # 1. 销售记录
        cur.execute("""
            INSERT INTO sale_record_shiwa (pond_id, customer_id, sale_type, quantity, unit_price, note)
            VALUES (%s,%s,%s,%s,%s,%s);
        """, (pond_id, customer_id, sale_type, qty, unit_price, note))

        # 2. 扣库存
        cur.execute(
            "UPDATE pond_shiwa SET current_count = current_count - %s WHERE id = %s;",
            (qty, pond_id)
        )

        # 3. ⭐ 把销售当成“出库”记录，movement_type = 'sale'
        cur.execute("""
            INSERT INTO stock_movement_shiwa (movement_type, from_pond_id, to_pond_id, quantity, description)
            VALUES ('sale', %s, NULL, %s, %s);
        """, (pond_id, qty, f"销售：{sale_type} {qty} 只，单价{unit_price}元"))

        conn.commit()
    except Exception as e:
        conn.rollback()
        raise
    finally:
        cur.close(); conn.close()

# ---------- 最近销售 ----------
def get_recent_sales(limit=20):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT sr.id, p.name pond, c.name customer, sr.sale_type, sr.quantity,
               sr.unit_price, sr.total_amount, sr.sold_at, sr.note
        FROM sale_record_shiwa sr
        JOIN pond_shiwa p ON p.id = sr.pond_id
        JOIN customer_shiwa c ON c.id = sr.customer_id
        ORDER BY sr.sold_at DESC
        LIMIT %s;
    """, (limit,))
    rows = cur.fetchall()
    cur.close(); conn.close()
    return rows
# -----------------------------
# ROI 分析专用函数
# -----------------------------
def get_roi_data():
    conn = get_db_connection()
    cur = conn.cursor()

    # 获取所有蛙种（确保细皮蛙、粗皮蛙都在）
    cur.execute("SELECT name FROM frog_type_shiwa ORDER BY name;")
    all_frog_types = [row[0] for row in cur.fetchall()]
    if not all_frog_types:
        all_frog_types = ["细皮蛙", "粗皮蛙"]  # 安全兜底

    # 1. 喂养成本
    cur.execute("""
        SELECT ft.name, COALESCE(SUM(fr.total_cost), 0)
        FROM frog_type_shiwa ft
        LEFT JOIN pond_shiwa p ON ft.id = p.frog_type_id
        LEFT JOIN feeding_record_shiwa fr ON p.id = fr.pond_id
        GROUP BY ft.name;
    """)
    feed_dict = {row[0]: float(row[1]) for row in cur.fetchall()}

    # 2. 外购成本（使用 unit_price，若为 NULL 则按 20.0 估算）
    cur.execute("""
        SELECT ft.name, 
               COALESCE(SUM(sm.quantity * COALESCE(sm.unit_price, 20.0)), 0) AS total_cost
        FROM frog_type_shiwa ft
        LEFT JOIN pond_shiwa p ON ft.id = p.frog_type_id
        LEFT JOIN stock_movement_shiwa sm 
            ON p.id = sm.to_pond_id AND sm.movement_type = 'purchase'
        GROUP BY ft.name;
    """)
    purchase_dict = {row[0]: float(row[1]) for row in cur.fetchall()}

    # 3. 销售收入
    cur.execute("""
        SELECT ft.name, COALESCE(SUM(sr.total_amount), 0)
        FROM frog_type_shiwa ft
        LEFT JOIN pond_shiwa p ON ft.id = p.frog_type_id
        LEFT JOIN sale_record_shiwa sr ON p.id = sr.pond_id
        GROUP BY ft.name;
    """)
    sales_dict = {row[0]: float(row[1]) for row in cur.fetchall()}

    cur.close()
    conn.close()

    # 构建结果（确保所有蛙种都有行）
    result = []
    for frog_type in all_frog_types:
        feed = feed_dict.get(frog_type, 0.0)
        purchase = purchase_dict.get(frog_type, 0.0)
        total_cost = feed + purchase
        income = sales_dict.get(frog_type, 0.0)
        profit = income - total_cost
        roi = (profit / total_cost * 100) if total_cost > 0 else 0.0

        result.append({
            "蛙种": frog_type,
            "喂养成本 (¥)": round(feed, 2),
            "外购成本 (¥)": round(purchase, 2),
            "总成本 (¥)": round(total_cost, 2),
            "销售收入 (¥)": round(income, 2),
            "净利润 (¥)": round(profit, 2),
            "ROI (%)": round(roi, 2)
        })

    return result
def get_pond_roi_details():
    """获取每个池塘的喂养、外购、销售明细，用于 ROI 明细分析"""
    conn = get_db_connection()
    cur = conn.cursor()

    # 1. 喂养明细
    cur.execute("""
        SELECT 
            p.name AS pond_name,
            ft.name AS frog_type,
            fr.feed_weight_kg,
            ftype.name AS feed_type,
            fr.unit_price_at_time,
            fr.total_cost,
            fr.fed_at
        FROM feeding_record_shiwa fr
        JOIN pond_shiwa p ON fr.pond_id = p.id
        JOIN frog_type_shiwa ft ON p.frog_type_id = ft.id
        JOIN feed_type_shiwa ftype ON fr.feed_type_id = ftype.id
        ORDER BY fr.fed_at DESC;
    """)
    feedings = cur.fetchall()

    # 2. 外购明细（movement_type = 'purchase'）
    cur.execute("""
        SELECT 
            p.name AS pond_name,
            ft.name AS frog_type,
            sm.quantity,
            sm.unit_price,
            (sm.quantity * COALESCE(sm.unit_price, 20.0)) AS total_cost,
            sm.moved_at
        FROM stock_movement_shiwa sm
        JOIN pond_shiwa p ON sm.to_pond_id = p.id
        JOIN frog_type_shiwa ft ON p.frog_type_id = ft.id
        WHERE sm.movement_type = 'purchase'
        ORDER BY sm.moved_at DESC;
    """)
    purchases = cur.fetchall()

    # 3. 销售明细
    cur.execute("""
        SELECT 
            p.name AS pond_name,
            ft.name AS frog_type,
            sr.quantity,
            sr.unit_price,
            sr.total_amount,
            sr.sold_at,
            c.name AS customer_name
        FROM sale_record_shiwa sr
        JOIN pond_shiwa p ON sr.pond_id = p.id
        JOIN frog_type_shiwa ft ON p.frog_type_id = ft.id
        JOIN customer_shiwa c ON sr.customer_id = c.id
        ORDER BY sr.sold_at DESC;
    """)
    sales = cur.fetchall()

    cur.close()
    conn.close()

    return feedings, purchases, sales
def add_daily_log(pond_id, log_date, water_temp, ph_value, light_condition, observation):
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("""
            INSERT INTO daily_log_shiwa 
            (pond_id, log_date, water_temp, ph_value, light_condition, observation)
            VALUES (%s, %s, %s, %s, %s, %s)
            ON CONFLICT (pond_id, log_date)
            DO UPDATE SET
                water_temp = EXCLUDED.water_temp,
                ph_value = EXCLUDED.ph_value,
                light_condition = EXCLUDED.light_condition,
                observation = EXCLUDED.observation,
                updated_at = NOW();
        """, (pond_id, log_date, water_temp, ph_value, light_condition, observation))
        conn.commit()
        st.success("✅ 每日日志已保存！")
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        cur.close()
        conn.close()

def get_daily_logs(limit=50):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT dl.log_date, p.name, dl.water_temp, dl.ph_value, dl.light_condition, dl.observation
        FROM daily_log_shiwa dl
        JOIN pond_shiwa p ON dl.pond_id = p.id
        ORDER BY dl.log_date DESC, dl.created_at DESC
        LIMIT %s;
    """, (limit,))
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return rows
# ================== ② AI 问答专用函数 ==================
def get_ai_client():
    """统一拿到 DashScope 兼容 OpenAI 客户端"""
    api_key = os.getenv("DASHSCOPE_API_KEY")
    if not api_key:
        raise RuntimeError("请在 .env 里配置 DASHSCOPE_API_KEY")
    return OpenAI(api_key=api_key,
                  base_url="https://dashscope.aliyuncs.com/compatible-mode/v1")

@st.cache_data(show_spinner=False)
def get_db_schema_for_ai():
    """一次性把 schema 抓回来给 AI，只抓表名-列名-类型，不做数据"""
    engine = create_engine(DATABASE_URL)
    inspector = inspect(engine)
    schema = {}
    for t in inspector.get_table_names():
        schema[t] = [{"col": c["name"], "type": str(c["type"])}
                     for c in inspector.get_columns(t)]
    return schema


def execute_safe_select(sql: str) -> pd.DataFrame:
    """只允许 SELECT，返回 DataFrame"""
    sql = sql.strip()
    if not sql.lower().startswith("select"):
        raise ValueError("仅允许 SELECT 查询")
    engine = create_engine(DATABASE_URL)
    with engine.connect() as conn:
        return pd.read_sql(text(sql), conn)


def ai_ask_database(question: str):
    """两阶段：生成 SQL -> 自然语言回答"""
    client = get_ai_client()
    schema = get_db_schema_for_ai()

    tools = [{
        "type": "function",
        "function": {
            "name": "execute_sql_query",
            "description": "生成安全的 SELECT 查询",
            "parameters": {
                "type": "object",
                "properties": {
                    "sql": {"type": "string"},
                    "explanation": {"type": "string"}
                },
                "required": ["sql", "explanation"]
            }
        }
    }]

    sys_prompt = f"""
你是石蛙养殖场数据分析师，数据库 schema 如下（仅使用存在的表和字段）：
{json.dumps(schema, ensure_ascii=False, indent=2)}

必须调用 execute_sql_query 函数，规则：
- 只生成 SELECT
- 表名/字段严格与上面一致
- 用中文写 explanation
"""

    response = client.chat.completions.create(
        model="qwen-plus",
        messages=[{"role": "system", "content": sys_prompt},
                  {"role": "user", "content": question}],
        tools=tools,
        tool_choice={"type": "function", "function": {"name": "execute_sql_query"}},
        temperature=0.1
    )

    args = json.loads(response.choices[0].message.tool_calls[0].function.arguments)
    sql = args["sql"]
    df = execute_safe_select(sql)

    # 第二阶段：用数据回答用户
    second = client.chat.completions.create(
        model="qwen-plus",
        messages=[
            {"role": "system", "content": "你是石蛙养殖场场长，用简洁中文直接回答用户问题，不要提 SQL 或技术词汇。"},
            {"role": "user", "content": f"用户问题：{question}\n查询结果：\n{df.head(15).to_string(index=False)}"}
        ],
        temperature=0.3
    )
    return second.choices[0].message.content.strip(), sql, df
# =======================================================
# ----------------------------- ① 池子分组 -----------------------------
def group_ponds_by_type(pond_dict):
        from collections import defaultdict
        grouped = defaultdict(list)
        for pid, info in pond_dict.items():
            grouped[info["pond_type"]].append(
                (pid, f"{info['name']}  （当前 {info['current_count']} / {info['max_capacity']}）")
            )
        return grouped


    # ----------------------------- ② 两级选择组件 -----------------------------
def pond_selector(label, candidate_dict, grouped, key):
        """两步选池：先类型 → 再具体池子"""
        col1, col2 = st.columns([1, 2])
        with col1:
            type_pick = st.selectbox(f"{label} · 类型", options=list(grouped.keys()), key=f"{key}_type")
        with col2:
            pid_pick = st.selectbox(f"{label} · 池子", options=[p[0] for p in grouped[type_pick]],
                                    format_func=lambda x: next(p[1] for p in grouped[type_pick] if p[0] == x),
                                    key=f"{key}_pond")
        return pid_pick
# -----------------------------
# 主应用入口
# -----------------------------
def run():
    st.set_page_config(page_title="石蛙养殖场管理系统", layout="wide")
    
    # 🚀 自动初始化数据库（只在首次加载时执行一次）
    if "db_initialized" not in st.session_state:
        initialize_database()
        st.session_state.db_initialized = True

    st.title("🐸 石蛙养殖场管理系统")
    st.markdown("---")

    # 创建三个 Tab
    tab1, tab2, tab3, tab4, tab5, tab6, tab7 = st.tabs(
    ["📊 池塘总览", "🍽️ 喂养日志", "➕ 池塘创建", "🔄 孵转池与外购", 
     "🪱 饲料类型", "💰 销售记录", "📈 投资回报（ROI）"]
)

        # Tab 1: 池塘总览（表格 + 图表）
    with tab1:
                                # ================== ③ 新增：AI 问答子模块 ==================
        st.markdown("---")
        st.subheader("🤖 AI 养殖场问答")
        st.caption("例：「现在全场共有多少只蛙？”、“哪类池塘占用率最高？」")
        if "ai_chat_history" not in st.session_state:
            st.session_state.ai_chat_history = []

        # 显示历史
        for q, a in st.session_state.ai_chat_history:
            with st.chat_message("user"):
                st.write(q)
            with st.chat_message("assistant"):
                st.write(a)

        # 用户输入
        if q := st.chat_input("输入你的问题，按回车"):
            with st.chat_message("user"):
                st.write(q)
            with st.chat_message("assistant"):
                with st.spinner("AI 正在查询数据库..."):
                    try:
                        answer, sql, df = ai_ask_database(q)
                        st.write(answer)
                        with st.expander("🔍 技术详情（点击展开）"):
                            st.code(sql, language="sql")
                            st.dataframe(df.head(20), use_container_width=True)
                        st.session_state.ai_chat_history.append((q, answer))
                    except Exception as e:
                        st.error(f"查询失败：{e}")

        if st.button("🗑️ 清空对话"):
            st.session_state.ai_chat_history.clear()
            st.rerun()
        # =======================================================
        st.subheader("📊 所有池塘状态")
        ponds = get_all_ponds()
        
        if not ponds:
            st.warning("暂无池塘。请在「池塘创建」Tab 中添加，或点击「一键初始化示例数据」。")
        else:
            # 转为 DataFrame 便于展示和绘图
            import pandas as pd
            df = pd.DataFrame(
                ponds,
                columns=["ID", "名称", "池类型", "蛙种", "最大容量", "当前数量"]
            )
            df["占用率 (%)"] = (df["当前数量"] / df["最大容量"] * 100).round(1)
            df["占用率 (%)"] = df["占用率 (%)"].clip(upper=100)  # 防止超容显示 >100

            # 可选：筛选器
            col1, col2 = st.columns(2)
            with col1:
                frog_filter = st.multiselect(
                    "按蛙种筛选",
                    options=df["蛙种"].unique(),
                    default=df["蛙种"].unique()
                )
            with col2:
                type_filter = st.multiselect(
                    "按池类型筛选",
                    options=df["池类型"].unique(),
                    default=df["池类型"].unique()
                )

            # 应用筛选
            filtered_df = df[
                (df["蛙种"].isin(frog_filter)) &
                (df["池类型"].isin(type_filter))
            ].copy()

            if filtered_df.empty:
                st.info("没有匹配的池塘。")
            else:
                # === 表格展示 ===
                st.dataframe(
                    filtered_df[["名称", "池类型", "蛙种", "当前数量", "最大容量", "占用率 (%)"]],
                    use_container_width=True,
                    hide_index=True
                )

                # === 图表展示 ===
                st.markdown("### 📈 池塘容量占用率")
                chart_data = filtered_df.set_index("名称")["占用率 (%)"]
                st.bar_chart(chart_data, height=400)


    # Tab 2: 喂养记录（录入 + 总览）
    with tab2:
        st.subheader("🍽️ 喂养日志")
        ponds = get_all_ponds()
        feed_types = get_feed_types()

        if not ponds:
            st.error("请先创建池塘！")
        elif not feed_types:
            st.error("🪱 尚未配置任何饲料类型，请切换到【饲料类型】Tab 添加至少一种饲料。")
        else:
            # —— 录入区域 ——
            with st.form("feeding_form"):
                c1, c2 = st.columns(2)
                with c1:
                    pond_dict = {p[0]: {
                        "name": p[1], "pond_type": p[2],
                        "current_count": p[5], "max_capacity": p[4]
                    } for p in ponds}
                    grouped = group_ponds_by_type(pond_dict)
                    pond_id = pond_selector("投喂池塘", pond_dict, grouped, key="feed")

                with c2:
                    feed_id = st.selectbox(
                        "饲料类型",
                        options=[f[0] for f in feed_types],
                        format_func=lambda x: f"{next(f[1] for f in feed_types if f[0] == x)} (¥{next(f[2] for f in feed_types if f[0] == x)}/kg)"
                    )
                weight = st.number_input("喂养重量 (kg)", min_value=0.1, step=0.1)

                # 日期+时段
                col_d, col_t = st.columns(2)
                with col_d:
                    feed_date = st.date_input("投喂日期", value=datetime.today())
                with col_t:
                    ampm = st.selectbox("时段", ["上午", "下午"])

                                # ---- 快捷备注 ----
                quick_feed_note = st.selectbox("快捷备注", COMMON_REMARKS["喂养备注"], key="quick_feed")
                notes = st.text_area("备注（可选）", value=quick_feed_note)
                submitted = st.form_submit_button("✅ 提交喂养记录")

                if submitted:
                    unit_price = next(f[2] for f in feed_types if f[0] == feed_id)
                    feed_dt = datetime.combine(feed_date, time(10 if ampm == "上午" else 15, 0))
                    add_feeding_record(pond_id, feed_id, weight, float(unit_price), notes, feed_dt)
                    st.success("✅ 喂养记录已保存！")
                    st.rerun()

                st.markdown("---")
                st.subheader("📊 喂食总览")
                conn = get_db_connection()
                cur = conn.cursor()
                cur.execute("""
                    SELECT
                        DATE(fr.fed_at AT TIME ZONE 'UTC' AT TIME ZONE '+08') AS 日期,
                        CASE WHEN EXTRACT(HOUR FROM fr.fed_at AT TIME ZONE 'UTC' AT TIME ZONE '+08') < 12
                            THEN '上午'
                            ELSE '下午'
                        END AS 时段,
                        ft.name         AS 蛙种,
                        ftype.name      AS 饲料,
                        SUM(fr.feed_weight_kg) AS 总重量kg,
                        SUM(fr.total_cost)     AS 总成本
                    FROM feeding_record_shiwa fr
                    JOIN pond_shiwa p   ON fr.pond_id  = p.id
                    JOIN frog_type_shiwa ft ON p.frog_type_id = ft.id
                    JOIN feed_type_shiwa ftype ON fr.feed_type_id = ftype.id
                    GROUP BY 日期, 时段, ft.name, ftype.name
                    ORDER BY 日期 DESC, 时段;
                """)
                rows = cur.fetchall()
                cur.close(); conn.close()

                if rows:
                    import pandas as pd
                    df = pd.DataFrame(rows, columns=["日期", "时段", "蛙种", "饲料", "总重量kg", "总成本"])
                    st.dataframe(df, use_container_width=True, hide_index=True)
                else:
                    st.info("暂无喂养记录")
        st.markdown("---")
        st.subheader("📝 每日养殖日志（水温 / pH / 观察等）")

        with st.form("daily_log_form"):
            c1, c2 = st.columns(2)
            with c1:
                pond_dict_dl = {p[0]: {
                    "name": p[1], "pond_type": p[2],
                    "current_count": p[5], "max_capacity": p[4]
                } for p in ponds}
                grouped_dl = group_ponds_by_type(pond_dict_dl)
                dl_pond_id = pond_selector("日志池塘", pond_dict_dl, grouped_dl, key="daily")
            with c2:
                dl_date = st.date_input("日志日期", value=datetime.today(), key="dl_date")

            col_temp, col_ph, col_light = st.columns(3)
            with col_temp:
                water_temp = st.number_input("水温 (℃)", min_value=0.0, max_value=40.0, step=0.5, value=22.0)
            with col_ph:
                ph_value = st.number_input("pH 值", min_value=0.0, max_value=14.0, step=0.1, value=7.0)
            with col_light:
                light_condition = st.selectbox(
                    "光照条件",
                    options=["散射光", "直射光", "阴暗", "人工补光", "其他"],
                    index=0
                )
                if light_condition == "其他":
                    light_condition = st.text_input("自定义光照", "请填写")

                            # ---- 快捷观察 ----
            quick_observe = st.selectbox("快捷观察", COMMON_REMARKS["每日观察"], key="quick_observe")
            observation = st.text_area("观察记录（可记录卵块、行为、异常等）", value=quick_observe, height=120)

            dl_submitted = st.form_submit_button("✅ 保存每日日志")
            if dl_submitted:
                add_daily_log(
                    pond_id=dl_pond_id,
                    log_date=dl_date,
                    water_temp=water_temp,
                    ph_value=ph_value,
                    light_condition=light_condition,
                    observation=observation.strip()
                )
                st.rerun()
        st.markdown("### 📖 历史每日日志")
        dl_records = get_daily_logs(30)
        if dl_records:
            import pandas as pd
            df_dl = pd.DataFrame(dl_records, columns=["日期", "池塘", "水温(℃)", "pH", "光照", "观察记录"])
            st.dataframe(df_dl, use_container_width=True, hide_index=True)
        else:
            st.info("暂无每日日志记录")

    with tab3:
        st.subheader("创建新池塘")
        pond_types = get_pond_types()
        frog_types = get_frog_types()

        with st.form("pond_create_form"):
            name = st.text_input("池塘名称", placeholder="例如：细皮蛙孵化池-001")
            pond_type_id = st.selectbox(
                "池塘类型",
                options=[pt[0] for pt in pond_types],
                format_func=lambda x: next(pt[1] for pt in pond_types if pt[0] == x)
            )
            frog_type_id = st.selectbox(
                "蛙种类型",
                options=[ft[0] for ft in frog_types],
                format_func=lambda x: next(ft[1] for ft in frog_types if ft[0] == x)
            )
            max_cap = st.number_input(
                "最大容量（可自由设置，建议根据池塘实际面积填写）",
                min_value=1,
                value=500,
                step=10,
                format="%d"
            )
            initial = st.number_input(
                "初始数量（不能超过最大容量）",
                min_value=0,
                value=0,
                step=1,
                format="%d"
            )

            submitted = st.form_submit_button("✅ 创建池塘")
            if submitted:
                if not name.strip():
                    st.error("请输入池塘名称！")
                else:
                    try:
                        create_pond(name.strip(), pond_type_id, frog_type_id, int(max_cap), int(initial))
                        st.success(f"✅ 池塘「{name}」创建成功！容量：{max_cap}，初始数量：{initial}")
                        st.rerun()
                    except Exception as e:
                        if "unique_pond_name" in str(e) or "已存在" in str(e):
                            st.error(f"❌ 创建失败：池塘名称「{name}」已存在，请换一个名称！")
                        else:
                            st.error(f"❌ 创建失败: {e}")

        # ================= 新增：实时展示已创建池子 =================
        st.markdown("---")
        st.subheader("📋 已创建的池塘")
        ponds_now = get_all_ponds()          # 复用已有函数，实时查库
        if not ponds_now:
            st.info("暂无池塘，快去创建第一个吧！")
        else:
            import pandas as pd
            df = pd.DataFrame(
                ponds_now,
                columns=["ID", "名称", "池类型", "蛙种", "最大容量", "当前数量"]
            )
            # 让最新创建的排在最上面
            df = df.iloc[::-1].reset_index(drop=True)
            st.dataframe(df, use_container_width=True, hide_index=True)
        # ==========================================================

        st.markdown("---")
        st.subheader("⚠️ 危险区域：清空测试数据")
        st.caption("**一键删除所有池塘、转池、喂养记录！操作不可恢复**")
        if st.checkbox("我已确认要清空全部测试数据"):
            if st.button("🗑️ 一键清空所有测试数据", type="secondary"):
                try:
                    delete_all_test_data()
                    st.success("✅ 所有测试数据已清空！")
                    st.rerun()
                except Exception as e:
                    st.error(f"❌ 清空失败: {e}")

   
    # ----------------------------- Tab 4: 转池 · 外购 · 孵化 -----------------------------
    with tab4:
        st.subheader("🔄 转池 / 外购 / 孵化操作")
        operation = st.radio("操作类型", ["转池", "外购", "孵化"], horizontal=True, key="op_type")

        ponds = get_all_ponds()
        if not ponds:
            st.warning("请先创建至少一个池塘！")
            # ✅ 不用 st.stop()，直接跳过本 Tab 剩余内容
        else:
            pond_id_to_info = {p[0]: {
                "name": p[1], "pond_type": p[2].strip(),
                "frog_type": p[3], "max_capacity": p[4], "current_count": p[5]
            } for p in ponds}

            grouped = group_ponds_by_type(pond_id_to_info)

            # 默认值
            from_pond_id   = None
            to_pond_id     = None
            purchase_price = None

            # ① 外购 ----------------------------------------------------------
            if operation == "外购":
                to_pond_id = pond_selector("目标池塘", pond_id_to_info, grouped, "purchase")
                purchase_price = st.number_input(
                    "外购单价 (元/只)",
                    min_value=0.1, value=20.0, step=1.0, format="%.2f",
                    help="请输入每只蛙的采购价格"
                )

            # ② 孵化 ----------------------------------------------------------
            elif operation == "孵化":
                hatch_grouped = {k: v for k, v in grouped.items() if k == "孵化池"}
                if not hatch_grouped:
                    st.error("❌ 请先至少创建一个‘孵化池’")
                else:
                    to_pond_id = pond_selector("孵化池", pond_id_to_info, hatch_grouped, "hatch")
                    purchase_price = None  # 孵化无成本

            # ③ 转池 ----------------------------------------------------------
            else:  # operation == "转池"
                src_grouped = {k: v for k, v in grouped.items() if k in TRANSFER_PATH_RULES}
                if not src_grouped:
                    st.error("❌ 无可用的转出池类型")
                else:
                    from_pond_id = pond_selector("源池塘（转出）", pond_id_to_info, src_grouped, "transfer_src")

                    live_info = pond_id_to_info[from_pond_id]
                    allowed = TRANSFER_PATH_RULES.get(live_info["pond_type"], [])
                    tgt_grouped = {k: v for k, v in grouped.items() if k in allowed and v}
                    if not tgt_grouped:
                        st.error("❌ 无合法目标池")
                    else:
                        to_pond_id = pond_selector("目标池塘（转入）", pond_id_to_info, tgt_grouped, "transfer_tgt")
                        purchase_price = None

            # 公共输入（只在有目标池时才显示）
            if to_pond_id is not None:
                quantity = st.number_input("数量", min_value=1, value=1000, step=50)
                            # ---- 快捷描述 ----
                quick_desc = st.selectbox("快捷描述", COMMON_REMARKS["操作描述"], key="quick_desc")
                description = st.text_input("操作描述", value=quick_desc, placeholder="如：产卵转出 / 外购幼蛙 / 自孵蝌蚪")

                if st.button(f"✅ 执行{operation}", type="primary"):
                    try:
                        to_pond = get_pond_by_id(to_pond_id)
                        if to_pond[4] + quantity > to_pond[3]:
                            st.error(f"❌ 目标池「{to_pond[1]}」容量不足！当前 {to_pond[4]}/{to_pond[3]}，无法容纳 {quantity} 只。")
                        elif operation == "转池" and from_pond_id is not None:
                            from_pond = get_pond_by_id(from_pond_id)
                            if from_pond[4] < quantity:
                                st.error(f"❌ 源池「{from_pond[1]}」数量不足！当前只有 {from_pond[4]} 只。")
                            else:
                                movement_type = 'transfer'
                                add_stock_movement(
                                    movement_type=movement_type,
                                    from_pond_id=from_pond_id,
                                    to_pond_id=to_pond_id,
                                    quantity=quantity,
                                    description=description or f"{operation} {quantity} 只",
                                    unit_price=purchase_price
                                )
                                st.success(f"✅ {operation}成功！")
                                st.rerun()
                        else:
                            movement_type = {'外购':'purchase', '孵化':'hatch'}[operation]
                            add_stock_movement(
                                movement_type=movement_type,
                                from_pond_id=None,
                                to_pond_id=to_pond_id,
                                quantity=quantity,
                                description=description or f"{operation} {quantity} 只",
                                unit_price=purchase_price
                            )
                            st.success(f"✅ {operation}成功！")
                            st.rerun()

                    except Exception as e:
                        st.error(f"❌ 操作失败: {e}")

                # 最近记录
                st.markdown("---")
                st.subheader("📋 最近转池 / 外购 / 孵化记录")
                records = get_recent_movements(15)
                if not records:
                    st.info("暂无操作记录")
                else:
                    import pandas as pd
                    df_log = pd.DataFrame(records, columns=["ID", "类型", "源池", "目标池", "数量", "描述", "时间"])
                    st.dataframe(df_log, use_container_width=True, hide_index=True)
                    csv = df_log.to_csv(index=False)
                    st.download_button(
                        label="📥 导出 CSV",
                        data=csv,
                        file_name=f"movement_log_{pd.Timestamp.now().strftime('%Y%m%d_%H%M%S')}.csv",
                        mime="text/csv"
                    )
                    if st.button("🔄 刷新列表"):
                        st.rerun()
                        # ----------------------------- Tab 5: 饲料类型 ---------------------------
    with tab5:
        st.subheader("🪱 饲料类型管理")
        conn = get_db_connection()
        cur = conn.cursor()

        # 1. 已有列表
        cur.execute("SELECT id, name, unit_price FROM feed_type_shiwa ORDER BY id;")
        feed_rows = cur.fetchall()
        if feed_rows:
            df_feed = pd.DataFrame(feed_rows, columns=["ID", "名称", "单价(¥/kg)"])
            st.dataframe(df_feed, use_container_width=True, hide_index=True)
        else:
            st.info("暂无饲料类型，请添加。")

        # 2. 新增/修改
        with st.form("feed_form", clear_on_submit=True):
            c1, c2 = st.columns(2)
            with c1:
                name = st.text_input("饲料名称", placeholder="如：红虫")
            with c2:
                price = st.number_input("单价 (¥/kg)", min_value=0.0, step=1.0, value=20.0)
            submitted = st.form_submit_button("✅ 添加/更新")
            if submitted:
                # 若同名则 ON CONFLICT 更新单价
                cur.execute("""
                    INSERT INTO feed_type_shiwa (name, unit_price)
                    VALUES (%s, %s)
                    ON CONFLICT (name)
                    DO UPDATE SET unit_price = EXCLUDED.unit_price;
                """, (name, price))
                conn.commit()
                st.success(f"✅ 饲料「{name}」已保存！")
                st.rerun()

        # 3. 删除
        if feed_rows:
            with st.form("del_feed"):
                to_del = st.selectbox("删除饲料",
                                    options=[r[0] for r in feed_rows],
                                    format_func=lambda x:
                                    next(r[1] for r in feed_rows if r[0] == x))
                if st.form_submit_button("🗑️ 删除", type="secondary"):
                    cur.execute("DELETE FROM feed_type_shiwa WHERE id = %s;", (to_del,))
                    conn.commit()
                    st.success("已删除！")
                    st.rerun()
        cur.close()
        conn.close()
        # ----------------------------- Tab 6: 销售记录 ---------------------------
    # ----------------------------- Tab 6: 销售记录 ---------------------------
    with tab6:
        st.subheader("💰 销售记录")
        ponds = get_all_ponds()
        if not ponds:
            st.warning("暂无可销售池塘")
            st.stop()

        # ---- 可售池过滤 ----
        sale_src = ["养殖池", "商品蛙池", "三年蛙池", "四年蛙池", "五年蛙池", "六年蛙池", "种蛙池"]
        cand = [p for p in ponds if p[2] in sale_src and p[5] > 0]
        if not cand:
            st.info("没有可销售的蛙")
            st.stop()

        # ========================
        # ✅ 新增：快速选择可销售池塘（放在客户选择之前）
        # ========================
        st.markdown("#### 🔍 快速选择可销售池塘")
        
        # 构建选项列表
        pond_options = []
        pond_id_map = {}
        for p in cand:
            pid, name, pond_type, frog_type, max_cap, current = p
            label = f"[{frog_type}] {name}（{pond_type}｜现存 {current} 只）"
            pond_options.append(label)
            pond_id_map[label] = pid

        # 使用 session_state 记住选择
        if "selected_sale_pond_label" not in st.session_state:
            st.session_state.selected_sale_pond_label = pond_options[0] if pond_options else None

        selected_label = st.selectbox(
            "选择池塘快速预览",
            options=pond_options,
            index=pond_options.index(st.session_state.selected_sale_pond_label) if st.session_state.selected_sale_pond_label in pond_options else 0,
            key="quick_pond_selector"
        )
        st.session_state.selected_sale_pond_label = selected_label

        # 显示所选池塘详情（可选）
        if selected_label:
            pid = pond_id_map[selected_label]
            info = next(p for p in cand if p[0] == pid)
            st.info(f"已选：{info[1]}｜类型：{info[2]}｜蛙种：{info[3]}｜当前库存：{info[5]} 只")

        st.markdown("---")

        # ---- 客户区 ----
        st.markdown("#### 1. 选择客户")
        customers = get_customers() or []
        c1, c2 = st.columns([3, 1])
        with c1:
            cust_opt = ["新建客户"] + [f"{c[1]} ({c[3]})" for c in customers]
            cust_sel = st.selectbox("客户", cust_opt, key="sale_customer")
        new_cust = cust_sel == "新建客户"
        with c2:
            sale_type = st.radio("销售类型", ["零售", "批发"], horizontal=True, key="sale_type")

        customer_id = None

        if new_cust:
            with st.form("new_customer"):
                name = st.text_input("客户姓名")
                phone = st.text_input("电话", max_chars=20)
                if st.form_submit_button("添加客户"):
                    if not name.strip():
                        st.error("请输入姓名")
                        # ✅ 不用 st.stop()，表单提交失败就停在这里
                    else:
                        customer_id = add_customer(name.strip(), phone, sale_type)
                        st.success(f"✅ 客户 {name} 已创建")
                        st.rerun()  # 重新加载以显示新客户
        else:
            if customers:
                customer_id = customers[cust_opt.index(cust_sel) - 1][0]
            # else: customer_id 保持 None

        # ✅ 统一判断：是否有有效客户 ID
        if customer_id is None:
            st.info("请选择现有客户或创建新客户以继续")
            # 不渲染销售表单和客户信息
        else:
            # --- 显示客户信息（简洁版）---
            conn = get_db_connection()
            cur = conn.cursor()
            cur.execute("SELECT name, phone, type FROM customer_shiwa WHERE id = %s;", (customer_id,))
            cust_detail = cur.fetchone()
            cur.close()
            conn.close()
            
            if cust_detail:
                name, phone, ctype = cust_detail
                phone_str = f"｜电话：{phone}" if phone else ""
                st.info(f"已选客户：{name}（{ctype}）{phone_str}")
            
            # --- 销售表单将在后面渲染 ---

        # ✅ 新增：简洁显示客户信息（仿照池塘快速预览）
        # 获取客户详情
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT name, phone, type FROM customer_shiwa WHERE id = %s;", (customer_id,))
        cust_detail = cur.fetchone()
        cur.close()
        conn.close()

        if cust_detail:
            name, phone, ctype = cust_detail
            phone_str = f"｜电话：{phone}" if phone else ""
            st.info(f"已选客户：{name}（{ctype}）{phone_str}")

        # ---- 销售表单 ----
        st.markdown("#### 2. 销售明细")
        with st.form("sale_form"):
            # 安全 format_func
            def pond_label(pid):
                for c in cand:
                    if c[0] == pid:
                        return f"{c[1]}  ({c[2]}-{c[3]}  现存{c[5]})"
                return "未知池"

            # ✅ 自动预选用户在上方选择的池塘
            pre_selected_pid = pond_id_map.get(st.session_state.selected_sale_pond_label)
            default_index = 0
            if pre_selected_pid and pre_selected_pid in [c[0] for c in cand]:
                try:
                    default_index = [c[0] for c in cand].index(pre_selected_pid)
                except ValueError:
                    default_index = 0

            pond_id = st.selectbox(
                "选择池塘",
                options=[c[0] for c in cand],
                format_func=pond_label,
                index=default_index,
                key="sale_pond"
            )
            pond_info = next(c for c in cand if c[0] == pond_id)
            max_q = pond_info[5]
            qty = st.number_input("销售数量", min_value=1, max_value=max_q, step=1)
            default_price = 60.0 if sale_type == "零售" else 45.0
            price = st.number_input("单价 (元/只)", min_value=0.1, value=default_price, step=5.0)
            note = st.text_area("备注")
            if st.form_submit_button("✅ 确认销售", type="primary"):
                do_sale(pond_id, customer_id, sale_type, qty, price, note)
                st.success(f"✅ 销售成功：{qty} 只 × {price} = {qty*price:.2f} 元")
                st.rerun()

        # ---- 最近销售 ----
        st.markdown("#### 3. 最近销售记录")
        recent_sales = get_recent_sales(15)
        if recent_sales:
            df = pd.DataFrame(
                recent_sales,
                columns=["ID", "池塘", "客户", "类型", "数量", "单价", "总金额", "时间", "备注"]
            )
            st.dataframe(df, use_container_width=True, hide_index=True)
            csv = df.to_csv(index=False)
            st.download_button("📥 导出 CSV", csv, file_name=f"sale_{pd.Timestamp.now():%Y%m%d_%H%M%S}.csv")
        else:
            st.info("暂无销售记录")
    # ----------------------------- Tab 7: 投资回报 ROI -----------------------------
    with tab7:
        st.subheader("📈 蛙种投资回报率（ROI）分析")
        st.caption("ROI = (销售收入 - 总成本) / 总成本 × 100% | 外购成本按 20 元/只估算（若未填单价）")

        # ========== 汇总视图 ==========
        roi_data = get_roi_data()
        if roi_data:
            import pandas as pd
            df_roi = pd.DataFrame(roi_data)
            st.dataframe(
                df_roi.style.format({
                    "喂养成本 (¥)": "¥{:.2f}",
                    "外购成本 (¥)": "¥{:.2f}",
                    "总成本 (¥)": "¥{:.2f}",
                    "销售收入 (¥)": "¥{:.2f}",
                    "净利润 (¥)": "¥{:.2f}",
                    "ROI (%)": "{:.2f}%"
                }),
                use_container_width=True,
                hide_index=True
            )

            # ROI 柱状图
            st.markdown("### 📊 ROI 对比")
            chart_df = df_roi.set_index("蛙种")["ROI (%)"]
            st.bar_chart(chart_df, height=300)

            # 导出按钮
            csv = df_roi.to_csv(index=False)
            st.download_button(
                "📥 导出汇总报告 (CSV)",
                csv,
                file_name=f"shiwa_roi_summary_{pd.Timestamp.now().strftime('%Y%m%d')}.csv"
            )
        else:
            st.info("暂无 ROI 数据")

        st.markdown("---")
        st.subheader("🔍 ROI 明细：按池塘查看成本与收入")

        # ========== 明细视图 ==========
        feedings, purchases, sales = get_pond_roi_details()
        
        if not (feedings or purchases or sales):
            st.info("暂无喂养、外购或销售明细记录")
        else:
            # 按池塘分组
            from collections import defaultdict
            pond_details = defaultdict(lambda: {"feedings": [], "purchases": [], "sales": []})

            # 喂养
            for row in feedings:
                pond_name = row[0]
                pond_details[pond_name]["feedings"].append({
                    "feed_type": row[3],
                    "weight_kg": row[2],
                    "unit_price": row[4],
                    "total_cost": row[5],
                    "time": row[6]
                })

            # 外购
            for row in purchases:
                pond_name = row[0]
                pond_details[pond_name]["purchases"].append({
                    "quantity": row[2],
                    "unit_price": row[3] or 20.0,
                    "total_cost": row[4],
                    "time": row[5]
                })

            # 销售
            for row in sales:
                pond_name = row[0]
                pond_details[pond_name]["sales"].append({
                    "quantity": row[2],
                    "unit_price": row[3],
                    "total_amount": row[4],
                    "customer": row[6],
                    "time": row[5]
                })

            # 显示每个池塘
            for pond_name, details in pond_details.items():
                with st.expander(f"📍 {pond_name}", expanded=False):
                    frog_type = None
                    if details["feedings"]:
                        frog_type = next(iter(details["feedings"]))  # 无法直接取，改用其他方式
                    # 实际上我们可以在查询时带上 frog_type，但为简化，此处略过

                    # 喂养记录
                    if details["feedings"]:
                        st.markdown("**🍽️ 喂养记录**")
                        for f in details["feedings"]:
                            st.caption(f"- {f['feed_type']} {f['weight_kg']}kg × ¥{f['unit_price']}/kg = **¥{f['total_cost']:.2f}** ({f['time'].strftime('%Y-%m-%d')})")

                    # 外购记录
                    if details["purchases"]:
                        st.markdown("**📦 外购记录**")
                        for p in details["purchases"]:
                            st.caption(f"- 外购 {p['quantity']} 只 × ¥{p['unit_price']}/只 = **¥{p['total_cost']:.2f}** ({p['time'].strftime('%Y-%m-%d')})")

                    # 销售记录
                    if details["sales"]:
                        st.markdown("**💰 销售记录**")
                        for s in details["sales"]:
                            st.caption(f"- 销售 {s['quantity']} 只 × ¥{s['unit_price']}/只 = **¥{s['total_amount']:.2f}** （客户：{s['customer']}，{s['time'].strftime('%Y-%m-%d')})")

                    # 小计（可选）
                    total_feed = sum(f["total_cost"] for f in details["feedings"])
                    total_purchase = sum(p["total_cost"] for p in details["purchases"])
                    total_sales_amt = sum(s["total_amount"] for s in details["sales"])
                    net = total_sales_amt - total_feed - total_purchase
