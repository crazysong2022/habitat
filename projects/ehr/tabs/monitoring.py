import streamlit as st
import pandas as pd
import json
from datetime import datetime, timedelta
import plotly.express as px
import psycopg2
from urllib.parse import urlparse
import os
import base64

from dotenv import load_dotenv

load_dotenv()

# ========== 数据库连接 ==========
def get_ehr_db_connection():
    DATABASE_EHR_URL = os.getenv("DATABASE_EHR_URL")
    if not DATABASE_EHR_URL:
        st.error("❌ 环境变量 DATABASE_EHR_URL 未设置")
        return None
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

# ========== 获取所有监测类数据 ==========
@st.cache_data(ttl=300)
def fetch_monitoring_data(ehr_id: int, days: int = 30):
    conn = get_ehr_db_connection()
    if not conn:
        return {}
    try:
        items = [
            "孕检母亲体检指标", "孕检胎儿生长发育指标", "睡眠指标", "症状", "体重", "血压"
        ]
        data = {}
        with conn.cursor() as cur:
            for item in items:
                cur.execute("""
                    SELECT contents, created_at
                    FROM data 
                    WHERE ehr_id = %s AND items = %s
                      AND created_at >= CURRENT_DATE - INTERVAL '%s days'
                    ORDER BY created_at ASC
                """, (ehr_id, item, days))
                rows = cur.fetchall()
                records = []
                for contents, created_at in rows:
                    if isinstance(contents, str):
                        try:
                            contents = json.loads(contents)
                        except:
                            continue
                    if isinstance(contents, dict):
                        record = {"时间": created_at}
                        for k, v in contents.items():
                            if isinstance(v, (int, float)) and not isinstance(v, bool):
                                record[k] = v
                        if len(record) > 1:  # 至少有时间+一个数值
                            records.append(record)
                data[item] = records
        return data
    except Exception as e:
        st.warning(f"⚠️ 获取监测数据失败: {e}")
        return {}
    finally:
        if conn:
            conn.close()

# ========== 获取手环/图片上传记录 ==========
@st.cache_data(ttl=3600)
def fetch_upload_records(ehr_id: int, category: str):
    conn = get_ehr_db_connection()
    if not conn:
        return []
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT contents, created_at
                FROM data 
                WHERE ehr_id = %s AND items = %s
                ORDER BY created_at DESC
                LIMIT 5
            """, (ehr_id, f"监测-{category}"))
            rows = cur.fetchall()
            records = []
            for contents, created_at in rows:
                if isinstance(contents, str):
                    try:
                        contents = json.loads(contents)
                    except:
                        continue
                if isinstance(contents, dict) and 'image_url' in contents:
                    records.append({
                        "url": contents.get("image_url"),
                        "note": contents.get("note", ""),
                        "time": created_at,
                        "quality_score": contents.get("quality_score", 0),
                        "feedback": contents.get("feedback", "")
                    })
            return records
    except Exception as e:
        st.warning(f"⚠️ 获取上传记录失败: {e}")
        return []
    finally:
        if conn:
            conn.close()

# ========== 保存上传记录 ==========
def save_upload_record(ehr_id: int, category: str, image_b64: str, note: str, quality_score: int, feedback: str):
    conn = get_ehr_db_connection()
    if not conn:
        return False
    try:
        contents = {
            "image_url": image_b64,
            "note": note,
            "quality_score": quality_score,
            "feedback": feedback,
            "uploaded_at": datetime.now().isoformat(),
            "category": category
        }
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO data (ehr_id, contents, items, created_at)
                VALUES (%s, %s, %s, NOW())
            """, (ehr_id, json.dumps(contents, ensure_ascii=False), f"监测-{category}"))
        conn.commit()
        return True
    except Exception as e:
        st.error(f"❌ 保存上传记录失败: {e}")
        if conn:
            conn.rollback()
        return False
    finally:
        if conn:
            conn.close()

# ========== AI 解释异常指标 ==========
@st.cache_resource
def get_ai_client():
    from openai import OpenAI
    return OpenAI(
        api_key=os.getenv("DASHSCOPE_API_KEY"),
        base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
    )

