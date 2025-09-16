"""
Data Hub Module: PostgreSQL Data Browser (Snowflake部分已注释)
功能：密码保护 + 多数据库浏览 + 表数据查看
依赖：.env 中的 ADMIN_PASSWORD + PostgreSQL 连接信息
"""

import streamlit as st
import pandas as pd
from dotenv import load_dotenv
import os
from sqlalchemy import create_engine

# -----------------------------
# 1. 加载环境变量
# -----------------------------
load_dotenv()

# 密码保护
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD")
if not ADMIN_PASSWORD:
    st.error("❌ Environment variable `ADMIN_PASSWORD` is not set. Please check `.env` file.")
    st.stop()

# -----------------------------
# 2. 数据枢纽核心逻辑（仅 PostgreSQL）
# -----------------------------
def get_postgres_engine(db_name=None):
    try:
        user = os.getenv("PG_SUPER_USER")
        password = os.getenv("PG_SUPER_PASSWORD")
        host = os.getenv("PG_HOST")
        port = os.getenv("PG_PORT")
        default_db = os.getenv("PG_DEFAULT_DB", "postgres")
        db = db_name or default_db
        conn_string = f"postgresql://{user}:{password}@{host}:{port}/{db}"
        engine = create_engine(conn_string)
        with engine.connect() as conn:
            pass
        return engine
    except Exception as e:
        st.error(f"❌ Failed to connect to PostgreSQL {db}: {e}")
        return None

def get_postgres_databases():
    try:
        default_engine = get_postgres_engine(None)
        if not default_engine:
            return []
        query = """
        SELECT datname FROM pg_database 
        WHERE datistemplate = false 
          AND datname NOT IN ('postgres', 'template0', 'template1')
        ORDER BY datname;
        """
        df = pd.read_sql(query, default_engine)
        return df['datname'].tolist()
    except Exception as e:
        st.error(f"❌ Failed to fetch database list: {e}")
        return []

def get_pg_tables(engine):
    try:
        tables = pd.read_sql("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public'
        """, engine)
        return tables['table_name'].tolist()
    except Exception as e:
        st.error(f"❌ Failed to get tables: {e}")
        return []

# -----------------------------
# 3. 渲染函数（兼容主程序调用）
# -----------------------------
def render(t=None):
    """
    渲染数据枢纽页面（仅英文）
    :param t: 翻译函数（不使用，仅为了兼容）
    """
    st.title("🗃️ Data Hub - PostgreSQL Browser")
    st.markdown("Secure PostgreSQL data browse platform.")

    # -----------------------------
    # 密码保护
    # -----------------------------
    if "authenticated" not in st.session_state:
        pwd = st.text_input("Password", type="password")
        if st.button("Login"):
            if pwd == ADMIN_PASSWORD:
                st.session_state.authenticated = True
                st.rerun()
            else:
                st.error("❌ Incorrect password.")
        return

    st.success("✅ Authorized")
    st.markdown("---")

    # -----------------------------
    # 初始化连接
    # -----------------------------
    pg_databases = get_postgres_databases()
    if not pg_databases:
        st.warning("⚠️ No PostgreSQL databases found.")
        return

    # -----------------------------
    # 侧边栏：选择数据库
    # -----------------------------
    st.sidebar.header("🗃️ PostgreSQL Databases")
    selected_pg_db = st.sidebar.selectbox("Select Database", pg_databases, key="select_pg_db")

    @st.cache_resource
    def get_current_pg_engine(db_name):
        return get_postgres_engine(db_name)

    pg_engine = get_current_pg_engine(selected_pg_db)
    if not pg_engine:
        st.error(f"❌ Cannot connect to {selected_pg_db}")
        return

    # -----------------------------
    # 导航菜单（仅保留 PostgreSQL 相关）
    # -----------------------------
    st.sidebar.header("⚙️ Operation Mode")
    page = st.sidebar.radio("Select Function", [
        "📊 Browse PostgreSQL Tables",
        # "📈 Browse Snowflake Tables",  # ❌ 注释掉
        # "🚀 Data Transfer",            # ❌ 注释掉（除非你想保留 PG→PG 或导出）
        # "🗺️ Auto Mapping Configuration" # ❌ 注释掉
    ])

    # -----------------------------
    # 页面逻辑（仅 PostgreSQL 浏览）
    # -----------------------------
    if page == "📊 Browse PostgreSQL Tables":
        tables = get_pg_tables(pg_engine)
        if not tables:
            st.info("No tables found in this database.")
        else:
            selected = st.selectbox("Select Table", tables)
            limit = st.number_input("Row Limit", min_value=1, max_value=10000, value=1000, step=100)
            if st.button("Load Data"):
                try:
                    df = pd.read_sql(f'SELECT * FROM "{selected}" LIMIT {int(limit)}', pg_engine)
                    st.write(f"### Table: `{selected}` ({len(df)} rows)")
                    st.dataframe(df, use_container_width=True)
                except Exception as e:
                    st.error(f"❌ Query failed: {e}")

    # ❌ 注释掉以下所有 Snowflake 相关页面逻辑
    # elif page == "📈 Browse Snowflake Tables":
    #     ... 

    # elif page == "🚀 Data Transfer":
    #     ...

    # elif page == "🗺️ Auto Mapping Configuration":
    #     ...

    # -----------------------------
    # 退出按钮
    # -----------------------------
    st.sidebar.markdown("---")
    if st.sidebar.button("Logout"):
        del st.session_state.authenticated
        st.rerun()

    st.sidebar.info(
        "✅ Features:\n"
        "- Read-only browsing\n"
        "- Switch between databases\n"
        "- Preview tables & charts\n"
        "- Password protected"
    )