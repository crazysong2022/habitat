# chatbot.py - AI 聊天助手（双语支持）
import os
import streamlit as st
from openai import OpenAI
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

# 初始化 OpenAI 客户端（阿里云百炼）
@st.cache_resource
def get_client():
    return OpenAI(
        api_key=os.getenv("DASHSCOPE_API_KEY"),
        base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
    )


def render(t):
    """
    主入口函数
    :param t: 翻译函数，t(key) -> str
    """
    st.title(t("chatbot_title"))
    st.markdown(f"""
    ### {t("chatbot_description")}

    I'm the AI assistant from **Habitats Studio**. I can help you with:
    
    - {t("chatbot_service_1")}
    - {t("chatbot_service_2")}
    - {t("chatbot_service_3")}
    - {t("chatbot_service_4")}

    {t("chatbot_instruction")}
    """)
    st.markdown("---")

    client = get_client()

    # 初始化 session_state 中的消息历史
    if "messages" not in st.session_state:
        st.session_state.messages = [
            {
                "role": "system",
                "content": """You are a helpful, professional AI assistant for Habitat Studio, a data analytics consultancy.
                - Always reply in the SAME LANGUAGE as the user's latest message.
                - If the user uses Chinese, reply in Chinese. If English, reply in English. Support mixed input.
                - Be concise, friendly, and informative.
                - For collaboration requests, suggest they visit the Contact page.
                - Do not use markdown formatting in your responses."""
            },
            {
                "role": "assistant",
                "content": t("chatbot_welcome")  # 多语言欢迎语（AI 会自动适配）
            }
        ]

    # 显示聊天历史
    for msg in st.session_state.messages:
        if msg["role"] == "assistant":
            with st.chat_message("assistant", avatar="🤖"):
                st.write(msg["content"])
        elif msg["role"] == "user":
            with st.chat_message("user", avatar="👤"):
                st.write(msg["content"])

    # 用户输入框
    prompt = st.chat_input(t("chatbot_input"))
    if prompt:
        # 显示用户消息
        with st.chat_message("user", avatar="👤"):
            st.write(prompt)

        # 添加到历史
        st.session_state.messages.append({"role": "user", "content": prompt})

        try:
            stream = client.chat.completions.create(
                model="qwen-plus",
                messages=st.session_state.messages,
                stream=True
            )

            # 流式输出
            with st.chat_message("assistant", avatar="🤖"):
                response = st.write_stream(stream)

            st.session_state.messages.append({"role": "assistant", "content": response})

        except Exception as e:
            st.error(t("chatbot_error").format(error=str(e)))
            st.info(t("chatbot_check"))

    # 清除对话按钮
    st.markdown("---")
    if st.button(t("chatbot_clear")):
        st.session_state.messages = st.session_state.messages[:1]  # 保留 system 消息
        st.rerun()