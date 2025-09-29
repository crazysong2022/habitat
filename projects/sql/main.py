# projects/your_project/main.py
import streamlit as st
import os
import json
import pandas as pd
from dotenv import load_dotenv
from sqlalchemy import create_engine, text, inspect
from openai import OpenAI
import tempfile

# -----------------------------
# 初始化
# -----------------------------
load_dotenv()

def get_ai_client():
    api_key = os.getenv("DASHSCOPE_API_KEY")
    base_url = os.getenv("DASHSCOPE_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1").strip()
    if not api_key:
        st.error("❌ 请在 .env 中设置 DASHSCOPE_API_KEY")
        st.stop()
    return OpenAI(api_key=api_key, base_url=base_url)

# -----------------------------
# 数据库连接管理
# -----------------------------
DB_TYPES = {
    "PostgreSQL": "postgresql",
    "MySQL": "mysql",
    "SQLite": "sqlite",
    "Oracle": "oracle"
}

def build_connection_string(db_type, config):
    if db_type == "postgresql":
        return f"postgresql://{config['user']}:{config['password']}@{config['host']}:{config['port']}/{config['database']}"
    elif db_type == "mysql":
        return f"mysql+pymysql://{config['user']}:{config['password']}@{config['host']}:{config['port']}/{config['database']}"
    elif db_type == "sqlite":
        return f"sqlite:///{config['file_path']}"
    elif db_type == "oracle":
        return f"oracle+cx_oracle://{config['user']}:{config['password']}@{config['host']}:{config['port']}/?service_name={config['service_name']}"
    else:
        raise ValueError("不支持的数据库类型")

def test_database_connection(db_type, config):
    try:
        if db_type == "sqlite":
            if "file_path" not in config:
                return False, "请上传 SQLite 文件"
            url = build_connection_string(db_type, config)
            engine = create_engine(url)
            with engine.connect() as conn:
                conn.execute(text("SELECT sqlite_version()"))
            return True, "✅ SQLite 连接成功"
        else:
            url = build_connection_string(db_type, config)
            engine = create_engine(url)
            with engine.connect() as conn:
                if db_type == "postgresql":
                    conn.execute(text("SELECT version()"))
                elif db_type == "mysql":
                    conn.execute(text("SELECT VERSION()"))
                elif db_type == "oracle":
                    conn.execute(text("SELECT * FROM v$version WHERE rownum = 1"))
            return True, "✅ 数据库连接成功"
    except Exception as e:
        return False, f"❌ 连接失败: {str(e)}"

def get_db_schema(db_type, config):
    try:
        url = build_connection_string(db_type, config)
        engine = create_engine(url)
        inspector = inspect(engine)
        schema = {}
        for table in inspector.get_table_names():
            cols = inspector.get_columns(table)
            schema[table] = [
                {"column": col["name"], "type": str(col["type"])}
                for col in cols
            ]
        return schema
    except Exception as e:
        st.error(f"获取 schema 失败: {e}")
        return {}

def execute_safe_query(db_type, config, sql):
    if not sql.strip().lower().startswith("select"):
        return None, "❌ 仅允许 SELECT 查询"
    dangerous = ["drop", "delete", "update", "insert", "alter", "create", "truncate"]
    if any(kw in sql.lower() for kw in dangerous):
        return None, "❌ 检测到危险操作"

    try:
        url = build_connection_string(db_type, config)
        engine = create_engine(url)
        with engine.connect() as conn:
            df = pd.read_sql(text(sql), conn)
        return df, None
    except Exception as e:
        return None, f"SQL 执行错误: {str(e)}"

# -----------------------------
# AI 助手：两阶段
# -----------------------------
def ask_ai_generate_sql(user_question: str, schema_info: dict):
    client = get_ai_client()
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

    system_prompt = f"""
数据库中包含以下表（名称区分大小写）：
{', '.join(schema_info.keys())}

完整结构：
{json.dumps(schema_info, indent=2, ensure_ascii=False)}

你必须调用 execute_sql_query 函数。
规则：
- 只生成 SELECT
- 表名和字段必须存在
- 用中文写 explanation
"""

    response = client.chat.completions.create(
        model="qwen-plus",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_question}
        ],
        tools=tools,
        tool_choice={"type": "function", "function": {"name": "execute_sql_query"}},
        temperature=0.1
    )

    tool_calls = response.choices[0].message.tool_calls
    if not tool_calls:
        return {"error": "模型未调用函数"}

    try:
        args = json.loads(tool_calls[0].function.arguments)
        sql = args.get("sql", "").strip()
        explanation = args.get("explanation", "").strip()
        if not sql:
            return {"error": "SQL 为空"}
        return {"sql": sql, "explanation": explanation}
    except Exception as e:
        return {"error": f"解析失败: {e}"}

