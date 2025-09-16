# projects/shiwa/main.py
import streamlit as st
import psycopg2
from psycopg2.extras import RealDictCursor
from urllib.parse import urlparse
import os
from datetime import datetime, date, timedelta
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from dotenv import load_dotenv

# -----------------------------
# 加载环境变量
# -----------------------------
load_dotenv()

DATABASE_SHIWA_URL = os.getenv("DATABASE_SHIWA_URL")
if not DATABASE_SHIWA_URL:
    st.error("❌ DATABASE_SHIWA_URL 未设置，请检查 .env 文件。")
    st.stop()


# -----------------------------
# 数据库连接函数
# -----------------------------
def get_shiwa_db_connection():
    try:
        url = urlparse(DATABASE_SHIWA_URL)
        conn = psycopg2.connect(
            host=url.hostname,
            port=url.port or 5432,
            database=url.path[1:],
            user=url.username,
            password=url.password,
        )
        return conn
    except Exception as e:
        st.error(f"🔗 数据库连接失败: {e}")
        return None

# -----------------------------
# 📘 中文字段映射表（前端展示用）
# -----------------------------
COLUMN_MAPPING = {
    # breeders 种蛙表
    "id": "编号",
    "source": "来源",
    "count": "数量",
    "health_status": "健康状态",
    "created_at": "创建时间",

    # hatchings 孵化表
    "breeder_batch_id": "种蛙批次ID",
    "egg_count": "产卵数",
    "hatch_count": "孵化数",
    "hatch_rate": "孵化率(%)",
    "temp": "温度(℃)",
    "humidity": "湿度(%)",
    "duration_days": "孵化天数",

    # tadpoles 蝌蚪表
    "hatching_id": "孵化批次ID",
    "start_count": "初始数量",
    "end_count": "结束数量",
    "survival_rate": "存活率(%)",
    "feed_amount_kg": "投喂量(kg)",
    "water_temp": "水温(℃)",
    "ph": "pH值",

    # juvenile_frogs 幼蛙表
    "tadpole_batch_id": "蝌蚪批次ID",
    "avg_weight_g": "平均体重(g)",
    "transfer_date": "转池日期",

    # adult_frogs 成蛙表
    "juvenile_batch_id": "幼蛙批次ID",
    "ready_for_sale": "是否可售",
    "状态": "状态",  # 特殊字段，已在函数中生成

    # feeds 饲料表
    "feed_type": "饲料种类",
    "batch_no": "批次号",
    "total_kg": "总量(kg)",
    "used_kg": "已用量(kg)",
    "剩余量": "剩余量(kg)",
    "unit_price": "单价(元/kg)",
    "总价值": "总价值(元)",
    "supplier": "供应商",

    # environment_logs 环境监控
    "pond_no": "池号",
    "do_mg_l": "溶氧(mg/L)",
    "nh3_mg_l": "氨氮(mg/L)",
    "log_date": "记录日期",

    # sales 销售表
    "adult_frog_batch_id": "成蛙批次ID",
    "customer_name": "客户名称",
    "weight_kg": "销售重量(kg)",
    "total_price": "总金额(元)",
    "sale_date": "销售日期",
}
# -----------------------------
# 初始化数据库表
# -----------------------------
def init_db():
    conn = get_shiwa_db_connection()
    if not conn:
        return

    try:
        with conn.cursor() as cur:
            # 种蛙表
            cur.execute("""
                CREATE TABLE IF NOT EXISTS breeders (
                    id SERIAL PRIMARY KEY,
                    source VARCHAR(100),
                    count INT NOT NULL,
                    health_status VARCHAR(50),
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)

            # 孵化表
            cur.execute("""
                CREATE TABLE IF NOT EXISTS hatchings (
                    id SERIAL PRIMARY KEY,
                    breeder_batch_id INT REFERENCES breeders(id) ON DELETE SET NULL,
                    egg_count INT NOT NULL,
                    hatch_count INT NOT NULL,
                    hatch_rate DECIMAL(5,2),
                    temp DECIMAL(4,2),
                    humidity DECIMAL(5,2),
                    duration_days INT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)

            # 蝌蚪表
            cur.execute("""
                CREATE TABLE IF NOT EXISTS tadpoles (
                    id SERIAL PRIMARY KEY,
                    hatching_id INT REFERENCES hatchings(id) ON DELETE SET NULL,
                    start_count INT NOT NULL,
                    end_count INT NOT NULL,
                    survival_rate DECIMAL(5,2),
                    feed_amount_kg DECIMAL(6,2),
                    water_temp DECIMAL(4,2),
                    ph DECIMAL(3,2),
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)

            # 幼蛙表
            cur.execute("""
                CREATE TABLE IF NOT EXISTS juvenile_frogs (
                    id SERIAL PRIMARY KEY,
                    tadpole_batch_id INT REFERENCES tadpoles(id) ON DELETE SET NULL,
                    start_count INT NOT NULL,
                    end_count INT NOT NULL,
                    survival_rate DECIMAL(5,2),
                    avg_weight_g DECIMAL(5,2),
                    feed_amount_kg DECIMAL(6,2),
                    transfer_date DATE,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)

            # 成蛙表
            cur.execute("""
                CREATE TABLE IF NOT EXISTS adult_frogs (
                    id SERIAL PRIMARY KEY,
                    juvenile_batch_id INT REFERENCES juvenile_frogs(id) ON DELETE SET NULL,
                    count INT NOT NULL,
                    avg_weight_g DECIMAL(5,2),
                    ready_for_sale BOOLEAN DEFAULT FALSE,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)

            # 饲料表
            cur.execute("""
                CREATE TABLE IF NOT EXISTS feeds (
                    id SERIAL PRIMARY KEY,
                    feed_type VARCHAR(50) NOT NULL,
                    batch_no VARCHAR(50),
                    total_kg DECIMAL(8,2) NOT NULL,
                    used_kg DECIMAL(8,2) DEFAULT 0,
                    unit_price DECIMAL(6,2),
                    supplier VARCHAR(100),
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)

            # 环境监控
            cur.execute("""
                CREATE TABLE IF NOT EXISTS environment_logs (
                    id SERIAL PRIMARY KEY,
                    pond_no VARCHAR(20),
                    water_temp DECIMAL(4,2),
                    ph DECIMAL(3,2),
                    do_mg_l DECIMAL(4,2),
                    nh3_mg_l DECIMAL(4,2),
                    log_date DATE DEFAULT CURRENT_DATE,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)

            # 销售表
            cur.execute("""
                CREATE TABLE IF NOT EXISTS sales (
                    id SERIAL PRIMARY KEY,
                    adult_frog_batch_id INT REFERENCES adult_frogs(id) ON DELETE SET NULL,
                    customer_name VARCHAR(100),
                    weight_kg DECIMAL(6,2) NOT NULL,
                    unit_price DECIMAL(6,2),
                    total_price DECIMAL(8,2),
                    sale_date DATE DEFAULT CURRENT_DATE,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)

            conn.commit()
            st.success("✅ 石蛙养殖数据库初始化完成")
    except Exception as e:
        st.error(f"❌ 初始化数据库失败: {e}")
    finally:
        if conn:
            conn.close()


# -----------------------------
# 通用数据插入函数（简化版）
# -----------------------------
def insert_record(table, data):
    conn = get_shiwa_db_connection()
    if not conn:
        return None
    try:
        with conn.cursor() as cur:
            columns = ", ".join(data.keys())
            values_placeholder = ", ".join(["%s"] * len(data))
            query = f"INSERT INTO {table} ({columns}) VALUES ({values_placeholder}) RETURNING id"
            cur.execute(query, list(data.values()))
            record_id = cur.fetchone()[0]
            conn.commit()
            return record_id
    except Exception as e:
        st.error(f"❌ 插入 {table} 失败: {e}")
        return None
    finally:
        if conn:
            conn.close()


# -----------------------------
# 获取数据函数（通用）
# -----------------------------
def fetch_records(table, where_clause="", params=()):
    conn = get_shiwa_db_connection()
    if not conn:
        return []
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            query = f"SELECT * FROM {table}"
            if where_clause:
                query += " WHERE " + where_clause
            query += " ORDER BY created_at DESC"
            cur.execute(query, params)
            return cur.fetchall()
    except Exception as e:
        st.error(f"❌ 查询 {table} 失败: {e}")
        return []
    finally:
        if conn:
            conn.close()


# -----------------------------
# 📊 数据看板函数
# -----------------------------
def show_dashboard():
    st.header("📈 石蛙养殖数据总览看板")

    # 获取关键数据
    breeders = fetch_records("breeders")
    hatchings = fetch_records("hatchings")
    tadpoles = fetch_records("tadpoles")
    juveniles = fetch_records("juvenile_frogs")
    adults = fetch_records("adult_frogs")
    sales = fetch_records("sales")
    feeds = fetch_records("feeds")
    env_logs = fetch_records("environment_logs", "log_date >= %s", (date.today() - timedelta(days=7),))

    total_breeders = sum(b['count'] for b in breeders) if breeders else 0
    total_adults = sum(a['count'] for a in adults if not a['ready_for_sale']) if adults else 0
    total_for_sale = sum(a['count'] for a in adults if a['ready_for_sale']) if adults else 0
    total_sales = sum(s['weight_kg'] for s in sales) if sales else 0
    total_sales_value = sum(s['total_price'] for s in sales) if sales else 0
    total_feed_used = sum(f['used_kg'] for f in feeds) if feeds else 0

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("🐸 总种蛙数", f"{total_breeders} 只")
    col2.metric("🛒 待售成蛙", f"{total_for_sale} 只")
    col3.metric("📦 本月销售", f"{total_sales:.1f} kg", f"¥{total_sales_value:,.0f}")
    col4.metric("🍽️ 饲料消耗", f"{total_feed_used:.1f} kg")

    st.markdown("---")

    # 存活率趋势（模拟数据，实际应关联批次）
    if hatchings and tadpoles and juveniles:
        survival_data = pd.DataFrame({
            "阶段": ["孵化", "蝌蚪", "幼蛙"],
            "平均存活率": [
                pd.DataFrame(hatchings)['hatch_rate'].mean() if hatchings else 0,
                pd.DataFrame(tadpoles)['survival_rate'].mean() if tadpoles else 0,
                pd.DataFrame(juveniles)['survival_rate'].mean() if juveniles else 0,
            ]
        })
        fig_survival = px.bar(survival_data, x="阶段", y="平均存活率", title="各阶段平均存活率", text_auto=True)
        fig_survival.update_traces(marker_color=['#FF6B6B', '#4ECDC4', '#45B7D1'])
        st.plotly_chart(fig_survival, use_container_width=True)

    # 最近7天环境参数
    if env_logs:
        df_env = pd.DataFrame(env_logs)
        fig_env = px.line(df_env, x="log_date", y=["water_temp", "ph", "do_mg_l", "nh3_mg_l"],
                          title="最近7天环境参数趋势",
                          labels={"value": "数值", "variable": "参数"})
        st.plotly_chart(fig_env, use_container_width=True)


# -----------------------------
# 🐸 种蛙管理
# -----------------------------
def show_breeder_management():
    st.header("🐸 种蛙管理")

    with st.form("breeder_form"):
        col1, col2, col3 = st.columns(3)
        with col1:
            source = st.selectbox("来源", ["自繁", "外购", "其他"])
        with col2:
            count = st.number_input("数量（只）", min_value=1, step=1)
        with col3:
            health = st.selectbox("健康状态", ["健康", "亚健康", "病态", "死亡"])

        if st.form_submit_button("💾 添加种蛙批次"):
            if insert_record("breeders", {
                "source": source,
                "count": count,
                "health_status": health
            }):
                st.success("✅ 种蛙批次添加成功！")
                st.rerun()

    st.markdown("---")
    st.subheader("📋 种蛙批次列表")
    breeders = fetch_records("breeders")
    if breeders:
        df = pd.DataFrame(breeders)
        df['created_at'] = df['created_at'].dt.strftime('%Y-%m-%d')
        display_cols = ["id", "source", "count", "health_status", "created_at"]
        df_display = df[display_cols].rename(columns=COLUMN_MAPPING)
        st.dataframe(df_display, use_container_width=True, hide_index=True)
    else:
        st.info("暂无种蛙记录")


# -----------------------------
# 🥚 孵化管理
# -----------------------------
def show_hatching_management():
    st.header("🥚 孵化管理")

    breeders = fetch_records("breeders")
    breeder_options = {b['id']: f"批次#{b['id']} - {b['source']} ({b['count']}只)" for b in breeders} if breeders else {}

    with st.form("hatching_form"):
        col1, col2, col3 = st.columns(3)
        with col1:
            breeder_id = st.selectbox("关联种蛙批次", options=list(breeder_options.keys()),
                                      format_func=lambda x: breeder_options.get(x, "未知"))
        with col2:
            egg_count = st.number_input("产卵数", min_value=1, step=1)
        with col3:
            hatch_count = st.number_input("孵化数", min_value=0, step=1)

        col4, col5, col6 = st.columns(3)
        with col4:
            temp = st.number_input("温度(℃)", min_value=0.0, max_value=40.0, value=25.0, step=0.1)
        with col5:
            humidity = st.number_input("湿度(%)", min_value=0.0, max_value=100.0, value=80.0, step=1.0)
        with col6:
            days = st.number_input("孵化天数", min_value=1, max_value=30, value=10, step=1)

        hatch_rate = round(hatch_count / egg_count * 100, 2) if egg_count > 0 else 0
        st.info(f"📊 计算孵化率: {hatch_rate}%")

        if st.form_submit_button("💾 记录孵化批次"):
            if insert_record("hatchings", {
                "breeder_batch_id": breeder_id,
                "egg_count": egg_count,
                "hatch_count": hatch_count,
                "hatch_rate": hatch_rate,
                "temp": temp,
                "humidity": humidity,
                "duration_days": days
            }):
                st.success("✅ 孵化批次记录成功！")
                st.rerun()

    st.markdown("---")
    st.subheader("📋 孵化批次列表")
    hatchings = fetch_records("hatchings")
    if hatchings:
        df = pd.DataFrame(hatchings)
        df['created_at'] = df['created_at'].dt.strftime('%Y-%m-%d')
        display_cols = ["id", "breeder_batch_id", "egg_count", "hatch_count", "hatch_rate",
                        "temp", "humidity", "duration_days", "created_at"]
        df_display = df[display_cols].rename(columns=COLUMN_MAPPING)
        st.dataframe(df_display, use_container_width=True, hide_index=True)
    else:
        st.info("暂无孵化记录")


# -----------------------------
# 🐣 蝌蚪管理
# -----------------------------
def show_tadpole_management():
    st.header("🐣 蝌蚪管理")

    hatchings = fetch_records("hatchings")
    hatching_options = {h['id']: f"孵化#{h['id']} - 孵化率{h['hatch_rate']}%" for h in hatchings} if hatchings else {}

    with st.form("tadpole_form"):
        col1, col2, col3 = st.columns(3)
        with col1:
            hatching_id = st.selectbox("关联孵化批次", options=list(hatching_options.keys()),
                                       format_func=lambda x: hatching_options.get(x, "未知"))
        with col2:
            start_count = st.number_input("初始数量", min_value=1, step=1)
        with col3:
            end_count = st.number_input("结束数量", min_value=0, step=1)

        col4, col5, col6 = st.columns(3)
        with col4:
            feed_kg = st.number_input("投喂量(kg)", min_value=0.0, step=0.1)
        with col5:
            water_temp = st.number_input("水温(℃)", min_value=0.0, max_value=40.0, value=22.0, step=0.1)
        with col6:
            ph = st.number_input("pH值", min_value=0.0, max_value=14.0, value=7.0, step=0.1)

        survival_rate = round(end_count / start_count * 100, 2) if start_count > 0 else 0
        st.info(f"📊 计算存活率: {survival_rate}%")

        if st.form_submit_button("💾 记录蝌蚪批次"):
            if insert_record("tadpoles", {
                "hatching_id": hatching_id,
                "start_count": start_count,
                "end_count": end_count,
                "survival_rate": survival_rate,
                "feed_amount_kg": feed_kg,
                "water_temp": water_temp,
                "ph": ph
            }):
                st.success("✅ 蝌蚪批次记录成功！")
                st.rerun()

    st.markdown("---")
    st.subheader("📋 蝌蚪批次列表")
    tadpoles = fetch_records("tadpoles")
    if tadpoles:
        df = pd.DataFrame(tadpoles)
        df['created_at'] = df['created_at'].dt.strftime('%Y-%m-%d')
        display_cols = ["id", "hatching_id", "start_count", "end_count", "survival_rate",
                        "feed_amount_kg", "water_temp", "ph", "created_at"]
        df_display = df[display_cols].rename(columns=COLUMN_MAPPING)
        st.dataframe(df_display, use_container_width=True, hide_index=True)
    else:
        st.info("暂无蝌蚪记录")


# -----------------------------
# 🐛 幼蛙管理
# -----------------------------
def show_juvenile_management():
    st.header("🐛 幼蛙管理")

    tadpoles = fetch_records("tadpoles")
    tadpole_options = {t['id']: f"蝌蚪#{t['id']} - 存活率{t['survival_rate']}%" for t in tadpoles} if tadpoles else {}

    with st.form("juvenile_form"):
        col1, col2, col3 = st.columns(3)
        with col1:
            tadpole_id = st.selectbox("关联蝌蚪批次", options=list(tadpole_options.keys()),
                                      format_func=lambda x: tadpole_options.get(x, "未知"))
        with col2:
            start_count = st.number_input("转入数量", min_value=1, step=1)
        with col3:
            end_count = st.number_input("转出数量", min_value=0, step=1)

        col4, col5, col6 = st.columns(3)
        with col4:
            avg_weight = st.number_input("平均体重(g)", min_value=0.1, step=0.1)
        with col5:
            feed_kg = st.number_input("投喂量(kg)", min_value=0.0, step=0.1)
        with col6:
            transfer_date = st.date_input("转池日期", value=date.today())

        survival_rate = round(end_count / start_count * 100, 2) if start_count > 0 else 0
        st.info(f"📊 计算存活率: {survival_rate}%")

        if st.form_submit_button("💾 记录幼蛙批次"):
            if insert_record("juvenile_frogs", {
                "tadpole_batch_id": tadpole_id,
                "start_count": start_count,
                "end_count": end_count,
                "survival_rate": survival_rate,
                "avg_weight_g": avg_weight,
                "feed_amount_kg": feed_kg,
                "transfer_date": transfer_date
            }):
                st.success("✅ 幼蛙批次记录成功！")
                st.rerun()

    st.markdown("---")
    st.subheader("📋 幼蛙批次列表")
    juveniles = fetch_records("juvenile_frogs")
    if juveniles:
        df = pd.DataFrame(juveniles)
        df['created_at'] = df['created_at'].dt.strftime('%Y-%m-%d')
        display_cols = ["id", "tadpole_batch_id", "start_count", "end_count", "survival_rate",
                        "avg_weight_g", "feed_amount_kg", "transfer_date", "created_at"]
        df_display = df[display_cols].rename(columns=COLUMN_MAPPING)
        st.dataframe(df_display, use_container_width=True, hide_index=True)
    else:
        st.info("暂无幼蛙记录")


# -----------------------------
# 🐸 成蛙管理
# -----------------------------
def show_adult_management():
    st.header("🐸 成蛙管理")

    juveniles = fetch_records("juvenile_frogs")
    juvenile_options = {j['id']: f"幼蛙#{j['id']} - {j['avg_weight_g']}g" for j in juveniles} if juveniles else {}

    with st.form("adult_form"):
        col1, col2, col3 = st.columns(3)
        with col1:
            juvenile_id = st.selectbox("关联幼蛙批次", options=list(juvenile_options.keys()),
                                       format_func=lambda x: juvenile_options.get(x, "未知"))
        with col2:
            count = st.number_input("数量", min_value=1, step=1)
        with col3:
            avg_weight = st.number_input("平均体重(g)", min_value=1.0, step=1.0)

        ready = st.checkbox("标记为可销售")

        if st.form_submit_button("💾 记录成蛙批次"):
            if insert_record("adult_frogs", {
                "juvenile_batch_id": juvenile_id,
                "count": count,
                "avg_weight_g": avg_weight,
                "ready_for_sale": ready
            }):
                st.success("✅ 成蛙批次记录成功！")
                st.rerun()

    st.markdown("---")
    st.subheader("📋 成蛙批次列表")
    adults = fetch_records("adult_frogs")
    if adults:
        df = pd.DataFrame(adults)
        df['created_at'] = df['created_at'].dt.strftime('%Y-%m-%d')
        df['状态'] = df['ready_for_sale'].map({True: '✅ 可售', False: '🔄 养殖中'})
        display_cols = ["id", "juvenile_batch_id", "count", "avg_weight_g", "状态", "created_at"]
        df_display = df[display_cols].rename(columns=COLUMN_MAPPING)
        st.dataframe(df_display, use_container_width=True, hide_index=True)
    else:
        st.info("暂无成蛙记录")


# -----------------------------
# 🍽️ 饲料管理
# -----------------------------
def show_feed_management():
    st.header("🍽️ 饲料管理")

    with st.form("feed_form"):
        col1, col2, col3 = st.columns(3)
        with col1:
            feed_type = st.text_input("饲料种类*", placeholder="如：蝌蚪粉、幼蛙颗粒、成蛙膨化")
        with col2:
            batch_no = st.text_input("批次号", placeholder="可选")
        with col3:
            total_kg = st.number_input("总量(kg)*", min_value=0.1, step=0.1)

        col4, col5 = st.columns(2)
        with col4:
            unit_price = st.number_input("单价(元/kg)", min_value=0.0, step=0.1)
        with col5:
            supplier = st.text_input("供应商", placeholder="可选")

        if st.form_submit_button("💾 添加饲料批次"):
            if not feed_type.strip():
                st.error("请填写饲料种类")
            else:
                if insert_record("feeds", {
                    "feed_type": feed_type.strip(),
                    "batch_no": batch_no,
                    "total_kg": total_kg,
                    "unit_price": unit_price,
                    "supplier": supplier
                }):
                    st.success("✅ 饲料批次添加成功！")
                    st.rerun()

    st.markdown("---")
    st.subheader("📋 饲料库存列表")
    feeds = fetch_records("feeds")
    if feeds:
        df = pd.DataFrame(feeds)
        df['剩余量'] = df['total_kg'] - df['used_kg']
        df['总价值'] = df['total_kg'] * df['unit_price']
        df['created_at'] = df['created_at'].dt.strftime('%Y-%m-%d')
        display_cols = ["id", "feed_type", "batch_no", "total_kg", "used_kg", "剩余量", "unit_price", "总价值", "supplier", "created_at"]
        df_display = df[display_cols].rename(columns=COLUMN_MAPPING)
        st.dataframe(df_display, use_container_width=True, hide_index=True)
    else:
        st.info("暂无饲料记录")


# -----------------------------
# 🌡️ 环境监控
# -----------------------------
def show_environment_monitoring():
    st.header("🌡️ 环境监控日志")

    with st.form("env_form"):
        col1, col2, col3 = st.columns(3)
        with col1:
            pond_no = st.text_input("池号*", placeholder="如：A1, B2")
        with col2:
            water_temp = st.number_input("水温(℃)*", min_value=0.0, max_value=40.0, value=22.0, step=0.1)
        with col3:
            ph = st.number_input("pH值*", min_value=0.0, max_value=14.0, value=7.0, step=0.1)

        col4, col5 = st.columns(2)
        with col4:
            do = st.number_input("溶氧(mg/L)", min_value=0.0, max_value=20.0, value=5.0, step=0.1)
        with col5:
            nh3 = st.number_input("氨氮(mg/L)", min_value=0.0, max_value=5.0, value=0.1, step=0.01)

        log_date = st.date_input("记录日期", value=date.today())

        if st.form_submit_button("💾 记录环境数据"):
            if not pond_no.strip():
                st.error("请填写池号")
            else:
                if insert_record("environment_logs", {
                    "pond_no": pond_no.strip(),
                    "water_temp": water_temp,
                    "ph": ph,
                    "do_mg_l": do,
                    "nh3_mg_l": nh3,
                    "log_date": log_date
                }):
                    st.success("✅ 环境数据记录成功！")
                    st.rerun()

    st.markdown("---")
    st.subheader("📋 最近环境记录")
    envs = fetch_records("environment_logs", "log_date >= %s", (date.today() - timedelta(days=30),))
    if envs:
        df = pd.DataFrame(envs)
        df['log_date'] = df['log_date'].astype(str)
        display_cols = ["id", "pond_no", "water_temp", "ph", "do_mg_l", "nh3_mg_l", "log_date", "created_at"]
        df_display = df[display_cols].rename(columns=COLUMN_MAPPING)
        st.dataframe(df_display, use_container_width=True, hide_index=True)
    else:
        st.info("最近30天无环境记录")


# -----------------------------
# 💰 销售管理
# -----------------------------
def show_sales_management():
    st.header("💰 销售管理")

    adults = fetch_records("adult_frogs", "ready_for_sale = TRUE")
    adult_options = {a['id']: f"成蛙#{a['id']} - {a['count']}只, {a['avg_weight_g']}g/只" for a in adults} if adults else {}

    with st.form("sale_form"):
        col1, col2, col3 = st.columns(3)
        with col1:
            adult_id = st.selectbox("销售批次", options=list(adult_options.keys()),
                                    format_func=lambda x: adult_options.get(x, "无可用批次"))
        with col2:
            customer = st.text_input("客户名称*")
        with col3:
            weight_kg = st.number_input("销售重量(kg)*", min_value=0.1, step=0.1)

        col4, col5 = st.columns(2)
        with col4:
            unit_price = st.number_input("单价(元/kg)*", min_value=0.0, step=0.1)
        with col5:
            sale_date = st.date_input("销售日期", value=date.today())

        total_price = weight_kg * unit_price
        st.info(f"💰 总金额: ¥{total_price:,.2f}")

        if st.form_submit_button("💾 记录销售"):
            if not customer.strip():
                st.error("请填写客户名称")
            else:
                sale_id = insert_record("sales", {
                    "adult_frog_batch_id": adult_id,
                    "customer_name": customer.strip(),
                    "weight_kg": weight_kg,
                    "unit_price": unit_price,
                    "total_price": total_price,
                    "sale_date": sale_date
                })
                if sale_id:
                    # 🎯 高级功能：自动减少成蛙库存（这里简化处理，实际应扣减对应批次数量）
                    st.success("✅ 销售记录成功！")
                    st.rerun()

    st.markdown("---")
    st.subheader("📋 销售记录")
    sales = fetch_records("sales")
    if sales:
        df = pd.DataFrame(sales)
        df['sale_date'] = df['sale_date'].astype(str)
        df['created_at'] = df['created_at'].dt.strftime('%Y-%m-%d %H:%M')
        display_cols = ["id", "adult_frog_batch_id", "customer_name", "weight_kg", "unit_price", "total_price", "sale_date", "created_at"]
        df_display = df[display_cols].rename(columns=COLUMN_MAPPING)
        st.dataframe(df_display, use_container_width=True, hide_index=True)
    else:
        st.info("暂无销售记录")


# -----------------------------
# 📊 生产统计分析
# -----------------------------
def show_production_analysis():
    st.header("📊 生产统计与分析")

    # 获取各阶段数据
    hatchings = fetch_records("hatchings")
    tadpoles = fetch_records("tadpoles")
    juveniles = fetch_records("juvenile_frogs")
    adults = fetch_records("adult_frogs")
    sales = fetch_records("sales")

    if not (hatchings and tadpoles and juveniles):
        st.warning("⚠️ 数据不足，无法生成完整分析图表")
        return

    # 1. 各阶段存活率对比
    st.subheader("📈 各阶段存活率对比")
    survival_rates = {
        "孵化": pd.DataFrame(hatchings)['hatch_rate'].mean() if hatchings else 0,
        "蝌蚪": pd.DataFrame(tadpoles)['survival_rate'].mean() if tadpoles else 0,
        "幼蛙": pd.DataFrame(juveniles)['survival_rate'].mean() if juveniles else 0,
    }
    df_survival = pd.DataFrame(list(survival_rates.items()), columns=['阶段', '平均存活率'])
    fig1 = px.bar(df_survival, x='阶段', y='平均存活率', text='平均存活率',
                  color='阶段', color_discrete_sequence=px.colors.qualitative.Bold)
    fig1.update_traces(texttemplate='%{text:.1f}%', textposition='outside')
    st.plotly_chart(fig1, use_container_width=True)

    # 2. 成本效益分析（简化）
    st.subheader("💹 成本效益模拟分析")
    total_sales_value = sum(s['total_price'] for s in sales) if sales else 0
    # 假设饲料成本占70%（简化模型）
    feeds = fetch_records("feeds")
    total_feed_cost = sum(f['total_kg'] * f['unit_price'] for f in feeds) if feeds else 0
    other_cost = total_sales_value * 0.2  # 假设其他成本占收入20%
    total_cost = total_feed_cost + other_cost
    profit = total_sales_value - total_cost

    fig2 = go.Figure(go.Waterfall(
        name="2024", orientation="v",
        measure=["relative", "relative", "total"],
        x=["销售收入", "总成本", "净利润"],
        textposition="outside",
        text=[f"¥{total_sales_value:,.0f}", f"-¥{total_cost:,.0f}", f"¥{profit:,.0f}"],
        y=[total_sales_value, -total_cost, profit],
        connector={"line": {"color": "rgb(63, 63, 63)"}},
        increasing={"marker": {"color": "#28a745"}},
        decreasing={"marker": {"color": "#dc3545"}},
        totals={"marker": {"color": "#007bff"}}
    ))
    fig2.update_layout(title="简化成本效益瀑布图", height=500)
    st.plotly_chart(fig2, use_container_width=True)

    # 3. 销售趋势
    if sales:
        st.subheader("📅 月度销售趋势")
        df_sales = pd.DataFrame(sales)
        df_sales['sale_date'] = pd.to_datetime(df_sales['sale_date'])
        df_sales['month'] = df_sales['sale_date'].dt.to_period('M').astype(str)
        monthly_sales = df_sales.groupby('month')['total_price'].sum().reset_index()
        fig3 = px.line(monthly_sales, x='month', y='total_price', markers=True,
                       labels={'total_price': '销售额 (¥)', 'month': '月份'},
                       title="月度销售趋势")
        fig3.update_traces(line=dict(width=3, color='#FF6B6B'))
        st.plotly_chart(fig3, use_container_width=True)


# -----------------------------
# Streamlit 主函数（使用 Tabs）
# -----------------------------
def run():
    st.set_page_config(page_title="🌿 石蛙养殖基地管理系统", layout="wide", page_icon="🐸")
    init_db()

    st.title("🌿 石蛙养殖基地智能管理系统")
    st.markdown("### 🐸 全流程数字化管理平台")
    st.markdown("---")

    # 👇 使用 st.tabs 创建顶部标签页
    tab_names = [
        "📊 数据看板",
        "🐸 种蛙管理",
        "🥚 孵化管理",
        "🐣 蝌蚪管理",
        "🐛 幼蛙管理",
        "🐸 成蛙管理",
        "🍽️ 饲料管理",
        "🌡️ 环境监控",
        "💰 销售管理",
        "📈 生产统计"
    ]

    tabs = st.tabs(tab_names)

    # 每个 Tab 对应一个功能函数
    with tabs[0]:
        show_dashboard()
    with tabs[1]:
        show_breeder_management()
    with tabs[2]:
        show_hatching_management()
    with tabs[3]:
        show_tadpole_management()
    with tabs[4]:
        show_juvenile_management()
    with tabs[5]:
        show_adult_management()
    with tabs[6]:
        show_feed_management()
    with tabs[7]:
        show_environment_monitoring()
    with tabs[8]:
        show_sales_management()
    with tabs[9]:
        show_production_analysis()

    # 页脚（可选）
    st.markdown("---")
    st.caption("🐸 石蛙养殖基地智能管理系统 © 2025 | 数据云端安全存储")