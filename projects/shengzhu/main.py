# projects/shengzhu/main.py
import streamlit as st
import pandas as pd
import psycopg2
import plotly.express as px
from urllib.parse import urlparse
import os
from dotenv import load_dotenv

# -----------------------------
# 加载环境变量 & 数据库配置
# -----------------------------
load_dotenv()
DATABASE_URL = os.getenv("DATABASE_SHENGZHU_URL") or os.getenv("DATABASE_URL")
if not DATABASE_URL:
    st.error("❌ 未设置 DATABASE_URL，请检查 .env 文件")
    st.stop()

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
# 通用数据库函数
# -----------------------------
def execute_query(query, params=None, fetch=False):
    try:
        with psycopg2.connect(**DB_CONFIG) as conn:
            with conn.cursor() as cur:
                cur.execute(query, params)
                if fetch:
                    rows = cur.fetchall()
                    cols = [desc[0] for desc in cur.description]
                    return pd.DataFrame(rows, columns=cols)
                conn.commit()
        return None
    except Exception as e:
        st.error(f"⚠️ 数据库操作失败: {e}")
        return None


# -----------------------------
# 中文列名映射字典（统一管理）
# -----------------------------
COLUMN_TRANSLATIONS = {
    # pigs
    "ear_tag": "耳标号",
    "breed": "品种",
    "gender": "性别",
    "birth_date": "出生日期",
    "birth_weight_kg": "出生体重(kg)",
    "dam_ear_tag": "母猪耳标",
    "sire_ear_tag": "公猪耳标",
    "status": "状态",
    "farm": "养殖场",
    "pigsty": "当前猪舍",
    
    # farms
    "name": "名称",
    "location": "地址",
    "manager_name": "负责人",
    "contact_phone": "联系电话",
    
    # pigsties
    "capacity": "容量(头)",
    "type": "类型",
    
    # movements
    "from_pigsty": "原猪舍",
    "to_pigsty": "目标猪舍",
    "move_date": "转栏日期",
    "reason": "原因",
    "operator": "操作人",
    
    # vaccinations
    "vaccine_name": "疫苗名称",
    "batch_number": "批次号",
    "dose_ml": "剂量(ml)",
    "admin_date": "接种日期",
    "next_due_date": "下次免疫日期",
    "veterinarian": "兽医",
    "notes": "备注",
    
    # treatments
    "drug_name": "药品名称",
    "dosage": "用量",
    
    # feed_records
    "feed_name": "饲料名称",
    "feed_batch": "饲料批次",
    "amount_kg": "用量(kg)",
    "feed_date": "饲喂日期",
    "target": "饲喂对象",
    
    # sales
    "sale_date": "销售日期",
    "weight_kg": "销售体重(kg)",
    "price_per_kg": "单价(元/kg)",
    "buyer_name": "买家",
    "destination": "去向",
    "sale_type": "销售类型",
    
    # slaughter_records
    "slaughter_date": "屠宰日期",
    "slaughterhouse": "屠宰场",
    "carcass_weight_kg": "胴体重(kg)",
    "meat_batch_number": "肉品批次号",
    "inspector": "检疫员",
}


def translate_columns(df: pd.DataFrame) -> pd.DataFrame:
    """将 DataFrame 列名翻译为中文"""
    return df.rename(columns={k: v for k, v in COLUMN_TRANSLATIONS.items() if k in df.columns})


