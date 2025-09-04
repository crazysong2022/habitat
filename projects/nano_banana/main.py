# projects/nano_banana/main.py
# 后端主模块 - Gemini 图像与文本生成应用

import os
import base64
import mimetypes
from io import BytesIO
from pathlib import Path

import streamlit as st
from google import genai
from google.genai import types
from PIL import Image
from dotenv import load_dotenv

# 加载环境变量（确保独立运行时也能工作）
load_dotenv()

# -----------------------------
# 配置
# -----------------------------
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if not GEMINI_API_KEY:
    st.error("❌ GEMINI_API_KEY 未设置，请检查 .env 文件。")
    st.stop()

# 初始化客户端
client = genai.Client(api_key=GEMINI_API_KEY)

# 输出目录
OUTPUT_DIR = Path("outputs") / "gemini_images"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# 模型名称（你现在可以访问）
MODEL_NAME = "gemini-2.5-flash-image-preview"


# -----------------------------
# 工具函数：保存图像
# -----------------------------
def save_image_data(data: bytes, prefix: str = "gemini_output") -> Path:
    """保存图像数据到本地，并返回路径"""
    file_name = f"{prefix}_{len(list(OUTPUT_DIR.glob('*.png')))+1}.png"
    file_path = OUTPUT_DIR / file_name
    with open(file_path, "wb") as f:
        f.write(data)
    return file_path


# -----------------------------
# 主生成函数
# -----------------------------
def generate_image_from_prompt(prompt: str):
    """调用 Gemini 模型生成图像和文本内容"""
    try:
        # 构建请求
        contents = [
            types.Content(
                role="user",
                parts=[
                    types.Part.from_text(text=prompt),
                ],
            ),
        ]

        config = types.GenerateContentConfig(
            response_modalities=["TEXT", "IMAGE"],
        )

        # 流式调用
        placeholder = st.empty()
        full_text = ""
        image_count = 0

        for chunk in client.models.generate_content_stream(
            model=MODEL_NAME,
            contents=contents,
            config=config,
        ):
            if not chunk.candidates or not chunk.candidates[0].content:
                continue

            part = chunk.candidates[0].content.parts[0]

            # 处理图像输出
            if part.inline_data and part.inline_data.data:
                inline_data = part.inline_data
                img_data = inline_data.data
                mime_type = inline_data.mime_type or "image/png"

                # 使用 PIL 打开图像
                try:
                    image = Image.open(BytesIO(img_data))
                    st.image(image, caption=f"🎨 生成的图像 #{image_count + 1}", use_column_width=True)

                    # 保存图像
                    file_ext = mimetypes.guess_extension(mime_type) or ".png"
                    file_path = save_image_data(img_data, prefix=f"image_{image_count + 1}")
                    st.session_state.last_image = str(file_path)

                    image_count += 1
                except Exception as img_err:
                    st.error(f"🖼️ 图像处理失败：{img_err}")

            # 处理文本输出
            elif part.text:
                full_text += part.text
                placeholder.markdown(full_text + " ▌")

        # 最终刷新文本
        if full_text:
            placeholder.markdown(full_text)

        if image_count > 0:
            st.success(f"✅ 成功生成 {image_count} 张图像！")
        else:
            st.info("💬 仅生成文本回复。")

    except Exception as e:
        if "429" in str(e) or "RESOURCE_EXHAUSTED" in str(e) or "quota" in str(e).lower():
            st.error("❌ 今日生成次数已达上限。")
            st.info("""
                **解决方法：**
                1. 等待明天配额重置（太平洋时间午夜）
                2. 或升级到付费计划以获得更高配额
                3. 启用计费后，配额将自动提升
            """)
            st.link_button("🔗 前往 Google Cloud 启用计费", "https://console.cloud.google.com/billing")
        else:
            st.error(f"❌ 调用 Gemini API 失败：{e}")


# -----------------------------
# 主运行函数（必须存在）
# -----------------------------
def run():
    st.markdown("### 🖼️ Gemini AI 图像生成器")
    st.markdown("输入你的创意描述，Gemini 将为你生成图像和文字内容！")
    st.info("💡 示例：一个漂浮在星空中的水晶图书馆，充满未来感，细节丰富。")

    # 输入提示词
    prompt = st.text_area(
        "📝 输入你的提示词（支持中文）：",
        height=150,
        placeholder="例如：一只穿着宇航服的小猫在火星上吃冰淇淋"
    )

    # 生成按钮
    if st.button("🚀 生成内容", type="primary", use_container_width=True):
        if not prompt.strip():
            st.warning("请输入提示词！")
        else:
            st.session_state.generated = True
            with st.spinner("🧠 Gemini 正在创作中..."):
                generate_image_from_prompt(prompt.strip())

    # 显示最近生成的图像（可选）
    if hasattr(st.session_state, "last_image"):
        st.markdown("---")
        st.markdown("📁 **最近生成的图像**：")
        st.image(st.session_state.last_image, use_column_width=True)

    # 清除按钮
    if st.button("🧹 清除结果", type="secondary", use_container_width=True):
        if "last_image" in st.session_state:
            del st.session_state.last_image
        st.rerun()


# -----------------------------
# 支持直接运行调试
# -----------------------------
if __name__ == "__main__":
    st.set_page_config(
        page_title="Gemini 图像生成器",
        page_icon="🖼️",
        layout="centered"
    )
    run()