# demo.py - 多行业数据采集与可视化平台（双语支持）
import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime


@st.cache_data
def get_sample_data():
    """生成各行业的默认模拟数据（用于首次加载）"""
    np.random.seed(42)
    dates = pd.date_range("2023-01-01", periods=100, freq="D")

    data = {
        "Finance": pd.DataFrame({
            "Date": dates,
            "Stock_Price": 150 + np.cumsum(np.random.randn(100) * 0.5),
            "Volume": np.random.randint(1e5, 1e6, size=100),
            "Currency_Rate": 1.08 + np.cumsum(np.random.randn(100) * 0.01),
            "Risk_Score": np.random.uniform(0.1, 0.9, size=100)
        }),

        "Healthcare": pd.DataFrame({
            "Timestamp": dates,
            "Patient_ID": np.random.choice([f"P{i}" for i in range(1, 21)], 100),
            "Temperature": 36.5 + np.random.randn(100) * 0.8,
            "Blood_Pressure_Systolic": np.random.randint(110, 160, size=100),
            "Heart_Rate": np.random.randint(60, 100, size=100),
            "Oxygen_Level": 95 + np.random.randn(100) * 2,
            "Alert": (np.random.rand(100) < 0.05) |
                     (np.random.randint(110, 160, size=100) > 140)
        }),

        "Education": pd.DataFrame({
            "Student_ID": [f"S{i}" for i in range(1, 51)] * 2,
            "Course": np.random.choice(["Math", "Science", "English"], 100),
            "Test_Score": np.random.normal(75, 15, 100).clip(0, 100),
            "Study_Hours": np.random.exponential(3, 100).clip(0, 10),
            "Attendance": np.random.uniform(0.5, 1.0, 100)
        }).assign(At_Risk=lambda df: df["Test_Score"] < 60),

        "Retail": pd.DataFrame({
            "Date": np.random.choice(dates[-30:], 200),
            "Product": np.random.choice(["Laptop", "Phone", "Headphones", "Tablet"], 200),
            "Revenue": np.random.lognormal(8, 1, 200),
            "Units_Sold": np.random.poisson(5, 200),
            "Customer_Age": np.random.randint(18, 65, 200),
            "Region": np.random.choice(["North", "South", "East", "West"], 200)
        }),

        "Logistics": pd.DataFrame({
            "Delivery_ID": [f"D{i}" for i in range(1, 201)],
            "Route": np.random.choice(["A→B", "B→C", "C→D", "A→D"], 200),
            "Distance_km": np.random.randint(50, 500, 200),
            "Delivery_Time_h": np.random.gamma(3, 2, 200),
            "Fuel_Cost": np.random.lognormal(2, 0.5, 200),
            "On_Time": np.random.choice([True]*80 + [False]*20, 200)
        }),

        "Research": pd.DataFrame({
            "Experiment_ID": [f"E{i}" for i in range(1, 101)],
            "Variable_X": np.linspace(0, 10, 100) + np.random.normal(0, 0.1, 100),
            "Response_Y": np.sin(np.linspace(0, 10, 100)) + np.random.normal(0, 0.2, 100),
            "Group": np.random.choice(["Control", "Treatment"], 100),
            "p_value": np.random.uniform(0.001, 0.8, 100)
        }),

        "Marketing": pd.DataFrame({
            "Campaign": ["Spring Sale", "Summer Promo", "Back-to-School", "Holiday Blitz"],
            "Spend": [5000, 8000, 6000, 12000],
            "Clicks": [12000, 25000, 18000, 40000],
            "Conversions": [120, 300, 200, 600],
            "Revenue_Generated": [15000, 40000, 25000, 90000]
        })
    }
    return data


# ==============================
# 可视化渲染函数（保持不变）
# ==============================

