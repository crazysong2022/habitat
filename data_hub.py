# data_hub.py
"""
Data Hub Module: PostgreSQL ↔ Snowflake Sync & Browse
功能：密码保护 + 多数据库浏览 + Schema 映射 + 安全同步
依赖：.env 中的 ADMIN_PASSWORD + PostgreSQL/Snowflake 连接信息
"""

import streamlit as st
import pandas as pd
from dotenv import load_dotenv
import snowflake.connector
import os
from sqlalchemy import create_engine
import urllib.parse

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
# 2. 数据枢纽核心逻辑
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

@st.cache_resource
def get_snowflake_connector_conn():
    try:
        conn = snowflake.connector.connect(
            account=os.getenv("SNOWFLAKE_ACCOUNT"),
            user=os.getenv("SNOWFLAKE_USER"),
            password=os.getenv("SNOWFLAKE_PASSWORD"),
            warehouse=os.getenv("SNOWFLAKE_WAREHOUSE"),
            database=os.getenv("SNOWFLAKE_DATABASE"),
            schema=os.getenv("SNOWFLAKE_SCHEMA")
        )
        return conn
    except Exception as e:
        st.error(f"❌ Snowflake connection failed: {e}")
        return None

@st.cache_resource
def create_snowflake_sqlalchemy_engine():
    try:
        password = urllib.parse.quote_plus(os.getenv("SNOWFLAKE_PASSWORD"))
        user = urllib.parse.quote_plus(os.getenv("SNOWFLAKE_USER"))
        conn_string = (
            f"snowflake://{user}:{password}@{os.getenv('SNOWFLAKE_ACCOUNT')}/"
            f"{os.getenv('SNOWFLAKE_DATABASE')}?warehouse={os.getenv('SNOWFLAKE_WAREHOUSE')}"
        )
        return create_engine(conn_string)
    except Exception as e:
        st.error(f"❌ Failed to create Snowflake SQLAlchemy engine: {e}")
        return None

def get_sf_schemas():
    try:
        query = f"SHOW SCHEMAS IN DATABASE {os.getenv('SNOWFLAKE_DATABASE')};"
        df = pd.read_sql(query, get_snowflake_connector_conn())
        return df['name'].tolist()
    except Exception as e:
        st.error(f"❌ Failed to get schemas: {e}")
        return []

def create_sf_schema(schema_name):
    try:
        with get_snowflake_connector_conn().cursor() as cur:
            cur.execute(f'CREATE SCHEMA IF NOT EXISTS "{schema_name.upper()}"')
        return True
    except Exception as e:
        st.error(f"❌ Failed to create schema {schema_name}: {e}")
        return False

