# app.py - 孕期健康COM-B系统（Dashboard重构版）
import streamlit as st
import os
import json
import pandas as pd
import plotly.express as px
from datetime import datetime, timedelta
from urllib.parse import urlparse
import psycopg2
from dotenv import load_dotenv
import importlib

load_dotenv()

# ========== 数据库连接配置 ==========
DATABASE_EHR_URL = os.getenv("DATABASE_EHR_URL")
if not DATABASE_EHR_URL:
    st.error("❌ 环境变量 DATABASE_EHR_URL 未设置，请检查 .env 文件")
    st.stop()

def get_ehr_db_connection():
    try:
        url = urlparse(DATABASE_EHR_URL)
        conn = psycopg2.connect(
            host=url.hostname,
            port=url.port or 5432,
            database=url.path[1:],
            user=url.username,
            password=url.password,
        )
        return conn
    except Exception as e:
        st.error(f"❌ 数据库连接失败: {e}")
        return None
    
CATEGORY_TO_TABS_MODULE = {
    "监测": "monitoring",
    "饮食": "diet",
    "运动": "exercise",
    "心理": "mental",
    "药物": "medication",
}

from openai import OpenAI

@st.cache_resource
def get_ai_client():
    return OpenAI(
        api_key=os.getenv("DASHSCOPE_API_KEY"),
        base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
    )
def get_recent_summary_for_ai(ehr_id: int, item_type: str, limit: int = 5) -> str:
    """
    获取最近几条记录的摘要，用于 AI 上下文
    返回格式化字符串，如：
    "最近3次记录：平均总睡眠时长=7.3小时，深睡眠占比=23%，入睡时间=23:30"
    """
    conn = get_ehr_db_connection()
    if not conn:
        return ""

    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT contents, created_at
                FROM data
                WHERE ehr_id = %s AND items = %s
                ORDER BY created_at DESC
                LIMIT %s
            """, (ehr_id, item_type, limit))
            rows = cur.fetchall()

        if not rows:
            return "尚无历史数据"

        # 合并所有记录的数值字段
        all_data = []
        field_values = {}

        for contents, _ in rows:
            if isinstance(contents, str):
                try:
                    contents = json.loads(contents)
                except:
                    continue
            if isinstance(contents, dict):
                record = {}
                for k, v in contents.items():
                    if isinstance(v, (int, float)) and not isinstance(v, bool):
                        record[k] = v
                        if k not in field_values:
                            field_values[k] = []
                        field_values[k].append(v)
                all_data.append(record)

        if not field_values:
            return "有记录但无有效数值指标"

        # 生成摘要
        summary_parts = []
        for field, values in field_values.items():
            avg_val = sum(values) / len(values)
            if "时间" in field or "入睡" in field:
                # 假设是小时制小数，转为 HH:MM
                hours = int(avg_val)
                minutes = int((avg_val - hours) * 60)
                avg_str = f"{hours:02d}:{minutes:02d}"
            else:
                avg_str = f"{avg_val:.2f}"
            summary_parts.append(f"{field}={avg_str}")

        trend_desc = "趋于稳定"
        if len(rows) >= 2:
            # 简单趋势：比较第一条和最后一条（时间倒序，第一条是最新）
            first_vals = {}
            last_vals = {}
            if len(all_data) >= 2:
                newest = all_data[0]  # 最新
                oldest = all_data[-1] # 最旧
                trends = []
                for field in field_values.keys():
                    if field in newest and field in oldest:
                        diff = newest[field] - oldest[field]
                        if abs(diff) > 0.1:
                            trend = "上升" if diff > 0 else "下降"
                            trends.append(f"{field}{trend}")
                if trends:
                    trend_desc = "；".join(trends)

        return f"最近{len(rows)}次记录：{'，'.join(summary_parts)}（{trend_desc}）"

    except Exception as e:
        st.warning(f"⚠️ 生成AI摘要失败: {e}")
        return "数据摘要生成失败"
    finally:
        if conn:
            conn.close()
def render_pregnancy_ai_assistant(ehr_id: int, item_type: str, title: str):
    """
    为指定模块渲染专属 AI 助手
    """
    st.markdown("### 🤖 AI 孕期助手")

    # 为每个 expander 创建独立聊天历史
    chat_key = f"ai_chat_{item_type}_{title.replace(' ', '_')}"

    if chat_key not in st.session_state:
        # 获取数据摘要
        data_summary = get_recent_summary_for_ai(ehr_id, item_type)

        # 构造专属 system prompt
        system_prompt = f"""你是一位专业的孕期健康AI助手，当前正在与用户讨论「{title}」专题。