def _render_finance(df, t):
    st.subheader(t("demo_finance_title"))

    col1, col2, col3 = st.columns(3)
    col1.metric(t("demo_finance_stock_price"), f"${df['Stock_Price'].iloc[-1]:.2f}")
    col2.metric(t("demo_finance_avg_volume"), f"{df['Volume'].mean():,.0f}")
    risk_level = f"{df['Risk_Score'].iloc[-1]:.0%}"
    col3.metric(t("demo_finance_risk_level"), risk_level, delta="-5%")

    fig1 = px.line(df, x="Date", y="Stock_Price", title=t("demo_finance_stock_trend"))
    fig1.add_scatter(x=df["Date"], y=df["Stock_Price"].rolling(10).mean(), name="MA(10)", line=dict(color="orange"))
    st.plotly_chart(fig1, use_container_width=True)

    fig2 = px.scatter(df, x="Currency_Rate", y="Stock_Price", size="Volume",
                      color="Risk_Score", color_continuous_scale="Reds",
                      title=t("demo_finance_stock_vs_currency"))
    st.plotly_chart(fig2, use_container_width=True)

    st.info(t("demo_finance_anomaly"))


def _render_healthcare(df, t):
    st.subheader(t("demo_healthcare_title"))

    alert_count = df["Alert"].sum()
    if alert_count > 0:
        st.warning(t("demo_healthcare_alert").format(count=alert_count))
    else:
        st.success(t("demo_healthcare_normal"))

    col1, col2 = st.columns(2)
    with col1:
        fig1 = px.histogram(df, x="Blood_Pressure_Systolic", nbins=20, title=t("demo_healthcare_bp_dist"))
        fig1.add_vline(x=140, line_dash="dash", line_color="red", annotation_text=t("demo_healthcare_hypertension"))
        st.plotly_chart(fig1)

    with col2:
        fig2 = px.line(df, x="Timestamp", y="Oxygen_Level", color="Patient_ID",
                       title=t("demo_healthcare_oxygen"), line_group="Patient_ID")
        fig2.update_traces(opacity=0.6, line_width=1)
        st.plotly_chart(fig2)

    st.markdown("#### " + t("demo_healthcare_vital_corr"))
    fig3 = px.scatter(df, x="Temperature", y="Heart_Rate", color="Blood_Pressure_Systolic",
                      color_continuous_scale="Viridis", title=t("demo_healthcare_vital_corr"))
    st.plotly_chart(fig3, use_container_width=True)

    st.success(t("demo_healthcare_alerts"))


def _render_education(df, t):
    st.subheader(t("demo_education_title"))

    at_risk_count = df["At_Risk"].sum()
    st.metric(t("demo_education_at_risk"), at_risk_count)

    col1, col2 = st.columns(2)
    with col1:
        fig1 = px.scatter(df, x="Study_Hours", y="Test_Score", color="Course",
                          title=t("demo_education_study_vs_score"), labels={"color": "Course"})
        fig1.add_shape(type="line", x0=0, y0=60, x1=10, y1=60, line=dict(dash="dash", color="red"))
        st.plotly_chart(fig1)

    with col2:
        avg_score = df.groupby("Course")["Test_Score"].mean().reset_index()
        fig2 = px.bar(avg_score, x="Course", y="Test_Score", title=t("demo_education_avg_score"))
        st.plotly_chart(fig2)

    st.markdown("#### " + t("demo_education_at_risk_list"))
    risk_df = df[df["At_Risk"]][["Student_ID", "Course", "Test_Score", "Study_Hours", "Attendance"]]
    st.dataframe(risk_df, use_container_width=True)

    st.info(t("demo_education_intervention"))


def _render_retail(df, t):
    st.subheader(t("demo_retail_title"))

    col1, col2 = st.columns(2)
    with col1:
        sales_by_product = df.groupby("Product")["Revenue"].sum().round(2).reset_index()
        fig1 = px.pie(sales_by_product, values="Revenue", names="Product", title=t("demo_retail_revenue_share"))
        st.plotly_chart(fig1)

    with col2:
        daily_rev = df.groupby("Date")["Revenue"].sum().reset_index()
        fig2 = px.bar(daily_rev, x="Date", y="Revenue", title=t("demo_retail_daily_revenue"))
        st.plotly_chart(fig2)

    st.markdown("#### " + t("demo_retail_behavior"))
    fig3 = px.scatter(df, x="Customer_Age", y="Revenue", color="Product", size="Units_Sold",
                      title=t("demo_retail_behavior"))
    st.plotly_chart(fig3, use_container_width=True)

    st.success(t("demo_retail_recommend"))


