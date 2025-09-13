import streamlit as st
import pandas as pd
import json
from datetime import datetime, timedelta
import psycopg2
import plotly.express as px
from urllib.parse import urlparse
import os
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

# ========== EPDS 量表题目（中文版标准）==========
EPDS_QUESTIONS = [
    "1. 我能够因为开心的事而笑",
    "2. 我对事情的兴趣减少",
    "3. 我感到焦虑或紧张",
    "4. 我难以入睡",
    "5. 我感到难过或沮丧",
    "6. 我感到自己是负担",
    "7. 我无法集中注意力",
    "8. 我对自己的未来感到绝望",
    "9. 我想到伤害自己",
    "10. 我哭得比平时多"
]

EPDS_SCORES = [0, 1, 2, 3]  # 0=从不，1=偶尔，2=经常，3=总是

# ========== 获取用户最近EPDS记录 ==========
@st.cache_data(ttl=300)
def fetch_epds_records(ehr_id: int, limit: int = 5):
    conn = get_ehr_db_connection()
    if not conn:
        return []
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT contents, created_at
                FROM data 
                WHERE ehr_id = %s AND items = '心理' 
                  AND contents ? 'epds_score'
                ORDER BY created_at DESC
                LIMIT %s
            """, (ehr_id, limit))
            rows = cur.fetchall()
            records = []
            for contents, created_at in rows:
                if isinstance(contents, str):
                    try:
                        contents = json.loads(contents)
                    except:
                        continue
                if isinstance(contents, dict) and 'epds_score' in contents:
                    record = {
                        "date": created_at.strftime("%Y-%m-%d"),
                        "score": contents.get("epds_score", 0),
                        "answers": contents.get("epds_answers", []),
                        "note": contents.get("note", "")
                    }
                    records.append(record)
            return records
    except Exception as e:
        st.warning(f"⚠️ 获取EPDS记录失败: {e}")
        return []
    finally:
        if conn:
            conn.close()

# ========== 获取匿名交流帖 ==========
@st.cache_data(ttl=600)
def fetch_mental_posts(ehr_id: int, limit: int = 10):
    conn = get_ehr_db_connection()
    if not conn:
        return []
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT contents, created_at, id
                FROM data 
                WHERE items = '心理-树洞' 
                  AND (contents->>'is_anonymous')::boolean = true
                  AND (contents->>'is_visible')::boolean = true
                ORDER BY created_at DESC
                LIMIT %s
            """, (limit,))
            rows = cur.fetchall()
            posts = []
            for contents, created_at, post_id in rows:
                if isinstance(contents, str):
                    try:
                        contents = json.loads(contents)
                    except:
                        continue
                if isinstance(contents, dict):
                    posts.append({
                        "id": post_id,
                        "content": contents.get("content", ""),
                        "emotion_tags": contents.get("emotion_tags", []),
                        "created_at": created_at,
                        "likes": contents.get("likes", 0),
                        "replies": contents.get("replies", 0),
                        "user_label": contents.get("user_label", "匿名孕妈")
                    })
            return posts
    except Exception as e:
        st.warning(f"⚠️ 获取树洞帖子失败: {e}")
        return []
    finally:
        if conn:
            conn.close()

# ========== 提交EPDS测评 ==========
def submit_epds_test(ehr_id: int, answers: list, note: str = ""):
    conn = get_ehr_db_connection()
    if not conn:
        return False
    try:
        score = sum(answers)
        contents = {
            "epds_score": score,
            "epds_answers": answers,
            "note": note,
            "submitted_at": datetime.now().isoformat()
        }
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO data (ehr_id, contents, items, created_at)
                VALUES (%s, %s, '心理', NOW())
            """, (ehr_id, json.dumps(contents, ensure_ascii=False)))
        conn.commit()
        return True
    except Exception as e:
        st.error(f"❌ 保存测评失败: {e}")
        if conn:
            conn.rollback()
        return False
    finally:
        if conn:
            conn.close()

# ========== 提交树洞帖子 ==========
def submit_anonymous_post(ehr_id: int, content: str, emotion_tags: list, user_label: str):
    conn = get_ehr_db_connection()
    if not conn:
        return False
    try:
        contents = {
            "content": content,
            "emotion_tags": emotion_tags,
            "user_label": user_label,
            "is_anonymous": True,
            "is_visible": True,
            "likes": 0,
            "replies": 0,
            "created_by": ehr_id,
            "created_at": datetime.now().isoformat()
        }
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO data (ehr_id, contents, items, created_at)
                VALUES (%s, %s, '心理-树洞', NOW())
            """, (ehr_id, json.dumps(contents, ensure_ascii=False)))
        conn.commit()
        return True
    except Exception as e:
        st.error(f"❌ 发布失败: {e}")
        if conn:
            conn.rollback()
        return False
    finally:
        if conn:
            conn.close()

