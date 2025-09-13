import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import plotly.express as px
from urllib.parse import urlparse
import psycopg2
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

# ========== 辅助函数：获取最近7天步数数据 ==========
@st.cache_data(ttl=300)  # 缓存5分钟
def fetch_daily_steps(ehr_id: int, days: int = 7):
    conn = get_ehr_db_connection()
    if not conn:
        return pd.DataFrame()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT 
                    DATE(created_at) as date,
                    MAX(CASE WHEN contents->>'日活动步数' IS NOT NULL THEN (contents->>'日活动步数')::int END) as steps
                FROM data 
                WHERE ehr_id = %s AND items = '运动' 
                  AND created_at >= CURRENT_DATE - INTERVAL '%s days'
                GROUP BY DATE(created_at)
                ORDER BY date ASC
            """, (ehr_id, days))
            rows = cur.fetchall()
        df = pd.DataFrame(rows, columns=["date", "steps"])
        df['date'] = pd.to_datetime(df['date'])
        return df
    except Exception as e:
        st.warning(f"⚠️ 获取步数数据失败: {e}")
        return pd.DataFrame()
    finally:
        if conn:
            conn.close()

# ========== 获取用户历史成就 ==========
@st.cache_data(ttl=3600)
def fetch_achievements(ehr_id: int):
    conn = get_ehr_db_connection()
    if not conn:
        return []
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT achievement_name, achieved_at, level
                FROM user_achievements 
                WHERE ehr_id = %s 
                ORDER BY achieved_at DESC
                LIMIT 10
            """, (ehr_id,))
            rows = cur.fetchall()
            return [{"name": r[0], "date": r[1], "level": r[2]} for r in rows]
    except Exception as e:
        st.warning(f"⚠️ 获取成就失败: {e}")
        return []
    finally:
        if conn:
            conn.close()

# ========== 保存成就（首次调用时自动创建） ==========
def award_achievement(ehr_id: int, achievement_name: str, level: str = "bronze"):
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
        st.warning(f"⚠️ 奖励成就失败: {e}")
        return False
    finally:
        if conn:
            conn.close()