def _render_logistics(df, t):
    st.subheader(t("demo_logistics_title"))

    on_time_rate = df["On_Time"].mean()
    st.metric(t("demo_logistics_on_time"), f"{on_time_rate:.1%}")

    col1, col2 = st.columns(2)
    with col1:
        fig1 = px.box(df, x="Route", y="Delivery_Time_h", title=t("demo_logistics_delivery_time"))
        st.plotly_chart(fig1)

    with col2:
        fig2 = px.scatter(df, x="Distance_km", y="Delivery_Time_h", color="On_Time",
                          color_discrete_map={True: "green", False: "red"},
                          title=t("demo_logistics_time_vs_dist"))
        st.plotly_chart(fig2)

    st.markdown("#### " + t("demo_logistics_fuel_cost"))
    fig3 = px.histogram(df, x="Fuel_Cost", nbins=20, title=t("demo_logistics_fuel_cost"))
    st.plotly_chart(fig3)

    st.info(t("demo_logistics_optimize"))


def _render_research(df, t):
    st.subheader(t("demo_research_title"))

    fig1 = px.scatter(df, x="Variable_X", y="Response_Y", color="Group",
                      title=t("demo_research_response"),
                      color_discrete_sequence=px.colors.qualitative.Set1)
    fig1.add_scatter(x=np.linspace(0, 10, 100), y=np.sin(np.linspace(0, 10, 100)),
                     mode="lines", line=dict(color="black", dash="dash"), name=t("demo_research_theoretical"))
    st.plotly_chart(fig1)

    col1, col2 = st.columns(2)
    with col1:
        p_sig = (df["p_value"] < 0.05).sum()
        fig2 = px.bar(x=[t("demo_research_significant"), t("demo_research_not_significant")],
                      y=[p_sig, len(df)-p_sig],
                      title=t("demo_research_significance"))
        st.plotly_chart(fig2)

    with col2:
        group_means = df.groupby("Group")["Response_Y"].mean().reset_index()
        fig3 = px.bar(group_means, x="Group", y="Response_Y", title=t("demo_research_mean_response"))
        st.plotly_chart(fig3)

    st.success(t("demo_research_communicate"))


def _render_marketing(df, t):
    st.subheader(t("demo_marketing_title"))

    df["ROI"] = (df["Revenue_Generated"] - df["Spend"]) / df["Spend"]
    df["CPC"] = df["Spend"] / df["Clicks"]
    df["Conversion_Rate"] = df["Conversions"] / df["Clicks"]

    col1, col2, col3 = st.columns(3)
    col1.metric(t("demo_marketing_roi"), f"{df['ROI'].max():.1%}")
    col2.metric(t("demo_marketing_cpc"), f"${df['CPC'].min():.2f}")
    col3.metric(t("demo_marketing_conv_rate"), f"{df['Conversion_Rate'].max():.1%}")

    fig1 = px.bar(df, x="Campaign", y="Revenue_Generated", color="ROI",
                  color_continuous_scale="Blugrn", title=t("demo_marketing_revenue_roi"))
    st.plotly_chart(fig1)

    st.dataframe(df[["Campaign", "Spend", "Clicks", "Conversions", "ROI"]], use_container_width=True)

    st.info(t("demo_marketing_attribution"))


def _render_data_hub(data, t):
    st.subheader(t("demo_datahub_title"))
    st.markdown(t("demo_datahub_select"))
    domain = st.selectbox("Select Dataset to Export", list(data.keys()), label_visibility="collapsed")
    df = data[domain]

    st.dataframe(df.head(10), use_container_width=True)

    csv = df.to_csv(index=False)
    filename = f"{domain.lower()}_{datetime.now().strftime('%Y%m%d_%H%M')}.csv"

    st.download_button(
        label=t("demo_datahub_download").format(domain=domain),
        data=csv,
        file_name=filename,
        mime="text/csv"
    )

    st.markdown("---")
    st.markdown(t("demo_datahub_integration"))
    st.markdown(t("demo_datahub_connect"))


