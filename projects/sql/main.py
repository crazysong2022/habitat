import streamlit as st
import os
import json
import pandas as pd
from dotenv import load_dotenv
from sqlalchemy import create_engine, text, inspect
import plotly.express as px
from openai import OpenAI
import tempfile
import uuid

load_dotenv()

# -----------------------------  AI 客户端 ----------------------------- #
def get_ai_client():
    api_key = os.getenv("DASHSCOPE_API_KEY")
    base_url = os.getenv("DASHSCOPE_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1 ").strip()
    if not api_key:
        st.error("❌ 请在 .env 中设置 DASHSCOPE_API_KEY")
        st.stop()
    return OpenAI(api_key=api_key, base_url=base_url)

# -----------------------------  数据库连接 ----------------------------- #
DB_TYPES = {"PostgreSQL": "postgresql", "MySQL": "mysql", "SQLite": "sqlite", "Oracle": "oracle"}

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

# -----------------------------  参数化执行 SQL ----------------------------- #
def execute_safe_query(db_type, config, sql: str, params: dict):
    if not sql.strip().lower().startswith("select"):
        return None, "❌ 仅允许 SELECT 查询"
    dangerous = ["drop", "delete", "update", "insert", "alter", "create", "truncate"]
    if any(kw in sql.lower() for kw in dangerous):
        return None, "❌ 检测到危险关键字（仅允许 SELECT 查询）"
    try:
        # Excel 转表模式：config 里只有 table 字段
        if config.get("table") and "host" not in config:
            engine = create_engine(os.getenv("DATABASE_URL"), pool_pre_ping=True)
        else:
            url = build_connection_string(db_type, config)
            engine = create_engine(url, pool_pre_ping=True)
        with engine.connect() as conn:
            stmt = text(sql).bindparams(**params)
            df = pd.read_sql(stmt, conn)
        return df, None
    except Exception as e:
        return None, f"SQL 执行错误: {str(e)}"