用户的最新数据摘要：{data_summary}
请根据数据提供个性化、科学、温暖的建议。用用户的语言（中/英）回复。保持简洁、实用、鼓励性。
不要使用 markdown，不要编造数据，不确定时建议咨询医生。"""

        st.session_state[chat_key] = [
            {"role": "system", "content": system_prompt},
            {"role": "assistant", "content": f"您好！我是您的「{title}」专属AI助手。根据您的数据，我会为您提供个性化建议。有什么想问的吗？"}
        ]

    client = get_ai_client()

    # 显示聊天历史
    for msg in st.session_state[chat_key]:
        if msg["role"] == "assistant":
            with st.chat_message("assistant", avatar="🤖"):
                st.write(msg["content"])
        elif msg["role"] == "user":
            with st.chat_message("user", avatar="👩‍⚕️"):
                st.write(msg["content"])

    # 用户输入
    prompt = st.chat_input("问AI助手...", key=f"chat_input_{chat_key}")
    if prompt:
        # 显示用户消息
        with st.chat_message("user", avatar="👩‍⚕️"):
            st.write(prompt)

        st.session_state[chat_key].append({"role": "user", "content": prompt})

        try:
            with st.chat_message("assistant", avatar="🤖"):
                with st.spinner("AI思考中..."):
                    stream = client.chat.completions.create(
                        model="qwen-plus",
                        messages=st.session_state[chat_key],
                        stream=True
                    )
                    response = st.write_stream(stream)

            st.session_state[chat_key].append({"role": "assistant", "content": response})

        except Exception as e:
            st.error(f"❌ AI 回复失败: {e}")

    # 清除按钮
    if st.button("🗑️ 清除对话", key=f"clear_chat_{chat_key}"):
        data_summary = get_recent_summary_for_ai(ehr_id, item_type)
        system_prompt = f"""你是一位专业的孕期健康AI助手，当前正在与用户讨论「{title}」专题。
用户的最新数据摘要：{data_summary}
请根据数据提供个性化、科学、温暖的建议。用用户的语言（中/英）回复。保持简洁、实用、鼓励性。
不要使用 markdown，不要编造数据，不确定时建议咨询医生。"""
        st.session_state[chat_key] = [
            {"role": "system", "content": system_prompt},
            {"role": "assistant", "content": f"对话已重置。我是您的「{title}」专属AI助手，随时为您服务！"}
        ]
        st.rerun()

@st.cache_data(ttl=timedelta(minutes=5), show_spinner="🔍 正在查询数据库，请稍候...")
def fetch_data_for_items(ehr_id: int, item_type: str):
    """
    从数据库查询指定 ehr_id 和 item_type 的记录，带缓存
    """
    conn = get_ehr_db_connection()
    if not conn:
        return []

    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT contents, created_at
                FROM data
                WHERE ehr_id = %s AND items = %s
                ORDER BY created_at ASC
            """, (ehr_id, item_type))
            rows = cur.fetchall()
        return rows
    except Exception as e:
        st.error(f"❌ 查询失败: {e}")
        return []
    finally:
        if conn:
            conn.close()