# -----------------------------
# 初始化数据库
# -----------------------------
def init_database():
    create_tables_sql = """
    CREATE TABLE IF NOT EXISTS farms (
        id SERIAL PRIMARY KEY,
        name VARCHAR(100) NOT NULL,
        location TEXT,
        manager_name VARCHAR(50),
        contact_phone VARCHAR(20),
        created_at TIMESTAMP DEFAULT NOW()
    );

    CREATE TABLE IF NOT EXISTS pigsties (
        id SERIAL PRIMARY KEY,
        farm_id INT REFERENCES farms(id) ON DELETE CASCADE,
        name VARCHAR(50) NOT NULL,
        capacity INT,
        type VARCHAR(20) CHECK (type IN ('产房', '保育舍', '育肥舍', '后备舍')),
        created_at TIMESTAMP DEFAULT NOW()
    );

    CREATE TABLE IF NOT EXISTS pigs (
        id SERIAL PRIMARY KEY,
        ear_tag VARCHAR(50) UNIQUE NOT NULL,
        breed VARCHAR(50),
        gender VARCHAR(10) CHECK (gender IN ('公', '母', '阉')),
        birth_date DATE,
        birth_weight_kg DECIMAL(5,2),
        dam_ear_tag VARCHAR(50),
        sire_ear_tag VARCHAR(50),
        status VARCHAR(20) DEFAULT '在栏' CHECK (status IN ('在栏', '已出栏', '已死亡', '已屠宰')),
        farm_id INT NOT NULL REFERENCES farms(id),
        current_pigsty_id INT REFERENCES pigsties(id),
        created_at TIMESTAMP DEFAULT NOW(),
        updated_at TIMESTAMP DEFAULT NOW()
    );

    CREATE TABLE IF NOT EXISTS movements (
        id SERIAL PRIMARY KEY,
        pig_id INT REFERENCES pigs(id) ON DELETE CASCADE,
        from_pigsty_id INT REFERENCES pigsties(id),
        to_pigsty_id INT REFERENCES pigsties(id) NOT NULL,
        move_date DATE NOT NULL,
        reason VARCHAR(100),
        operator VARCHAR(50),
        created_at TIMESTAMP DEFAULT NOW()
    );

    CREATE TABLE IF NOT EXISTS vaccinations (
        id SERIAL PRIMARY KEY,
        pig_id INT REFERENCES pigs(id) ON DELETE CASCADE,
        vaccine_name VARCHAR(100) NOT NULL,
        batch_number VARCHAR(50),
        dose_ml DECIMAL(5,2),
        admin_date DATE NOT NULL,
        next_due_date DATE,
        veterinarian VARCHAR(50),
        notes TEXT,
        created_at TIMESTAMP DEFAULT NOW()
    );

    CREATE TABLE IF NOT EXISTS treatments (
        id SERIAL PRIMARY KEY,
        pig_id INT REFERENCES pigs(id) ON DELETE CASCADE,
        drug_name VARCHAR(100) NOT NULL,
        batch_number VARCHAR(50),
        dosage VARCHAR(50),
        admin_date DATE NOT NULL,
        reason TEXT,
        veterinarian VARCHAR(50),
        created_at TIMESTAMP DEFAULT NOW()
    );

    CREATE TABLE IF NOT EXISTS feed_records (
        id SERIAL PRIMARY KEY,
        pig_id INT REFERENCES pigs(id) ON DELETE CASCADE,
        pigsty_id INT REFERENCES pigsties(id),
        feed_name VARCHAR(100) NOT NULL,
        feed_batch VARCHAR(50),
        amount_kg DECIMAL(6,2) NOT NULL,
        feed_date DATE NOT NULL,
        operator VARCHAR(50),
        created_at TIMESTAMP DEFAULT NOW()
    );

    CREATE TABLE IF NOT EXISTS sales (
        id SERIAL PRIMARY KEY,
        pig_id INT REFERENCES pigs(id) ON DELETE CASCADE,
        sale_date DATE NOT NULL,
        weight_kg DECIMAL(6,2),
        price_per_kg DECIMAL(8,2),
        buyer_name VARCHAR(100),
        destination VARCHAR(200),
        sale_type VARCHAR(20) CHECK (sale_type IN ('活猪销售', '屠宰')),
        created_at TIMESTAMP DEFAULT NOW()
    );

    CREATE TABLE IF NOT EXISTS slaughter_records (
        id SERIAL PRIMARY KEY,
        pig_id INT REFERENCES pigs(id) ON DELETE CASCADE,
        slaughter_date DATE NOT NULL,
        slaughterhouse VARCHAR(100),
        carcass_weight_kg DECIMAL(6,2),
        meat_batch_number VARCHAR(50),
        inspector VARCHAR(50),
        created_at TIMESTAMP DEFAULT NOW()
    );
    """
    execute_query(create_tables_sql)


