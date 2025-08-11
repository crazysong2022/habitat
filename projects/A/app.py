# projects/A/app.py
# 数据可视化工具（中文界面）
import streamlit as st
import pandas as pd
import plotly.express as px
from io import BytesIO

# -----------------------------
# 页面配置
# -----------------------------
st.set_page_config(
    page_title="📊 数据可视化工具",
    page_icon="📈",
    layout="wide"
)

st.title("📈 交互式数据可视化工具")
st.markdown("""
上传 **CSV 或 Excel** 文件，立即生成精美图表。  
支持图表类型：折线图、柱状图、散点图、饼图、直方图、箱线图。
""")

# -----------------------------
# 文件上传
# -----------------------------
uploaded_file = st.file_uploader(
    "📤 上传数据文件（CSV 或 Excel）",
    type=["csv", "xlsx", "xls"],
    help="支持格式：CSV、XLSX"
)

if not uploaded_file:
    st.info("请上传一个文件以开始。")
    st.stop()

# -----------------------------
# 加载数据（带类型转换）
# -----------------------------
@st.cache_data
def load_data(uploaded_file):
    try:
        if uploaded_file.name.endswith('.csv'):
            df = pd.read_csv(uploaded_file)
        else:
            df = pd.read_excel(uploaded_file)
        
        # 尝试将数值列自动转换
        for col in df.columns:
            # 如果是非数值列，尝试转为数值
            if df[col].dtype == 'object':
                # 转换为数值，错误值转为 NaN
                numeric_series = pd.to_numeric(df[col], errors='coerce')
                if not numeric_series.isna().all():  # 如果部分可转为数字
                    df[col] = numeric_series
        
        return df
    except Exception as e:
        st.error(f"❌ 读取文件失败：{e}")
        return None

df = load_data(uploaded_file)

if df is None or df.empty:
    st.stop()

# -----------------------------
# 显示数据预览
# -----------------------------
st.success(f"✅ 已加载数据：{df.shape[0]} 行 × {df.shape[1]} 列")
st.dataframe(df.head(10), use_container_width=True)

# -----------------------------
# 检查列类型
# -----------------------------
numeric_columns = df.select_dtypes(include='number').columns.tolist()
text_columns = df.select_dtypes(include='object').columns.tolist()

if len(numeric_columns) == 0:
    st.warning("⚠️ 未找到数值列，部分图表类型将不可用。")
else:
    st.info(f"🔢 数值列：{', '.join(numeric_columns)}")

if len(text_columns) == 0:
    st.warning("⚠️ 未找到文本/分类列。")
    text_columns = []
else:
    st.info(f"🔤 文本列：{', '.join(text_columns)}")

# 如果完全没有列，退出
if df.columns.size == 0:
    st.error("❌ 文件中未找到任何列。")
    st.stop()

# -----------------------------
# 图表配置
# -----------------------------
st.markdown("---")
st.header("🎨 创建图表")

col1, col2, col3 = st.columns(3)

# 默认选择第一列作为 X 轴
default_x_index = 0

with col1:
    chart_type = st.selectbox(
        "图表类型",
        ["折线图", "柱状图", "散点图", "饼图", "直方图", "箱线图"],
        key="chart_type"
    )

with col2:
    x_col = st.selectbox(
        "X 轴",
        options=df.columns.tolist(),
        index=default_x_index,
        key="x_axis"
    )

# 确定 Y 轴选项
y_options = numeric_columns if numeric_columns else df.columns.tolist()
default_y_index = 0 if y_options else 0

with col3:
    if chart_type == "饼图":
        y_col = st.selectbox(
            "数值（饼图）",
            options=y_options,
            index=default_y_index,
            disabled=not y_options,
            key="y_pie"
        ) if y_options else None
    elif chart_type == "直方图":
        y_col = st.selectbox(
            "变量",
            options=y_options,
            index=default_y_index,
            disabled=not y_options,
            key="y_hist"
        ) if y_options else None
    else:
        y_col = st.selectbox(
            "Y 轴",
            options=y_options,
            index=default_y_index,
            disabled=not y_options,
            key="y_axis"
        ) if y_options else None

# 颜色映射（可选）
color_col = None
if chart_type not in ["饼图", "直方图"] and (text_columns or numeric_columns):
    with col1:
        color_options = ["无"] + text_columns + numeric_columns
        color_selected = st.selectbox(
            "颜色（可选）",
            options=color_options,
            key="color_select"
        )
        color_col = color_selected if color_selected != "无" else None
elif chart_type not in ["饼图", "直方图"]:
    with col1:
        st.selectbox("颜色（可选）", options=["无"], disabled=True)

# -----------------------------
# 生成图表
# -----------------------------
if st.button("🚀 生成图表", key="gen_chart"):
    if not x_col:
        st.error("❌ 请选择 X 轴列。")
    elif not y_col and chart_type not in ["饼图", "直方图"]:
        st.error("❌ 请选择 Y 轴列。")
    elif chart_type == "饼图" and not y_col:
        st.error("❌ 饼图需要一个数值列。")
    elif chart_type == "直方图" and not y_col:
        st.error("❌ 直方图需要一个变量来绘制。")
    else:
        try:
            fig = None
            title = f"{chart_type}: {y_col or '计数'} vs {x_col}"

            if chart_type == "折线图":
                fig = px.line(df, x=x_col, y=y_col, color=color_col, title=title)
            elif chart_type == "柱状图":
                fig = px.bar(df, x=x_col, y=y_col, color=color_col, title=title)
            elif chart_type == "散点图":
                fig = px.scatter(df, x=x_col, y=y_col, color=color_col, title=title)
            elif chart_type == "饼图":
                fig = px.pie(df, names=x_col, values=y_col, title=f"饼图：{y_col} 按 {x_col} 分布")
            elif chart_type == "直方图":
                fig = px.histogram(df, x=y_col, color=color_col, nbins=30, title=f"直方图：{y_col}")
            elif chart_type == "箱线图":
                fig = px.box(df, x=x_col, y=y_col, color=color_col, title=f"箱线图：{y_col} 按 {x_col} 分组")

            if fig:
                fig.update_layout(height=600)
                st.plotly_chart(fig, use_container_width=True)

                # 下载图表
                buf = BytesIO()
                fig.write_image(buf, format='png', scale=2)
                buf.seek(0)
                st.download_button(
                    label="📥 下载图表为 PNG",
                    data=buf,
                    file_name=f"{chart_type}_图表.png",
                    mime="image/png",
                    key=f"download_{chart_type}"
                )

        except Exception as e:
            st.error(f"❌ 生成图表失败：{e}")

# -----------------------------
# 导出数据
# -----------------------------
st.markdown("---")
with st.expander("💾 导出处理后的数据"):
    format_choice = st.radio("导出为：", ["CSV", "Excel"], horizontal=True)
    if st.button("生成导出", key="gen_export"):
        try:
            if format_choice == "CSV":
                csv = df.to_csv(index=False)
                st.download_button(
                    label="📥 下载 CSV",
                    data=csv,
                    file_name="处理后的数据.csv",
                    mime="text/csv",
                    key="export_csv"
                )
            else:
                buf = BytesIO()
                df.to_excel(buf, index=False, sheet_name="Sheet1")
                buf.seek(0)
                st.download_button(
                    label="📥 下载 Excel",
                    data=buf,
                    file_name="处理后的数据.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    key="export_xlsx"
                )
        except Exception as e:
            st.error(f"❌ 导出失败：{e}")