def render_dashboard_for_items(ehr_id: int, item_type: str):
    """
    查询 data 表中 items = item_type 的所有记录，绘制专业趋势图
    """
    rows = fetch_data_for_items(ehr_id, item_type)  # 👈 使用缓存函数，避免重复查库

    if not rows:
        st.info(f"📭 暂无「{item_type}」相关数据")
        return

    # 解析数据 → 构建 DataFrame
    records = []
    for contents, created_at in rows:
        if isinstance(contents, str):
            try:
                contents = json.loads(contents)
            except json.JSONDecodeError:
                continue
        if not isinstance(contents, dict):
            continue
        record = {"时间": created_at}
        for k, v in contents.items():
            # 只保留数值型数据（int/float），排除布尔
            if isinstance(v, (int, float)) and not isinstance(v, bool):
                record[k] = v
        records.append(record)

    if not records:
        st.warning("⚠️ 未找到可绘制的数值型数据")
        return

    df = pd.DataFrame(records)
    if len(df) < 2:
        st.info("📈 数据点不足，至少需要 2 个时间点才能绘图")
        return

    # 获取所有数值列（排除“时间”）
    numeric_cols = [col for col in df.columns if col != "时间"]
    if not numeric_cols:
        st.warning("⚠️ 无可视化指标")
        return

    # ========== 开始绘图 ==========
    st.subheader(f"📊 {item_type} 趋势分析")
    st.caption(f"共 {len(df)} 条记录 · 更新至 {df['时间'].max()}")

    # 创建 Plotly 图表
    fig = px.line(
        df,
        x="时间",
        y=numeric_cols,
        markers=True,
        title=f"<b>{item_type} 核心指标趋势</b>",
        labels={"value": "数值", "variable": "指标"},
        template="plotly_white",  # 专业白底模板
        height=600,
    )

    # 优化样式
    fig.update_layout(
        hovermode="x unified",  # 悬停统一垂直线
        legend_title_text="📈 指标",
        xaxis_title="📅 时间",
        yaxis_title="🔢 数值",
        title_x=0.5,
        title_font_size=20,
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1
        ),
        margin=dict(l=40, r=40, t=80, b=40),
    )

    # 优化线条和标记
    fig.update_traces(
        line=dict(width=3),
        marker=dict(size=8, symbol="circle"),
    )

    # 显示图表
    st.plotly_chart(fig, use_container_width=True, config={
        'displayModeBar': True,
        'displaylogo': False,
        'modeBarButtonsToRemove': ['lasso2d', 'select2d'],
        'toImageButtonOptions': {
            'format': 'png',
            'filename': f'{item_type}_trend',
            'height': 600,
            'width': 1200,
            'scale': 2
        }
    })

    # 可选：显示原始数据表格（折叠）
    with st.expander("📋 原始数据表"):
        st.dataframe(
            df.style.format(precision=2),
            use_container_width=True,
            hide_index=True
        )


# ========== 配置区：expander 标题与 icon ==========
CATEGORY_EXPANDERS = {
    "监测": [
        ("导诊", "🩺"),
        ("孕检母亲体检指标", "👩‍⚕️"),
        ("孕检胎儿生长发育指标", "👶"),
        ("睡眠指标", "😴"),
        ("症状", "🤒"),
    ],
    "饮食": [
        ("饮食种类丰富度", "🥗"),
        ("饮食热量", "🔥"),
        ("妊娠期糖尿病饮食监测", "🩸"),
    ],
    "运动": [
        ("每日活动时间", "⏰"),
        ("运动时间", "🏃"),
        ("运动热量", "⚡"),
        ("日活动步数", "👣"),
        ("久坐时间", "🪑"),
    ],
    "心理": [
        ("爱丁堡产后抑郁量表（EPDS）", "🧠"),
    ],
    "药物": [
        ("补剂（钙、叶酸、铁、维生素）医嘱", "💊"),
        ("合并症药物医嘱", "📋"),
        ("服药依从性", "✅"),
    ],
}

DISPLAY_TO_ITEM_TYPE = {
    "🩺 监测": "监测",
    "🍎 饮食": "饮食",
    "🏃 运动": "运动",
    "🧠 心理": "心理",
    "💊 药物": "药物"
}

CATEGORY_DISPLAY_NAMES = list(DISPLAY_TO_ITEM_TYPE.keys())


