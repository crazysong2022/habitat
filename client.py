# client.py - 客户项目门户（云端安全执行）
import streamlit as st
import os
import importlib.util
import sys
from urllib.parse import urlparse
import psycopg2
import bcrypt

# -----------------------------
# 加载环境变量
# -----------------------------
from dotenv import load_dotenv
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


# -----------------------------
# 检查项目是否存在
# -----------------------------
def project_exists(project_name: str) -> bool:
    return os.path.exists(f"projects/{project_name}/main.py")


# -----------------------------
# 动态运行项目模块
# -----------------------------
def run_project_app(project_name: str):
    project_path = f"projects/{project_name}/main.py"

    if not os.path.exists(project_path):
        st.error(f"❌ 项目文件未找到: {project_path}")
        return

    try:
        # 动态导入模块
        spec = importlib.util.spec_from_file_location(f"project_{project_name}", project_path)
        module = importlib.util.module_from_spec(spec)

        # 注入 streamlit 到 sys.modules，避免导入问题
        sys.modules[f"project_{project_name}"] = module

        # 执行模块
        spec.loader.exec_module(module)

        # 如果模块有 run() 函数，优先调用
        if hasattr(module, "run"):
            module.run()

    except Exception as e:
        st.error(f"❌ 运行项目失败：{e}")
        st.code(f"Traceback:\n{e}", language="traceback")


# -----------------------------
# 渲染客户端登录与执行界面
# -----------------------------
def render(t):
    st.title(t("client_title"))
    st.markdown(t("client_intro"))
    st.markdown("---")

    if "client_authenticated" not in st.session_state:
        _show_login_form(t)
    else:
        _show_dashboard(t)


def _show_login_form(t):
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
            if project_name and project_exists(project_name):
                st.session_state.client_authenticated = True
                st.session_state.project_name = project_name
                st.session_state.username = username.strip()
                st.rerun()
            else:
                st.error(t("client_error_invalid") if not project_name else t("client_error_no_project").format(project=project_name))


def _show_dashboard(t):
    st.success(f"✅ {t('client_welcome')} {st.session_state.username}!")
    st.info(f"{t('client_your_project')}: **{st.session_state.project_name}**")

    if st.button(t("client_run_app")):
        st.markdown("---")
        run_project_app(st.session_state.project_name)

    if st.button(t("client_logout")):
        for key in ["client_authenticated", "project_name", "username"]:
            st.session_state.pop(key, None)
        st.rerun()