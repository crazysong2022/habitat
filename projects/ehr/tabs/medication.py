import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import plotly.express as px
import json
import psycopg2
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

# ========== 获取当前医嘱药物列表（模拟）==========
@st.cache_data(ttl=3600)
def fetch_prescribed_medications(ehr_id: int):
    conn = get_ehr_db_connection()
    if not conn:
        return []

    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT jsonb_path_query_array(
                    plan_data,
                    '$.medications[*] ? (@.status == "active")'
                ) AS active_medications
                FROM medication_plan
                WHERE ehr_id = %s
            """, (ehr_id,))
            row = cur.fetchone()

            if not row or not row[0]:  # 没有数据或为空数组
                return []

            medications = row[0]  # 是一个 jsonb 数组
            result = []
            for med in medications:
                result.append({
                    "name": med.get("name", ""),
                    "dosage": med.get("dosage", ""),
                    "frequency": med.get("frequency", ""),
                    "start": med.get("start_date"),
                    "end": med.get("end_date"),
                    "notes": med.get("instructions", "")
                })
            return result

    except Exception as e:
        st.warning(f"⚠️ 获取医嘱失败: {e}")
        return []
    finally:
        if conn:
            conn.close()

# ========== 获取服药记录 ==========
@st.cache_data(ttl=300)
def fetch_medication_records(ehr_id: int, medication_name: str, days: int = 7):
    conn = get_ehr_db_connection()
    if not conn:
        return pd.DataFrame()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT 
                    DATE(created_at) as date,
                    (contents->>'taken')::boolean as taken,
                    (contents->>'time_taken')::text as time_taken,
                    (contents->>'note')::text as note
                FROM data 
                WHERE ehr_id = %s AND items = '药物' 
                  AND contents->>'medication' = %s
                  AND created_at >= CURRENT_DATE - INTERVAL '%s days'
                ORDER BY date ASC
            """, (ehr_id, medication_name, days))
            rows = cur.fetchall()
        df = pd.DataFrame(rows, columns=["date", "taken", "time_taken", "note"])
        df['date'] = pd.to_datetime(df['date'])
        return df
    except Exception as e:
        st.warning(f"⚠️ 获取服药记录失败: {e}")
        return pd.DataFrame()
    finally:
        if conn:
            conn.close()

# ========== 获取服药成就 ==========
@st.cache_data(ttl=3600)
def fetch_med_achievements(ehr_id: int):
    conn = get_ehr_db_connection()
    if not conn:
        return []
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT achievement_name, achieved_at, level
                FROM user_achievements 
                WHERE ehr_id = %s AND achievement_name LIKE 'med_%'
                ORDER BY achieved_at DESC
                LIMIT 10
            """, (ehr_id,))
            rows = cur.fetchall()
            return [{"name": r[0], "date": r[1], "level": r[2]} for r in rows]
    except Exception as e:
        st.warning(f"⚠️ 获取服药成就失败: {e}")
        return []
    finally:
        if conn:
            conn.close()

# ========== 奖励服药成就 ==========
def award_med_achievement(ehr_id: int, achievement_name: str, level: str = "bronze"):
    conn = get_ehr_db_connection()
    if not conn:
        return False
    try:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO user_achievements (ehr_id, achievement_name, level, achieved_at)
                VALUES (%s, %s, %s, NOW())
                ON CONFLICT (ehr_id, achievement_name) DO NOTHING
            """, (ehr_id, achievement_name, level))
        conn.commit()
        return True
    except Exception as e:
        st.warning(f"⚠️ 奖励服药成就失败: {e}")
        return False
    finally:
        if conn:
            conn.close()

