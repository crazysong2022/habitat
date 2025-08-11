# contact.py - 联系我们页面（双语支持）
import streamlit as st
import psycopg2
from urllib.parse import urlparse
import os
from dotenv import load_dotenv


# -----------------------------
# 1. 加载环境变量 & 解析数据库连接
# -----------------------------
load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    st.error("❌ DATABASE_URL is not set. Please check your .env file.")
    st.stop()

try:
    url = urlparse(DATABASE_URL)
    DB_CONFIG = {
        "host": url.hostname,
        "port": url.port,
        "database": url.path[1:],  # 去掉开头的 '/'
        "user": url.username,
        "password": url.password,
    }
except Exception as e:
    st.error(f"❌ Failed to parse database URL: {e}")
    st.stop()


def get_db_connection(t=None):
    """获取数据库连接"""
    try:
        return psycopg2.connect(**DB_CONFIG)
    except Exception as e:
        st.error(t("contact_conn_fail").format(error=str(e)) if t else f"🔗 Database connection failed: {e}")
        return None


# -----------------------------
# 2. 初始化表（如果不存在）
# -----------------------------
def init_database(t=None):
    conn = get_db_connection(t=t)
    if not conn:
        return False
    try:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS contact_messages (
                    id SERIAL PRIMARY KEY,
                    name VARCHAR(100) NOT NULL,
                    email VARCHAR(100) NOT NULL,
                    subject VARCHAR(100),
                    message TEXT NOT NULL,
                    submitted_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
                );
            """)
            conn.commit()
        return True
    except Exception as e:
        st.error(t("contact_db_init_fail").format(error=str(e)))
        conn.rollback()
        return False
    finally:
        conn.close()


# -----------------------------
# 3. 保存留言
# -----------------------------
def save_message(name: str, email: str, subject: str, message: str, t=None):
    conn = get_db_connection(t=t)
    if not conn:
        return False
    try:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO contact_messages (name, email, subject, message)
                VALUES (%s, %s, %s, %s)
            """, (name, email, subject or "No Subject", message))
            conn.commit()
        return True
    except Exception as e:
        st.error(t("contact_save_fail").format(error=str(e)))
        conn.rollback()
        return False
    finally:
        conn.close()


# -----------------------------
# 4. 渲染 Contact 页面 UI
# -----------------------------
def render(t):
    """
    渲染联系页面
    :param t: 翻译函数，t(key) -> str
    """
    st.title(t("contact_title"))
    st.markdown(t("contact_intro_full"))

    # 确保表存在
    if not init_database(t=t):
        st.error(t("contact_init_error"))
        return

    with st.form("contact_form"):
        name = st.text_input(
            t("contact_name"),
            placeholder=t("contact_name_placeholder")
        )
        email = st.text_input(
            t("contact_email"),
            placeholder=t("contact_email_placeholder")
        )
        subject = st.text_input(
            t("contact_subject"),
            placeholder=t("contact_subject_placeholder")
        )
        message = st.text_area(
            t("contact_message"),
            placeholder=t("contact_message_placeholder"),
            height=150
        )

        submitted = st.form_submit_button(t("contact_send"))

        if submitted:
            if not name.strip():
                st.error(t("contact_error_name"))
            elif "@" not in email:
                st.error(t("contact_error_email"))
            elif not message.strip():
                st.error(t("contact_error_message"))
            else:
                success = save_message(
                    name=name.strip(),
                    email=email.strip(),
                    subject=subject.strip(),
                    message=message.strip(),
                    t=t  # ✅ 传入 t
                )
                if success:
                    st.success(t("contact_success_title"))
                    st.info(t("contact_success_info"))
                else:
                    st.error(t("contact_save_fail").format(error="Save failed"))