# ========== 渲染函数 ==========
def render_expanders_for_category(item_type: str):
    """根据类别渲染对应的 expanders，支持懒加载 + 数据录入 + AI助手"""
    expanders_config = CATEGORY_EXPANDERS.get(item_type, [])
    if not expanders_config:
        st.info("ℹ️ 该类别暂无可用模块")
        return

    st.subheader(f"📌 {item_type} 相关模块")

    # ========== 渲染所有 expanders ==========
    for i, (title, icon) in enumerate(expanders_config):
        load_key = f"load_data_{item_type}_{i}_{title.replace(' ', '_')}"
        show_form_key = f"show_form_{item_type}_{i}"
        show_ai_key = f"show_ai_{item_type}_{i}"

        with st.expander(f"{icon} {title}"):
            col1, col2, col3 = st.columns(3)
            with col1:
                if st.button(f"➕ 添加记录", key=f"btn_add_{load_key}"):
                    st.session_state[show_form_key] = not st.session_state.get(show_form_key, False)
            with col2:
                if st.button(f"🤖 AI助手", key=f"btn_ai_{load_key}"):
                    st.session_state[show_ai_key] = not st.session_state.get(show_ai_key, False)
            with col3:
                if not st.session_state.get(load_key, False):
                    if st.button(f"▶️ 加载图表", key=f"btn_load_{load_key}"):
                        st.session_state[load_key] = True
                        st.rerun()
                else:
                    if st.button(f"↩️ 收起图表", key=f"btn_reset_{load_key}"):
                        st.session_state[load_key] = False
                        st.rerun()

            # ========== 数据录入 ==========
            if st.session_state.get(show_form_key, False):
                render_data_entry_form(st.session_state["ehr_id"], title)

            # ========== AI助手 ==========
            if st.session_state.get(show_ai_key, False):
                render_pregnancy_ai_assistant(st.session_state["ehr_id"], title, title)

            # ========== 图表 ==========
            if st.session_state.get(load_key, False):
                render_dashboard_for_items(st.session_state["ehr_id"], title)

    # ========== 动态加载专属 Tabs（放在 for 循环外！） ========== 👇
    st.markdown("---")
    st.subheader("📌 专属分析面板")

    module_name = CATEGORY_TO_TABS_MODULE.get(item_type)
    if not module_name:
        st.info("ℹ️ 该类别暂无专属分析面板")
        return

    # 构造绝对路径
    tabs_dir = os.path.join(os.path.dirname(__file__), "tabs")
    module_file = os.path.join(tabs_dir, f"{module_name}.py")

    if not os.path.exists(module_file):
        st.info(f"ℹ️ 专属面板模块 `{module_name}.py` 尚未创建")
        return

    try:
        spec = importlib.util.spec_from_file_location(module_name, module_file)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        if hasattr(module, "render_tabs"):
            module.render_tabs(st.session_state["ehr_id"])
        else:
            st.warning(f"⚠️ 模块 `{module_name}` 未定义 `render_tabs` 函数")

    except Exception as e:
        st.error(f"❌ 加载模块 `{module_name}.py` 失败: {e}")

@st.cache_data(ttl=3600)  # 缓存1小时，结构不会频繁变
def get_sample_fields_for_items(ehr_id: int, item_type: str) -> list:
    """
    从历史数据中提取该 item_type 的常见字段名（数值型），用于生成表单
    """
    conn = get_ehr_db_connection()
    if not conn:
        return []

    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT contents
                FROM data
                WHERE ehr_id = %s AND items = %s
                ORDER BY created_at DESC
                LIMIT 10
            """, (ehr_id, item_type))
            rows = cur.fetchall()

        field_set = set()
        for row in rows:
            contents = row[0]
            if isinstance(contents, str):
                try:
                    contents = json.loads(contents)
                except:
                    continue
            if isinstance(contents, dict):
                for k, v in contents.items():
                    if isinstance(v, (int, float)) and not isinstance(v, bool):
                        field_set.add(k)

        return sorted(list(field_set)) if field_set else []

    except Exception as e:
        st.warning(f"⚠️ 获取字段结构失败: {e}")
        return []
    finally:
        if conn:
            conn.close()
def save_new_record_to_db(ehr_id: int, item_type: str, contents: dict) -> bool:
    """保存新记录到 data 表"""
    conn = get_ehr_db_connection()
    if not conn:
        return False

    try:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO data (ehr_id, contents, items, created_at)
                VALUES (%s, %s, %s, NOW())
            """, (ehr_id, json.dumps(contents, ensure_ascii=False), item_type))
        conn.commit()
        return True
    except Exception as e:
        st.error(f"❌ 保存失败: {e}")
        if conn:
            conn.rollback()
        return False
    finally:
        if conn:
            conn.close()