# ========== 保存服药记录 ==========
def save_medication_record(ehr_id: int, medication: str, taken: bool, time_taken: str = "", note: str = ""):
    conn = get_ehr_db_connection()
    if not conn:
        return False
    try:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO data (ehr_id, contents, items, created_at)
                VALUES (%s, %s, '药物', NOW())
            """, (
                ehr_id,
                json.dumps({
                    "medication": medication,
                    "taken": taken,
                    "time_taken": time_taken,
                    "note": note
                }, ensure_ascii=False)
            ))
        conn.commit()
        return True
    except Exception as e:
        st.error(f"❌ 保存服药记录失败: {e}")
        if conn:
            conn.rollback()
        return False
    finally:
        if conn:
            conn.close()

# ========== 初始化成就表 ==========
def init_med_achievements_table_if_needed():
    conn = get_ehr_db_connection()
    if not conn:
        return
    try:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS user_achievements (
                    id SERIAL PRIMARY KEY,
                    ehr_id INTEGER NOT NULL,
                    achievement_name VARCHAR(100) NOT NULL,
                    level VARCHAR(20) DEFAULT 'bronze',
                    achieved_at TIMESTAMP DEFAULT NOW(),
                    UNIQUE(ehr_id, achievement_name)
                );
            """)
            conn.commit()
            # st.toast("✅ 服药成就系统初始化完成", icon="💊")
    except Exception as e:
        st.warning(f"⚠️ 初始化服药成就表失败: {e}")
    finally:
        if conn:
            conn.close()

