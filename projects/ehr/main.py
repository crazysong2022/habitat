# -*- coding: utf-8 -*-
"""
Streamlit 智能健康档案系统（纯文本粘贴版）
基于数据库 my_concerns.concerns 动态加载用户关注项目
"""

import streamlit as st
import os
import psycopg2
from urllib.parse import urlparse
import plotly.express as px
import pandas as pd
import json
from datetime import datetime
import re

# ----------  环境变量  ----------
from dotenv import load_dotenv
load_dotenv()

DATABASE_EHR_URL = os.getenv("DATABASE_EHR_URL")
if not DATABASE_EHR_URL:
    st.error("❌ 环境变量 DATABASE_EHR_URL 未设置，请检查 .env 文件")
    st.stop()

try:
    url = urlparse(DATABASE_EHR_URL)
    EHR_DB_CONFIG = dict(
        host=url.hostname,
        port=url.port or 5432,
        database=url.path[1:],
        user=url.username,
        password=url.password,
    )
except Exception as e:
    st.error(f"❌ 解析数据库地址失败: {e}")
    st.stop()


# ----------  数据库连接  ----------
def get_ehr_db_connection():
    try:
        return psycopg2.connect(**EHR_DB_CONFIG)
    except Exception as e:
        st.error(f"❌ 数据库连接失败: {e}")
        return None


# ==========  内置常见项目池（作为基础选项）==========
# 用于补全用户未添加的常见项目，提升可用性
DEFAULT_ITEMS = [
    "白细胞计数", "中性粒细胞绝对值", "淋巴细胞绝对值", "单核细胞绝对值",
    "嗜酸性粒细胞绝对值", "嗜碱性粒细胞绝对值", "中性粒细胞百分率", "淋巴细胞百分率",
    "单核细胞百分率", "嗜酸性粒细胞百分率", "嗜碱性粒细胞百分率",
    "红细胞计数", "血红蛋白", "红细胞压积", "平均红细胞体积", "平均红细胞血红蛋白量",
    "平均红细胞血红蛋白浓度", "红细胞分布宽度变异系数", "红细胞分布宽度标准差",
    "血小板计数", "平均血小板体积", "血小板分布宽度", "血小板压积",
    "血糖", "总胆固醇", "甘油三酯", "高密度脂蛋白胆固醇", "低密度脂蛋白胆固醇",
    "肌酐", "尿素氮", "尿酸", "丙氨酸氨基转移酶", "天门冬氨酸氨基转移酶",
]

# 英文缩写映射（提升提取准确率）
ITEM_ABBR = {
    "白细胞计数": "WBC", "红细胞计数": "RBC", "血红蛋白": "HB|HGB",
    "血小板计数": "PLT", "血糖": "GLU", "肌酐": "CREA", "尿素氮": "BUN",
}


# ==========  从 my_concerns 表加载用户关注项目  ==========
def load_user_concerns(ehr_id: int) -> list:
    """
    从 my_concerns 表加载该用户的关注项目
    若无记录，返回 DEFAULT_ITEMS 前10项作为推荐
    """
    conn = get_ehr_db_connection()
    if not conn:
        return DEFAULT_ITEMS[:10]
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT concerns FROM my_concerns WHERE ehr_id = %s", (ehr_id,))
            row = cur.fetchone()
            if row and row[0]:
                return row[0]  # 返回数据库中的项目列表
            else:
                return DEFAULT_ITEMS[:10]
    except Exception as e:
        st.warning(f"⚠️ 加载用户关注项目失败，使用默认推荐: {e}")
        return DEFAULT_ITEMS[:10]
    finally:
        conn.close()