# ==============================
# 数据采集应用函数
# ==============================

def _acquire_finance(t):
    st.subheader(t("demo_finance_acquire_title"))
    st.markdown(t("demo_finance_acquire_desc"))

    col1, col2, col3 = st.columns(3)
    initial_price = col1.number_input(t("demo_finance_initial_price"), 50.0, 300.0, 150.0)
    volatility = col2.number_input(t("demo_finance_volatility"), 0.01, 2.0, 0.5, step=0.01)
    days = col3.number_input(t("demo_finance_days"), 10, 365, 100)

    if st.button(t("demo_finance_generate")):
        dates = pd.date_range("2023-01-01", periods=days, freq="D")
        price = initial_price + np.cumsum(np.random.randn(days) * volatility)
        volume = np.random.randint(1e5, 1e6, size=days)
        currency = 1.08 + np.cumsum(np.random.randn(days) * 0.01)
        risk = np.random.uniform(0.1, 0.9, size=days)

        df = pd.DataFrame({
            "Date": dates,
            "Stock_Price": price,
            "Volume": volume,
            "Currency_Rate": currency,
            "Risk_Score": risk
        })
        st.session_state["Finance"] = df
        st.dataframe(df.tail(), use_container_width=True)
        st.success(f"✅ {days} {t('demo_days')} {t('demo_finance_generated')}!")


def _acquire_healthcare(t):
    st.subheader(t("demo_healthcare_acquire_title"))
    st.markdown(t("demo_healthcare_acquire_desc"))

    col1, col2 = st.columns(2)
    num_patients = col1.number_input(t("demo_healthcare_num_patients"), 1, 50, 20)
    duration = col2.number_input(t("demo_healthcare_duration"), 1, 365, 30)

    if st.button(t("demo_healthcare_generate")):
        np.random.seed()
        dates = pd.date_range("2023-01-01", periods=duration, freq="D")
        patients = [f"P{i}" for i in range(1, num_patients + 1)]
        n = num_patients * duration

        df = pd.DataFrame({
            "Timestamp": np.repeat(dates, num_patients),
            "Patient_ID": patients * duration,
            "Temperature": 36.5 + np.random.randn(n) * 0.8,
            "Blood_Pressure_Systolic": np.random.randint(110, 160, size=n),
            "Heart_Rate": np.random.randint(60, 100, size=n),
            "Oxygen_Level": 95 + np.random.randn(n) * 2,
        })
        df["Alert"] = (df["Blood_Pressure_Systolic"] > 140) | (df["Oxygen_Level"] < 90)

        st.session_state["Healthcare"] = df
        st.dataframe(df.sample(10), use_container_width=True)
        st.success(f"✅ {num_patients} {t('demo_patients')} {duration} {t('demo_days')} {t('demo_healthcare_generated')}!")


def _acquire_education(t):
    st.subheader(t("demo_education_acquire_title"))
    st.markdown(t("demo_education_acquire_desc"))

    num_students = st.number_input(t("demo_education_num_students"), 10, 100, 50)
    courses = st.multiselect(t("demo_education_courses"),
                             ["Math", "Science", "English", "History", "Art"],
                             default=["Math", "Science", "English"])

    if st.button(t("demo_education_generate")):
        n = num_students * len(courses)
        df = pd.DataFrame({
            "Student_ID": np.random.choice([f"S{i}" for i in range(1, num_students+1)], n),
            "Course": np.random.choice(courses, n),
            "Test_Score": np.random.normal(75, 15, n).clip(0, 100),
            "Study_Hours": np.random.exponential(3, n).clip(0, 10),
            "Attendance": np.random.uniform(0.5, 1.0, n)
        })
        df["At_Risk"] = df["Test_Score"] < 60
        st.session_state["Education"] = df
        st.dataframe(df.head(10), use_container_width=True)
        st.success(t("demo_education_generated"))