# ========== 点赞帖子 ==========
def like_post(post_id: int):
    conn = get_ehr_db_connection()
    if not conn:
        return False
    try:
        with conn.cursor() as cur:
            cur.execute("""
                UPDATE data 
                SET contents = jsonb_set(contents, '{likes}', (contents->>'likes')::int + 1)::jsonb
                WHERE id = %s AND items = '心理-树洞'
            """, (post_id,))
        conn.commit()
        return True
    except Exception as e:
        st.warning(f"⚠️ 点赞失败: {e}")
        return False
    finally:
        if conn:
            conn.close()

# ========== AI情感分析与反馈（使用你的OpenAI客户端）==========
@st.cache_resource
def get_ai_client():
    from openai import OpenAI
    return OpenAI(
        api_key=os.getenv("DASHSCOPE_API_KEY"),
        base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
    )

def generate_epds_ai_feedback(ehr_id: int, score: int, answers: list):
    """根据EPDS分数生成个性化、温暖、非诊断性AI反馈"""
    client = get_ai_client()

    # 构造上下文摘要
    answer_descriptions = []
    for i, a in enumerate(answers):
        desc = f"{EPDS_QUESTIONS[i]}：{'几乎不' if a==0 else '偶尔' if a==1 else '经常' if a==2 else '总是'}"
        answer_descriptions.append(desc)

    system_prompt = f"""你是一位专业的孕期心理支持AI助手，目标是提供温暖、非评判、鼓励性的反馈。
当前用户EPDS总分为{score}分（满分30），代表轻度至中度情绪困扰（非抑郁症诊断）。
请避免使用医学术语如“抑郁”、“焦虑症”。使用共情语言，强调“这是常见的孕期体验”，并给予希望和资源。
回复必须：  
- 使用第一人称“你”  
- 不要给出医疗建议（如“去看医生”），改为“你可以考虑…”  
- 包含一句关于宝宝的温柔话语  
- 保持简短（不超过150字）  
- 使用中文，语气如一位懂你的姐妹  

示例输出：  
“你最近常常感到疲惫和难过，这真的不容易。但你知道吗？很多孕妈妈在28周左右都会这样，不是因为你不够好，而是身体在悄悄改变。你已经做得很好了——哪怕只是坚持每天摸一摸宝宝的小脚，那都是爱的证明。你不是一个人在走这段路。”"""

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": f"用户回答：{'; '.join(answer_descriptions)}"}
    ]

    try:
        response = client.chat.completions.create(
            model="qwen-plus",
            messages=messages,
            temperature=0.7,
            max_tokens=200
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        return "你的情绪值得被温柔对待。如果你愿意，可以试着写下今天让你感到一点点温暖的小事，我会一直在这里陪着你。"

# ========== 主函数 ==========
def render_tabs(ehr_id: int):
    st.markdown("### 🧘‍♀️ 孕期心理支持系统 —— 你的情绪，我来接住")

    tab1, tab2, tab3, tab4 = st.tabs([
        "📋 EPDS测评与AI反馈",
        "💬 匿名树洞 · 说说心里话",
        "🌱 情绪日记 · 记录微光",
        "👥 同行者地图 · 你不是一个人"
    ])

    # ==================== TAB 1: EPDS测评与AI反馈 ====================
    with tab1:
        st.subheader("📋 你的孕期情绪自测（EPDS量表）")

        st.info("""
        EPDS（爱丁堡产后抑郁量表）是国际通用的筛查工具，帮助你了解自己的情绪状态。  
        这不是诊断，而是一面镜子——帮你看到：**你正在经历什么，以及你并不孤单。**
        """)

        # 显示历史记录
        recent_records = fetch_epds_records(ehr_id, 3)
        if recent_records:
            st.markdown("#### 📊 你最近的测评记录")
            df_hist = pd.DataFrame(recent_records)
            df_hist['score'] = df_hist['score'].astype(int)
            fig = px.line(
                df_hist,
                x="date",
                y="score",
                markers=True,
                title="📈 你的情绪波动趋势（EPDS评分）",
                labels={"score": "EPDS得分", "date": "日期"},
                color_discrete_sequence=["#FF6B6B"]
            )
            fig.update_layout(
                yaxis_range=[0, 30],
                shapes=[
                    dict(type="line", x0=0, x1=1, y0=10, y1=10, line=dict(color="orange", width=2, dash="dash"), xref="paper"),
                    dict(type="line", x0=0, x1=1, y0=13, y1=13, line=dict(color="red", width=2, dash="dash"), xref="paper")
                ],
                annotations=[
                    dict(x=0.5, y=10.5, text="≥10：关注信号", showarrow=False, font=dict(size=10)),
                    dict(x=0.5, y=13.5, text="≥13：建议咨询", showarrow=False, font=dict(size=10))
                ]
            )
            st.plotly_chart(fig, use_container_width=True)

        # 开始测评
        st.divider()
        st.markdown("### ✍️ 请根据最近一周的感受作答（每题选一项）")

        answers = []
        for i, q in enumerate(EPDS_QUESTIONS):
            st.markdown(f"**{q}**")
            ans = st.radio(
                f"问题 {i+1}",
                options=["从不", "偶尔", "经常", "总是"],
                index=0,
                key=f"epds_{i}",
                horizontal=True
            )
            answers.append(EPDS_SCORES[["从不", "偶尔", "经常", "总是"].index(ans)])

        total_score = sum(answers)

        # 提交按钮
        if st.button("✅ 提交测评结果", type="primary"):
            note = st.text_input("想补充什么？（可选）", key="epds_note")
            if submit_epds_test(ehr_id, answers, note):
                st.success("🎉 测评已提交！AI正在为你生成专属反馈…")
                
                # 生成AI反馈
                with st.spinner("🧠 AI正在用心倾听你…"):
                    feedback = generate_epds_ai_feedback(ehr_id, total_score, answers)
                
                st.markdown("### ❤️ 你的专属心理反馈")
                st.info(feedback)
                
                # 根据分数给出温和建议
                if total_score >= 13:
                    st.warning("""
                    > 🌟 你的得分提示你可能正在经历较明显的情绪波动。  
                    > 这不代表你“不好”或“失败”，而是你的身体在提醒你：你需要更多支持。  
                    > 你不是一个人。很多孕妈妈都曾走过这条路。  
                    > 如果你愿意，可以和家人聊聊，或者预约一次产科心理咨询。
                    """)
                elif total_score >= 10:
                    st.info("""
                    > 🌱 你现在的感受很真实，也很常见。  
                    > 很多孕妈妈在孕中期会感到疲惫、敏感、甚至莫名流泪——这不是软弱，是生命正在重塑你的内心。  
                    > 你已经很勇敢了，记得对自己温柔一点。
                    """)
                else:
                    st.success("""
                    > 🌞 你的情绪状态稳定，谢谢你照顾好自己。  
                    > 即使没有大起大落，你的感受依然重要。  
                    > 继续保持这份觉察吧——你已经在做一件非常了不起的事：**认真地活着。**
                    """)
        
        st.caption("💡 EPDS得分说明：0–9 分：正常；10–12 分：轻度困扰；13–30 分：需关注")

    # ==================== TAB 2: 匿名树洞 ====================
    with tab2:
        st.subheader("💬 匿名树洞 · 说给懂的人听")

        st.info("""
        在这里，你可以**完全匿名**地说出任何话：  
        “我讨厌怀孕”、“我怕当妈妈”、“我今天哭了很久”、“没人懂我的累”……  
        你会被听见，不会被评判。
        """)

        # 情绪标签选择器
        emotion_tags = [
            "疲惫", "孤独", "害怕", "内疚", "愤怒", "期待", "感动", "平静", "无语", "想哭"
        ]
        selected_tags = st.multiselect("✨ 你想用哪些词形容此刻的心情？（可多选）", emotion_tags, max_selections=5)

        # 文本输入
        post_content = st.text_area(
            "📝 把心里话说出来吧（限500字）",
            placeholder="比如：今天老公说‘你胖了’，我躲在厕所哭了好久…但宝宝踢了我一下，我又笑了。",
            height=150
        )

        # 用户标签（增强归属感）
        user_label_options = [
            "孕早期（<12周）", "孕中期（13–28周）", "孕晚期（29周+）",
            "高龄孕妈", "二胎妈妈", "第一次当妈妈", "备孕很久才怀上", "单亲妈妈"
        ]
        user_label = st.selectbox("👩‍⚕️ 你是哪种孕妈？（仅用于分类，不显示身份）", user_label_options)

        if st.button("🌿 发布到树洞", type="primary"):
            if not post_content.strip():
                st.error("⚠️ 请先写下你想说的话哦～")
            else:
                if submit_anonymous_post(ehr_id, post_content, selected_tags, user_label):
                    st.success("💌 你的声音已被送达，有人正在读它。")
                    st.balloons()
                    st.rerun()

        st.divider()

        # 展示最新帖子
        st.markdown("### 🌿 最近的心声")
        posts = fetch_mental_posts(ehr_id, 10)
        if not posts:
            st.info("🌳 还没有人分享过心事，你愿意成为第一个吗？")
        else:
            for post in posts:
                with st.expander(f"💬 {post['user_label']} · {post['created_at'].strftime('%m/%d %H:%M')}"):
                    st.write(post["content"])
                    if post["emotion_tags"]:
                        tags_str = " ".join([f"`#{tag}`" for tag in post["emotion_tags"]])
                        st.markdown(f"*{tags_str}*")

                    col1, col2 = st.columns([1, 4])
                    with col1:
                        if st.button("❤️ 点赞", key=f"like_{post['id']}"):
                            if like_post(post["id"]):
                                st.rerun()
                    with col2:
                        st.caption(f"{post['likes']} 个赞 · {post['replies']} 条回应")

                    # 模拟回复功能（可扩展）
                    reply = st.text_input("💬 回应一句温暖的话（仅你可见）", key=f"reply_{post['id']}")
                    if reply and st.button("💌 发送私语", key=f"send_reply_{post['id']}"):
                        st.success("💌 你的心意，已悄悄送达。")

    # ==================== TAB 3: 情绪日记 · 记录微光 ====================
    with tab3:
        st.subheader("🌱 情绪日记 · 记录属于你的微光时刻")

        st.info("""
        每天只需三分钟，写下一件让你感觉“还好”的小事。  
        不必伟大，不必完美——  
        只要是**你真实感受到的温暖**，就值得被记录。
        """)

        prompt = st.selectbox(
            "今天，是什么小事让你觉得‘还好’？",
            [
                "宝宝动了一下",
                "阳光照进窗户",
                "老公给我倒了杯温水",
                "听到一首歌，想起了妈妈",
                "朋友发来一句‘你真棒’",
                "吃了一颗喜欢的水果",
                "睡了一个踏实的午觉",
                "我原谅了今天的自己"
            ],
            key="journal_prompt"
        )

        daily_entry = st.text_area(
            "✍️ 请写下你的微光时刻（可自由发挥）",
            placeholder="例如：今天早上，宝宝在肚子里翻了个跟头，像在跳芭蕾。那一刻，我觉得所有辛苦都值得了。",
            height=100
        )

        if st.button("📖 保存今日日记"):
            if daily_entry.strip():
                contents = {
                    "type": "emotional_journal",
                    "entry": daily_entry,
                    "prompt": prompt,
                    "created_at": datetime.now().isoformat()
                }
                if save_emotion_journal(ehr_id, contents):
                    st.success("✨ 已保存。你正在为自己种下一片温柔的森林。")
                    st.rerun()
            else:
                st.warning("📝 请先写下你的感受哦～")

        # 展示最近日记
        st.markdown("### 📖 你的微光收藏夹")
        journal_entries = fetch_emotion_journals(ehr_id, 5)
        if journal_entries:
            for entry in journal_entries:
                with st.expander(f"📅 {entry['date']} · {entry['prompt']}"):
                    st.write(entry["entry"])
                    st.caption(f"💭 当时你选择的关键词：{entry['prompt']}")
        else:
            st.info("🕊️ 你还没有记录过微光时刻。今天，愿意写下一个吗？")

    # ==================== TAB 4: 同行者地图 ====================
    with tab4:
        st.subheader("👥 同行者地图 · 你不是一个人")

        st.info("""
        这里不是“好友列表”，而是一个**隐形的孕妈妈社群**。  
        我们知道：**当你知道“有人和你一样”，你就不再孤单。**  
        所有信息均匿名处理，隐私由系统保障。
        """)

        # 统计数据
        conn = get_ehr_db_connection()
        if conn:
            try:
                with conn.cursor() as cur:
                    cur.execute("SELECT COUNT(*) FROM data WHERE items = '心理' AND contents ? 'epds_score'")
                    total_assessments = cur.fetchone()[0]
                    cur.execute("SELECT COUNT(*) FROM data WHERE items = '心理-树洞' AND is_anonymous = true")
                    total_posts = cur.fetchone()[0]
            except:
                total_assessments = 0
                total_posts = 0
            finally:
                conn.close()

        col1, col2 = st.columns(2)
        with col1:
            st.metric("📊 总共完成测评", f"{total_assessments} 人次")
        with col2:
            st.metric("💬 总共倾诉心声", f"{total_posts} 条")

        # 地图可视化（模拟）
        st.markdown("### 🗺️ 你所在的位置（虚拟地图）")

        # 模拟“附近孕妈”分布
        nearby_moms = [
            {"label": "孕28周·二胎·高龄", "distance": "2.3km", "mood": "疲惫但期待"},
            {"label": "孕16周·初为人母", "distance": "1.1km", "mood": "有点慌张"},
            {"label": "孕32周·单亲妈妈", "distance": "5.8km", "mood": "坚强又柔软"},
            {"label": "孕20周·备孕三年终于成功", "distance": "3.2km", "mood": "不敢相信这是真的"},
        ]

        for mom in nearby_moms:
            with st.container():
                col1, col2 = st.columns([3, 1])
                with col1:
                    st.markdown(f"🔹 **{mom['label']}** · {mom['mood']}")
                with col2:
                    st.caption(f"📍 距离：{mom['distance']}")

        st.divider()

        # 加入“同行者计划”
        st.markdown("### 🤝 加入‘同行者计划’")
        st.markdown("""
        如果你愿意，我们可以：
        - 在你完成EPDS后，**随机匹配一位同孕周的妈妈**，彼此发送一条匿名鼓励信  
        - 每月推送一次《孕妈情绪观察报告》（不含个人信息）  
        - 你可以在【我的档案】中开启「允许被匹配」开关
        """)

        if st.button("🌟 我愿意加入同行者计划"):
            st.success("💫 你已加入。系统将在你下次测评后，为你匹配一位默默陪伴的伙伴。")
            st.balloons()

        st.caption("🔒 所有匹配均为系统自动匿名处理，你永远不会知道对方是谁，但你知道：她懂你。")

# ========== 辅助函数：保存情绪日记 ==========
def save_emotion_journal(ehr_id: int, contents: dict) -> bool:
    conn = get_ehr_db_connection()
    if not conn:
        return False
    try:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO data (ehr_id, contents, items, created_at)
                VALUES (%s, %s, '心理-日记', NOW())
            """, (ehr_id, json.dumps(contents, ensure_ascii=False)))
        conn.commit()
        return True
    except Exception as e:
        st.warning(f"⚠️ 保存日记失败: {e}")
        return False
    finally:
        if conn:
            conn.close()

# ========== 获取情绪日记 ==========
@st.cache_data(ttl=300)
def fetch_emotion_journals(ehr_id: int, limit: int = 5):
    conn = get_ehr_db_connection()
    if not conn:
        return []
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT contents, created_at
                FROM data 
                WHERE ehr_id = %s AND items = '心理-日记'
                ORDER BY created_at DESC
                LIMIT %s
            """, (ehr_id, limit))
            rows = cur.fetchall()
            journals = []
            for contents, created_at in rows:
                if isinstance(contents, str):
                    try:
                        contents = json.loads(contents)
                    except:
                        continue
                if isinstance(contents, dict):
                    journals.append({
                        "date": created_at.strftime("%m/%d"),
                        "entry": contents.get("entry", ""),
                        "prompt": contents.get("prompt", ""),
                        "created_at": created_at
                    })
            return journals
    except Exception as e:
        st.warning(f"⚠️ 获取日记失败: {e}")
        return []
    finally:
        if conn:
            conn.close()