# ==========  保存用户关注项目  ==========
def save_user_concerns(ehr_id: int, items: list) -> bool:
    """插入或更新用户关注项目"""
    conn = get_ehr_db_connection()
    if not conn:
        return False
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO my_concerns (ehr_id, concerns, updated_at)
                VALUES (%s, %s, NOW())
                ON CONFLICT (ehr_id) DO UPDATE
                    SET concerns = EXCLUDED.concerns, updated_at = NOW()
                """,
                (ehr_id, json.dumps(items, ensure_ascii=False))
            )
        conn.commit()
        return True
    except Exception as e:
        st.error(f"❌ 保存失败: {e}")
        conn.rollback()
        return False
    finally:
        conn.close()


# ==========  从文本中提取指定项目  ==========
def extract_selected_items(text: str, selected: list) -> dict:
    text = re.sub(r'\s+', ' ', text.strip())
    result = {}
    for name in selected:
        abbr = ITEM_ABBR.get(name, "")
        pattern = abbr if abbr else name
        regex = rf'(?:{name}|{abbr}).*?(\d+\.?\d*)' if abbr else rf'{name}.*?(\d+\.?\d*)'
        match = re.search(regex, text, re.I)
        if match:
            result[name] = float(match.group(1))
    return result


# ==========  保存提取结果到 data 表  ==========
def save_to_database(ehr_id: int, structured_data: dict) -> bool:
    conn = get_ehr_db_connection()
    if not conn:
        return False
    try:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO data (ehr_id, contents) VALUES (%s, %s)",
                (ehr_id, json.dumps(structured_data, ensure_ascii=False))
            )
        conn.commit()
        return True
    except Exception as e:
        st.error(f"❌ 数据库写入失败: {e}")
        conn.rollback()
        return False
    finally:
        conn.close()


# ==========  查询历史记录  ==========
def fetch_history(ehr_id: int) -> list:
    conn = get_ehr_db_connection()
    if not conn:
        return []
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT contents, created_at FROM data WHERE ehr_id = %s ORDER BY created_at ASC",
                (ehr_id,)
            )
            rows = cur.fetchall()
            return [
                {"contents": json.loads(r[0]) if isinstance(r[0], str) else r[0], "created_at": r[1]}
                for r in rows
            ]
    except Exception as e:
        st.error(f"❌ 查询历史失败: {e}")
        return []
    finally:
        conn.close()


# ==========  绘图函数  ==========
def plot_all_trends(history: list):
    if not history:
        st.info("📊 暂无数据可绘图")
        return

    df_data = []
    for item in history:
        row = {"时间": item["created_at"]}
        for k, v in item["contents"].items():
            if k.startswith("__") or not isinstance(v, (int, float)):
                continue
            row[k] = v
        df_data.append(row)

    df = pd.DataFrame(df_data)
    if df.empty or len(df.columns) <= 1:
        st.info("🔍 无足够数值数据用于绘图")
        return

    numeric_cols = [c for c in df.columns if c != "时间"]
    st.subheader(f"📈 自动趋势分析（{len(numeric_cols)} 个指标）")

    for col in numeric_cols:
        if df[col].notna().sum() >= 2:
            ascii_col = re.sub(r'[^A-Za-z0-9_]', '_', col)
            temp_df = df.rename(columns={col: ascii_col})
            fig = px.line(temp_df, x="时间", y=ascii_col, markers=True, title=f"{col} 趋势")
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.caption(f"🟡 `{col}` 数据不足，无法绘图")


# ==========  主界面  ==========
def run():
    # 初始化 session_state
    if "to_save" not in st.session_state:
        st.session_state["to_save"] = {}
    if "show_save" not in st.session_state:
        st.session_state["show_save"] = False

    st.header("🩺 智能健康档案系统（纯文本粘贴版）")
    ehr_id = st.number_input("🔢 请输入您的 EHR ID", min_value=1, step=1, value=123123)

    tab1, tab2, tab3, tab4 = st.tabs([
        "📁 历史记录", 
        "📋 粘贴报告文本", 
        "📊 趋势图表", 
        "⚙️ 编辑提取项目"
    ])

    # ========== Tab1: 历史记录 ==========
    with tab1:
        st.subheader("📁 历史记录")
        history = fetch_history(ehr_id)
        if not history:
            st.info("📭 暂无历史数据")
        else:
            st.success(f"✅ 共 {len(history)} 条记录")
            for idx, item in enumerate(history):
                with st.expander(f"📝 记录 {idx + 1} - {item['created_at']}"):
                    st.json(item["contents"])

    # ========== Tab2: 粘贴报告文本 ==========
    with tab2:
        st.subheader("📋 粘贴报告文本")
        st.caption("系统将根据你在【编辑提取项目】中设置的关注项，自动推荐可提取项目。")

        # ---- 1. 加载用户关注项目（来自数据库 my_concerns.concerns）----
        user_concerns = load_user_concerns(ehr_id)

        # ---- 2. 构建完整可选项：DEFAULT_ITEMS + 用户独有的自定义项 ----
        custom_only = [item for item in user_concerns if item not in DEFAULT_ITEMS]
        all_options = list(dict.fromkeys(DEFAULT_ITEMS + custom_only))  # 去重，保持顺序

        # ---- 3. 布局选择 ----
        col1, col2 = st.columns([1, 1])

        with col1:
            picked = st.multiselect(
                "✅ 从常用项目中选择",
                options=all_options,
                default=user_concerns,  # 来自数据库
                help="灰色项为系统推荐，彩色项为你自定义添加"
            )

        with col2:
            custom_input = st.text_input(
                "✏️ 临时添加新项目（中文逗号分隔）",
                placeholder="如：糖化血红蛋白，甲胎蛋白"
            )
            custom_list = [c.strip() for c in custom_input.split("，") if c.strip()]

        selected_items = list(dict.fromkeys(picked + custom_list))

        if not selected_items:
            st.warning("⚠️ 请至少选择或输入一个项目")
            st.info("提示：左侧列表来自数据库 `my_concerns.concerns`，右侧可临时添加")
        else:
            st.success(f"🎯 已选择 {len(selected_items)} 个项目")

            # ---- 粘贴文本 ----
            pasted_text = st.text_area("📎 粘贴化验单文本", height=300)

            if not pasted_text.strip():
                st.info("请粘贴原始报告文本...")
            else:
                if st.button("🔍 开始提取", type="primary"):
                    extracted = extract_selected_items(pasted_text, selected_items)
                    st.session_state["to_save"] = extracted
                    st.session_state["show_save"] = True
                    st.success("✅ 提取完成，请检查数值")

                # ---- 显示并编辑结果 ----
                if st.session_state.get("show_save", False):
                    data = st.session_state["to_save"]
                    st.divider()
                    st.markdown("### 📊 提取结果（可修改）")

                    with st.expander("点击查看/编辑", expanded=True):
                        edited = {}
                        cols = st.columns(2)
                        for i, item in enumerate(selected_items):
                            col = cols[i % 2]
                            val = data.get(item, 0.0)
                            edited[item] = col.number_input(
                                item,
                                value=float(val),
                                format="%.3f",
                                key=f"edit_{item}"
                            )

                    if st.button("💾 保存到档案"):
                        if save_to_database(ehr_id, edited):
                            st.success("✅ 保存成功！可在【趋势图表】中查看")
                            st.session_state.pop("to_save", None)
                            st.session_state.pop("show_save", None)
                            st.rerun()
                        else:
                            st.error("❌ 保存失败")

    # ========== Tab3: 趋势图表 ==========
    with tab3:
        st.subheader("📊 趋势图表")
        history = fetch_history(ehr_id)
        if not history:
            st.info("📭 暂无数据，去「粘贴报告文本」添加记录吧！")
        else:
            plot_all_trends(history)

    # ========== Tab4: 编辑关注项目 ==========
    with tab4:
        st.subheader("⚙️ 编辑个人关注项目")
        st.info("此处设置的项目将作为你在「粘贴报告文本」页的默认选项")

        user_concerns = load_user_concerns(ehr_id)
        col1, col2 = st.columns([1, 1])

        with col1:
            picked = st.multiselect(
                "系统常见项目",
                DEFAULT_ITEMS,
                default=[i for i in user_concerns if i in DEFAULT_ITEMS],
                help="选择你常关注的常规项目"
            )

        with col2:
            custom_input = st.text_input(
                "自定义项目（中文逗号分隔）",
                value="，".join([i for i in user_concerns if i not in DEFAULT_ITEMS]),
                placeholder="如：糖化血红蛋白，肿瘤标志物"
            )
            custom_list = [c.strip() for c in custom_input.split("，") if c.strip()]

        new_concerns = list(dict.fromkeys(picked + custom_list))

        if st.button("💾 保存为默认关注项目"):
            if save_user_concerns(ehr_id, new_concerns):
                st.success("✅ 保存成功！下次进入将自动加载")
            else:
                st.error("❌ 保存失败")


# ========== 启动入口 ==========
if __name__ == "__main__":
    run()