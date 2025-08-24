# projects/excel/main.py

import streamlit as st
import pandas as pd
import plotly.express as px
from openai import OpenAI
from io import BytesIO
from pathlib import Path
import os
from dotenv import load_dotenv


# ================================
# 1. 加载环境变量
# ================================
def load_environment():
    # -----------------------------
    # 直接依赖 os.environ（由 .env 或 Secrets 注入）
    # -----------------------------
    api_key = os.getenv("DASHSCOPE_API_KEY")
    base_url = os.getenv("DASHSCOPE_BASE_URL")

    # 如果环境变量已经存在（线上 Secrets 注入），直接返回
    if api_key and base_url:
        return {"api_key": api_key, "base_url": base_url.strip()}

    # 否则尝试加载本地 .env
    env_path = Path(__file__).parent.parent.parent / ".env"
    if env_path.exists():
        load_dotenv(dotenv_path=env_path)
        st.info(f"📁 从本地 .env 加载配置：{env_path}")
    else:
        st.error(f"❌ 未找到 .env 文件：{env_path}")
        st.info("💡 提示：\n- 本地请确保 `.env` 存在\n- 线上请在 Secrets 中设置 `DASHSCOPE_API_KEY` 和 `DASHSCOPE_BASE_URL`")
        return None

    # 再次尝试从环境变量读取
    api_key = os.getenv("DASHSCOPE_API_KEY")
    base_url = os.getenv("DASHSCOPE_BASE_URL")

    if not api_key:
        st.error("❌ 请设置 `DASHSCOPE_API_KEY`")
        return None
    if not base_url:
        st.error("❌ 请设置 `DASHSCOPE_BASE_URL`")
        return None

    return {"api_key": api_key, "base_url": base_url.strip()}


# ================================
# 2. 初始化 session_state
# ================================
def initialize_session_state():
    if 'df' not in st.session_state:
        st.session_state.df = None
    if 'history' not in st.session_state:
        st.session_state.history = []
    if 'editor_key' not in st.session_state:
        st.session_state.editor_key = 0  


# ================================
# 3. AI 生成新表格
# ================================
def ai_generate_dataframe(client):
    """让用户描述一个表格，AI 生成并创建 DataFrame"""
    st.markdown("### 🆕 AI 生成新表格")
    st.write("描述你想要的表格结构，例如：")
    st.caption("“创建一个包含5个员工的表格，有姓名、部门、工资（8000-15000）”")

    user_desc = st.text_area(
        "表格描述",
        placeholder="例如：生成一个产品库存表，包含名称、价格、库存数量...",
        key="ai_gen_table_desc"
    )

    col1, col2 = st.columns([1, 4])
    with col1:
        num_rows = st.number_input("行数", min_value=1, max_value=1000, value=5, key="gen_row_count")
    with col2:
        if st.button("✨ 生成表格", key="btn_gen_table"):
            if not user_desc.strip():
                st.warning("请输入表格描述")
                return

            with st.spinner("🧠 AI 正在生成表格结构..."):
                try:
                    prompt = f"""
你是一个 pandas 专家。请根据用户的描述生成一段 Python 代码，创建一个包含 {num_rows} 行数据的 DataFrame。
- 变量名必须是 `df`
- 使用 pandas 和 numpy 生成合理数据（如随机数、枚举值等）
- 数值字段可用 np.random.randint 或 np.random.uniform
- 文本字段可用预设列表
- 不要使用真实敏感数据
- 不要输出解释，只输出代码

用户描述：
{user_desc}

请输出 Python 代码：
                    """.strip()

                    response = client.chat.completions.create(
                        model="qwen-plus",
                        messages=[{"role": "user", "content": prompt}],
                        temperature=0.7,
                        max_tokens=512
                    )
                    code = response.choices[0].message.content.strip()

                    # 清理代码块
                    if code.startswith("```python"):
                        code = code[10:]
                    if code.endswith("```"):
                        code = code[:-3]
                    code = code.strip()

                    if not code:
                        st.error("AI 未生成有效代码")
                        return

                    st.code(code, language='python')

                    # 执行并获取 df
                    local_vars = {}
                    global_vars = {
                        'pd': pd,
                        'np': __import__('numpy'),
                        'random': __import__('random')
                    }
                    exec(code, global_vars, local_vars)

                    if 'df' in local_vars and isinstance(local_vars['df'], pd.DataFrame):
                        st.session_state.df = local_vars['df']
                        st.session_state.history = [f"AI 生成表格：{user_desc}"]
                        st.success(f"✅ 表格生成成功！{local_vars['df'].shape[0]} 行 × {local_vars['df'].shape[1]} 列")
                    else:
                        st.error("❌ 未生成有效的 DataFrame")

                except Exception as e:
                    st.error(f"❌ 生成失败：{e}")