def _acquire_retail(t):
    st.subheader(t("demo_retail_acquire_title"))
    st.markdown(t("demo_retail_acquire_desc"))

    days = st.number_input(t("demo_retail_days"), 1, 90, 30)
    products = st.multiselect(t("demo_retail_products"),
                              ["Laptop", "Phone", "Headphones", "Tablet", "Watch"],
                              default=["Laptop", "Phone", "Headphones", "Tablet"])

    if st.button(t("demo_retail_generate")):
        dates = pd.date_range("2023-01-01", periods=days, freq="D")
        n = len(products) * 50  # 模拟 50 笔/产品
        df = pd.DataFrame({
            "Date": np.random.choice(dates, n),
            "Product": np.random.choice(products, n),
            "Revenue": np.random.lognormal(8, 1, n),
            "Units_Sold": np.random.poisson(5, n),
            "Customer_Age": np.random.randint(18, 65, n),
            "Region": np.random.choice(["North", "South", "East", "West"], n)
        })
        st.session_state["Retail"] = df
        st.dataframe(df.head(10), use_container_width=True)
        st.success(t("demo_retail_generated"))


def _acquire_logistics(t):
    st.subheader(t("demo_logistics_acquire_title"))
    st.markdown(t("demo_logistics_acquire_desc"))

    num_deliveries = st.number_input(t("demo_logistics_num_deliveries"), 50, 1000, 200)
    routes = st.multiselect(t("demo_logistics_routes"),
                            ["A→B", "B→C", "C→D", "A→D", "X→Y"],
                            default=["A→B", "B→C", "C→D", "A→D"])

    if st.button(t("demo_logistics_generate")):
        df = pd.DataFrame({
            "Delivery_ID": [f"D{i}" for i in range(1, num_deliveries + 1)],
            "Route": np.random.choice(routes, num_deliveries),
            "Distance_km": np.random.randint(50, 500, num_deliveries),
            "Delivery_Time_h": np.random.gamma(3, 2, num_deliveries),
            "Fuel_Cost": np.random.lognormal(2, 0.5, num_deliveries),
            "On_Time": np.random.choice([True]*80 + [False]*20, num_deliveries)
        })
        st.session_state["Logistics"] = df
        st.dataframe(df.head(10), use_container_width=True)
        st.success(t("demo_logistics_generated"))


def _acquire_research(t):
    st.subheader(t("demo_research_acquire_title"))
    st.markdown(t("demo_research_acquire_desc"))

    col1, col2 = st.columns(2)
    n = col1.number_input(t("demo_research_sample_size"), 50, 500, 100)
    noise = col2.number_input(t("demo_research_noise"), 0.01, 1.0, 0.2, step=0.01)

    if st.button(t("demo_research_generate")):
        x = np.linspace(0, 10, n) + np.random.normal(0, 0.1, n)
        y = np.sin(x) + np.random.normal(0, noise, n)
        group = np.random.choice(["Control", "Treatment"], n)
        p_val = np.random.uniform(0.001, 0.8, n)

        df = pd.DataFrame({
            "Experiment_ID": [f"E{i}" for i in range(1, n+1)],
            "Variable_X": x,
            "Response_Y": y,
            "Group": group,
            "p_value": p_val
        })
        st.session_state["Research"] = df
        st.dataframe(df.head(10), use_container_width=True)
        st.success(t("demo_research_generated"))


def _acquire_marketing(t):
    st.subheader(t("demo_marketing_acquire_title"))
    st.markdown(t("demo_marketing_acquire_desc"))

    st.markdown("#### " + t("demo_marketing_edit_data"))
    campaigns = [
        t("demo_campaign_spring_sale"),
        t("demo_campaign_summer_promo"),
        t("demo_campaign_back_to_school"),
        t("demo_campaign_holiday_blitz")
    ]
    data = []
    for camp in campaigns:
        with st.expander(camp):
            spend = st.number_input(f"{t('demo_marketing_spend')} - {camp}", 1000, 50000, 5000)
            clicks = st.number_input(f"{t('demo_marketing_clicks')} - {camp}", 1000, 100000, 12000)
            conversions = st.number_input(f"{t('demo_marketing_conversions')} - {camp}", 10, 1000, 120)
            revenue = st.number_input(f"{t('demo_marketing_revenue')} - {camp}", 5000, 200000, 15000)
            data.append([camp, spend, clicks, conversions, revenue])

    if st.button(t("demo_marketing_save")):
        df = pd.DataFrame(data, columns=["Campaign", "Spend", "Clicks", "Conversions", "Revenue_Generated"])
        st.session_state["Marketing"] = df
        st.success(t("demo_marketing_saved"))
        return df
    return None


