import streamlit as st
import os
import psycopg2
from urllib.parse import urlparse
from dotenv import load_dotenv
import pandas as pd
import json
from pathlib import Path
import plotly.express as px

# -----------------------------
# 加载环境变量
# -----------------------------
if "DATABASE_PETS_URL" not in os.environ:
    env_path = Path(__file__).parent.parent / ".env"
    if env_path.exists():
        load_dotenv(dotenv_path=env_path)

# -----------------------------
# 数据库连接函数
# -----------------------------
def get_db_connection():
    db_url = os.getenv("DATABASE_PETS_URL")
    if not db_url:
        st.error("❌ 环境变量 `DATABASE_PETS_URL` 未设置。")
        return None

    try:
        url = urlparse(db_url)
        conn = psycopg2.connect(
            host=url.hostname,
            port=url.port,
            database=url.path[1:],
            user=url.username,
            password=url.password,
        )
        return conn
    except Exception as e:
        st.error(f"🔗 数据库连接失败：{e}")
        return None

# -----------------------------
# 工具函数：将中文 JSON 列表转为标准化 DataFrame
# -----------------------------
def to_standard_df(data_list, value_key, time_key="时间", value_name="value"):
    """
    将中文结构的列表转为含 'date' 和 'value' 的 DataFrame
    """
    if not isinstance(data_list, list):
        return None

    records = []
    for item in data_list:
        if isinstance(item, dict) and time_key in item:
            try:
                date = pd.to_datetime(item[time_key], errors='coerce')
                if pd.isna(date):
                    continue
                value = item.get(value_key)
                if value is None:
                    continue
                records.append({"date": date, value_name: value})
            except Exception:
                continue

    return pd.DataFrame(records) if records else None

# -----------------------------
# 特殊处理：饮食、运动、关注点
# -----------------------------
def diet_to_df(diet_list):
    if not isinstance(diet_list, list):
        return None
    records = []
    for item in diet_list:
        if isinstance(item, dict) and "时间" in item:
            date = pd.to_datetime(item["时间"], errors='coerce')
            if pd.isna(date):
                continue
            meals = len([k for k in item.keys() if k in ["食物", "零食", "加餐"]])  # 简单估算餐次
            notes = " + ".join([f"{item.get('食物','')}({item.get('量','')})"])
            records.append({"date": date, "meals": meals, "notes": notes})
    return pd.DataFrame(records) if records else None

def activities_to_df(acts_list):
    if not isinstance(acts_list, list):
        return None
    records = []
    for item in acts_list:
        if isinstance(item, dict) and "时间" in item:
            date = pd.to_datetime(item["时间"], errors='coerce')
            if pd.isna(date):
                continue
            duration_str = item.get("时长", "")
            duration = extract_minutes(duration_str)
            records.append({"date": date, "duration": duration})
    return pd.DataFrame(records) if records else None

def concerns_to_df(concerns_list):
    if not isinstance(concerns_list, list):
        return None
    records = []
    for item in concerns_list:
        if isinstance(item, dict) and "时间" in item:
            date = pd.to_datetime(item["时间"], errors='coerce')
            if pd.isna(date):
                continue
            issue = item.get("关注点", "未知问题")
            records.append({"date": date, "issue": issue})
    return pd.DataFrame(records) if records else None

def extract_minutes(duration: str) -> int:
    """解析 '30分钟' -> 30"""
    if not duration or not isinstance(duration, str):
        return 0
    import re
    match = re.search(r"(\d+)", duration)
    return int(match.group(1)) if match else 0