def generate_natural_answer(user_question: str, sql: str, result_df: pd.DataFrame):
    client = get_ai_client()
    
    if result_df.empty:
        result_text = "查询返回空结果。"
    else:
        sample = result_df.head(10)
        result_text = sample.to_string(index=False)

    messages = [
        {
            "role": "system",
            "content": "你是一个专业的数据分析师。请根据用户的原始问题、执行的 SQL 和查询结果，用简洁、友好的自然语言直接回答用户。不要提 SQL，不要用技术术语，使用中文。"
        },
        {
            "role": "user",
            "content": f"原始问题：{user_question}\n\n执行的 SQL：{sql}\n\n查询结果：\n{result_text}"
        }
    ]

    response = client.chat.completions.create(
        model="qwen-plus",
        messages=messages,
        temperature=0.3
    )
    return response.choices[0].message.content.strip()

# -----------------------------
# 主应用
# -----------------------------
def run():
    st.title("🤖 AI 领导决策助手")
    st.caption("支持 PostgreSQL / MySQL / SQLite / Oracle ")

    # 1. 选择数据库类型
    db_type_name = st.selectbox("1️⃣ 选择数据库类型", list(DB_TYPES.keys()))
    db_type = DB_TYPES[db_type_name]

    # 2. 配置连接
    config = {}
    if db_type == "sqlite":
        uploaded_file = st.file_uploader("2️⃣ 上传 SQLite 文件 (.db, .sqlite)", type=["db", "sqlite"])
        if uploaded_file:
            with tempfile.NamedTemporaryFile(delete=False, suffix=".db") as tmp:
                tmp.write(uploaded_file.getvalue())
                config["file_path"] = tmp.name
    else:
        config["host"] = st.text_input("主机 (Host)", value="localhost")
        default_port = {"postgresql": 5432, "mysql": 3306, "oracle": 1521}
        config["port"] = st.number_input("端口 (Port)", value=default_port[db_type], min_value=1, max_value=65535)
        if db_type != "oracle":
            config["database"] = st.text_input("数据库名 (Database)")
        else:
            config["service_name"] = st.text_input("服务名 (Service Name)")
        config["user"] = st.text_input("用户名 (User)")
        config["password"] = st.text_input("密码 (Password)", type="password")

    # 3. 测试连接
    if st.button("🧪 测试连接"):
        if db_type == "sqlite" and "file_path" not in config:
            st.error("请先上传 SQLite 文件")
        elif db_type != "sqlite" and not all(
            config.get(k) for k in ["host", "port", "user", "password"] 
            if k in config
        ):
            st.error("请填写所有必要字段")
        else:
            success, msg = test_database_connection(db_type, config)
            if success:
                st.success(msg)
                st.session_state.db_config = config
                st.session_state.db_type = db_type
            else:
                st.error(msg)

    # 4. AI 助手
    if "db_config" in st.session_state:
        st.markdown("---")
        st.subheader("💬 问任何关于你数据的问题")

        schema = get_db_schema(st.session_state.db_type, st.session_state.db_config)
        if not schema:
            st.warning("无法加载数据结构")
            return

        if "ai_chat" not in st.session_state:
            st.session_state.ai_chat = []

        # 显示历史
        for msg in st.session_state.ai_chat:
            with st.chat_message("user"):
                st.markdown(msg["user"])
            with st.chat_message("assistant"):
                st.markdown(msg["answer"])
                if "sql" in msg:
                    with st.expander("🔍 技术详情"):
                        st.code(msg["sql"], language="sql")
                        st.dataframe(msg["df"], use_container_width=True)

        # 用户输入
        if prompt := st.chat_input("例如：最近利润最高的销售是哪笔？"):
            with st.chat_message("user"):
                st.markdown(prompt)

            with st.chat_message("assistant"):
                with st.spinner("🧠 AI 正在分析数据..."):
                    # 阶段1: 生成 SQL
                    ai_sql_result = ask_ai_generate_sql(prompt, schema)
                    if "error" in ai_sql_result:
                        st.error(ai_sql_result["error"])
                        st.session_state.ai_chat.append({
                            "user": prompt,
                            "answer": ai_sql_result["error"],
                            "sql": None,
                            "df": None
                        })
                        st.stop()

                    sql = ai_sql_result["sql"]
                    # 阶段2: 执行
                    df, exec_error = execute_safe_query(st.session_state.db_type, st.session_state.db_config, sql)
                    if exec_error:
                        st.error(exec_error)
                        st.session_state.ai_chat.append({
                            "user": prompt,
                            "answer": exec_error,
                            "sql": sql,
                            "df": None
                        })
                        st.stop()

                    # 阶段3: 生成自然语言回答
                    natural_answer = generate_natural_answer(prompt, sql, df)

                st.markdown(natural_answer)

                # 显示技术详情
                with st.expander("🔍 技术详情"):
                    st.code(sql, language="sql")
                    st.dataframe(df, use_container_width=True)

                # 保存到历史
                st.session_state.ai_chat.append({
                    "user": prompt,
                    "answer": natural_answer,
                    "sql": sql,
                    "df": df
                })

        st.markdown("---")
        if st.button("🗑️ 清除对话"):
            st.session_state.ai_chat = []
            st.rerun()