# ==============================
# 主入口函数
# ==============================

def render(t):
    """主入口函数：支持双语和双层 Tabs（数据采集 + 数据可视化）"""
    st.title(t("demo_title"))
    st.markdown(t("demo_intro"))
    st.markdown("---")

    # 获取默认模拟数据（缓存）
    base_data = get_sample_data()

    # 优先使用用户生成的数据，否则用默认数据
    def get_data(key):
        return st.session_state.get(key, base_data[key])

    # === 主行业列表（使用下划线命名，用于查找翻译 key）===
    domain_keys = [
        "Finance",
        "Healthcare",
        "Education",
        "Retail",
        "Logistics",
        "Research",
        "Marketing",
        "Data_Hub"  # 使用下划线，避免 KeyError
    ]

    # === 使用 t() 翻译主 Tabs 标签（实现双语切换）===
    main_tab_labels = [t(f"demo_{key.lower()}") for key in domain_keys]
    main_tabs = st.tabs(main_tab_labels)

    # ==============================
    # 1. Finance
    # ==============================
    with main_tabs[0]:
        subtabs = st.tabs([t("demo_data_acquisition"), t("demo_dashboard")])
        with subtabs[0]:
            _acquire_finance(t)
        with subtabs[1]:
            _render_finance(get_data("Finance"), t)

    # ==============================
    # 2. Healthcare
    # ==============================
    with main_tabs[1]:
        subtabs = st.tabs([t("demo_data_acquisition"), t("demo_dashboard")])
        with subtabs[0]:
            _acquire_healthcare(t)
        with subtabs[1]:
            _render_healthcare(get_data("Healthcare"), t)

    # ==============================
    # 3. Education
    # ==============================
    with main_tabs[2]:
        subtabs = st.tabs([t("demo_data_acquisition"), t("demo_dashboard")])
        with subtabs[0]:
            _acquire_education(t)
        with subtabs[1]:
            _render_education(get_data("Education"), t)

    # ==============================
    # 4. Retail
    # ==============================
    with main_tabs[3]:
        subtabs = st.tabs([t("demo_data_acquisition"), t("demo_dashboard")])
        with subtabs[0]:
            _acquire_retail(t)
        with subtabs[1]:
            _render_retail(get_data("Retail"), t)

    # ==============================
    # 5. Logistics
    # ==============================
    with main_tabs[4]:
        subtabs = st.tabs([t("demo_data_acquisition"), t("demo_dashboard")])
        with subtabs[0]:
            _acquire_logistics(t)
        with subtabs[1]:
            _render_logistics(get_data("Logistics"), t)

    # ==============================
    # 6. Research
    # ==============================
    with main_tabs[5]:
        subtabs = st.tabs([t("demo_data_acquisition"), t("demo_dashboard")])
        with subtabs[0]:
            _acquire_research(t)
        with subtabs[1]:
            _render_research(get_data("Research"), t)

    # ==============================
    # 7. Marketing
    # ==============================
    with main_tabs[6]:
        subtabs = st.tabs([t("demo_data_acquisition"), t("demo_dashboard")])
        with subtabs[0]:
            df = _acquire_marketing(t)
            if df is not None:
                st.session_state["Marketing"] = df  # 保存用户输入数据
        with subtabs[1]:
            _render_marketing(get_data("Marketing"), t)

    # ==============================
    # 8. Data Hub
    # ==============================
    with main_tabs[7]:
        # 构建当前所有数据（排除 Data_Hub 自身）
        current_data = {key: get_data(key) for key in domain_keys if key != "Data_Hub"}
        _render_data_hub(current_data, t)