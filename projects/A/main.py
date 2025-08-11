# projects/A/main.py
# 项目 A：数据可视化工具（极简稳定版）
import streamlit as st
import pandas as pd
import plotly.express as px

# 命名空间（防止 key 冲突）
NS = "project_a"


def run():
    """
    项目 A 的入口函数
    被 client.py 动态导入并执行
    """
    st.subheader("📁 项目 A：数据可视化分析")
    st.markdown("上传 CSV 或 Excel 文件，生成交互式图表。")
    st.caption("📌 提示：图表右上角有「相机」图标，可下载为 PNG。")

    # -----------------------------
    # 文件上传
    # -----------------------------
    uploaded_file = st.file_uploader(
        "📤 上传数据文件（CSV 或 Excel）",
        type=["csv", "xlsx", "xls"],
        help="支持格式：CSV、XLSX",
        key=f"{NS}_file_uploader"
    )

    if not uploaded_file:
        st.info("请上传一个文件以开始分析。")
        return

    # -----------------------------
    # 加载数据（自动类型转换）
    # -----------------------------
    @st.cache_data
    def load_data(file):
        try:
            if file.name.endswith('.csv'):
                df = pd.read_csv(file)
            else:
                df = pd.read_excel(file)

            # 自动将可转为数字的列转为数值
            for col in df.columns:
                if df[col].dtype == 'object':
                    numeric = pd.to_numeric(df[col], errors='coerce')
                    if not numeric.isna().all():
                        df[col] = numeric
            return df
        except Exception as e:
            st.error(f"❌ 读取文件失败：{e}")
            return None

    df = load_data(uploaded_file)

    if df is None or df.empty:
        st.warning("⚠️ 数据为空或加载失败。")
        return

    # 显示数据预览
    st.success(f"✅ 已加载：{df.shape[0]} 行 × {df.shape[1]} 列")
    st.dataframe(df.head(10), use_container_width=True)

    # -----------------------------
    # 列类型检查
    # -----------------------------
    numeric_columns = df.select_dtypes(include='number').columns.tolist()
    text_columns = df.select_dtypes(include='object').columns.tolist()

    if not numeric_columns:
        st.warning("⚠️ 未找到数值列，部分图表不可用。")
    else:
        st.info(f"🔢 数值列：{', '.join(numeric_columns)}")

    if not text_columns:
        st.info("🔤 未找到文本列。")
    else:
        st.info(f"🔤 文本列：{', '.join(text_columns)}")

    if df.columns.empty:
        st.error("❌ 文件中无有效列。")
        return

    # -----------------------------
    # 图表配置
    # -----------------------------
    st.markdown("---")
    st.markdown("### 🎨 创建图表")

    col1, col2, col3 = st.columns(3)

    with col1:
        chart_type = st.selectbox(
            "图表类型",
            ["折线图", "柱状图", "散点图", "饼图", "直方图", "箱线图"],
            key=f"{NS}_chart_type"
        )

    with col2:
        x_col = st.selectbox(
            "X 轴",
            df.columns,
            index=0,
            key=f"{NS}_x_axis"
        )

    y_col = None
    if chart_type != "饼图":
        with col3:
            y_col = st.selectbox(
                "Y 轴",
                numeric_columns if numeric_columns else df.columns,
                index=0 if numeric_columns else 0,
                key=f"{NS}_y_axis"
            )
    else:
        with col3:
            y_col = st.selectbox(
                "数值（饼图）",
                numeric_columns if numeric_columns else df.columns,
                index=0 if numeric_columns else 0,
                key=f"{NS}_pie_value"
            )

    # 颜色映射（可选）
    color_col = None
    if chart_type in ["散点图", "柱状图", "折线图"]:
        with col1:
            color_options = ["无"] + text_columns + numeric_columns
            color_selected = st.selectbox(
                "颜色（可选）",
                color_options,
                key=f"{NS}_color_select"
            )
            color_col = color_selected if color_selected != "无" else None

    # -----------------------------
    # 生成图表
    # -----------------------------
    if st.button("🚀 生成图表", key=f"{NS}_gen_chart_btn"):
        if not x_col:
            st.error("❌ 请选择 X 轴。")
        elif not y_col and chart_type != "饼图":
            st.error("❌ 请选择 Y 轴。")
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

                    # ✅ 只导出数据，不导出图表
                    export_df = df[[x_col, y_col]]
                    if color_col:
                        export_df = export_df.copy()
                        export_df[color_col] = df[color_col]
                    
                    st.download_button(
                        label="📥 下载图表数据 (CSV)",
                        data=export_df.to_csv(index=False),
                        file_name=f"{chart_type}_数据.csv",
                        mime="text/csv",
                        key=f"{NS}_download_data_csv"
                    )

            except Exception as e:
                st.error(f"❌ 生成图表失败：{e}")

    # -----------------------------
    # 导出完整数据
    # -----------------------------
    st.markdown("---")
    if st.button("💾 导出完整数据", key=f"{NS}_export_full_btn"):
        try:
            csv = df.to_csv(index=False)
            st.download_button(
                "📥 下载为 CSV",
                csv,
                "完整数据.csv",
                "text/csv",
                key=f"{NS}_download_full_csv"
            )
        except Exception as e:
            st.error(f"❌ 导出失败：{e}")