# ================================
# 4. 文件上传（主页面）
# ================================
def upload_and_load_file():
    st.markdown("### 📂 上传 Excel 或 CSV 文件")
    uploaded_file = st.file_uploader(
        label="支持格式：.csv、.xlsx",
        type=["csv", "xlsx"],
        key="file_uploader_main",
        label_visibility="collapsed"
    )

    if uploaded_file:
        try:
            with st.spinner("📊 正在读取文件..."):
                if uploaded_file.name.endswith(".csv"):
                    df = pd.read_csv(uploaded_file)
                else:
                    df = pd.read_excel(uploaded_file)
            st.session_state.df = df
            st.session_state.history = []
            st.success(f"✅ '{uploaded_file.name}' 上传成功！{df.shape[0]} 行 × {df.shape[1]} 列")
        except Exception as e:
            st.error(f"❌ 文件读取失败：{e}")


# ================================
# 5. 显示数据基本信息
# ================================
def display_data_info():
    df = st.session_state.df
    st.markdown("### 📊 数据基本信息")
    st.write(f"**行数**：{df.shape[0]}")
    st.write(f"**列数**：{df.shape[1]}")
    st.write("**列名预览**：")
    cols_display = ", ".join([f"`{col}`" for col in df.columns[:15]])
    if len(df.columns) > 15:
        cols_display += f" …（共 {len(df.columns)} 列）"
    st.code(cols_display, language="")


# ================================
# 6. 显示可编辑表格
# ================================
def display_data_editor():
    st.markdown("### 🖼️ 数据预览与编辑")
    edited_df = st.data_editor(
        st.session_state.df,
        use_container_width=True,
        key=f"data_editor_{st.session_state.editor_key}"
    )
    st.session_state.df = edited_df


# ================================
# 7. AI 操作表格（修复版：支持 pd.concat, pd.DataFrame 等）
# ================================
def ai_pandas_operations(client):
    """AI 驱动的表格操作 + 手动刷新表格按钮"""
    st.markdown("### 🔧 用自然语言操作表格")
    user_command = st.text_input(
        "例如：新增一列 total = quantity × price；或：添加一行数据",
        help="描述越清晰，AI 操作越准确",
        placeholder="输入你的操作指令...",
        key="ai_command_input"
    )

    col_exec, col_refresh = st.columns([1, 1])

    with col_exec:
        if user_command and st.button("🚀 执行 AI 操作", key="exec_ai"):
            with st.spinner("🧠 AI 正在生成代码..."):
                try:
                    df = st.session_state.df
                    columns = list(df.columns)
                    dtypes = {col: str(df[col].dtypes) for col in columns[:10]}

                    prompt = f"""
你是一个专业的 Python pandas 数据分析助手（pandas 2.0+ 环境）。请根据用户的自然语言指令，生成可执行的 pandas 代码。
- 数据框变量名为 `df`
- 不要输出解释、注释或 markdown 代码块
- 只输出纯 Python 代码
- ✅ 重要：pandas 已移除 .append() 方法，请使用 pd.concat() 替代
- ✅ 添加行：df = pd.concat([df, pd.DataFrame([{{'name': '张三'}}])], ignore_index=True)

当前列名：{columns}
数据类型示例：{dtypes}

用户指令：
{user_command}

请输出对应的 pandas 代码：
                    """.strip()

                    response = client.chat.completions.create(
                        model="qwen-plus",
                        messages=[{"role": "user", "content": prompt}],
                        temperature=0.1,
                        max_tokens=256,
                        top_p=0.9
                    )
                    code = response.choices[0].message.content.strip()
                    if code.startswith("```python"):
                        code = code[10:]
                    if code.endswith("```"):
                        code = code[:-3]
                    code = code.strip()

                    if not code:
                        st.warning("⚠️ AI 未生成有效代码，请换种说法试试。")
                        return

                    st.code(code, language='python')

                    global_vars = {
                        'pd': pd,
                        'np': __import__('numpy'),
                        '__builtins__': {
                            'True': True, 'False': False, 'None': None,
                            'int': int, 'float': float, 'str': str, 'list': list, 'dict': dict
                        }
                    }
                    local_vars = {'df': st.session_state.df}

                    if '=' in code:
                        exec(code, global_vars, local_vars)
                        st.success("✅ 操作已执行（请点右侧刷新表格）")
                    else:
                        result = eval(code, global_vars, local_vars)
                        st.success(f"✅ 计算结果：{result}")

                    if 'df' in local_vars:
                        st.session_state.df = local_vars['df']
                    st.session_state.history.append(user_command)

                except Exception as e:
                    st.error(f"❌ 执行失败：{e}")

    # 🔁 刷新表格按钮
    with col_refresh:
        if st.button("🔁 刷新表格", key="refresh_table", use_container_width=True):
            if st.session_state.df is not None:
                st.session_state.editor_key += 1
                st.success("✅ 表格已刷新，显示最新数据！")
            else:
                st.warning("❌ 当前没有数据可刷新")


