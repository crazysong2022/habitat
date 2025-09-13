import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import plotly.express as px
from urllib.parse import urlparse
import psycopg2
import os
from dotenv import load_dotenv
import json

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

# ========== 辅助函数：获取最近7天饮食数据 ==========
@st.cache_data(ttl=300)
def fetch_daily_diet_records(ehr_id: int, days: int = 7):
    conn = get_ehr_db_connection()
    if not conn:
        return pd.DataFrame()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT 
                    DATE(created_at) as date,
                    (contents->>'饮食热量_kcal')::int as calories,
                    (contents->>'含糖饮料次数')::int as sugary_drinks,
                    (contents->>'蔬菜份数')::int as veggies,
                    (contents->>'水果份数')::int as fruits
                FROM data 
                WHERE ehr_id = %s AND items = '饮食' 
                  AND created_at >= CURRENT_DATE - INTERVAL '%s days'
                ORDER BY date ASC
            """, (ehr_id, days))
            rows = cur.fetchall()
        df = pd.DataFrame(rows, columns=["date", "calories", "sugary_drinks", "veggies", "fruits"])
        df['date'] = pd.to_datetime(df['date'])
        return df
    except Exception as e:
        st.warning(f"⚠️ 获取饮食数据失败: {e}")
        return pd.DataFrame()
    finally:
        if conn:
            conn.close()

# ========== 获取用户饮食成就 ==========
@st.cache_data(ttl=3600)
def fetch_diet_achievements(ehr_id: int):
    conn = get_ehr_db_connection()
    if not conn:
        return []
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT achievement_name, achieved_at, level
                FROM user_achievements 
                WHERE ehr_id = %s 
                  AND achievement_name LIKE 'diet_%'
                ORDER BY achieved_at DESC
                LIMIT 10
            """, (ehr_id,))
            rows = cur.fetchall()
            return [{"name": r[0], "date": r[1], "level": r[2]} for r in rows]
    except Exception as e:
        st.warning(f"⚠️ 获取饮食成就失败: {e}")
        return []
    finally:
        if conn:
            conn.close()

# ========== 保存饮食成就 ==========
def award_diet_achievement(ehr_id: int, achievement_name: str, level: str = "bronze"):
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
        st.warning(f"⚠️ 奖励饮食成就失败: {e}")
        return False
    finally:
        if conn:
            conn.close()

# ========== 初始化成就表（仅执行一次）==========
def init_diet_achievements_table_if_needed():
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
            # st.toast("✅ 饮食成就系统初始化完成", icon="🍎")
    except Exception as e:
        st.warning(f"⚠️ 初始化饮食成就表失败: {e}")
    finally:
        if conn:
            conn.close()