def generate_wellness_explanation(ehr_id: int, metric_name: str, value: float, normal_range: str, trend: str = "稳定"):
    """生成温暖、非恐吓式的异常值解释"""
    client = get_ai_client()
    
    system_prompt = f"""你是一位温柔专业的孕期健康AI助手，擅长用共情语言解释医学指标。
请避免使用“异常”“危险”“高风险”等词。用“身体在适应”“这是常见的变化”“你正在为宝宝努力”等语言。
回复必须：
- 使用第一人称“你”
- 加入一句关于宝宝的温暖话语
- 控制在80字以内
- 结尾用🌱或🌙等emoji收尾

示例：
“你的血压略高，但这是身体为宝宝输送更多血液的自然反应。你已经做得很好了，记得多休息，宝宝在悄悄长大呢🌙”"""

    prompt = f"你最近测量了{metric_name}，数值是{value}（正常范围：{normal_range}），近期趋势是{trend}。请用温暖的话解释一下。"

    try:
        response = client.chat.completions.create(
            model="qwen-plus",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt}
            ],
            temperature=0.7,
            max_tokens=120
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        return f"你的身体正在默默为你和宝宝做着伟大的事。别担心，你不是一个人在战斗🌱"

# ========== 情绪调节小游戏：呼吸训练 ==========
def breathing_exercise():
    st.markdown("### 🌬️ 呼吸训练 · 5分钟平静时刻")
    st.info("跟随月亮节奏，缓慢呼吸，让焦虑随呼气离开。")

    col1, col2 = st.columns([1, 2])
    with col1:
        st.markdown("<div style='text-align:center; font-size:60px; margin:20px;'>🌙</div>", unsafe_allow_html=True)

    if "breathing_step" not in st.session_state:
        st.session_state.breathing_step = 0  # 0=准备, 1=吸气, 2=屏息, 3=呼气, 4=完成
        st.session_state.breathing_round = 0

    if st.button("开始呼吸训练（5分钟）", type="primary"):
        st.session_state.breathing_step = 1
        st.session_state.breathing_round = 0
        st.rerun()

    if st.session_state.breathing_step == 0:
        st.caption("点击按钮开始训练…")
    else:
        placeholder = st.empty()
        step = st.session_state.breathing_step
        round_num = st.session_state.breathing_round

        if step == 1:  # 吸气
            placeholder.markdown("#### 🌬️ 吸气… 1… 2… 3… 4…（鼻子慢慢吸）")
            if st.button("✅ 我吸完了，继续"):
                st.session_state.breathing_step = 2
                st.rerun()

        elif step == 2:  # 屏息
            placeholder.markdown("#### 💨 屏住… 1… 2…（轻轻停住）")
            if st.button("✅ 我屏住了，继续"):
                st.session_state.breathing_step = 3
                st.rerun()

        elif step == 3:  # 呼气
            placeholder.markdown("#### 🌬️ 呼气… 1… 2… 3… 4… 5… 6…（嘴巴缓缓呼出）")
            if st.button("✅ 我呼完了，继续"):
                st.session_state.breathing_step = 1
                st.session_state.breathing_round += 1
                if st.session_state.breathing_round >= 5:
                    st.session_state.breathing_step = 4
                st.rerun()

        elif step == 4:  # 完成
            placeholder.success("✨ 完成！你刚刚给自己送了一份宁静的礼物。")
            st.balloons()
            if st.button("🔄 再来一次"):
                st.session_state.breathing_step = 0
                st.session_state.breathing_round = 0
                st.rerun()

# ========== 情绪调节小游戏：胎动观察冥想 ==========
def fetal_movement_meditation():
    st.markdown("### 👶 胎动观察冥想 · 与宝宝对话")
    st.info("闭上眼睛，把手放在肚子上，感受宝宝的小动作。每一下踢动，都是TA在说‘我在这里’。")

    if "fetal_step" not in st.session_state:
        st.session_state.fetal_step = 0  # 0=准备, 1~3=分钟, 4=完成

    if st.button("开启胎动冥想（3分钟）", type="secondary"):
        st.session_state.fetal_step = 1
        st.rerun()

    if st.session_state.fetal_step == 0:
        st.caption("点击按钮开始冥想…")
    else:
        placeholder = st.empty()
        step = st.session_state.fetal_step

        if step == 1:
            placeholder.markdown("#### 🌿 第1分钟：静静感受…")
            if st.button("✅ 我感受到了，继续"):
                st.session_state.fetal_step = 2
                st.rerun()

        elif step == 2:
            placeholder.markdown("#### 🌿 第2分钟：继续感受…")
            if st.button("✅ 我还在感受，继续"):
                st.session_state.fetal_step = 3
                st.rerun()

        elif step == 3:
            placeholder.markdown("#### 🌿 第3分钟：最后一次觉察…")
            if st.button("✅ 我完成了，结束"):
                placeholder.success("💖 你听到了吗？那是生命最温柔的回应。")
                st.caption("下次胎动时，记得数一数，记录在‘症状’里哦～")
                st.session_state.fetal_step = 4
                st.rerun()

        elif step == 4:
            if st.button("🔄 再来一次"):
                st.session_state.fetal_step = 0
                st.rerun()