# ================================
# 8. AI 生成图表
# ================================
def ai_generate_chart(client):
    st.markdown("### 📈 AI 生成可视化图表")
    viz_command = st.text_input(
        "例如：画一个 quantity 随 product 变化的柱状图",
        placeholder="描述你想看的图表...",
        key="viz_input"
    )

    if viz_command and st.button("🎨 生成图表", key="gen_viz"):
        with st.spinner("📊 AI 正在生成图表代码..."):
            try:
                df = st.session_state.df
                columns = list(df.columns)
                prompt = f"""
你是一个 Plotly 可视化专家。请根据用户需求生成一段可执行的 Python 代码，使用 plotly.express。
- 图形变量名为 `fig`
- 数据框为 `df`
- 不要包含 fig.show()
- 不要输出解释

当前列名：{columns}

用户需求：
{viz_command}

请输出 Python 代码：
                """.strip()

                response = client.chat.completions.create(
                    model="qwen-plus",
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.3,
                    max_tokens=512
                )
                plot_code = response.choices[0].message.content.strip()
                if plot_code.startswith("```python"):
                    plot_code = plot_code[10:]
                if plot_code.endswith("```"):
                    plot_code = plot_code[:-3]
                plot_code = plot_code.strip()

                if not plot_code:
                    st.warning("⚠️ 未生成图表代码")
                    return

                local_vars = {}
                global_vars = {
                    'df': st.session_state.df,
                    'px': __import__('plotly.express'),
                    'go': __import__('plotly.graph_objects'),
                    'np': __import__('numpy')
                }
                exec(plot_code, global_vars, local_vars)
                fig = local_vars.get('fig')
                if fig:
                    st.plotly_chart(fig, use_container_width=True)
                else:
                    st.error("❌ 图表未生成，请检查指令是否清晰。")

            except Exception as e:
                st.error(f"❌ 图表生成失败：{e}")


# ================================
# 9. 导出功能（侧边栏）
# ================================
def export_to_excel():
    st.sidebar.markdown("---")
    st.sidebar.subheader("📤 导出数据")
    def to_excel(df):
        output = BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            df.to_excel(writer, index=False, sheet_name='Sheet1')
        return output.getvalue()

    excel_data = to_excel(st.session_state.df)
    st.sidebar.download_button(
        label="📥 下载处理后的 Excel",
        data=excel_data,
        file_name="ai_edited_data.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )


# ================================
# 10. 操作历史（侧边栏）
# ================================
def display_history():
    if st.session_state.history:
        st.sidebar.markdown("---")
        st.sidebar.subheader("🔁 操作历史")
        for i, cmd in enumerate(st.session_state.history, 1):
            st.sidebar.text(f"{i}. {cmd}")


# ================================
# ✅ 主入口函数
# ================================
def run():
    st.title("🤖 AI Excel 智能操作助手")

    # 1. 加载环境
    config = load_environment()
    if not config:
        return
    try:
        client = OpenAI(api_key=config["api_key"], base_url=config["base_url"])
    except Exception as e:
        st.error(f"❌ 初始化 AI 客户端失败：{e}")
        return

    # 2. 初始化状态
    initialize_session_state()

    # 3. AI 生成表格（优先级最高）
    ai_generate_dataframe(client)

    # 4. 或者上传文件
    upload_and_load_file()

    # 5. 如果有数据，显示后续功能
    if st.session_state.df is not None:
        display_data_info()
        display_data_editor()
        ai_pandas_operations(client)
        ai_generate_chart(client)
        export_to_excel()
        display_history()
    else:
        st.info("👆 使用上方功能生成或上传一个表格开始操作")