# -----------------------------
# 主应用入口
# -----------------------------
def run():
    st.set_page_config(page_title="生猪养殖全流程溯源系统", layout="wide")
    st.title("🐷 生猪养殖全流程溯源管理系统")
    st.markdown("全程可追溯 · 一猪一码 · 安全可控")

    init_database()

    # 获取基础数据
    farms_df = execute_query("SELECT id, name FROM farms ORDER BY name", fetch=True)
    farm_options = dict(zip(farms_df['id'], farms_df['name'])) if farms_df is not None and not farms_df.empty else {}

    pigsties_df = execute_query("SELECT id, name, farm_id FROM pigsties ORDER BY name", fetch=True)
    pigsty_options = {}
    if pigsties_df is not None and not pigsties_df.empty:
        pigsty_options = {row['id']: f"{farm_options.get(row['farm_id'], '未知场')} - {row['name']}" for _, row in pigsties_df.iterrows()}

    pigs_df = execute_query("SELECT id, ear_tag FROM pigs ORDER BY ear_tag", fetch=True)
    pig_options = dict(zip(pigs_df['id'], pigs_df['ear_tag'])) if pigs_df is not None and not pigs_df.empty else {}

    tabs = st.tabs([
        "🐷 猪只档案",
        "🏠 养殖场管理",
        "🏠 猪舍管理",
        "🔄 转栏记录",
        "💉 免疫管理",
        "💊 用药记录",
        "🌾 饲料记录",
        "💰 出栏销售",
        "🔪 屠宰溯源",
        "📊 全流程数据分析"
    ])

    # ========== Tab 0: 猪只档案 ==========
    with tabs[0]:
        st.subheader("➕ 新增猪只")
        with st.form("add_pig"):
            ear_tag = st.text_input("耳标号 *", help="唯一标识")
            breed = st.text_input("品种")
            gender = st.selectbox("性别", ["公", "母", "阉"])
            birth_date = st.date_input("出生日期")
            birth_weight = st.number_input("出生体重 (kg)", min_value=0.0, step=0.1)
            dam = st.text_input("母猪耳标（可选）")
            sire = st.text_input("公猪耳标（可选）")
            farm_id = st.selectbox("所属养殖场 *", options=list(farm_options.keys()), format_func=lambda x: farm_options[x])
            pigsty_id = st.selectbox("当前猪舍", options=[None] + list(pigsty_options.keys()), format_func=lambda x: pigsty_options.get(x, "未分配") if x else "未分配")
            if st.form_submit_button("添加猪只"):
                if not ear_tag:
                    st.error("耳标号不能为空！")
                else:
                    query = """
                        INSERT INTO pigs (ear_tag, breed, gender, birth_date, birth_weight_kg, dam_ear_tag, sire_ear_tag, farm_id, current_pigsty_id)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """
                    if execute_query(query, (ear_tag, breed, gender, birth_date, birth_weight, dam, sire, farm_id, pigsty_id)) is not None:
                        st.success(f"✅ 猪只 {ear_tag} 添加成功！")
                        st.rerun()

        st.subheader("📋 猪只列表")
        df = execute_query("""
            SELECT p.ear_tag, p.breed, p.gender, p.birth_date, p.status, 
                   f.name as farm, ps.name as pigsty 
            FROM pigs p 
            LEFT JOIN farms f ON p.farm_id = f.id 
            LEFT JOIN pigsties ps ON p.current_pigsty_id = ps.id 
            ORDER BY p.created_at DESC
        """, fetch=True)
        if df is not None and not df.empty:
            st.dataframe(translate_columns(df), use_container_width=True)
        else:
            st.info("暂无猪只记录")

    # ========== Tab 1: 养殖场管理 ==========
    with tabs[1]:
        st.subheader("➕ 新增养殖场")
        with st.form("add_farm"):
            name = st.text_input("养殖场名称 *")
            location = st.text_input("地址")
            manager = st.text_input("负责人")
            phone = st.text_input("联系电话")
            if st.form_submit_button("添加养殖场"):
                if name:
                    execute_query("INSERT INTO farms (name, location, manager_name, contact_phone) VALUES (%s, %s, %s, %s)", (name, location, manager, phone))
                    st.success("✅ 养殖场添加成功！")
                    st.rerun()
                else:
                    st.error("名称不能为空")

        st.subheader("📋 养殖场列表")
        df = execute_query("SELECT name, location, manager_name, contact_phone FROM farms", fetch=True)
        if df is not None and not df.empty:
            st.dataframe(translate_columns(df), use_container_width=True)

    # ========== Tab 2: 猪舍管理 ==========
    with tabs[2]:
        st.subheader("➕ 新增猪舍")
        with st.form("add_pigsty"):
            farm_id = st.selectbox("所属养殖场 *", options=list(farm_options.keys()), format_func=lambda x: farm_options[x])
            name = st.text_input("猪舍名称 *")
            capacity = st.number_input("容量（头）", min_value=1, value=50)
            sty_type = st.selectbox("类型", ["产房", "保育舍", "育肥舍", "后备舍"])
            if st.form_submit_button("添加猪舍"):
                if name and farm_id:
                    execute_query("INSERT INTO pigsties (farm_id, name, capacity, type) VALUES (%s, %s, %s, %s)", (farm_id, name, capacity, sty_type))
                    st.success("✅ 猪舍添加成功！")
                    st.rerun()

        st.subheader("📋 猪舍列表")
        df = execute_query("""
            SELECT ps.name, ps.capacity, ps.type, f.name as farm 
            FROM pigsties ps 
            JOIN farms f ON ps.farm_id = f.id
            ORDER BY f.name, ps.name
        """, fetch=True)
        if df is not None and not df.empty:
            st.dataframe(translate_columns(df), use_container_width=True)

    # ========== Tab 3: 转栏记录 ==========
    with tabs[3]:
        st.subheader("➕ 新增转栏记录")
        with st.form("add_movement"):
            pig_id = st.selectbox("猪只 *", options=list(pig_options.keys()), format_func=lambda x: pig_options[x])
            from_pigsty = st.selectbox("原猪舍", options=[None] + list(pigsty_options.keys()), format_func=lambda x: pigsty_options.get(x, "无") if x else "无")
            to_pigsty = st.selectbox("目标猪舍 *", options=list(pigsty_options.keys()), format_func=lambda x: pigsty_options[x])
            move_date = st.date_input("转栏日期")
            reason = st.text_input("原因")
            operator = st.text_input("操作人")
            if st.form_submit_button("记录转栏"):
                if pig_id and to_pigsty:
                    execute_query("UPDATE pigs SET current_pigsty_id = %s WHERE id = %s", (to_pigsty, pig_id))
                    execute_query("""
                        INSERT INTO movements (pig_id, from_pigsty_id, to_pigsty_id, move_date, reason, operator)
                        VALUES (%s, %s, %s, %s, %s, %s)
                    """, (pig_id, from_pigsty, to_pigsty, move_date, reason, operator))
                    st.success("✅ 转栏记录已保存！")
                    st.rerun()

        st.subheader("📋 转栏历史")
        df = execute_query("""
            SELECT p.ear_tag, 
                   fps.name as from_pigsty, 
                   tps.name as to_pigsty,
                   m.move_date,
                   m.reason,
                   m.operator
            FROM movements m
            JOIN pigs p ON m.pig_id = p.id
            LEFT JOIN pigsties fps ON m.from_pigsty_id = fps.id
            JOIN pigsties tps ON m.to_pigsty_id = tps.id
            ORDER BY m.move_date DESC
        """, fetch=True)
        if df is not None and not df.empty:
            st.dataframe(translate_columns(df), use_container_width=True)

    # ========== Tab 4–8: 免疫、用药、饲料、销售、屠宰 ==========
    # （为节省篇幅，此处省略中间 Tab 的重复代码，仅展示关键差异：使用 translate_columns）
    # 实际使用时请保留完整逻辑，仅将 st.dataframe(df) 改为 st.dataframe(translate_columns(df))

    # 示例：免疫管理（Tab 4）
    with tabs[4]:
        st.subheader("➕ 新增免疫记录")
        with st.form("add_vaccination"):
            pig_id = st.selectbox("猪只 *", options=list(pig_options.keys()), format_func=lambda x: pig_options[x])
            vaccine = st.text_input("疫苗名称 *")
            batch = st.text_input("疫苗批次")
            dose = st.number_input("剂量 (ml)", min_value=0.0, step=0.1)
            admin_date = st.date_input("接种日期")
            next_due = st.date_input("下次免疫日期", value=None)
            vet = st.text_input("兽医")
            notes = st.text_area("备注")
            if st.form_submit_button("记录免疫"):
                if pig_id and vaccine:
                    execute_query("""
                        INSERT INTO vaccinations (pig_id, vaccine_name, batch_number, dose_ml, admin_date, next_due_date, veterinarian, notes)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    """, (pig_id, vaccine, batch, dose, admin_date, next_due, vet, notes))
                    st.success("✅ 免疫记录已保存！")
                    st.rerun()

        st.subheader("📋 免疫记录")
        df = execute_query("""
            SELECT p.ear_tag, v.vaccine_name, v.batch_number, v.dose_ml, v.admin_date, v.next_due_date, v.veterinarian
            FROM vaccinations v
            JOIN pigs p ON v.pig_id = p.id
            ORDER BY v.admin_date DESC
        """, fetch=True)
        if df is not None and not df.empty:
            st.dataframe(translate_columns(df), use_container_width=True)

        # ========== Tab 5: 用药记录 ==========
    with tabs[5]:
        st.subheader("➕ 新增用药记录")
        with st.form("add_treatment"):
            pig_id = st.selectbox("猪只 *", options=list(pig_options.keys()), format_func=lambda x: pig_options[x])
            drug = st.text_input("药品名称 *")
            batch = st.text_input("药品批次")
            dosage = st.text_input("用量（如 10mg/kg）")
            admin_date = st.date_input("用药日期")
            reason = st.text_area("病因/症状")
            vet = st.text_input("兽医")
            if st.form_submit_button("记录用药"):
                if pig_id and drug:
                    execute_query("""
                        INSERT INTO treatments (pig_id, drug_name, batch_number, dosage, admin_date, reason, veterinarian)
                        VALUES (%s, %s, %s, %s, %s, %s, %s)
                    """, (pig_id, drug, batch, dosage, admin_date, reason, vet))
                    st.success("✅ 用药记录已保存！")
                    st.rerun()
                else:
                    st.error("请填写猪只和药品名称")

        st.subheader("📋 用药记录")
        df = execute_query("""
            SELECT p.ear_tag, t.drug_name, t.batch_number, t.dosage, t.admin_date, t.reason, t.veterinarian
            FROM treatments t
            JOIN pigs p ON t.pig_id = p.id
            ORDER BY t.admin_date DESC
        """, fetch=True)
        if df is not None and not df.empty:
            st.dataframe(translate_columns(df), use_container_width=True)
        else:
            st.info("暂无用药记录")

    # ========== Tab 6: 饲料记录 ==========
    with tabs[6]:
        st.subheader("➕ 新增饲喂记录")
        with st.form("add_feed"):
            pig_id = st.selectbox("猪只（可选，若按栏记录则留空）", options=[None] + list(pig_options.keys()), format_func=lambda x: pig_options[x] if x else "按猪舍记录")
            pigsty_id = st.selectbox("猪舍（若按猪舍记录必填）", options=[None] + list(pigsty_options.keys()), format_func=lambda x: pigsty_options[x] if x else "不指定")
            feed_name = st.text_input("饲料名称 *")
            feed_batch = st.text_input("饲料批次")
            amount = st.number_input("用量 (kg) *", min_value=0.1, step=0.1)
            feed_date = st.date_input("饲喂日期")
            operator = st.text_input("操作人")
            if st.form_submit_button("记录饲喂"):
                if feed_name and amount and (pig_id or pigsty_id):
                    execute_query("""
                        INSERT INTO feed_records (pig_id, pigsty_id, feed_name, feed_batch, amount_kg, feed_date, operator)
                        VALUES (%s, %s, %s, %s, %s, %s, %s)
                    """, (pig_id, pigsty_id, feed_name, feed_batch, amount, feed_date, operator))
                    st.success("✅ 饲喂记录已保存！")
                    st.rerun()
                else:
                    st.error("请至少指定猪只或猪舍，并填写饲料名称和用量")

        st.subheader("📋 饲喂记录")
        df = execute_query("""
            SELECT 
                COALESCE(p.ear_tag, '栏位饲喂') as target,
                ps.name as pigsty,
                f.feed_name,
                f.feed_batch,
                f.amount_kg,
                f.feed_date,
                f.operator
            FROM feed_records f
            LEFT JOIN pigs p ON f.pig_id = p.id
            LEFT JOIN pigsties ps ON f.pigsty_id = ps.id
            ORDER BY f.feed_date DESC
        """, fetch=True)
        if df is not None and not df.empty:
            st.dataframe(translate_columns(df), use_container_width=True)
        else:
            st.info("暂无饲喂记录")

    # ========== Tab 7: 出栏销售 ==========
    with tabs[7]:
        st.subheader("➕ 新增销售记录")
        with st.form("add_sale"):
            pig_id = st.selectbox("猪只 *", options=list(pig_options.keys()), format_func=lambda x: pig_options[x])
            sale_date = st.date_input("销售日期")
            weight = st.number_input("销售体重 (kg)", min_value=0.1, step=0.1)
            price = st.number_input("单价 (元/kg)", min_value=0.0, step=0.1)
            buyer = st.text_input("买家")
            dest = st.text_input("去向（屠宰场/市场）")
            sale_type = st.selectbox("销售类型", ["活猪销售", "屠宰"])
            if st.form_submit_button("记录销售"):
                if pig_id:
                    # 更新猪只状态
                    status = "已屠宰" if sale_type == "屠宰" else "已出栏"
                    execute_query("UPDATE pigs SET status = %s WHERE id = %s", (status, pig_id))
                    # 插入销售记录
                    execute_query("""
                        INSERT INTO sales (pig_id, sale_date, weight_kg, price_per_kg, buyer_name, destination, sale_type)
                        VALUES (%s, %s, %s, %s, %s, %s, %s)
                    """, (pig_id, sale_date, weight, price, buyer, dest, sale_type))
                    st.success("✅ 销售记录已保存！")
                    st.rerun()
                else:
                    st.error("请选择猪只")

        st.subheader("📋 销售记录")
        df = execute_query("""
            SELECT p.ear_tag, s.sale_date, s.weight_kg, s.price_per_kg, s.buyer_name, s.destination, s.sale_type
            FROM sales s
            JOIN pigs p ON s.pig_id = p.id
            ORDER BY s.sale_date DESC
        """, fetch=True)
        if df is not None and not df.empty:
            st.dataframe(translate_columns(df), use_container_width=True)
        else:
            st.info("暂无销售记录")

    # ========== Tab 8: 屠宰溯源 ==========
    with tabs[8]:
        st.subheader("➕ 新增屠宰记录")
        with st.form("add_slaughter"):
            pig_id = st.selectbox("猪只 *", options=list(pig_options.keys()), format_func=lambda x: pig_options[x])
            slaughter_date = st.date_input("屠宰日期")
            slaughterhouse = st.text_input("屠宰场")
            carcass_weight = st.number_input("胴体重 (kg)", min_value=0.1, step=0.1)
            meat_batch = st.text_input("肉品批次号")
            inspector = st.text_input("检疫员")
            if st.form_submit_button("记录屠宰"):
                if pig_id:
                    execute_query("UPDATE pigs SET status = '已屠宰' WHERE id = %s", (pig_id,))
                    execute_query("""
                        INSERT INTO slaughter_records (pig_id, slaughter_date, slaughterhouse, carcass_weight_kg, meat_batch_number, inspector)
                        VALUES (%s, %s, %s, %s, %s, %s)
                    """, (pig_id, slaughter_date, slaughterhouse, carcass_weight, meat_batch, inspector))
                    st.success("✅ 屠宰记录已保存！")
                    st.rerun()
                else:
                    st.error("请选择猪只")

        st.subheader("📋 屠宰记录")
        df = execute_query("""
            SELECT p.ear_tag, sl.slaughter_date, sl.slaughterhouse, sl.carcass_weight_kg, sl.meat_batch_number, sl.inspector
            FROM slaughter_records sl
            JOIN pigs p ON sl.pig_id = p.id
            ORDER BY sl.slaughter_date DESC
        """, fetch=True)
        if df is not None and not df.empty:
            st.dataframe(translate_columns(df), use_container_width=True)
        else:
            st.info("暂无屠宰记录")

    # ========== Tab 9: 全流程数据分析 ==========
    with tabs[9]:
        st.subheader("📈 生猪养殖全流程数据洞察")

        # 1. 猪只状态分布
        status_df = execute_query("SELECT status, COUNT(*) as count FROM pigs GROUP BY status", fetch=True)
        if status_df is not None and not status_df.empty:
            fig1 = px.pie(status_df, values='count', names='status', title="猪只当前状态分布", 
                          color_discrete_sequence=px.colors.qualitative.Set3)
            fig1.update_traces(textinfo='percent+label')
            st.plotly_chart(fig1, use_container_width=True)

        # 2. 月度出栏趋势
        sales_trend = execute_query("""
            SELECT DATE_TRUNC('month', sale_date)::DATE as month, 
                   COUNT(*) as sales_count,
                   SUM(weight_kg) as total_weight
            FROM sales 
            GROUP BY month 
            ORDER BY month
        """, fetch=True)
        if sales_trend is not None and not sales_trend.empty:
            fig2 = px.bar(sales_trend, x='month', y='sales_count', 
                          title="月度出栏数量趋势", 
                          labels={"month": "月份", "sales_count": "出栏数量"},
                          color_discrete_sequence=["#636EFA"])
            st.plotly_chart(fig2, use_container_width=True)

        # 3. 免疫 vs 用药频次（按药品/疫苗名）
        vac_top = execute_query("""
            SELECT vaccine_name as name, COUNT(*) as freq 
            FROM vaccinations 
            GROUP BY vaccine_name 
            ORDER BY freq DESC 
            LIMIT 5
        """, fetch=True)
        treat_top = execute_query("""
            SELECT drug_name as name, COUNT(*) as freq 
            FROM treatments 
            GROUP BY drug_name 
            ORDER BY freq DESC 
            LIMIT 5
        """, fetch=True)

        col1, col2 = st.columns(2)
        with col1:
            if vac_top is not None and not vac_top.empty:
                fig3 = px.bar(vac_top, x='freq', y='name', orientation='h',
                              title="高频疫苗使用TOP5",
                              labels={"name": "疫苗名称", "freq": "使用次数"},
                              color_discrete_sequence=["#EF553B"])
                st.plotly_chart(fig3, use_container_width=True)
        with col2:
            if treat_top is not None and not treat_top.empty:
                fig4 = px.bar(treat_top, x='freq', y='name', orientation='h',
                              title="高频药品使用TOP5",
                              labels={"name": "药品名称", "freq": "使用次数"},
                              color_discrete_sequence=["#00CC96"])
                st.plotly_chart(fig4, use_container_width=True)

        # 4. 饲料月度消耗
        feed_trend = execute_query("""
            SELECT DATE_TRUNC('month', feed_date)::DATE as month,
                   SUM(amount_kg) as total_feed
            FROM feed_records
            GROUP BY month
            ORDER BY month
        """, fetch=True)
        if feed_trend is not None and not feed_trend.empty:
            fig5 = px.line(feed_trend, x='month', y='total_feed',
                           title="月度饲料消耗趋势",
                           labels={"month": "月份", "total_feed": "饲料总量(kg)"},
                           markers=True)
            st.plotly_chart(fig5, use_container_width=True)

        # 5. 屠宰率 vs 出栏类型
        slaughter_count = execute_query("SELECT COUNT(*) as cnt FROM slaughter_records", fetch=True)
        sale_count = execute_query("SELECT COUNT(*) as cnt FROM sales WHERE sale_type = '活猪销售'", fetch=True)
        s_cnt = slaughter_count['cnt'].iloc[0] if slaughter_count is not None else 0
        l_cnt = sale_count['cnt'].iloc[0] if sale_count is not None else 0

        if s_cnt + l_cnt > 0:
            out_type_df = pd.DataFrame({
                "类型": ["屠宰", "活猪销售"],
                "数量": [s_cnt, l_cnt]
            })
            fig6 = px.pie(out_type_df, values='数量', names='类型', title="出栏类型占比")
            st.plotly_chart(fig6, use_container_width=True)