def render_data_entry_form(ehr_id: int, item_type: str):
    """
    渲染数据录入表单（动态字段 + 图片上传占位）
    """
    st.markdown("### ➕ 添加新记录")

    tab1, tab2 = st.tabs(["✍️ 手动填写", "🖼️ 上传图片（未来）"])

    with tab1:
        # 获取历史字段
        sample_fields = get_sample_fields_for_items(ehr_id, item_type)

        if not sample_fields:
            st.info(f"ℹ️ 首次使用，建议填写常见指标，例如：")
            # 提供默认字段（按类别）
            default_fields_map = {
                "睡眠指标": ["总睡眠时长", "深睡眠占比", "入睡时间", "夜间醒来次数"],
                "孕检母亲体检指标": ["空腹血糖", "血红蛋白", "血压收缩压", "体重"],
                "饮食热量": ["总热量_kcal", "早餐热量", "午餐热量", "晚餐热量"],
                "日活动步数": ["总步数", "户外步数", "室内步数"],
                "爱丁堡产后抑郁量表（EPDS）": ["情绪低落评分", "焦虑评分", "睡眠障碍评分", "自责评分", "总分"],
                "补剂（钙、叶酸、铁、维生素）医嘱": ["钙摄入_mg", "叶酸_mcg", "铁_mg", "维生素D_IU"],
            }
            sample_fields = default_fields_map.get(item_type, ["指标1", "指标2", "指标3"])

        st.write(f"📝 请填写以下指标（基于历史数据推荐）：")

        # 动态生成输入框
        new_data = {}
        cols = st.columns(2)  # 两列布局

        for i, field in enumerate(sample_fields):
            col = cols[i % 2]
            with col:
                # 尝试从历史数据获取最近值作为默认值（可选增强）
                default_val = 0.0
                new_data[field] = st.number_input(
                    field,
                    value=float(default_val),
                    format="%.2f",
                    key=f"input_{item_type}_{field}"
                )

        # 保存按钮
        if st.button("💾 保存记录", type="primary", key=f"save_{item_type}"):
            if save_new_record_to_db(ehr_id, item_type, new_data):
                st.success("✅ 保存成功！图表将在下次加载时更新")
                # 可选：清除缓存，确保下次加载最新数据
                fetch_data_for_items.clear()  # 清除该函数的缓存
                # 不自动 rerun，让用户手动刷新图表更稳妥
            else:
                st.error("❌ 保存失败")

    with tab2:
        st.info("🖼️ 图片识别功能正在开发中，敬请期待！")
        # 占位：未来可加 st.file_uploader + OCR 逻辑
        # uploaded_file = st.file_uploader("上传检验单图片", type=["png", "jpg", "jpeg"])
        # if uploaded_file:
        #     st.image(uploaded_file, caption="预览", use_container_width=True)

# ========== 主函数 ==========
def run():
    st.header("🩺 孕期健康COM-B系统 Dashboard")
    ehr_id = st.number_input("🔢 请输入您的 EHR ID", min_value=1, step=1, value=123123)

    # 保存到 session_state，供子模块使用
    st.session_state["ehr_id"] = ehr_id

    # 初始化 session state
    if "current_category_display" not in st.session_state:
        st.session_state.current_category_display = CATEGORY_DISPLAY_NAMES[0]

    # 类别选择器
    selected_display = st.radio(
        "选择类别",
        CATEGORY_DISPLAY_NAMES,
        index=CATEGORY_DISPLAY_NAMES.index(st.session_state.current_category_display),
        horizontal=True,
        label_visibility="collapsed"
    )

    if selected_display != st.session_state.current_category_display:
        st.session_state.current_category_display = selected_display
        st.rerun()

    current_item_type = DISPLAY_TO_ITEM_TYPE[st.session_state.current_category_display]
    render_expanders_for_category(current_item_type)


# ========== 启动 ==========
if __name__ == "__main__":
    run()