"""
fetch_messages.py
Admin 模块：查看所有用户留言
功能：密码保护 + 数据查询 + 表格展示 + CSV 下载
依赖：.env 中的 DATABASE_URL 和 ADMIN_PASSWORD
"""

import streamlit as st
import pandas as pd
import psycopg2
from urllib.parse import urlparse
from dotenv import load_dotenv
import os


# -----------------------------
# 1. 加载环境变量
# -----------------------------
load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD")

if not DATABASE_URL:
    st.error("❌ Environment variable `DATABASE_URL` is not set. Please check `.env` file.")
    st.stop()

if not ADMIN_PASSWORD:
    st.error("❌ Environment variable `ADMIN_PASSWORD` is not set. Please check `.env` file.")
    st.stop()


# -----------------------------
# 2. 数据库连接
# -----------------------------
def get_db_connection():
    try:
        url = urlparse(DATABASE_URL)
        conn = psycopg2.connect(
            host=url.hostname,
            port=url.port or 5432,
            database=url.path[1:],  # 去掉开头的 '/'
            user=url.username,
            password=url.password,
        )
        return conn
    except Exception as e:
        st.error(f"❌ Database connection failed: {e}")
        return None


# -----------------------------
# 3. 查询所有留言
# -----------------------------
def load_messages():
    conn = get_db_connection()
    if not conn:
        return None
    try:
        query = """
        SELECT 
            name,
            email,
            subject,
            message,
            submitted_at AT TIME ZONE 'UTC' AT TIME ZONE 'Asia/Shanghai' AS received_at
        FROM contact_messages
        ORDER BY submitted_at DESC
        """
        df = pd.read_sql_query(query, conn)
        conn.close()
        return df
    except Exception as e:
        st.error("❌ Failed to load message data.")
        st.exception(e)
        return None


# -----------------------------
# 4. 渲染 Admin 页面（保持英文）
# -----------------------------
def render(t=None):
    """
    渲染管理员页面（仅英文）
    :param t: 翻译函数（不使用，仅为了兼容）
    """
    st.title("🔐 Admin Panel - All Messages")
    st.markdown("Enter your password to view all user messages.")

    # 使用 session_state 管理登录状态
    if "authenticated" not in st.session_state:
        pwd = st.text_input("Password", type="password")
        if st.button("Login"):
            if pwd == ADMIN_PASSWORD:
                st.session_state.authenticated = True
                st.rerun()
            else:
                st.error("❌ Incorrect password.")
        return

    # 已登录：显示数据
    st.success("✅ Authorized")
    st.markdown("---")

    df = load_messages()

    if df is not None and not df.empty:
        st.markdown(f"**📬 Total Messages: {len(df)}**")
        st.dataframe(
            df,
            use_container_width=True,
            hide_index=True,
            column_config={
                "received_at": st.column_config.DatetimeColumn(
                    "Received Time (CST)",
                    format="YYYY-MM-DD HH:mm:ss"
                ),
                "message": st.column_config.TextColumn("Message", width="large")
            }
        )

        # CSV 下载功能
        @st.cache_data
        def convert_df_to_csv(_df):
            return _df.to_csv(index=False).encode('utf-8')

        csv = convert_df_to_csv(df)
        st.download_button(
            label="📥 Download as CSV",
            data=csv,
            file_name=f"messages_export_{pd.Timestamp.now().strftime('%Y%m%d_%H%M')}.csv",
            mime="text/csv",
        )
    else:
        st.info("📭 No messages have been submitted yet.")

    # 退出按钮
    if st.button("Logout"):
        del st.session_state.authenticated
        st.rerun()