# client.py - 客户项目门户（双语支持）
import streamlit as st
import os
import subprocess
import sys
import time
import psycopg2
from urllib.parse import urlparse
from dotenv import load_dotenv
import bcrypt
import socket
# -----------------------------
# 加载环境变量
# -----------------------------
load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    st.error("❌ DATABASE_URL is not set.")
    st.stop()

try:
    url = urlparse(DATABASE_URL)
    DB_CONFIG = {
        "host": url.hostname,
        "port": url.port,
        "database": url.path[1:],
        "user": url.username,
        "password": url.password,
    }
except Exception as e:
    st.error(f"❌ Failed to parse database URL: {e}")
    st.stop()


# -----------------------------
# 数据库连接
# -----------------------------
def get_db_connection():
    try:
        return psycopg2.connect(**DB_CONFIG)
    except Exception as e:
        st.error(f"🔗 Database connection failed: {e}")
        return None

def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return bcrypt.checkpw(plain_password.encode('utf-8'), hashed_password.encode('utf-8'))
# -----------------------------
# 验证用户登录
# -----------------------------
def verify_user(username: str, password: str):
    conn = get_db_connection()
    if not conn:
        return None
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT password_hash, project_name FROM users WHERE username = %s", (username,))
            row = cur.fetchone()
            if row:
                password_hash, project_name = row
                if bcrypt.checkpw(password.encode('utf-8'), password_hash.encode('utf-8')):
                    return project_name
            return None
    except Exception as e:
        st.error(f"❌ Login failed: {e}")
        return None
    finally:
        conn.close()

def project_exists(project_name: str) -> bool:
    project_dir = f"projects/{project_name}"
    app_path = f"{project_dir}/app.py"
    return os.path.exists(app_path)

# -----------------------------
# 检查项目是否存在
# -----------------------------
def find_free_port():
    """找一个空闲端口"""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("", 0))
        s.listen(1)
        port = s.getsockname()[1]
        return port

def run_project_app(project_name: str):
    project_path = f"projects/{project_name}"
    app_path = f"{project_path}/app.py"

    if not os.path.exists(app_path):
        st.error(f"❌ Project app.py not found: {app_path}")
        return

    # ✅ 自动找空闲端口
    port = find_free_port()

    try:
        proc = subprocess.Popen(
            [
                "streamlit", "run", "app.py",
                f"--server.port={port}",
                "--server.headless=true",
                "--browser.gatherUsageStats=false"
            ],
            cwd=project_path,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding='utf-8'
        )

        # 等待几秒看是否启动成功
        time.sleep(3)
        if proc.poll() is not None:
            stderr = proc.stderr.read()
            st.error("❌ Failed to start Streamlit app:")
            st.code(stderr)
            return

        # ✅ 启动成功
        st.success("✅ Project is running!")
        url = f"http://localhost:{port}"
        st.markdown(f"🔗 **Access your project:**")
        st.markdown(f"<a href='{url}' target='_blank' style='font-size: 1.1em;'>👉 Open Project {project_name} (Port {port})</a>", unsafe_allow_html=True)

    except Exception as e:
        st.error(f"❌ Error: {e}")


# -----------------------------
# 渲染客户端登录与执行界面
# -----------------------------
def render(t):
    st.title(t("client_title"))
    st.markdown(t("client_intro"))
    st.markdown("---")

    # 会话状态：是否已登录
    if "client_authenticated" not in st.session_state:
        _show_login_form(t)
    else:
        _show_dashboard(t)


def _show_login_form(t):
    """显示登录表单"""
    st.subheader(t("client_login"))

    username = st.text_input(t("client_username"), key="login_user")
    password = st.text_input(t("client_password"), type="password", key="login_pwd")

    if st.button(t("client_login_button")):
        if not username.strip():
            st.error(t("client_error_username"))
        elif not password:
            st.error(t("client_error_password"))
        else:
            project_name = verify_user(username.strip(), password)
            if project_name:
                if project_exists(project_name):
                    st.session_state.client_authenticated = True
                    st.session_state.project_name = project_name
                    st.session_state.username = username.strip()
                    st.rerun()
                else:
                    st.error(t("client_error_no_project").format(project=project_name))
            else:
                st.error(t("client_error_invalid"))


def _show_dashboard(t):
    """已登录：显示项目信息和运行按钮"""
    st.success(f"✅ {t('client_welcome')} {st.session_state.username}!")
    st.info(f"{t('client_your_project')}: **{st.session_state.project_name}**")

    if st.button(t("client_run_app")):
        with st.spinner(t("client_running")):
            run_project_app(st.session_state.project_name)

    if st.button(t("client_logout")):
        del st.session_state.client_authenticated
        del st.session_state.project_name
        del st.session_state.username
        st.rerun()