def render_health_consultation(client):
    """
    渲染健康咨询 AI 对话模块（支持流式输出 + 历史关注点上下文）
    :param client: 当前客户数据（包含 basic_info 等）
    """
    # 初始化 session_state 状态
    if "chat_active" not in st.session_state:
        st.session_state.chat_active = False
    if "chat_messages" not in st.session_state:
        pet_info = client['basic_info']
        name = pet_info.get("名字", "该宠物")
        species = pet_info.get("种类", "犬/猫")
        age = pet_info.get("年龄", "未知")

        system_content = f"""你是一名专业的宠物健康顾问，名叫「PetCare AI」。
你正在为一只 {age} 岁的 {species}（{name}）提供健康咨询服务。
请结合宠物的年龄、种类和常见护理知识，用中文友好、专业地回答用户关于饮食、运动、皮肤、情绪、疾病预防等问题。
如果问题超出宠物健康范畴，请礼貌说明你只专注于宠物服务。"""

        st.session_state.chat_messages = [{"role": "system", "content": system_content}]
        st.session_state.chat_history = []

    # 显示健康咨询标题
    st.markdown("### 💬 健康咨询")
    st.markdown("#### 🩺 与宠物健康助手对话")

    # -----------------------------
    # 新增：显示并选择历史关注点
    # -----------------------------
    concerns_data = client.get("concerns") or []
    available_concerns = []

    for item in concerns_data:
        if isinstance(item, dict) and "关注点" in item:
            issue = item["关注点"].strip()
            if issue:
                date = item.get("时间", "未知时间")
                available_concerns.append(f"{issue}（{date}）")

    if available_concerns:
        st.markdown("#### 🔍 历史关注点（可多选）")
        selected_options = st.multiselect(
            "选择需要参考的关注点（AI 将结合这些信息回答）",
            options=available_concerns,
            default=[],
            placeholder="可不选，或选择一个/多个"
        )
        # 提取纯关注点（去掉日期）
        selected_concerns = [
            opt.split("（")[0] for opt in selected_options if "（" in opt
        ] or selected_options  # 兼容无日期情况
    else:
        selected_concerns = []
        st.caption("📭 暂无历史关注点记录。")

    # -----------------------------
    # 显示聊天历史
    # -----------------------------
    for message in st.session_state.chat_history:
        with st.chat_message(message["role"]):
            st.write(message["content"])

    # -----------------------------
    # 聊天输入框
    # -----------------------------
    user_input = st.chat_input("请输入您的问题...", key="health_chat_input")

    # -----------------------------
    # 处理用户输入
    # -----------------------------
    if user_input and user_input.strip():
        st.session_state.chat_active = True

        # 构建增强版用户问题（加入关注点上下文）
        enhanced_input = user_input
        if selected_concerns:
            context = "【历史关注点参考】：" + "；".join(selected_concerns)
            enhanced_input = f"{context}\n\n用户当前问题：{user_input}"

        # 添加到消息历史
        st.session_state.chat_messages.append({"role": "user", "content": enhanced_input})
        st.session_state.chat_history.append({"role": "user", "content": user_input})

        # 显示用户消息（原始问题）
        with st.chat_message("user"):
            st.write(user_input)

        # AI 回复 - 流式输出
        with st.chat_message("assistant"):
            with st.spinner("PetCare AI 正在思考..."):
                try:
                    from openai import OpenAI
                    import os

                    api_key = os.getenv("DASHSCOPE_API_KEY")
                    base_url = os.getenv("DASHSCOPE_BASE_URL")

                    if not api_key:
                        st.error("❌ DASHSCOPE_API_KEY 未设置")
                    elif not base_url:
                        st.error("❌ DASHSCOPE_BASE_URL 未设置")
                    else:
                        client_openai = OpenAI(
                            api_key=api_key,
                            base_url=base_url.strip(),
                        )

                        message_placeholder = st.empty()
                        full_response = ""

                        stream = client_openai.chat.completions.create(
                            model="qwen-plus",
                            messages=st.session_state.chat_messages,
                            temperature=0.7,
                            max_tokens=1024,
                            stream=True,
                        )

                        for chunk in stream:
                            if chunk.choices:
                                content = chunk.choices[0].delta.content
                                if content:
                                    full_response += content
                                    message_placeholder.markdown(full_response + "▌")

                        message_placeholder.markdown(full_response)

                        st.session_state.chat_messages.append({"role": "assistant", "content": full_response})
                        st.session_state.chat_history.append({"role": "assistant", "content": full_response})

                except Exception as e:
                    st.error(f"🤖 AI 服务调用失败：{e}")