# ========== 主函数 ==========
def render_tabs(ehr_id: int):
    st.markdown("### 🍎 饮食专属分析与激励系统")

    # 初始化成就表（首次使用）
    init_diet_achievements_table_if_needed()

    # ========== TABS 配置 ==========
    tab1, tab2, tab3, tab4 = st.tabs([
        "🎯 每日小目标",
        "📸 拍照识餐",
        "🏆 我的成就",
        "👨‍👩‍👧‍👦 家庭共享菜单"
    ])

    # ==================== TAB 1: 每日小目标（微习惯） ====================
    with tab1:
        st.subheader("🎯 今天，我只做一件小事")

        # 设计5个“低阻力、高回报”的饮食微目标（符合孕期营养指南）
        micro_goals = [
            {
                "title": "少喝1杯含糖饮料",
                "desc": "奶茶、果汁、汽水 → 改为柠檬水或无糖豆浆",
                "target": "sugary_drinks",
                "value": 0,
                "emoji": "🥤➡️💧",
                "color": "#FF9999"
            },
            {
                "title": "多吃1份蔬菜",
                "desc": "每餐至少加一掌心大小的绿叶菜",
                "target": "veggies",
                "value": 1,
                "emoji": "🥬",
                "color": "#8BC34A"
            },
            {
                "title": "水果换甜点",
                "desc": "下午饿了？吃个苹果代替饼干",
                "target": "fruits",
                "value": 1,
                "emoji": "🍎",
                "color": "#FFCC80"
            },
            {
                "title": "晚餐提前1小时",
                "desc": "晚上8点前吃完，帮助血糖稳定",
                "target": "dinner_time",
                "value": "before_8pm",
                "emoji": "⏰",
                "color": "#64B5F6"
            },
            {
                "title": "多喝水1杯",
                "desc": "每天8杯水，孕妈更需要哦～",
                "target": "water",
                "value": 1,
                "emoji": "💧",
                "color": "#E0E0E0"
            }
        ]

        df_diet = fetch_daily_diet_records(ehr_id, 7)

        for goal in micro_goals:
            col1, col2 = st.columns([1, 3])
            with col1:
                st.markdown(f"#### {goal['emoji']} {goal['title']}")
            with col2:
                # 根据目标类型判断是否达标
                if goal["target"] == "sugary_drinks":
                    recent = df_diet.tail(1)
                    if len(recent) > 0 and recent.iloc[0]["sugary_drinks"] <= goal["value"]:
                        st.success("✅ 今天做到了！你真棒！")
                        achievement_key = f"diet_no_sugar_{datetime.now().strftime('%Y%m')}"
                        if not any(a['name'] == achievement_key for a in fetch_diet_achievements(ehr_id)):
                            award_diet_achievement(ehr_id, achievement_key, "bronze")
                            st.balloons()
                    else:
                        st.info("💡 尝试今天少喝一杯吧～你值得更好的能量来源。")

                elif goal["target"] == "veggies":
                    recent = df_diet.tail(1)
                    if len(recent) > 0 and recent.iloc[0]["veggies"] >= goal["value"]:
                        st.success("✅ 今天吃了1份以上蔬菜！颜色越深越好！")
                        achievement_key = f"diet_veggie_day_{datetime.now().strftime('%Y%m')}"
                        if not any(a['name'] == achievement_key for a in fetch_diet_achievements(ehr_id)):
                            award_diet_achievement(ehr_id, achievement_key, "bronze")
                            st.balloons()
                    else:
                        st.info("🌱 加点绿色吧！哪怕是一小把菠菜，也是胜利。")

                elif goal["target"] == "fruits":
                    recent = df_diet.tail(1)
                    if len(recent) > 0 and recent.iloc[0]["fruits"] >= goal["value"]:
                        st.success("🍎 水果自由，健康加倍！")
                        achievement_key = f"diet_fruit_day_{datetime.now().strftime('%Y%m')}"
                        if not any(a['name'] == achievement_key for a in fetch_diet_achievements(ehr_id)):
                            award_diet_achievement(ehr_id, achievement_key, "bronze")
                            st.balloons()
                    else:
                        st.info("🍇 选天然水果，拒绝加工果酱～")

                elif goal["target"] == "dinner_time":
                    st.info("⏳ 晚餐建议在8点前结束，有助于控制体重和血糖。")
                    # 可扩展：未来从睡眠/血糖数据推断晚餐时间
                    # 这里先作为提醒

                elif goal["target"] == "water":
                    st.info("💧 孕期每天建议饮水1.5–2L，相当于8杯。别等渴了才喝哦！")

                st.caption(goal["desc"])
                st.divider()

        # 添加“今日小目标”选择器（可选）
        st.markdown("### 📝 选择你的今日小挑战")
        selected_goal = st.selectbox(
            "今天我想做到：",
            [g["title"] for g in micro_goals],
            key="diet_micro_goal_select"
        )
        if st.button("📅 记录我的承诺"):
            st.session_state["today_diet_goal"] = selected_goal
            st.success(f"✅ 已记录：{selected_goal} —— 我一定会做到！")

    # ==================== TAB 2: 拍照识餐（AI食物识别引导） ====================
    with tab2:
        st.subheader("📸 拍照识餐 · 你的私人营养师助手")

        st.info("⚠️ 本功能为演示模式，真实部署后将接入AI图像识别模型（如ResNet+OCR），自动识别食物种类与热量。")

        # 引导用户如何拍得准（降低错误率）
        st.markdown("""
        ### 📷 拍照小贴士（提高识别准确率）：
        
        1. **光线充足**：自然光最佳，避免背光  
        2. **平放拍摄**：食物平铺在盘子上，不要堆叠  
        3. **完整拍摄**：包含主食、蛋白质、蔬菜三类  
        4. **标注备注**：如有特殊食材（如酱油、沙拉酱），请手写注明  

        > 💡 你拍得越清楚，AI就越懂你 ❤️
        """)

        # 占位上传区
        uploaded_file = st.file_uploader(
            "📷 上传你今天的午餐/晚餐照片",
            type=["jpg", "jpeg", "png"],
            accept_multiple_files=False,
            key="diet_photo_uploader"
        )

        if uploaded_file:
            st.image(uploaded_file, caption="你拍的照片", use_container_width=True)
            
            # 模拟AI识别结果（真实场景调用API）
            with st.spinner("🧠 AI正在分析你的餐盘…"):
                # 模拟返回结构
                mock_result = {
                    "food_items": ["糙米饭", "清蒸鱼", "西兰花", "番茄炒蛋", "一小勺橄榄油"],
                    "estimated_calories": 580,
                    "protein_g": 32,
                    "carbs_g": 65,
                    "fat_g": 24,
                    "recommendation": "非常棒的均衡餐！碳水适中，优质蛋白丰富，蔬菜充足。建议下次增加一份水果作为餐后甜点～"
                }

                # 显示模拟结果
                st.success("✅ 分析完成！")

                col1, col2 = st.columns(2)
                with col1:
                    st.metric("总热量", f"{mock_result['estimated_calories']} kcal")
                    st.metric("蛋白质", f"{mock_result['protein_g']}g")
                with col2:
                    st.metric("碳水", f"{mock_result['carbs_g']}g")
                    st.metric("脂肪", f"{mock_result['fat_g']}g")

                st.markdown("#### 📌 AI建议")
                st.info(mock_result["recommendation"])

                # 保存到数据库（模拟）
                if st.button("💾 保存本次识别结果"):
                    contents = {
                        "食物识别": ", ".join(mock_result["food_items"]),
                        "估算热量_kcal": mock_result["estimated_calories"],
                        "蛋白质_g": mock_result["protein_g"],
                        "碳水_g": mock_result["carbs_g"],
                        "脂肪_g": mock_result["fat_g"]
                    }
                    if save_food_image_record(ehr_id, contents):
                        st.success("✅ 已保存至你的饮食档案，下次可查看趋势！")
                    else:
                        st.error("❌ 保存失败，请重试")

        else:
            st.info("📸 上传一张照片，开启智能饮食之旅～")

        # 展示“正确 vs 错误”示范图（占位）
        st.divider()
        st.markdown("### 🖼️ 正确拍照示例（对比）")
        col1, col2 = st.columns(2)
        with col1:
            st.image("https://via.placeholder.com/200x200?text=✅+好照片：平铺+光线足", caption="✅ 好照片", use_container_width=True)
        with col2:
            st.image("https://via.placeholder.com/200x200?text=❌+差照片：堆叠+背光", caption="❌ 避免这样拍", use_container_width=True)

    # ==================== TAB 3: 我的成就 ====================
    with tab3:
        st.subheader("🏆 我的饮食成就墙")

        achievements = fetch_diet_achievements(ehr_id)
        if not achievements:
            st.info("尚未获得任何饮食成就，从今天的小目标开始吧！")
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
                    name = a['name'].replace("diet_", "").replace("_day_", " ").replace("_", " ").title()
                    st.caption(name)
                    st.caption(f"({a['date'].strftime('%m/%d')})")

        # 动态成就提示
        if achievements:
            latest = achievements[0]
            achievement_name = latest['name'].replace("diet_", "").replace("_day_", " ").replace("_", " ").title()
            st.success(f"🎉 **恭喜！你已连续达成「{achievement_name}」三天以上！**")

        # 成就说明
        st.divider()
        st.markdown("### 🏅 成就等级说明")
        st.markdown("""
        - 🟤 **青铜**：完成1项微习惯连续3天  
        - ⚪ **白银**：完成2项微习惯各达5天  
        - 🟡 **黄金**：连续7天摄入足量蔬菜  
        - 🔵 **白金**：一周内零含糖饮料 + 高蛋白饮食  
        """)

    # ==================== TAB 4: 家庭共享菜单 ====================
    with tab4:
        st.subheader("👨‍👩‍👧‍👦 家庭共享健康菜单 · 让爱在餐桌上流动")

        st.info("⚠️ 本功能为演示模式，正式版将支持家庭成员绑定，同步菜单偏好与营养建议。")

        # 推荐3个“全家都爱吃”的孕期友好食谱（科学+美味）
        family_meals = [
            {
                "name": "彩虹藜麦碗",
                "desc": "藜麦+鸡胸肉+彩椒+牛油果+南瓜籽，高蛋白低GI，宝宝喜欢的颜色！",
                "ingredients": ["藜麦 100g", "鸡胸肉 150g", "红黄椒各半颗", "牛油果半个", "南瓜籽 10g"],
                "benefit": "富含叶酸、铁、Omega-3，适合孕早期",
                "icon": "🥗"
            },
            {
                "name": "番茄豆腐炖排骨",
                "desc": "慢炖汤品，补钙又开胃，爸爸也爱喝！",
                "ingredients": ["猪肋排 200g", "豆腐 1块", "番茄 2个", "胡萝卜 1根", "姜片少许"],
                "benefit": "高钙、高蛋白、易消化，缓解孕吐",
                "icon": "🍲"
            },
            {
                "name": "香蕉燕麦奶昔",
                "desc": "早餐神器！不用糖，天然甜味，饱腹感强",
                "ingredients": ["燕麦 40g", "香蕉 1根", "无糖豆浆 200ml", "奇亚籽 5g"],
                "benefit": "稳定血糖，预防妊娠糖尿病，全家都能喝",
                "icon": "🍌"
            }
        ]

        st.markdown("### 📋 推荐菜单（点击收藏）")
        for meal in family_meals:
            with st.expander(f"{meal['icon']} {meal['name']}"):
                st.write(f"**描述**：{meal['desc']}")
                st.write(f"**主要食材**：{', '.join(meal['ingredients'])}")
                st.write(f"**孕期益处**：{meal['benefit']}")

                if st.button(f"❤️ 收藏到我的菜单", key=f"save_{meal['name']}"):
                    st.success(f"✅ 已收藏「{meal['name']}」，可在【我的菜单】中查看！")

        st.divider()

        # 家庭协作功能（模拟）
        st.markdown("### 👨‍👩‍👧‍👦 邀请家人加入健康餐桌")
        st.caption("让配偶、父母共同参与，减少饮食冲突，提升幸福感。")

        col1, col2 = st.columns([2, 1])
        with col1:
            family_member = st.text_input("输入家人姓名（如：老公/妈妈）", placeholder="例如：张伟")
        with col2:
            if st.button("💌 发送邀请"):
                if family_member:
                    st.success(f"✅ 已发送邀请给 {family_member}！他/她将收到一条温馨消息：\n\n「亲爱的，我们一起为宝宝吃得更健康吧～」")
                else:
                    st.warning("请输入家人姓名")

        # 家庭菜单共享面板（模拟）
        st.markdown("### 🧩 家人共享菜单（模拟）")
        shared_menu = [
            {"member": "老公", "liked": "番茄豆腐炖排骨", "notes": "汤太香了，每天都要喝"},
            {"member": "婆婆", "liked": "香蕉燕麦奶昔", "notes": "比甜品健康多了，我也要学着做"},
        ]
        for item in shared_menu:
            st.markdown(f"- 👨‍👩‍👧‍👦 **{item['member']}**：最爱 **{item['liked']}** — _“{item['notes']}”_")

        # 底部彩蛋
        st.markdown("---")
        st.markdown("<p style='text-align:center; color:#888;'>🍴 吃得好，不只是为了自己，更是为了宝宝和家人的爱 ❤️</p>", unsafe_allow_html=True)


# ========== 保存AI识别记录（模拟）==========
def save_food_image_record(ehr_id: int, contents: dict) -> bool:
    """模拟保存识别结果到data表"""
    conn = get_ehr_db_connection()
    if not conn:
        return False
    try:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO data (ehr_id, contents, items, created_at)
                VALUES (%s, %s, '饮食', NOW())
            """, (ehr_id, json.dumps(contents, ensure_ascii=False)))
        conn.commit()
        return True
    except Exception as e:
        st.error(f"❌ 保存识别记录失败: {e}")
        if conn:
            conn.rollback()
        return False
    finally:
        if conn:
            conn.close()