# ========== 主函数 ==========
def render_tabs(ehr_id: int):
    st.markdown("### 🏃‍♀️ 运动专属分析与激励系统")

    # 1. 检查是否已初始化成就表（首次使用自动创建）
    init_achievements_table_if_needed()

    # ========== TABS 配置 ==========
    tab1, tab2, tab3, tab4 = st.tabs([
        "🎯 关卡挑战",
        "📹 视频示范",
        "🏆 我的成就",
        "👥 小组竞赛"
    ])

    # ==================== TAB 1: 关卡挑战（分层目标） ====================
    with tab1:
        st.subheader("🎯 我的运动关卡挑战")

        # 定义孕期友好关卡体系（科学递进）
        levels = [
            {"name": "新手起步", "steps": 3000, "days": 3, "emoji": "🌱", "desc": "每天走3000步，相当于散步20分钟"},
            {"name": "活力小达人", "steps": 5000, "days": 5, "emoji": "🌼", "desc": "每天5000步，轻松逛完一个公园"},
            {"name": "健康孕妈", "steps": 7000, "days": 7, "emoji": "🌺", "desc": "每天7000步，促进血液循环，缓解水肿"},
            {"name": "运动冠军", "steps": 9000, "days": 10, "emoji": "🥇", "desc": "每天9000步，保持体能，为分娩储备力量"}
        ]

        df_steps = fetch_daily_steps(ehr_id, 14)

        # 计算当前连续达标天数
        def calculate_streak(df, target_steps):
            if len(df) == 0:
                return 0
            recent = df.tail(14).copy()
            recent['达标'] = recent['steps'] >= target_steps
            streak = 0
            for i in range(len(recent)-1, -1, -1):
                if recent.iloc[i]['达标']:
                    streak += 1
                else:
                    break
            return streak

        # 显示所有关卡状态
        for i, lvl in enumerate(levels):
            col1, col2 = st.columns([1, 3])
            with col1:
                st.markdown(f"#### {lvl['emoji']} {lvl['name']}")
            with col2:
                current_streak = calculate_streak(df_steps, lvl['steps'])
                target_days = lvl['days']
                progress = min(current_streak / target_days, 1.0)

                # 进度条
                st.progress(progress, text=f"✅ 已连续达标 {current_streak}/{target_days} 天")

                # 判断是否达成
                if current_streak >= target_days:
                    st.success(f"🎉 恭喜您已解锁「{lvl['name']}」！")
                    # 自动奖励成就（仅一次）
                    achievement_key = f"{lvl['name']}_unlocked"
                    if not any(a['name'] == achievement_key for a in fetch_achievements(ehr_id)):
                        award_achievement(ehr_id, achievement_key, "bronze")
                        st.balloons()
                else:
                    remaining = target_days - current_streak
                    if current_streak > 0:
                        st.info(f"💡 只差 {remaining} 天即可解锁！坚持就是胜利～")
                    else:
                        st.info(f"💪 开始你的第一步吧！目标：{lvl['steps']} 步/天")

                st.caption(lvl['desc'])

        # 添加“今日目标”输入框（可选增强）
        st.divider()
        st.markdown("##### 📝 设置今日目标（可选）")
        daily_target = st.number_input(
            "今天想走多少步？",
            min_value=1000,
            max_value=15000,
            value=7000,
            step=500,
            key="daily_target_input"
        )
        if st.button("📅 记录今日目标"):
            st.session_state["today_target"] = daily_target
            st.success(f"✅ 已记录：今天的目标是 {daily_target} 步！")

    # ==================== TAB 2: 视频示范 ====================
    with tab2:
        st.subheader("📹 孕期安全运动示范（专业指导）")

        st.info("以下为示例视频，实际部署后将接入医院认证内容库。")

        # 使用占位视频（YouTube 或本地嵌入）
        # 注意：孕妇避免仰卧、跳跃、高强度动作
        videos = [
            {
                "title": "【孕期】温和散步法（适合孕早期）",
                "desc": "每天30分钟，保持心率在120以下，呼吸均匀。",
                "url": "https://www.youtube.com/embed/dQw4w9WgXcQ?autoplay=0"  # 替换为真实视频ID
            },
            {
                "title": "【孕期】骨盆底肌训练（凯格尔运动）",
                "desc": "帮助预防尿失禁，促进产后恢复。",
                "url": "https://www.youtube.com/embed/dQw4w9WgXcQ?autoplay=0"
            },
            {
                "title": "【孕期】坐姿伸展操（缓解腰背痛）",
                "desc": "每小时做一次，改善久坐不适。",
                "url": "https://www.youtube.com/embed/dQw4w9WgXcQ?autoplay=0"
            }
        ]

        for v in videos:
            with st.expander(f"▶️ {v['title']}"):
                st.write(v['desc'])
                st.markdown(
                    f"""
                    <iframe width="100%" height="240" src="{v['url']}" 
                    frameborder="0" allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture" 
                    allowfullscreen>
                    </iframe>
                    """,
                    unsafe_allow_html=True
                )

        st.divider()
        st.markdown("""
        > 💡 **温馨提示**：  
        > 请在医生指导下选择运动方式，避免剧烈运动、仰卧位超过10分钟、跳跃或高冲击动作。  
        > 推荐运动：散步、游泳、瑜伽、水中健身、固定自行车。
        """)

    # ==================== TAB 3: 我的成就 ====================
    with tab3:
        st.subheader("🏆 我的运动成就墙")

        achievements = fetch_achievements(ehr_id)
        if not achievements:
            st.info("尚未获得任何成就，开始挑战吧！")
        else:
            cols = st.columns(4)
            for i, a in enumerate(achievements[:8]):  # 最多展示8个
                with cols[i % 4]:
                    badge_color = {
                        "bronze": "🟤",
                        "silver": "⚪",
                        "gold": "🟡",
                        "platinum": "🔵"
                    }.get(a['level'], "🟢")
                    st.markdown(f"### {badge_color}")
                    st.caption(a['name'].replace("_unlocked", "").title())
                    st.caption(f"({a['date'].strftime('%m/%d')})")

        # 展示“最近成就”动态提示
        if achievements:
            latest = achievements[0]
            st.success(f"🎉 **恭喜！您刚刚获得了「{latest['name'].replace('_unlocked', '').title()}」成就！**")

        # 加一个“成就说明”
        st.divider()
        st.markdown("### 🏅 成就等级说明")
        st.markdown("""
        - 🟤 **青铜**：完成首个连续挑战（3天）  
        - ⚪ **白银**：完成中等目标（5天）  
        - 🟡 **黄金**：完成高阶目标（7天+）  
        - 🔵 **白金**：连续完成多项挑战（10天+）
        """)

    # ==================== TAB 4: 小组挑战 & 积分榜 ====================
    with tab4:
        st.subheader("👥 我的孕产运动小组 · 积分排行榜")

        st.info("⚠️ 当前为模拟数据，正式版将关联医院/社区群组。")

        # 模拟小组成员（实际应从数据库拉取同医院/同社区用户）
        mock_groups = [
            {"name": "张妈妈", "steps": 8200, "streak": 12, "avatar": "👩‍⚕️"},
            {"name": "李妈妈", "steps": 6500, "streak": 7, "avatar": "👩‍🦰"},
            {"name": "王妈妈", "steps": 4200, "streak": 3, "avatar": "👩‍🦱"},
            {"name": "赵妈妈", "steps": 9100, "streak": 15, "avatar": "👩‍🦳"},
            {"name": "你", "steps": 7800, "streak": 9, "avatar": "🤰"},
        ]

        # 排名
        ranked = sorted(mock_groups, key=lambda x: x['steps'], reverse=True)

        st.markdown("### 🏆 本周运动积分榜（前5名）")
        for i, user in enumerate(ranked[:5]):
            rank = ["🥇", "🥈", "🥉", "🏅", "🎖️"][i] if i < 5 else f"{i+1}."
            color = "#FFD700" if i == 0 else "#C0C0C0" if i == 1 else "#CD7F32" if i == 2 else "#D3D3D3"
            st.markdown(
                f"""
                <div style='padding:12px; margin:8px 0; border-radius:8px; background-color:#f8f9fa; border-left:4px solid {color};'>
                    <strong>{rank} {user['avatar']} {user['name']}</strong><br>
                    步数：<strong>{user['steps']:,}</strong> · 连续打卡：<strong>{user['streak']}天</strong>
                </div>
                """,
                unsafe_allow_html=True
            )

        # 加一个“邀请好友”按钮（未来对接微信/短信）
        st.divider()
        st.markdown("### 💌 邀请好友加入小组")
        st.caption("扫描二维码或分享链接，和闺蜜一起打卡，互相鼓励！")
        st.image("https://via.placeholder.com/200x200?text=二维码", caption="扫码加入运动小组", use_container_width=True)

        # 挑战任务（每日刷新）
        st.markdown("### 🎯 今日挑战任务")
        challenges = [
            "今天走满7000步 → 赢得‘能量徽章’",
            "和一位孕友互发鼓励消息 → 解锁‘友谊之星’",
            "上传一张散步照片 → 获得‘阳光妈妈’称号"
        ]
        for c in challenges:
            st.checkbox(c, key=f"challenge_{c}", disabled=True)
        st.caption("*（正式版中完成任务会自动更新）*")

        # 底部彩蛋
        st.markdown("---")
        st.markdown("<p style='text-align:center; color:#888;'>✨ 你不是一个人在战斗，整个孕期都有我们陪着你 ❤️</p>", unsafe_allow_html=True)


# ========== 初始化成就表（仅执行一次）==========
def init_achievements_table_if_needed():
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
            st.toast("✅ 成就系统初始化完成", icon="🎉")
    except Exception as e:
        st.warning(f"⚠️ 初始化成就表失败: {e}")
    finally:
        if conn:
            conn.close()