# -----------------------------
# AI 工具函数：生成问诊总结
# -----------------------------
def summarize_user_concerns(user_questions):
    """
    使用 AI 对用户提问列表进行归纳，生成一句简洁的关注点描述（中文，30字以内）
    :param user_questions: list[str]，用户的多条提问
    :return: str | None，返回总结文本或 None（失败时）
    """
    if not user_questions:
        return None

    try:
        from openai import OpenAI
        import os

        api_key = os.getenv("DASHSCOPE_API_KEY")
        base_url = os.getenv("DASHSCOPE_BASE_URL")

        if not api_key or not base_url:
            return None

        client_openai = OpenAI(api_key=api_key, base_url=base_url.strip())

        prompt = f"""
请对以下宠物主人提出的问题进行归纳总结，提炼出一个简洁、专业的「关注点」描述（不超过30字），用于归档到宠物健康档案中。

要求：
- 使用中文；
- 不要解释过程，只输出一句话；
- 聚焦最核心的健康问题或咨询意图；
- 避免使用“主人担心”这类表述，直接说问题。

问题记录：
{'；'.join(user_questions)}

请输出总结：
""".strip()

        response = client_openai.chat.completions.create(
            model="qwen-plus",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
            max_tokens=64,
            top_p=0.9
        )
        summary = response.choices[0].message.content.strip()
        # 清理多余引号或句式
        summary = summary.strip('。"\'')
        return summary if len(summary) > 0 else None

    except Exception as e:
        st.error(f"🤖 AI 总结生成失败：{e}")
        return None