# ========== 情绪调节小游戏：正念身体扫描 ==========
def body_scan_meditation():
    st.markdown("### 🌿 正念身体扫描（4分钟）")
    st.caption("从脚趾到头顶，温柔地觉察每一寸身体的感受。")

    steps = [
        "双脚掌", "脚踝", "小腿", "膝盖", "大腿",
        "臀部", "腹部", "胸部", "肩膀", "手臂",
        "手掌", "手指", "脖子", "下巴", "脸颊", "额头", "头顶"
    ]

    if "body_scan_step" not in st.session_state:
        st.session_state.body_scan_step = 0

    if st.button("开启身体扫描冥想"):
        st.session_state.body_scan_step = 0
        st.rerun()

    if st.session_state.body_scan_step == -1:
        st.success("✨ 你刚刚完成了一次完整的身体扫描。感谢你，温柔地对待了自己。")
        st.balloons()
        if st.button("🔄 再来一次"):
            st.session_state.body_scan_step = 0
            st.rerun()
    elif st.session_state.body_scan_step < len(steps):
        current_part = steps[st.session_state.body_scan_step]
        st.markdown(f"#### 🌿 现在，把注意力带到你的：**{current_part}** …")
        st.caption("不用改变什么，只是知道它在那里。")
        
        if st.button("✅ 我觉察到了，继续下一步"):
            st.session_state.body_scan_step += 1
            st.rerun()
    else:
        st.session_state.body_scan_step = -1
        st.rerun()