# ========== 获取家属绑定关系 ==========
@st.cache_data(ttl=3600)
def fetch_family_members(ehr_id: int):
    conn = get_ehr_db_connection()
    if not conn:
        return []
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT fm.family_member_name, fm.relationship, fm.is_notified, fm.phone
                FROM family_members fm
                WHERE fm.ehr_id = %s AND fm.status = 'active'
            """, (ehr_id,))
            rows = cur.fetchall()
            return [
                {"name": r[0], "relation": r[1], "notified": r[2], "phone": r[3]}
                for r in rows
            ]
    except Exception as e:
        st.warning(f"⚠️ 获取家属信息失败: {e}")
        return []
    finally:
        if conn:
            conn.close()

# ========== 主函数 ==========
def render_tabs(ehr_id: int):
    st.markdown("### 💊 药物管理专属系统 —— 让每一次服药都有温度")

    # 初始化成就表
    init_med_achievements_table_if_needed()

    # 获取当前医嘱药物
    prescriptions = fetch_prescribed_medications(ehr_id)

    if not prescriptions:
        st.info("📭 暂无有效医嘱药物，请确认医生已录入您的用药方案。")
        return

    # ========== TABS 配置 ==========
    tab1, tab2, tab3, tab4 = st.tabs([
        "🎯 服药打卡与徽章",
        "📲 扫码提醒训练",
        "🏆 我的服药成就",
        "👨‍👩‍👧‍👦 家属同步与守护"
    ])

    # ==================== TAB 1: 服药打卡与徽章 ====================
    with tab1:
        st.subheader("🎯 今日服药打卡 · 为宝宝的健康按下确认键")

        for med in prescriptions:
            st.markdown(f"### 💊 {med['name']}")

            col1, col2 = st.columns([2, 1])
            with col1:
                st.caption(f"**剂量**：{med['dosage']} | **频次**：{med['frequency']}")
                if med['notes']:
                    st.info(f"💡 医生叮嘱：{med['notes']}")
                
                # 显示最近7天记录
                df = fetch_medication_records(ehr_id, med['name'], 7)
                if len(df) > 0:
                    # 计算完成率
                    total = len(df)
                    taken = df['taken'].sum()
                    rate = taken / total * 100 if total > 0 else 0

                    st.progress(rate / 100, text=f"本周完成率：{int(rate)}% ({taken}/{total} 天)")

                    # 显示打卡趋势图
                    fig = px.bar(
                        df,
                        x="date",
                        y="taken",
                        labels={"taken": "是否服药", "date": "日期"},
                        color="taken",
                        color_discrete_map={True: "#4CAF50", False: "#F44336"},
                        title="📅 近7天服药记录",
                        height=200
                    )
                    fig.update_layout(showlegend=False, margin=dict(l=0, r=0, t=30, b=0))
                    st.plotly_chart(fig, use_container_width=True)

                else:
                    st.info("暂无服药记录，从今天开始吧！")

            with col2:
                # 打卡按钮
                if st.button("✅ 我已服用", key=f"btn_{med['name']}", type="primary"):
                    # 保存记录
                    if save_medication_record(ehr_id, med['name'], True, datetime.now().strftime("%H:%M"), "手动打卡"):
                        st.success("🎉 恭喜你！已成功记录服药！")
                        
                        # 检查是否达成成就
                        check_and_award_med_achievements(ehr_id, med['name'])

                        # 播放正向反馈音效（Streamlit 不支持音频，但可用动效）
                        st.balloons()
                        
                        # 显示宝宝成长知识
                        st.markdown("#### 🌱 小知识：你的坚持，正在改变生命")
                        if "叶酸" in med['name']:
                            st.info("✨ 叶酸正在帮助宝宝的神经管闭合，这是大脑和脊髓发育的关键期。你做的每一件小事，都至关重要。")
                        elif "铁" in med['name']:
                            st.info("🩸 铁元素正在合成血红蛋白，让宝宝获得充足的氧气。你不是一个人在战斗，你的血液里流淌着爱。")
                        elif "钙" in med['name']:
                            st.info("🦴 你的钙质正在构筑宝宝的骨骼，像一座小小的城堡。你每天的坚持，就是最温柔的筑墙人。")
                        else:
                            st.info("💖 无论你吃的是什么药，你今天的这一口，都是对未来的承诺。谢谢你，伟大的妈妈。")

                # 忘记服药？提供补救入口
                if st.button("❌ 今天忘了吃", key=f"missed_{med['name']}"):
                    if save_medication_record(ehr_id, med['name'], False, "", "忘记服药，已记录，下次记得哦～"):
                        st.warning("📝 已记录漏服情况。请勿自责，我们一起来调整提醒方式吧。")

                # 添加备注
                note = st.text_input("📝 今天感觉如何？（可选）", placeholder="比如：有点恶心，但还是吃下去了！", key=f"note_{med['name']}")
                if note and st.button("💾 保存备注", key=f"save_note_{med['name']}"):
                    save_medication_record(ehr_id, med['name'], True, "", note)
                    st.success("✅ 备注已保存，医生未来可参考")

            st.divider()

    # ==================== TAB 2: 扫码提醒训练 ====================
    with tab2:
        st.subheader("📲 扫码提醒训练 · 用科技代替记忆")

        st.info("本功能通过**二维码+智能提醒**，帮你建立条件反射式服药习惯。")

        # 为每种药物生成唯一二维码（模拟）
        for med in prescriptions:
            st.markdown(f"### 🧩 {med['name']} 的专属提醒码")

            # 模拟生成一个带 EHR_ID 和 medication 的二维码 URL
            qr_code_url = f"https://yourapp.com/med-scan?ehr={ehr_id}&med={med['name'].replace(' ', '+')}"
            
            st.markdown(f"""
            <div style='text-align:center; padding:20px; background:#f0f8ff; border-radius:12px; border:1px solid #ddd;'>
                <p><strong>📱 手机扫码 → 自动打卡</strong></p>
                <p style='font-size:14px; color:#666;'>将此二维码贴在：牙刷旁、咖啡机边、床头柜、孕检包上</p>
                <p>每次看到它，就想起：“我正在为宝宝做一件了不起的事。”</p>
                <br>
                <img src="https://via.placeholder.com/150x150?text=扫码打卡" alt="扫码示意图" style='border-radius:8px;'>
                <p style='margin-top:10px; font-size:12px; color:#888;'>真实部署时将生成动态二维码，扫码后自动跳转并记录服药</p>
            </div>
            """, unsafe_allow_html=True)

            # 设置定时提醒（模拟）
            st.markdown("### ⏰ 设置每日提醒时间")
            reminder_time = st.time_input(
                f"⏰ 想在几点收到提醒？（{med['name']}）",
                value=datetime.strptime("08:00", "%H:%M").time(),
                key=f"time_{med['name']}"
            )

            if st.button(f"🔔 保存提醒时间", key=f"save_time_{med['name']}"):
                st.session_state[f"reminder_{med['name']}"] = reminder_time.strftime("%H:%M")
                st.success(f"✅ 已设置：每天 {reminder_time.strftime('%H:%M')} 提醒你服用 {med['name']}")

            # 教育提示
            st.markdown("""
            > 💡 **科学提示**：  
            > 行为心理学研究表明：**固定场景+视觉提示**（如贴在牙刷旁）比单纯闹钟更有效。  
            > 把服药变成像“刷牙”一样的日常动作，你就赢了。
            """)

            st.divider()

    # ==================== TAB 3: 我的服药成就 ====================
    with tab3:
        st.subheader("🏆 我的服药成就墙 —— 你值得被看见")

        achievements = fetch_med_achievements(ehr_id)
        if not achievements:
            st.info("尚未获得任何服药成就，从第一个打卡开始吧！")
        else:
            cols = st.columns(4)
            for i, a in enumerate(achievements[:8]):
                with cols[i % 4]:
                    badge_color = {
                        "bronze": "🟤",
                        "silver": "⚪",
                        "gold": "🟡",
                        "platinum": "🔵"
                    }.get(a['level'], "🟢")
                    st.markdown(f"### {badge_color}")
                    name = a['name'].replace("med_", "").replace("_day", "天").replace("_", " ").title()
                    st.caption(name)
                    st.caption(f"({a['date'].strftime('%m/%d')})")

        # 动态成就提示
        if achievements:
            latest = achievements[0]
            achievement_name = latest['name'].replace("med_", "").replace("_day", "天").replace("_", " ").title()
            st.success(f"🎉 **恭喜你！已连续达成「{achievement_name}」！你真的好棒！**")

        # 成就说明
        st.divider()
        st.markdown("### 🏅 成就等级说明")
        st.markdown("""
        - 🟤 **青铜奖章**：连续3天按时服药  
        - ⚪ **白银勋章**：连续7天无漏服  
        - 🟡 **黄金盾牌**：连续14天完整记录  
        - 🔵 **白金守护者**：连续30天坚持服药，守护宝宝安全成长
        """)

        # 成就背后的故事
        st.markdown("### ❤️ 为什么这些成就如此重要？")
        st.info("""
        > 服药不是任务，是**母爱的具象化**。  
        > 每一次你按下的“已服用”，都在为宝宝的神经系统、骨骼、血液打下坚实基础。  
        > 你不是在吃药，你是在**亲手编织生命的起点**。
        """)

    # ==================== TAB 4: 家属同步与守护 ====================
    with tab4:
        st.subheader("👨‍👩‍👧‍👦 家属同步与守护 · 你的坚强，有人看得见")

        st.info("本功能允许家人接收你的服药状态，给予温暖提醒，减少你的心理负担。")

        # 显示当前绑定家属
        family_members = fetch_family_members(ehr_id)
        if not family_members:
            st.warning("🚫 目前没有绑定任何家属。建议邀请一位亲人加入守护计划。")
            st.markdown("### 👉 如何邀请家属？")
            st.markdown("""
            1. 请家人打开【孕期健康COM-B】小程序  
            2. 点击「我的家庭」→「绑定孕妇」  
            3. 输入你的 **EHR ID**: `**{}**`  
            4. 选择关系（丈夫/婆婆/妈妈）  
            """.format(ehr_id))

            if st.button("📩 发送邀请短信模板"):
                st.code("""
                亲爱的，我是XXX，我的孕期健康管理ID是：{ehr_id}。  
                想请你帮我一起监督吃药，让我更有安全感～  
                下载APP → 点击「家庭」→ 输入我的ID即可查看我的服药情况。  
                谢谢你，爱你❤️
                """.format(ehr_id=ehr_id))

        else:
            st.success(f"✅ 已有 {len(family_members)} 位家人加入守护计划！")

            for member in family_members:
                st.markdown(f"### 👨‍👩‍👧‍👦 {member['name']}（{member['relation']}）")
                col1, col2 = st.columns([2, 1])

                with col1:
                    # 展示该家属是否开启“服药提醒”
                    if member['notified']:
                        st.success("🔔 已开启服药通知推送")
                    else:
                        st.warning("🔕 未开启通知，建议开启以更好支持你")

                    # 显示最近服药记录（仅显示“已服”）
                    recent_takes = []
                    for med in prescriptions:
                        df = fetch_medication_records(ehr_id, med['name'], 3)
                        if len(df) > 0 and df.iloc[-1]['taken']:
                            recent_takes.append(f"{med['name']}（{df.iloc[-1]['date'].strftime('%m/%d')}）")

                    if recent_takes:
                        st.info(f"最近3天：{'、'.join(recent_takes)}")
                    else:
                        st.info("暂无近期服药记录")

                with col2:
                    if st.button(f"💌 给{member['name']}发条鼓励", key=f"msg_{member['name']}"):
                        st.success(f"✅ 已发送消息：\n\n「亲爱的，谢谢你一直陪着我。我知道你很忙，但你每一次的关心，我都感受到了。」")

            st.divider()

            # 家属互动区（模拟）
            st.markdown("### 💬 家人留言墙（模拟）")
            messages = [
                {"from": "老公", "msg": "老婆，今天记得吃铁剂吗？我给你泡了温水，放在床头了~", "time": "昨天 19:20"},
                {"from": "妈妈", "msg": "我今天炖了猪骨汤，加了红枣和枸杞，记得喝一碗再吃药哦！", "time": "前天 17:30"},
            ]

            for msg in messages:
                with st.expander(f"💬 {msg['from']} · {msg['time']}"):
                    st.write(msg['msg'])

            st.markdown("---")
            st.markdown("<p style='text-align:center; color:#888;'>你不是一个人在战斗。你的坚持，有人在默默为你鼓掌。</p>", unsafe_allow_html=True)


# ========== 辅助函数：检查并奖励成就 ==========
def check_and_award_med_achievements(ehr_id: int, medication_name: str):
    """根据服药记录，自动判断是否达成成就"""
    df = fetch_medication_records(ehr_id, medication_name, 30)
    if len(df) == 0:
        return

    # 统计连续打卡天数
    df_sorted = df.sort_values('date').reset_index(drop=True)
    streak = 0
    for i in range(len(df_sorted)-1, -1, -1):
        if df_sorted.iloc[i]['taken']:
            streak += 1
        else:
            break

    # 检查是否达成成就
    if streak >= 30 and not any(a['name'] == 'med_30day_guardian' for a in fetch_med_achievements(ehr_id)):
        award_med_achievement(ehr_id, 'med_30day_guardian', 'platinum')
    elif streak >= 14 and not any(a['name'] == 'med_14day_gold' for a in fetch_med_achievements(ehr_id)):
        award_med_achievement(ehr_id, 'med_14day_gold', 'gold')
    elif streak >= 7 and not any(a['name'] == 'med_7day_silver' for a in fetch_med_achievements(ehr_id)):
        award_med_achievement(ehr_id, 'med_7day_silver', 'silver')
    elif streak >= 3 and not any(a['name'] == 'med_3day_bronze' for a in fetch_med_achievements(ehr_id)):
        award_med_achievement(ehr_id, 'med_3day_bronze', 'bronze')