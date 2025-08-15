# app.py - 主门户应用
import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
from translations import TRANSLATIONS

# -----------------------------
# 页面配置
# -----------------------------
st.set_page_config(
    page_title="Habitat Studio",
    page_icon="🌍",
    layout="centered",
    initial_sidebar_state="expanded",
)

# -----------------------------
# 初始化语言状态与翻译函数
# -----------------------------
if 'language' not in st.session_state:
    st.session_state.language = 'en'  # 默认英文

def t(key):
    """快捷翻译函数：根据当前语言返回对应文本"""
    return TRANSLATIONS[st.session_state.language][key]

# -----------------------------
# 自定义 CSS 样式（深色侧边栏）
# -----------------------------
st.markdown(
    """
    <style>
    /* 主容器内边距 */
    .main .block-container {
        padding-top: 1rem;
        padding-bottom: 2rem;
    }

    /* 深色侧边栏 */
    [data-testid="stSidebar"] {
        background: linear-gradient(135deg, #1E2A38, #2C3E50) !important;
        color: white;
    }

    /* 侧边栏文字颜色 */
    [data-testid="stSidebar"] .css-1v3fvcr,
    [data-testid="stSidebar"] .css-1v3fvcr * {
        color: white !important;
    }

    [data-testid="stSidebar"] h1,
    [data-testid="stSidebar"] h2,
    [data-testid="stSidebar"] h3,
    [data-testid="stSidebar"] p,
    [data-testid="stSidebar"] span,
    [data-testid="stSidebar"] div {
        color: white !important;
    }

    /* radio 按钮样式 */
    [data-testid="stSidebar"] .stRadio > div label {
        color: #D6EAF8 !important;
        font-size: 1.1em;
        font-weight: 500;
    }

    [data-testid="stSidebar"] .stRadio > div label:hover {
        color: #AED6F1 !important;
        background-color: rgba(255, 255, 255, 0.1);
        border-radius: 8px;
        padding: 0.3rem 0.6rem;
    }

    /* Logo 区域 */
    .sidebar-logo {
        text-align: center;
        margin-bottom: 1rem;
    }

    .sidebar-logo img {
        border-radius: 50%;
        border: 3px solid rgba(255, 255, 255, 0.3);
        box-shadow: 0px 4px 10px rgba(0, 0, 0, 0.2);
    }

    /* 页脚 */
    .footer {
        font-size: 0.9em;
        color: #7F8C8D;
        text-align: center;
        margin-top: 3rem;
        padding-top: 1rem;
        border-top: 1px solid #34495E;
    }

    /* 主标题颜色 */
    h1, h2, h3 {
        color: #2C3E50;
    }

    /* 分隔线 */
    hr {
        border-color: #34495E;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# -----------------------------
# 侧边栏：Logo + 语言切换 + 导航
# -----------------------------
with st.sidebar:
    # Logo 区域
    st.markdown('<div class="sidebar-logo">', unsafe_allow_html=True)
    st.image("images/logo.png", width=100)
    st.markdown('</div>', unsafe_allow_html=True)

    # --- 🔁 语言切换器 ---
    lang_choice = st.radio(
        "Select Language",
        options=["English", "中文"],
        horizontal=True,
        label_visibility="visible",
        key="sidebar_language_radio"  # ✅ 修复：添加 key 防止状态丢失
    )

    new_language = "zh" if lang_choice == "中文" else "en"
    
    if new_language != st.session_state.language:
        st.session_state.language = new_language
        st.rerun()

    # --- 显示标题 ---
    st.markdown(
        f"<h2 style='color: white; text-align: center; margin: 0;'>{t('app_title')}</h2>",
        unsafe_allow_html=True
    )
    st.markdown(
        f"<p style='color: #D6EAF8; text-align: center; font-style: italic; margin-top: 0.2rem;'>{t('app_subtitle')}</p>",
        unsafe_allow_html=True
    )

    st.markdown("---")

    # 导航菜单
    st.markdown(f"<p style='color: #D6EAF8; font-size: 1.1em;'>{t('navigate')}</p>", unsafe_allow_html=True)
    page = st.radio(
        "Go to",
        ["About", "Demo", "Chatbot", "Message", "Contact", "Admin", "Client"],
        format_func=lambda x: t(x.lower()),
        label_visibility="collapsed",
        key="sidebar_navigation_radio"  # ✅ 修复：添加 key
    )

# -----------------------------
# 主页面内容
# -----------------------------
if page == "About":
    st.title(t("about_title"))
    st.markdown(t("about_intro"))
    st.markdown("---")
    st.markdown(t("about_services"))
    for i in range(1, 6):
        st.markdown(t(f"service_{i}"))
    st.markdown("---")
    st.markdown(t("about_why"))
    for i in range(1, 5):
        st.markdown(t(f"why_{i}"))
    st.markdown("---")
    st.markdown(t("about_scenarios"))

    scenarios = [
        "finance", "healthcare", "education",
        "retail", "logistics", "research", "marketing"
    ]
    for s in scenarios:
        st.markdown(t(f"scenarios_{s}"))

    st.markdown("---")
    st.markdown(t("quote"))

elif page == "Demo":
    import demo
    demo.render(t)

elif page == "Chatbot":
    import chatbot
    chatbot.render(t)

elif page == "Message":
    import message
    message.render(t)

elif page == "Contact":
    import contact
    contact.render(t)

elif page == "Admin":
    import data_hub
    data_hub.render(t)

elif page == "Client":
    import client
    client.render(t)

# -----------------------------
# 页脚
# -----------------------------
st.markdown(f"<div class='footer'>{t('footer')}</div>", unsafe_allow_html=True)