# -----------------------------  AI：生成参数化 SQL ----------------------------- #
def ask_ai_generate_sql(user_question: str, schema_info: dict):
    client = get_ai_client()
    tools = [{
        "type": "function",
        "function": {
            "name": "execute_sql_query",
            "description": "生成安全的 SELECT 查询（含占位符）",
            "parameters": {
                "type": "object",
                "properties": {
                    "sql": {"type": "string"},
                    "params": {"type": "object"},
                    "explanation": {"type": "string"}
                },
                "required": ["sql", "params", "explanation"]
            }
        }
    }]

    system_prompt = f"""
数据库中包含以下表（名称区分大小写）：
{', '.join(schema_info.keys())}

完整结构：
{json.dumps(schema_info, indent=2, ensure_ascii=False)}

【重要】
1. 只允许生成带占位符的 SELECT 语句，示例：
   SELECT col1, col2
   FROM table_name
   WHERE col3 = :param_1
     AND col4 > :param_2
   LIMIT 100
2. 把占位符对应的值也一起返回，格式：
   {{"sql": "...", "params": {{"param_1": "真实值1", "param_2": 真实值2}}, "explanation": "..."}}
3. 禁止把任何用户输入直接拼进 SQL 字符串。
4. explanation 用中文。
"""
    response = client.chat.completions.create(
        model=os.getenv("AI_MODEL", "qwen-plus"),
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
        return {"sql": args["sql"], "params": args.get("params", {}), "explanation": args["explanation"]}
    except Exception as e:
        return {"error": f"解析失败: {e}"}

# -----------------------------  自然语言回答 ----------------------------- #
def generate_natural_answer(user_question: str, sql: str, result_df: pd.DataFrame):
    client = get_ai_client()
    result_text = "查询返回空结果。" if result_df.empty else result_df.head(10).to_string(index=False)
    messages = [
        {"role": "system", "content": "你是一个专业的数据分析师。请根据用户的原始问题、执行的 SQL 和查询结果，用简洁、友好的自然语言直接回答用户。不要提 SQL，不要用技术术语，使用中文。"},
        {"role": "user", "content": f"原始问题：{user_question}\n\n执行的 SQL：{sql}\n\n查询结果：\n{result_text}"}
    ]
    response = client.chat.completions.create(
        model=os.getenv("AI_MODEL", "qwen-plus"),
        messages=messages,
        temperature=0.3
    )
    return response.choices[0].message.content.strip()
# -----------------------------  自动画图 ----------------------------- #
def auto_plot(df: pd.DataFrame) -> None:
    """
    根据查询结果自动选图并渲染到 Streamlit。
    规则极简：
      1. 只有 1 行 -> 画饼图（第一列是标签，第二列是数值）
      2. 只有 2 列且都是数值 -> 散点图
      3. 第一列是日期/字符串，其余列是数值 -> 折线/柱状
    失败就静默跳过，不阻断主流程。
    """
    if df.empty or df.shape[1] < 2:
        return

    try:
        # 列类型识别
        cols = df.columns.to_list()
        first_col = df[cols[0]]
        other_cols = cols[1:]

        # 1 行 -> 饼图
        if len(df) == 1:
            fig = px.pie(names=cols, values=df.iloc[0].tolist(),
                         title="结果占比")
            st.plotly_chart(fig, use_container_width=True)
            return

        # 2 列且全数值 -> 散点图
        if df.shape[1] == 2 and pd.api.types.is_numeric_dtype(df[cols[1]]):
            fig = px.scatter(df, x=cols[0], y=cols[1],
                             title=f"{cols[1]} 随 {cols[0]} 变化")
            st.plotly_chart(fig, use_container_width=True)
            return

        # 第一列是类别/日期，其余数值 -> 折线 or 柱状
        if pd.api.types.is_datetime64_any_dtype(first_col) or pd.api.types.is_object_dtype(first_col):
            # 长表变换，方便 Plotly 自动图例
            df_melt = df.melt(id_vars=cols[0], value_vars=other_cols,
                              var_name='指标', value_name='值')
            fig = px.line(df_melt, x=cols[0], y='值', color='指标',
                          markers=True, title="趋势图")
            st.plotly_chart(fig, use_container_width=True)
            return

        # 默认：第一列类别，第二列数值 -> 横向柱状
        if pd.api.types.is_numeric_dtype(df[cols[1]]):
            fig = px.bar(df, x=cols[1], y=cols[0], orientation='h',
                         title=f"{cols[1]} 排行")
            st.plotly_chart(fig, use_container_width=True)
            return

    except Exception:
        # 画不出来就拉倒
        pass
# -----------------------------  数据库 schema ----------------------------- #
def get_db_schema(db_type, config):
    from sqlalchemy import inspect
    try:
        if config.get("table") and "host" not in config:
            # Excel 模式：只查指定的临时表
            engine = create_engine(os.getenv("DATABASE_URL"), pool_pre_ping=True)
            inspector = inspect(engine)
            table_name = config["table"]
            if table_name not in inspector.get_table_names():
                return {}
            cols = inspector.get_columns(table_name)
            return {table_name: [{"column": col["name"], "type": str(col["type"])} for col in cols]}
        else:
            # 原有逻辑：查所有表
            engine = create_engine(build_connection_string(db_type, config), pool_pre_ping=True)
            inspector = inspect(engine)
            schema = {}
            for table in inspector.get_table_names():
                cols = inspector.get_columns(table)
                schema[table] = [{"column": col["name"], "type": str(col["type"])} for col in cols]
            return schema
    except Exception as e:
        st.error(f"获取 schema 失败: {e}")
        return {}

# -----------------------------  文件数据源 → PG 临时表 ----------------------------- #
def excel_to_postgresql(df: pd.DataFrame, table_name: str) -> str:
    """
    把 DataFrame 写入 habitat 库临时表，返回表名（temp_sessionid_xxx）
    """
    from sqlalchemy import create_engine, text
    url = os.getenv("DATABASE_URL")
    engine = create_engine(url, pool_pre_ping=True)
    temp_table = f"temp_{st.session_state.session_id}_{table_name}"
    with engine.begin() as conn:
        conn.execute(text(f'DROP TABLE IF EXISTS "{temp_table}"'))
        df.to_sql(temp_table, conn, index=False, method='multi', chunksize=5000)
    st.success(f"✅ 已把 Excel 写入 habitat 库临时表：{temp_table}")
    return temp_table

def load_dataframe_from_file(uploaded_file):
    try:
        if uploaded_file.name.endswith('.csv'):
            df = pd.read_csv(uploaded_file)
        elif uploaded_file.name.endswith(('.xlsx', '.xls')):
            df = pd.read_excel(uploaded_file)
        else:
            return None, "❌ 仅支持 .csv, .xlsx, .xls 文件"
        return df, None
    except Exception as e:
        return None, f"❌ 文件解析失败: {str(e)}"

# -----------------------------  聊天处理函数 ----------------------------- #
def db_chat_handler(prompt: str):
    schema = get_db_schema(st.session_state.db_type, st.session_state.db_config)
    if not schema:
        st.warning("无法加载数据结构")
        return
    with st.chat_message("assistant"):
        error_msg = None
        with st.spinner("🧠 AI 正在分析数据..."):
            ai_res = ask_ai_generate_sql(prompt, schema)
            if "error" in ai_res:
                error_msg = ai_res["error"]
            else:
                df, err = execute_safe_query(
                    st.session_state.db_type,
                    st.session_state.db_config,
                    ai_res["sql"],
                    ai_res["params"]
                )
                if err:
                    error_msg = err
                else:
                    answer = generate_natural_answer(prompt, ai_res["sql"], df)
        if error_msg:
            st.error(error_msg)
            st.session_state.ai_chat.append({"user": prompt, "answer": error_msg, "sql": None, "df": None})
        else:
            st.markdown(answer)
            with st.expander("🔍 技术详情"):
                st.code(ai_res["sql"], language="sql")
                st.dataframe(df, use_container_width=True)
                auto_plot(df)
            st.session_state.ai_chat.append({
                "user": prompt, "answer": answer,
                "sql": ai_res["sql"], "df": df
            })

def file_chat_handler(prompt: str):
    df = st.session_state.file_df
    temp_table = excel_to_postgresql(df, "excel_data")

    # 切换到数据库模式
    st.session_state.db_type = "postgresql"
    st.session_state.db_config = {"table": temp_table}
    st.session_state.data_mode = "database"

    # 补上缺失的初始化
    if "ai_chat" not in st.session_state:
        st.session_state.ai_chat = []

    # 继续走数据库问答流
    db_chat_handler(prompt)
def cleanup_temp_table(table_name: str):
    """安全删除临时表，带错误提示"""
    if not table_name or not table_name.startswith("temp_"):
        return  # 安全防护
    
    try:
        engine = create_engine(os.getenv("DATABASE_URL"), pool_pre_ping=True)
        with engine.begin() as conn:  # ✅ 确保事务提交
            result = conn.execute(text(f'DROP TABLE IF EXISTS "{table_name}"'))
        # 可选：记录日志
        # st.toast(f"✅ 已删除临时表: {table_name}", icon="🗑️")
    except Exception as e:
        st.error(f"❌ 删除临时表 '{table_name}' 失败: {str(e)}")
        raise  # 在调试阶段建议 raise，上线后可注释
def list_temp_tables():
    """列出 habitat 库中所有以 temp_ 开头的表"""
    try:
        engine = create_engine(os.getenv("DATABASE_URL"), pool_pre_ping=True)
        inspector = inspect(engine)
        all_tables = inspector.get_table_names()
        temp_tables = [t for t in all_tables if t.startswith("temp_")]
        return sorted(temp_tables)
    except Exception as e:
        st.error(f"获取临时表列表失败: {e}")
        return []
# -----------------------------  主页面 ----------------------------- #
def run():
    st.set_page_config(page_title="AI 领导决策助手", layout="wide")
    if "session_id" not in st.session_state:
        st.session_state.session_id = uuid.uuid4().hex[:8]
        if "excel_table" not in st.session_state:
            st.session_state.excel_table = None  # 当前正在用的临时表名
        if "excel_df" not in st.session_state:
            st.session_state.excel_df = None     # 缓存的 DataFrame，可选

    st.title("🤖 AI 领导决策助手（参数化版）")
    st.caption("支持 PostgreSQL / MySQL / SQLite / Oracle / Excel / CSV")

    data_source = st.radio("选择数据源类型", ("数据库", "Excel/CSV 文件"), horizontal=True)

    # ========== 数据库模式（原封不动） ========== #
    if data_source == "数据库":
        db_type_name = st.selectbox("1️⃣ 选择数据库类型", list(DB_TYPES.keys()))
        db_type = DB_TYPES[db_type_name]
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
            config["database"] = st.text_input("数据库名 (Database)") if db_type != "oracle" else None
            config["service_name"] = st.text_input("服务名 (Service Name)") if db_type == "oracle" else None
            config["user"] = st.text_input("用户名 (User)")
            config["password"] = st.text_input("密码 (Password)", type="password")

        if st.button("🧪 测试连接"):
            if db_type == "sqlite" and "file_path" not in config:
                st.error("请先上传 SQLite 文件")
            elif db_type != "sqlite" and not all(config.get(k) for k in ["host", "port", "user", "password"] if k in config):
                st.error("请填写所有必要字段")
            else:
                from sqlalchemy import inspect
                try:
                    engine = create_engine(build_connection_string(db_type, config))
                    with engine.connect() as conn:
                        conn.execute(text("SELECT 1"))
                    st.success("✅ 数据库连接成功")
                    st.session_state.db_config = config
                    st.session_state.db_type = db_type
                    st.session_state.data_mode = "database"
                except Exception as e:
                    st.error(f"❌ 连接失败: {e}")

        if "db_config" in st.session_state and st.session_state.get("data_mode") == "database":
            st.markdown("---")
            st.subheader("💬 问任何关于你数据的问题")
            schema = get_db_schema(st.session_state.db_type, st.session_state.db_config)
            if not schema:
                st.warning("无法加载数据结构")
                return
            if "ai_chat" not in st.session_state:
                st.session_state.ai_chat = []
            for msg in st.session_state.ai_chat:
                with st.chat_message("user"):
                    st.markdown(msg["user"])
                with st.chat_message("assistant"):
                    st.markdown(msg["answer"])
                    if "sql" in msg and msg["sql"] is not None:
                        with st.expander("🔍 技术详情"):
                            st.code(msg["sql"], language="sql")
                            st.dataframe(msg["df"], use_container_width=True)
            if prompt := st.chat_input("例如：最近利润最高的销售是哪笔？", key="db_chat_input"):
                with st.chat_message("user"):
                    st.markdown(prompt)
                st.session_state.ai_chat.append({"user": prompt, "answer": "", "sql": None, "df": None})
                db_chat_handler(prompt)
            if st.button("🗑️ 清除对话"):
                st.session_state.ai_chat = []
                st.rerun()

        # ========== Excel/CSV 文件模式 ========== #
    else:
                                # ========== 临时表管理（新增） ========== #
        with st.expander("🗑️ 临时表管理（手动清理）", expanded=False):
            temp_tables = list_temp_tables()
            if not temp_tables:
                st.info("暂无临时表")
            else:
                selected_tables = st.multiselect(
                    "选择要删除的临时表",
                    options=temp_tables,
                    default=[]
                )
                if st.button("💥 批量删除选中的临时表", type="secondary"):
                    if selected_tables:
                        for table in selected_tables:
                            cleanup_temp_table(table)
                        st.success(f"✅ 已删除 {len(selected_tables)} 张临时表")
                        st.rerun()
                    else:
                        st.warning("请至少选择一张表")
        st.subheader("📁 上传你的 Excel 或 CSV 文件")
        uploaded_file = st.file_uploader(
            "上传数据文件", type=["csv", "xlsx", "xls"], key="uploader"
        )
        if uploaded_file:
            df, error = load_dataframe_from_file(uploaded_file)
            if error:
                st.error(error)
            else:
                # 1. 生成新表名
                new_table = f"temp_{st.session_state.session_id}_excel_data"
                # 2. 如果已经存在旧表，先删掉
                if st.session_state.excel_table and st.session_state.excel_table != new_table:
                    cleanup_temp_table(st.session_state.excel_table)
                # 3. 写一次表
                temp_table = excel_to_postgresql(df, "excel_data")  # 返回 temp_xxx_excel_data
                st.session_state.excel_table = temp_table
                st.session_state.excel_df = df
                st.success(f"✅ 文件已导入，表名：{temp_table}")
                with st.expander("📊 数据预览（前 5 行）"):
                    st.dataframe(df.head(), use_container_width=True)

        # 4. 只要表存在，就进入「数据库模式」问答
        if st.session_state.excel_table:
            st.markdown("---")
            st.subheader("💬 问任何关于你数据的问题")
            if "ai_chat" not in st.session_state:
                st.session_state.ai_chat = []

            # 复用数据库对话历史展示
            for msg in st.session_state.ai_chat:
                with st.chat_message("user"):
                    st.markdown(msg["user"])
                with st.chat_message("assistant"):
                    st.markdown(msg["answer"])
                    if "sql" in msg and msg["sql"] is not None:
                        with st.expander("🔍 技术详情"):
                            st.code(msg["sql"], language="sql")
                            st.dataframe(msg["df"], use_container_width=True)

            if prompt := st.chat_input("例如：销售额最高的产品是什么？", key="file_chat_input"):
                with st.chat_message("user"):
                    st.markdown(prompt)
                st.session_state.ai_chat.append({"user": prompt, "answer": "", "sql": None, "df": None})
                # 直接复用数据库 handler
                st.session_state.db_type = "postgresql"
                st.session_state.db_config = {"table": st.session_state.excel_table}
                st.session_state.data_mode = "database"
                db_chat_handler(prompt)

            if st.button("🗑️ 清除对话"):
                st.session_state.ai_chat = []
                st.rerun()

# -----------------------------  入口 ----------------------------- #
if __name__ == "__main__":
    run()