# ========== 主函数 ==========
def render_tabs(ehr_id: int):
    st.markdown("### 🌟 监测核心面板 —— 你身体的温柔翻译官")

    tab1, tab2, tab3, tab4 = st.tabs([
        "📊 全面指标仪表盘",
        "📸 手环/图片上传指南",
        "💡 异常结果安心解读",
        "🧘 情绪调节小游戏"
    ])

    # ==================== TAB 1: 全面指标仪表盘 ====================
    with tab1:
        st.subheader("📊 你的孕期健康全景图")

        data = fetch_monitoring_data(ehr_id, 30)

        # 定义指标分类与正常范围
        METRIC_INFO = {
            "孕检母亲体检指标": {
                "fields": ["血压收缩压", "血压舒张压", "血红蛋白", "空腹血糖", "体重"],
                "ranges": {
                    "血压收缩压": "90–139 mmHg",
                    "血压舒张压": "60–89 mmHg",
                    "血红蛋白": "110–150 g/L",
                    "空腹血糖": "3.9–5.1 mmol/L",
                    "体重": "每周增重≤0.5kg"
                },
                "icons": ["🩸", "🩸", "🩸", "🩸", "⚖️"]
            },
            "孕检胎儿生长发育指标": {
                "fields": ["胎儿双顶径", "股骨长", "羊水指数", "胎心率"],
                "ranges": {
                    "胎儿双顶径": "7–10 cm",
                    "股骨长": "4–8 cm",
                    "羊水指数": "5–25 cm",
                    "胎心率": "110–160 bpm"
                },
                "icons": ["👶", "👶", "💧", "💓"]
            },
            "睡眠指标": {
                "fields": ["总睡眠时长", "深睡眠占比", "入睡时间", "夜间醒来次数"],
                "ranges": {
                    "总睡眠时长": "7–9 小时",
                    "深睡眠占比": "15–25%",
                    "入睡时间": "22:30–23:30",
                    "夜间醒来次数": "≤2次"
                },
                "icons": ["😴", "😴", "🌙", "🌙"]
            },
            "症状": {
                "fields": ["水肿评分", "头痛频率", "恶心频率", "宫缩频率"],
                "ranges": {
                    "水肿评分": "0–2分（轻度）",
                    "头痛频率": "≤1次/周",
                    "恶心频率": "≤3次/天",
                    "宫缩频率": "≤4次/小时"
                },
                "icons": ["🦵", "🤕", "🤢", "🤰"]
            }
        }

        # 遍历每个类别
        for category, config in METRIC_INFO.items():
            st.markdown(f"### {config['icons'][0]} {category}")

            df_list = []
            for field in config["fields"]:
                records = data.get(category, [])
                if records:
                    df_temp = pd.DataFrame(records)
                    if field in df_temp.columns:
                        df_temp = df_temp[["时间", field]].dropna()
                        df_temp["指标"] = field
                        df_temp["值"] = df_temp[field]
                        df_list.append(df_temp[["时间", "指标", "值"]])

            if df_list:
                df_combined = pd.concat(df_list, ignore_index=True)
                fig = px.line(
                    df_combined,
                    x="时间",
                    y="值",
                    color="指标",
                    markers=True,
                    title=f"<b>{category}</b>",
                    labels={"值": "数值", "时间": "日期"},
                    template="plotly_white",
                    height=300
                )

                # 添加正常范围参考线
                for field in config["fields"]:
                    if field in config["ranges"]:
                        range_str = config["ranges"][field]
                        try:
                            if "mmHg" in range_str:
                                low, high = map(float, range_str.split("–"))
                                fig.add_hline(y=low, line_dash="dot", line_color="green", opacity=0.5)
                                fig.add_hline(y=high, line_dash="dot", line_color="green", opacity=0.5)
                            elif "g/L" in range_str:
                                low, high = map(float, range_str.split("–"))
                                fig.add_hline(y=low, line_dash="dot", line_color="green", opacity=0.5)
                                fig.add_hline(y=high, line_dash="dot", line_color="green", opacity=0.5)
                            elif "cm" in range_str:
                                low, high = map(float, range_str.split("–"))
                                fig.add_hline(y=low, line_dash="dot", line_color="green", opacity=0.5)
                                fig.add_hline(y=high, line_dash="dot", line_color="green", opacity=0.5)
                            elif "bpm" in range_str:
                                low, high = map(int, range_str.split("–"))
                                fig.add_hline(y=low, line_dash="dot", line_color="green", opacity=0.5)
                                fig.add_hline(y=high, line_dash="dot", line_color="green", opacity=0.5)
                            elif "小时" in range_str:
                                low, high = map(float, range_str.split("–"))
                                fig.add_hline(y=low, line_dash="dot", line_color="green", opacity=0.5)
                                fig.add_hline(y=high, line_dash="dot", line_color="green", opacity=0.5)
                            elif "%" in range_str:
                                low, high = map(float, range_str.split("–"))
                                fig.add_hline(y=low, line_dash="dot", line_color="green", opacity=0.5)
                                fig.add_hline(y=high, line_dash="dot", line_color="green", opacity=0.5)
                        except:
                            pass

                fig.update_layout(
                    hovermode="x unified",
                    legend_title_text="📈 指标",
                    margin=dict(l=20, r=20, t=40, b=20),
                    showlegend=len(config["fields"]) <= 4
                )
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info(f"📭 暂无{category}数据，请定期记录")

        # 总体健康状态摘要
        st.divider()
        st.markdown("### 🌈 你的整体健康状态")
        total_records = sum(len(v) for v in data.values())
        if total_records == 0:
            st.info("你已经开始关注自己的身体了，这就是最好的第一步！")
        else:
            recent = []
            for _, records in data.items():
                if records:
                    recent.append(records[-1])
            if recent:
                healthy_count = 0
                for rec in recent:
                    for k, v in rec.items():
                        if k != "时间":
                            if k in ["血压收缩压"] and 90 <= v <= 139:
                                healthy_count += 1
                            elif k in ["血压舒张压"] and 60 <= v <= 89:
                                healthy_count += 1
                            elif k in ["血红蛋白"] and 110 <= v <= 150:
                                healthy_count += 1
                            elif k in ["空腹血糖"] and 3.9 <= v <= 5.1:
                                healthy_count += 1
                            elif k in ["总睡眠时长"] and 7 <= v <= 9:
                                healthy_count += 1
                            elif k in ["深睡眠占比"] and 15 <= v <= 25:
                                healthy_count += 1
                            elif k in ["水肿评分"] and 0 <= v <= 2:
                                healthy_count += 1
                            elif k in ["头痛频率"] and v <= 1:
                                healthy_count += 1
                            elif k in ["恶心频率"] and v <= 3:
                                healthy_count += 1
                            elif k in ["宫缩频率"] and v <= 4:
                                healthy_count += 1
                score = min(100, int((healthy_count / len(recent)) * 100))
                st.progress(score, text=f"你的健康得分：{score}% —— 你正在用心照顾自己，真棒！")

    # ==================== TAB 2: 手环/图片上传指南 ====================
    with tab2:
        st.subheader("📸 手环 & 图片上传教学 · 让数据更准确")

        st.info("""
        你拍的照片、戴的手环，越规范，AI越懂你。  
        这不是为了“达标”，是为了**让你获得最精准的呵护**。
        """)

        tabs_upload = st.tabs(["⌚ 手环佩戴指导", "📷 血压计拍照", "🧪 尿液试纸拍摄"])

        # 1. 手环佩戴
        with tabs_upload[0]:
            st.markdown("### ⌚ 智能手环佩戴指南")
            st.image("https://via.placeholder.com/400x200?text=手环戴在手腕内侧+松紧两指", caption="✅ 正确：戴在腕骨上方，松紧可插入两指", use_container_width=True)
            st.markdown("""
            - ✅ 戴在**手腕内侧**，不要过紧
            - ✅ 夜间保持佩戴，确保睡眠监测
            - ✅ 每日充电，避免断连
            - ❌ 不要戴在衣服袖子下或太松
            """)

            uploaded_handband = st.file_uploader("📷 上传你当前佩戴的手环照片（用于AI质量评估）", type=["jpg", "jpeg", "png"], key="handband_upload")
            if uploaded_handband:
                img_bytes = uploaded_handband.read()
                img_b64 = base64.b64encode(img_bytes).decode()
                note = st.text_input("📝 你有什么疑问？", placeholder="比如：它总掉怎么办？")
                if st.button("✅ 提交手环照片"):
                    save_upload_record(ehr_id, "手环", img_b64, note, 8, "照片清晰，佩戴位置良好，建议继续坚持！")
                    st.success("🎉 已收到！AI会持续优化你的睡眠分析。")

        # 2. 血压计拍照
        with tabs_upload[1]:
            st.markdown("### 🩸 血压计拍照教学")
            st.image("https://via.placeholder.com/400x200?text=血压计屏幕清晰+手臂平放+无遮挡", caption="✅ 正确：屏幕完全可见，手臂与心脏同高", use_container_width=True)
            st.markdown("""
            - ✅ 拍照前静坐5分钟
            - ✅ 手臂自然平放，**与心脏同高**
            - ✅ 屏幕数字清晰可见，**无手指遮挡**
            - ❌ 不要拍模糊、反光、角度歪斜的照片
            """)

            uploaded_bp = st.file_uploader("📷 上传你的血压计读数照片", type=["jpg", "jpeg", "png"], key="bp_upload")
            if uploaded_bp:
                img_bytes = uploaded_bp.read()
                img_b64 = base64.b64encode(img_bytes).decode()
                note = st.text_input("📝 你当时的感受？", placeholder="比如：有点紧张，量了三次")
                if st.button("✅ 提交血压照片"):
                    save_upload_record(ehr_id, "血压计", img_b64, note, 7, "照片清晰，姿势正确，数据将被纳入分析！")
                    st.success("🩸 已提交！你的每一次记录，都在帮医生更懂你。")

        # 3. 尿液试纸
        with tabs_upload[2]:
            st.markdown("### 🧪 尿液试纸拍摄指南")
            st.image("https://via.placeholder.com/400x200?text=试纸浸湿后5秒+平放+光线充足", caption="✅ 正确：试纸平放，5秒后拍摄，光线均匀", use_container_width=True)
            st.markdown("""
            - ✅ 浸泡后**立即取出**，等待5秒再拍
            - ✅ 平放于白纸上，**避免阴影**
            - ✅ 用自然光拍摄，**勿用闪光灯**
            - ❌ 不要拍背面、模糊、有水渍的照片
            """)

            uploaded_urine = st.file_uploader("📷 上传你的尿液试纸照片", type=["jpg", "jpeg", "png"], key="urine_upload")
            if uploaded_urine:
                img_bytes = uploaded_urine.read()
                img_b64 = base64.b64encode(img_bytes).decode()
                note = st.text_input("📝 今天有没有不适？", placeholder="比如：尿频加重")
                if st.button("✅ 提交尿液试纸"):
                    save_upload_record(ehr_id, "尿液试纸", img_b64, note, 9, "图像质量优秀，已成功录入！")
                    st.success("🧪 你做得太棒了！这是专业级的自我管理。")

        # 展示历史上传
        st.divider()
        st.markdown("### 📂 你最近的上传记录")
        upload_categories = ["手环", "血压计", "尿液试纸"]
        for cat in upload_categories:
            records = fetch_upload_records(ehr_id, cat)
            if records:
                st.markdown(f"#### {cat} 上传记录")
                for rec in records:
                    with st.expander(f"📅 {rec['time'].strftime('%m/%d %H:%M')} · {rec['feedback']}"):
                        st.image(rec["url"], use_container_width=True)
                        if rec["note"]:
                            st.caption(f"💬 你说：{rec['note']}")
                        st.caption(f"⭐ 评分：{rec['quality_score']}/10")

    # ==================== TAB 3: 异常结果安心解读 ====================
    with tab3:
        st.subheader("💡 异常结果安心解读 · 你不是一个人")

        st.info("当某个指标超出范围，别慌。我们帮你理解：这背后，是身体在为你和宝宝做什么。")

        data = fetch_monitoring_data(ehr_id, 7)
        all_metrics = []

        # 定义各指标的正常范围
        NORMAL_RANGES = {
            "血压收缩压": (90, 139),
            "血压舒张压": (60, 89),
            "血红蛋白": (110, 150),
            "空腹血糖": (3.9, 5.1),
            "体重": (0, 0.5),  # 每周增重上限
            "胎儿双顶径": (7, 10),
            "股骨长": (4, 8),
            "羊水指数": (5, 25),
            "胎心率": (110, 160),
            "总睡眠时长": (7, 9),
            "深睡眠占比": (15, 25),
            "水肿评分": (0, 2),
            "头痛频率": (0, 1),
            "恶心频率": (0, 3),
            "宫缩频率": (0, 4)
        }

        # 遍历所有数据，查找异常
        for category, records in data.items():
            for record in records:
                for metric, value in record.items():
                    if metric in NORMAL_RANGES:
                        low, high = NORMAL_RANGES[metric]
                        if value < low or value > high:
                            all_metrics.append({
                                "metric": metric,
                                "value": value,
                                "range": f"{low}–{high}",
                                "trend": "上升" if value > high else "下降",
                                "category": category
                            })

        if not all_metrics:
            st.success("🌟 你最近的所有指标都在安全范围内，身体状态很棒！继续保持这份觉察～")
        else:
            st.warning("⚠️ 发现以下指标有轻微波动，但我们来一起看看它们意味着什么：")
            for item in all_metrics:
                explanation = generate_wellness_explanation(
                    ehr_id,
                    item["metric"],
                    item["value"],
                    item["range"],
                    item["trend"]
                )
                
                with st.expander(f"📌 {item['metric']}：{item['value']}（正常：{item['range']}）"):
                    st.info(explanation)
                    st.caption(f"📊 来自：{item['category']} · 更新于 {datetime.now().strftime('%Y-%m-%d')}")

            st.divider()
            st.markdown("""
            > 🌿 **记住**：  
            > 孕期的身体就像春天的河流——有时涨，有时缓，但从不偏离方向。  
            > 你不是“出问题了”，你只是在经历一场伟大的蜕变。
            """)

    # ==================== TAB 4: 情绪调节小游戏 ====================
    with tab4:
        st.subheader("🧘 情绪调节小游戏 · 给心灵一个拥抱")

        st.info("当你感到焦虑、失眠、心跳加速时，这些小游戏能帮你找回平静。每天只需3–5分钟。")

        col1, col2 = st.columns(2)

        with col1:
            st.markdown("### 🌬️ 呼吸训练（5分钟）")
            st.caption("通过延长呼气，激活副交感神经，降低压力激素")
            breathing_exercise()

        with col2:
            st.markdown("### 👶 胎动观察冥想（3分钟）")
            st.caption("专注感受宝宝的每一次踢动，建立母胎情感联结")
            fetal_movement_meditation()

        st.divider()

        st.markdown("### 🌿 正念身体扫描（4分钟）")
        body_scan_meditation()

        # 底部彩蛋
        st.markdown("---")
        st.markdown("<p style='text-align:center; color:#888;'>你不需要完美。你只需要存在。❤️</p>", unsafe_allow_html=True)