# -----------------------------
# 主函数入口
# -----------------------------
def run():
    st.header("🐾 宠物客户管理系统")
    st.subheader("📸 拍照核验身份")

    # ================= 初始化 session_state =================
    if "step" not in st.session_state:
        st.session_state.step = "input_id"  # 流程：input_id → fetch_data → take_photo → show_dashboard
    if "pet_id" not in st.session_state:
        st.session_state.pet_id = None
    if "client" not in st.session_state:
        st.session_state.client = None
    if "photo_taken" not in st.session_state:
        st.session_state.photo_taken = False
    if "photo" not in st.session_state:
        st.session_state.photo = None

        # ========== 步骤1：输入 Pet ID ==========
    if st.session_state.step == "input_id":
        st.markdown("### 🔍 请输入宠物 ID")

        # 使用 text_input，无按钮，回车触发
        pet_id_str = st.text_input(
            label="输入宠物 ID",
            value="",
            placeholder="输入数字 ID 后按回车...",
            label_visibility="collapsed",
            key="pet_id_input_field"  # 关键：使用 key 来管理状态
        )

        # 当用户输入内容并按回车时，st.text_input 会刷新，进入此判断
        if pet_id_str:
            if pet_id_str.isdigit():
                st.session_state.pet_id = int(pet_id_str)
                st.session_state.step = "fetch_data"
                st.rerun()
            else:
                st.error(f"⚠️ '{pet_id_str}' 不是有效的数字 ID。")

    # ========== 步骤2：查询数据库 ==========
    elif st.session_state.step == "fetch_data":
        conn = get_db_connection()
        if not conn:
            st.error("❌ 数据库连接失败，请检查环境变量。")
            if st.button("🔙 返回重试"):
                st.session_state.step = "input_id"
                st.rerun()
            st.stop()

        try:
            query = """
            SELECT pet_id, basic_info, height, weight, diet, activities, concerns 
            FROM clients WHERE pet_id = %s
            """
            df = pd.read_sql_query(query, conn, params=[st.session_state.pet_id])

            if df.empty:
                st.error(f"❌ 未找到 Pet ID 为 `{st.session_state.pet_id}` 的客户，请检查输入。")
                if st.button("🔙 返回修改"):
                    st.session_state.step = "input_id"
                    st.rerun()
                st.stop()

            client = df.iloc[0]
            st.session_state.client = client
            st.session_state.step = "take_photo"
            st.rerun()

        except Exception as e:
            st.error(f"🔍 查询失败：{e}")
            if st.button("🔙 返回"):
                st.session_state.step = "input_id"
                st.rerun()
            st.stop()
        finally:
            conn.close()

    # ========== 步骤3：拍照验证 ==========
    elif st.session_state.step == "take_photo":
        st.markdown("### 📷 请拍摄当前宠物的照片")

        if not st.session_state.photo_taken:
            photo = st.camera_input("点击拍照", key=f"camera_{st.session_state.pet_id}")

            if photo:
                st.session_state.photo_taken = True
                st.session_state.photo = photo
                st.success("📸 拍照成功！")
                st.image(st.session_state.photo, caption="本次拍摄的照片", use_container_width=True)
                st.info("正在加载服务...")
                import time
                time.sleep(1.5)  # 可选：模拟加载动画，也可去掉
                st.session_state.step = "show_dashboard"
                st.rerun()
            else:
                st.info("请对准宠物，点击上方按钮拍照。")

    # ========== 步骤4：主界面 + 图表 + AI 聊天 ==========
    elif st.session_state.step == "show_dashboard":
        client = st.session_state.client
        basic_info = client['basic_info']

        # --- 显示客户基本信息（双列：照片 + 信息）---
        st.markdown("### 📋 客户基本信息")
        col_photo, col_info = st.columns([1, 1])

        with col_photo:
            st.markdown("#### 🖼️ 当前照片")
            if st.session_state.photo:
                st.image(st.session_state.photo, use_container_width=True)
            else:
                st.markdown("📷 未拍摄照片")

        with col_info:
            st.markdown("#### 🐾 客户信息")

            basic_info = client['basic_info']

            if not basic_info:
               st.markdown("⚠️ 无客户信息")
            else:
               info_lines = []
               for key, value in basic_info.items():
            # 清理键和值
                    key_str = str(key).strip()
                    value_str = str(value).strip() if value is not None else ""

            # 替换空值
                    if not value_str:
                          value_str = "未填写"

            # 添加 Markdown 条目
                    info_lines.append(f"- **{key_str}**: {value_str}")

               if info_lines:
                    st.markdown("\n".join(info_lines))
               else:
                  st.markdown("📭 信息为空")

                        # --- 图表展示 ---
        with st.expander("📊 各项指标历史记录", expanded=False):
            st.markdown("### 📈 历史数据可视化")

            # 通用函数：为 Plotly 图表设置中文字体和标签
            def update_fig_layout(fig, x_title=None, y_title=None):
                fig.update_layout(
                    font=dict(family="SimHei, Microsoft YaHei, sans-serif", size=14, color="black"),
                    title=dict(font=dict(size=16)),
                    xaxis_title=x_title,
                    yaxis_title=y_title,
                    hovermode="x unified",
                    showlegend=True
                )
                return fig

            col1, col2 = st.columns(2)

            # ------------------------------
            # 1. 体长图（折线图）
            # ------------------------------
            with col1:
                height_data = client['height']
                df_h = to_standard_df(height_data, value_key="体长", value_name="value")
                if df_h is not None and len(df_h) > 0:
                    df_h['日期'] = df_h['date'].dt.strftime('%Y-%m-%d')
                    df_h['体长 (cm)'] = df_h['value'].round(1)

                    fig_h = px.line(
                        df_h,
                        x='date',
                        y='value',
                        title="📏 体长变化趋势",
                        markers=True,
                        hover_data={'value': False, 'date': False},  # 隐藏默认字段
                        custom_data=['日期', '体长 (cm)']
                    )
                    fig_h.update_traces(
                        hovertemplate=(
                            "<b>📏 体长记录</b><br>"
                            "📅 日期: %{customdata[0]}<br>"
                            "📏 体长: %{customdata[1]} cm<extra></extra>"
                        )
                    )
                    fig_h = update_fig_layout(fig_h, x_title="日期", y_title="体长 (cm)")
                    st.plotly_chart(fig_h, use_container_width=True)
                else:
                    st.caption("📏 体长：无有效数据")

            # ------------------------------
            # 2. 体重图（折线图）
            # ------------------------------
            with col2:
                weight_data = client['weight']
                df_w = to_standard_df(weight_data, value_key="体重", value_name="value")
                if df_w is not None and len(df_w) > 0:
                    df_w['日期'] = df_w['date'].dt.strftime('%Y-%m-%d')
                    df_w['体重 (kg)'] = df_w['value'].round(1)

                    fig_w = px.line(
                        df_w,
                        x='date',
                        y='value',
                        title="⚖️ 体重变化趋势",
                        markers=True,
                        color_discrete_sequence=["#FF7F0E"],
                        hover_data={'value': False, 'date': False},
                        custom_data=['日期', '体重 (kg)']
                    )
                    fig_w.update_traces(
                        hovertemplate=(
                            "<b>⚖️ 体重记录</b><br>"
                            "📅 日期: %{customdata[0]}<br>"
                            "⚖️ 体重: %{customdata[1]} kg<extra></extra>"
                        )
                    )
                    fig_w = update_fig_layout(fig_w, x_title="日期", y_title="体重 (kg)")
                    st.plotly_chart(fig_w, use_container_width=True)
                else:
                    st.caption("⚖️ 体重：无有效数据")

            # ------------------------------
            # 3. 饮食图（柱状图）
            # ------------------------------
            with col1:
                diet_data = client['diet']
                df_d = diet_to_df(diet_data)
                if df_d is not None and len(df_d) > 0:
                    # 确保 notes 字段存在
                    df_d['notes'] = df_d['notes'].fillna("无记录")
                    df_d['日期'] = df_d['date'].dt.strftime('%Y-%m-%d')
                    df_d['餐次'] = df_d['meals']

                    fig_d = px.bar(
                        df_d,
                        x='date',
                        y='meals',
                        title="🍽️ 每日餐次",
                        text='meals',
                        hover_data={'meals': False, 'date': False},
                        custom_data=['日期', '餐次', 'notes']
                    )
                    fig_d.update_traces(
                        hovertemplate=(
                            "<b>🍽️ 饮食记录</b><br>"
                            "📅 日期: %{customdata[0]}<br>"
                            "🍽️ 餐次: %{customdata[1]} 餐<br>"
                            "📝 细节: %{customdata[2]}<extra></extra>"
                        )
                    )
                    fig_d = update_fig_layout(fig_d, x_title="日期", y_title="餐次")
                    st.plotly_chart(fig_d, use_container_width=True)
                else:
                    st.caption("🍽️ 饮食：无有效数据")

            # ------------------------------
            # 4. 运动图（面积图）
            # ------------------------------
            with col2:
                activities_data = client['activities']
                df_a = activities_to_df(activities_data)
                if df_a is not None and len(df_a) > 0:
                    df_a['日期'] = df_a['date'].dt.strftime('%Y-%m-%d')
                    df_a['时长 (分钟)'] = df_a['duration']

                    fig_a = px.area(
                        df_a,
                        x='date',
                        y='duration',
                        title="🏃 每日运动时长（分钟）",
                        color_discrete_sequence=["#2CA02C"],
                        hover_data={'duration': False, 'date': False},
                        custom_data=['日期', '时长 (分钟)']
                    )
                    fig_a.update_traces(
                        hovertemplate=(
                            "<b>🏃 运动记录</b><br>"
                            "📅 日期: %{customdata[0]}<br>"
                            "🏃 时长: %{customdata[1]} 分钟<extra></extra>"
                        )
                    )
                    fig_a = update_fig_layout(fig_a, x_title="日期", y_title="时长 (分钟)")
                    st.plotly_chart(fig_a, use_container_width=True)
                else:
                    st.caption("🏃 运动：无有效数据")

            # ------------------------------
            # 5. 关注点图（散点图）
            # ------------------------------
            with st.container():
                concerns_data = client['concerns']
                df_c = concerns_to_df(concerns_data)
                if df_c is not None and len(df_c) > 0:
                    df_c['日期'] = df_c['date'].dt.strftime('%Y-%m-%d')

                    fig_c = px.scatter(
                        df_c,
                        x='date',
                        y='issue',
                        title="⚠️ 关注点记录",
                        height=300,
                        hover_data={'date': False},
                        custom_data=['日期', 'issue']
                    )
                    fig_c.update_traces(
                        hovertemplate=(
                            "<b>⚠️ 关注点</b><br>"
                            "📅 日期: %{customdata[0]}<br>"
                            "📌 问题: %{customdata[1]}<extra></extra>"
                        )
                    )
                    fig_c = update_fig_layout(fig_c, x_title="日期", y_title="关注点")
                    st.plotly_chart(fig_c, use_container_width=True)
                else:
                    st.caption("⚠️ 关注点：无有效数据")
            # --- 今日数据录入表单 ---
            st.markdown("### 📥 录入今日数据")
            with st.form(key="daily_data_form"):
                st.markdown("#### 🐾 基础测量")
                col_h, col_w = st.columns(2)
                with col_h:
                    height = st.number_input("体长 (cm)", min_value=0.0, max_value=300.0, step=0.5, format="%.1f")
                with col_w:
                    weight = st.number_input("体重 (kg)", min_value=0.0, max_value=100.0, step=0.1, format="%.1f")

                st.markdown("#### 🍲 今日饮食")
                diet_items = st.text_area(
                    "饮食记录（每行一条：食物,量，例如：狗粮,200g）",
                    placeholder="狗粮,300g\n零食,50g\n加餐,鸡肉,100g",
                    height=100
                )

                st.markdown("#### 🏃 今日运动")
                activities_items = st.text_area(
                    "运动记录（每行一条：活动,时长，例如：散步,30分钟）",
                    placeholder="散步,30分钟\n玩球,15分钟",
                    height=100
                )

                submit_btn = st.form_submit_button("✅ 确定并保存")

                if submit_btn:
                    from datetime import datetime
                    import json

                    today_str = datetime.now().strftime("%Y-%m-%d")
                    updated_fields = {}  # 只有真正需要更新的字段才放进来

                    # -------------------------------
                    # 1. 体长 (height)
                    # -------------------------------
                    if height > 0:
                        new_height = {"体长": round(height, 1), "时间": today_str}
                        current_height = (st.session_state.client.get("height") or [])
                        current_height.append(new_height)
                        updated_fields["height"] = current_height
                    else:
                        # 可选：提示用户
                        if height == 0:
                            st.info("ℹ️ 体长为 0，跳过更新。")

                    # -------------------------------
                    # 2. 体重 (weight)
                    # -------------------------------
                    if weight > 0:
                        new_weight = {"体重": round(weight, 1), "时间": today_str}
                        current_weight = (st.session_state.client.get("weight") or [])
                        current_weight.append(new_weight)
                        updated_fields["weight"] = current_weight
                    else:
                        if weight == 0:
                            st.info("ℹ️ 体重为 0，跳过更新。")

                    # -------------------------------
                    # 3. 饮食 (diet)
                    # -------------------------------
                    new_diet = []
                    if diet_items.strip():
                        for line in diet_items.strip().split("\n"):
                            parts = [p.strip() for p in line.split(",") if p.strip()]
                            if len(parts) >= 2:
                                food = parts[0]
                                amount = parts[1]
                                record = {"食物": food, "量": amount, "时间": today_str}
                                if len(parts) > 2:
                                    record["备注"] = " ".join(parts[2:])
                                new_diet.append(record)

                    if new_diet:
                        current_diet = (st.session_state.client.get("diet") or [])
                        current_diet.extend(new_diet)
                        updated_fields["diet"] = current_diet
                    else:
                        if diet_items.strip() == "":
                            st.info("ℹ️ 饮食为空，跳过更新。")
                        # 否则可能是格式错误
                        elif diet_items.strip():
                            st.warning("⚠️ 饮食输入格式有误（应为：食物,量），未更新。")

                    # -------------------------------
                    # 4. 运动 (activities)
                    # -------------------------------
                    new_activities = []
                    if activities_items.strip():
                        for line in activities_items.strip().split("\n"):
                            parts = [p.strip() for p in line.split(",") if p.strip()]
                            if len(parts) >= 2:
                                activity = parts[0]
                                duration = parts[1]
                                record = {"活动": activity, "时长": duration, "时间": today_str}
                                if len(parts) > 2:
                                    record["备注"] = " ".join(parts[2:])
                                new_activities.append(record)

                    if new_activities:
                        current_activities = (st.session_state.client.get("activities") or [])
                        current_activities.extend(new_activities)
                        updated_fields["activities"] = current_activities
                    else:
                        if activities_items.strip() == "":
                            st.info("ℹ️ 运动为空，跳过更新。")
                        elif activities_items.strip():
                            st.warning("⚠️ 运动输入格式有误（应为：活动,时长），未更新。")

                                        # -------------------------------
                    # 检查是否有任何字段需要更新
                    # -------------------------------
                    if not updated_fields:
                        st.warning("📭 没有有效数据需要保存。")
                        # 不 return，继续执行后续页面内容
                    else:
                        # 只有有数据时才执行数据库更新
                        conn = get_db_connection()
                        if not conn:
                            st.error("❌ 无法连接数据库")
                        else:
                            try:
                                with conn.cursor() as cur:
                                    set_parts = []
                                    values = []
                                    for field, data in updated_fields.items():
                                        set_parts.append(f"{field} = %s")
                                        values.append(json.dumps(data, ensure_ascii=False))
                                    values.append(st.session_state.pet_id)

                                    # 构建 SQL：确保 set_parts 不为空
                                    if not set_parts:
                                        st.error("❌ 更新字段为空，不应进入此分支。")
                                    else:
                                        query = f"UPDATE clients SET {', '.join(set_parts)} WHERE pet_id = %s"
                                        cur.execute(query, values)
                                        conn.commit()

                                        # 更新 session_state.client
                                        for k, v in updated_fields.items():
                                            st.session_state.client[k] = v

                                        st.success("✅ 数据已成功保存！共更新字段：" + ", ".join(updated_fields.keys()))

                            except Exception as e:
                                st.error("💾 数据库更新失败")
                                st.exception(e)  # 调试用，上线可注释
                            finally:
                                conn.close()
        # --- AI 健康咨询 ---
        render_health_consultation(client)

        # --- 底部操作按钮：清空对话 + 返回首页 ---
        st.markdown("---")
        col_summary, col_clear, col_home = st.columns([1, 1, 1])
        with col_summary:
            if st.button("📝 问诊总结", key="btn_summary", use_container_width=True):
                if not st.session_state.chat_history:
                    st.warning("💬 当前无聊天记录，无需总结。")
                else:
                    user_questions = [
                        msg["content"] for msg in st.session_state.chat_history
                        if msg["role"] == "user"
                    ]
                    if not user_questions:
                        st.warning("🔍 未检测到用户提问内容。")
                    else:
                        # --- 显示加载状态 ---
                        with st.spinner("🧠 PetCare AI 正在分析问诊内容..."):
                            progress_bar = st.progress(30)  # 模拟开始

                            try:
                                # 模拟逐步推进（视觉反馈）
                                import time
                                time.sleep(0.3)
                                progress_bar.progress(50)

                                # 调用 AI 函数生成总结
                                summary_text = summarize_user_concerns(user_questions)

                                progress_bar.progress(80)

                                if summary_text:
                                    from datetime import datetime
                                    import json

                                    now_str = datetime.now().strftime("%Y-%m-%d")
                                    new_concern = {"时间": now_str, "关注点": summary_text}

                                    current_concerns = client['concerns']
                                    if not isinstance(current_concerns, list):
                                        current_concerns = []
                                    current_concerns.append(new_concern)

                                    # 更新数据库
                                    conn = get_db_connection()
                                    if conn:
                                        try:
                                            with conn.cursor() as cur:
                                                cur.execute(
                                                    "UPDATE clients SET concerns = %s WHERE pet_id = %s",
                                                    (json.dumps(current_concerns, ensure_ascii=False), st.session_state.pet_id)
                                                )
                                                conn.commit()
                                                st.session_state.client['concerns'] = current_concerns
                                        except Exception as e:
                                            st.error(f"💾 数据库更新失败：{e}")
                                            progress_bar.empty()
                                            st.stop()
                                        finally:
                                            conn.close()
                                    else:
                                        st.error("🔗 无法连接数据库。")
                                        progress_bar.empty()
                                        st.stop()

                                    # 完成
                                    progress_bar.progress(100)
                                    time.sleep(0.2)
                                    progress_bar.empty()  # 清除进度条
                                    st.success(f"✅ 已记录关注点：{summary_text}")
                                else:
                                    progress_bar.empty()
                                    st.error("⚠️ 未能生成有效总结，请重试。")

                            except Exception as e:
                                progress_bar.empty()
                                st.error(f"❌ 处理过程中出错：{e}")
        with col_clear:
            if st.button("🗑️ 清空对话", key="clear_chat_btn_1", use_container_width=True):
                st.session_state.chat_messages = st.session_state.chat_messages[:1]  # 保留 system
                st.session_state.chat_history = []
                st.session_state.chat_active = False
                st.rerun()

        with col_home:
            if st.button("🔙 返回首页", key="btn_home", use_container_width=True):
                keys_to_clear = [
                    "step", "pet_id", "client", "photo_taken", "photo",
                    "chat_messages", "chat_history", "chat_active"
                ]
                for key in keys_to_clear:
                    st.session_state.pop(key, None)
                st.rerun()