def get_sf_tables_in_schema(schema):
    try:
        query = f'SHOW TABLES IN {os.getenv("SNOWFLAKE_DATABASE")}.{schema};'
        df = pd.read_sql(query, get_snowflake_connector_conn())
        return df['name'].tolist()
    except Exception as e:
        st.error(f"❌ Failed to get tables in {schema}: {e}")
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
    st.title("🔁 Data Hub - PostgreSQL ↔ Snowflake")
    st.markdown("Secure data sync and browse platform.")

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
    sf_conn = get_snowflake_connector_conn()
    sf_sqlalchemy_engine = create_snowflake_sqlalchemy_engine()

    if not sf_conn or not sf_sqlalchemy_engine:
        st.stop()

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
    # 导航菜单
    # -----------------------------
    st.sidebar.header("⚙️ Operation Mode")
    page = st.sidebar.radio("Select Function", [
        "📊 Browse PostgreSQL Tables",
        "📈 Browse Snowflake Tables",
        "🚀 Data Transfer",
        "🗺️ Auto Mapping Configuration"
    ])

    SNOWFLAKE_DATABASE = os.getenv("SNOWFLAKE_DATABASE")

    # -----------------------------
    # 页面逻辑
    # -----------------------------
    if page == "🗺️ Auto Mapping Configuration":
        st.subheader("🗺️ PostgreSQL → Snowflake Auto Mapping")
        st.markdown("""
        Configure how each PostgreSQL database maps to a Snowflake schema.
        - One PostgreSQL DB → One Snowflake Schema
        - Table names will be converted to uppercase
        """)

        sf_schemas = get_sf_schemas()
        mapping = {}
        for pg_db in pg_databases:
            default_schema = pg_db.upper()
            suggested = st.text_input(f"Map `{pg_db}` to Schema", default_schema, key=f"map_{pg_db}")
            mapping[pg_db] = suggested

        if st.button("Save Mapping & Ensure Schemas"):
            created = 0
            for pg_db, schema in mapping.items():
                if schema not in sf_schemas:
                    if create_sf_schema(schema):
                        created += 1
            if created:
                st.success(f"✅ Created {created} new schemas")
            else:
                st.info("✅ All schemas already exist")
            st.session_state.mapping = mapping
            st.success("💾 Mapping saved (current session)")

        if "mapping" in st.session_state:
            st.markdown("### Current Mapping")
            df_map = pd.DataFrame([
                {"PostgreSQL DB": k, "Snowflake Schema": v}
                for k, v in st.session_state.mapping.items()
            ])
            st.dataframe(df_map, use_container_width=True)

    elif page == "📊 Browse PostgreSQL Tables":
        tables = get_pg_tables(pg_engine)
        if not tables:
            st.info("No tables found in this database.")
        else:
            selected = st.selectbox("Select Table", tables)
            if st.button("Load Data"):
                try:
                    df = pd.read_sql(f'SELECT * FROM "{selected}" LIMIT 1000', pg_engine)
                    st.dataframe(df, use_container_width=True)
                    if len(df) > 0 and df.select_dtypes(include="number").columns.any():
                        st.bar_chart(df.set_index(df.columns[0]).select_dtypes(include="number").iloc[:30])
                except Exception as e:
                    st.error(f"❌ Query failed: {e}")

    elif page == "📈 Browse Snowflake Tables":
        sf_schemas = get_sf_schemas()
        selected_schema = st.selectbox("Select Schema", sf_schemas)
        tables = get_sf_tables_in_schema(selected_schema)
        if not tables:
            st.info(f"No tables in schema `{selected_schema}`")
        else:
            selected_table = st.selectbox("Select Table", tables)
            if st.button("Load Data"):
                try:
                    full = f'"{SNOWFLAKE_DATABASE}"."{selected_schema}"."{selected_table}"'
                    df = pd.read_sql(f"SELECT * FROM {full} LIMIT 100", sf_conn)
                    st.dataframe(df, use_container_width=True)
                    num_cols = df.select_dtypes(include="number").columns
                    if len(df) > 1 and len(num_cols) > 0:
                        st.bar_chart(df.set_index(df.columns[0])[num_cols[0]].head(30))
                except Exception as e:
                    st.error(f"❌ Query failed: {e}")

    elif page == "🚀 Data Transfer":
        st.subheader("🔄 Bidirectional Data Transfer")
        direction = st.radio("Direction", ["PostgreSQL → Snowflake", "Snowflake → PostgreSQL"])

        if direction == "PostgreSQL → Snowflake":
            tables = get_pg_tables(pg_engine)
            if not tables:
                st.info("No tables in this database")
            else:
                full_sync = st.checkbox("Sync Entire Database")
                if full_sync:
                    st.info(f"Will sync {len(tables)} tables from `{selected_pg_db}`")
                    target_schema = st.text_input("Target Schema", selected_pg_db.upper()).upper()
                    mode = st.radio("Write Mode", ["replace", "append"])
                    if st.button("Start Sync"):
                        create_sf_schema(target_schema)
                        success = 0
                        for t in tables:
                            try:
                                df = pd.read_sql(f'SELECT * FROM "{t}"', pg_engine)
                                df.to_sql(t.upper(), sf_sqlalchemy_engine, schema=target_schema, if_exists=mode, index=False)
                                success += 1
                            except Exception as e:
                                st.error(f"❌ {t}: {e}")
                        st.success(f"✅ Sync completed: {success}/{len(tables)} tables")
                else:
                    src = st.selectbox("Source Table (PG)", tables)
                    tgt_schema = st.text_input("Target Schema", selected_pg_db.upper()).upper()
                    tgt = st.text_input("Target Table Name", src.upper())
                    mode = st.radio("Write Mode", ["replace", "append"])
                    if st.button("Start Transfer"):
                        create_sf_schema(tgt_schema)
                        try:
                            df = pd.read_sql(f'SELECT * FROM "{src}"', pg_engine)
                            df.to_sql(tgt, sf_sqlalchemy_engine, schema=tgt_schema, if_exists=mode, index=False)
                            st.success(f"✅ Transferred to `{tgt_schema}.{tgt}`")
                        except Exception as e:
                            st.error(f"❌ Transfer failed: {e}")

        elif direction == "Snowflake → PostgreSQL":
            sf_schemas = get_sf_schemas()
            schema = st.selectbox("Source Schema", sf_schemas)
            tables = get_sf_tables_in_schema(schema)
            if not tables:
                st.info("No tables in this schema")
            else:
                src = st.selectbox("Source Table (SF)", tables)
                tgt = st.text_input("Target Table Name (PG)", src.lower())
                mode = st.radio("Write Mode", ["replace", "append"])
                if st.button("Start Transfer"):
                    try:
                        full = f'"{SNOWFLAKE_DATABASE}"."{schema}"."{src}"'
                        df = pd.read_sql(f"SELECT * FROM {full}", sf_conn)
                        df.to_sql(tgt, pg_engine, if_exists=mode, index=False)
                        st.success(f"✅ Transferred to `{selected_pg_db}.{tgt}`")
                    except Exception as e:
                        st.error(f"❌ Transfer failed: {e}")

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
        "- Safe data sync\n"
        "- Schema mapping\n"
        "- No direct table management"
    )