import streamlit as st
import os
import psycopg2
from dotenv import load_dotenv
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, date
import traceback  # 用于调试（可选）

def run():
    # ----------------------------- 环境 & 连接 ----------------------------- #
    load_dotenv()
    DATABASE_URL = os.getenv("DATABASE_XUNYU_URL") or os.getenv("DATABASE_URL")
    if not DATABASE_URL:
        st.error("❌ 未设置数据库连接URL，请检查 .env 文件中的 DATABASE_URL 或 DATABASE_XUNYU_URL")
        st.stop()

    # 兼容 Heroku 的 postgres://
    SQLALCHEMY_URL = DATABASE_URL.replace("postgres://", "postgresql://") if DATABASE_URL.startswith("postgres://") else DATABASE_URL

    # ----------------------------- 工具函数 ----------------------------- #
    def execute_query(query, params=None, fetch=False):
        """通用数据库查询函数"""
        try:
            with psycopg2.connect(DATABASE_URL) as conn:
                with conn.cursor() as cur:
                    cur.execute(query, params)
                    if fetch:
                        rows = cur.fetchall()
                        cols = [desc[0] for desc in cur.description]
                        return pd.DataFrame(rows, columns=cols)
                    conn.commit()
            return None
        except Exception as e:
            st.error(f"⚠️ 数据库操作失败: {e}")
            # 可选：显示详细错误（部署时建议关闭）
            # st.code(traceback.format_exc())
            return None

    def get_ponds():
        df = execute_query("SELECT pond_id, pond_name FROM ponds ORDER BY pond_name", fetch=True)
        return df if df is not None else pd.DataFrame()

    # ----------------------------- 初始化数据库表（修复 sales 表） ----------------------------- #
    init_queries = [
        """
        CREATE TABLE IF NOT EXISTS ponds (
            pond_id SERIAL PRIMARY KEY,
            pond_name VARCHAR(50) UNIQUE NOT NULL,
            capacity_kg NUMERIC(10, 2),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """,
        """
        CREATE TABLE IF NOT EXISTS stocking (
            stocking_id SERIAL PRIMARY KEY,
            pond_id INTEGER REFERENCES ponds(pond_id) ON DELETE CASCADE,
            fish_count INTEGER NOT NULL,
            total_weight_kg NUMERIC(10, 2) NOT NULL,
            purchase_price_per_kg NUMERIC(8, 2) NOT NULL,
            supplier VARCHAR(100),
            avg_weight_kg NUMERIC(6, 3) GENERATED ALWAYS AS (total_weight_kg / NULLIF(fish_count, 0)) STORED,
            stocking_date DATE NOT NULL DEFAULT CURRENT_DATE,
            notes TEXT
        );
        """,
        """
        CREATE TABLE IF NOT EXISTS sales (
            sale_id SERIAL PRIMARY KEY,
            pond_id INTEGER REFERENCES ponds(pond_id) ON DELETE CASCADE,
            fish_sold_count INTEGER,  -- ✅ 新增字段：销售条数
            weight_sold_kg NUMERIC(10, 2) NOT NULL,
            sale_date DATE NOT NULL DEFAULT CURRENT_DATE,
            price_per_kg NUMERIC(8, 2),
            buyer VARCHAR(100),
            notes TEXT
        );
        """,
        """
        CREATE TABLE IF NOT EXISTS mortalities (
            mortality_id SERIAL PRIMARY KEY,
            pond_id INTEGER REFERENCES ponds(pond_id) ON DELETE CASCADE,
            fish_count INTEGER NOT NULL,
            weight_kg NUMERIC(10, 2),
            mortality_date DATE NOT NULL DEFAULT CURRENT_DATE,
            reason VARCHAR(200),
            notes TEXT
        );
        """,
        """
        CREATE TABLE IF NOT EXISTS operating_costs (
            cost_id SERIAL PRIMARY KEY,
            pond_id INTEGER REFERENCES ponds(pond_id) ON DELETE CASCADE,
            cost_type VARCHAR(50) NOT NULL,
            amount NUMERIC(10, 2) NOT NULL,
            cost_date DATE NOT NULL DEFAULT CURRENT_DATE,
            notes TEXT
        );
        """
    ]

    for q in init_queries:
        execute_query(q)

    st.set_page_config(page_title="鲟鱼养殖场管理系统", layout="wide")
    st.title("🐟 鲟鱼养殖场管理系统")

    # ----------------------------- 主 Tabs ----------------------------- #
    tab1, tab2, tab3 = st.tabs(["养殖池管理", "经营成本管理", "数据可视化分析"])

    # ============================= Tab 1: 养殖池管理 =============================
    with tab1:
        st.header("养殖池生命周期管理")
        subtab1, subtab2, subtab3, subtab4 = st.tabs(["创建/管理养殖池", "进货装池", "销售记录", "死亡/损耗"])

        # --- Subtab 1: 创建/管理养殖池 ---
        with subtab1:
            st.subheader("创建新养殖池")
            with st.form("add_pond"):
                pond_name = st.text_input("养殖池名称", placeholder="如：Pond-A1")
                capacity = st.number_input("容量（公斤）", min_value=0.0, value=2000.0, step=100.0)
                if st.form_submit_button("✅ 创建养殖池"):
                    if pond_name.strip():
                        execute_query(
                            "INSERT INTO ponds (pond_name, capacity_kg) VALUES (%s, %s)",
                            (pond_name.strip(), capacity)
                        )
                        st.success(f"成功创建养殖池：{pond_name}")
                    else:
                        st.warning("请输入养殖池名称")

            st.subheader("现有养殖池列表")
            ponds_df = get_ponds()
            if ponds_df is not None and len(ponds_df) > 0:  # 修复：使用 len() 而不是 empty
                display_ponds = ponds_df.rename(columns={
                    'pond_id': '池ID',
                    'pond_name': '养殖池名称'
                })
                st.dataframe(display_ponds, use_container_width=True)
            else:
                st.info("暂无养殖池，请先创建。")

        # --- Subtab 2: 进货装池 ---
        with subtab2:
            st.subheader("进货装池（可多次，每次记录采购单价）")
            ponds_df = get_ponds()
            if ponds_df is None or len(ponds_df) == 0:  # 修复：使用 len() 而不是 empty
                st.warning("请先创建养殖池")
            else:
                with st.form("stocking_form"):
                    pond_id = st.selectbox("选择养殖池", ponds_df['pond_id'], format_func=lambda x: ponds_df[ponds_df['pond_id']==x]['pond_name'].iloc[0])
                    fish_count = st.number_input("鱼的条数", min_value=1, value=1000)
                    total_weight = st.number_input("总重量（公斤）", min_value=0.1, value=2000.0, step=10.0)
                    purchase_price = st.number_input("采购单价（元/公斤）", min_value=0.0, value=40.0, step=1.0)
                    supplier = st.text_input("供应商（可选）")
                    stocking_date = st.date_input("装池日期", value=date.today())
                    notes = st.text_area("备注（可选）")
                    if st.form_submit_button("📥 记录进货"):
                        execute_query("""
                            INSERT INTO stocking (pond_id, fish_count, total_weight_kg, purchase_price_per_kg, supplier, stocking_date, notes)
                            VALUES (%s, %s, %s, %s, %s, %s, %s)
                        """, (pond_id, fish_count, total_weight, purchase_price, supplier or None, stocking_date, notes))
                        st.success("进货记录已保存！")

                # 显示历史进货
                st.subheader("历史进货记录")
                df = execute_query("""
                    SELECT s.stocking_id, p.pond_name, s.fish_count, s.total_weight_kg, s.avg_weight_kg,
                        s.purchase_price_per_kg, s.supplier, s.stocking_date, s.notes
                    FROM stocking s
                    JOIN ponds p ON s.pond_id = p.pond_id
                    ORDER BY s.stocking_date DESC
                """, fetch=True)
                if df is not None and len(df) > 0:  # 修复：使用 len() 而不是 empty
                    df['purchase_cost'] = df['total_weight_kg'] * df['purchase_price_per_kg']
                    df_display = df.rename(columns={
                        'stocking_id': '记录ID',
                        'pond_name': '养殖池',
                        'fish_count': '鱼条数',
                        'total_weight_kg': '总重量(公斤)',
                        'avg_weight_kg': '平均单重(公斤)',
                        'purchase_price_per_kg': '采购单价(元/公斤)',
                        'supplier': '供应商',
                        'stocking_date': '装池日期',
                        'notes': '备注',
                        'purchase_cost': '采购成本(元)'
                    })
                    st.dataframe(df_display, use_container_width=True)

        # --- Subtab 3: 销售记录 ---
        with subtab3:
            st.subheader("销售记录（请同时填写重量和条数）")
            ponds_df = get_ponds()
            if ponds_df is None or len(ponds_df) == 0:  # 修复：使用 len() 而不是 empty
                st.warning("请先创建养殖池")
            else:
                with st.form("sales_form"):
                    pond_id = st.selectbox("选择养殖池", ponds_df['pond_id'], format_func=lambda x: ponds_df[ponds_df['pond_id']==x]['pond_name'].iloc[0])
                    fish_sold_count = st.number_input("销售条数", min_value=1, value=100)
                    weight_sold = st.number_input("销售重量（公斤）", min_value=0.1, value=100.0, step=1.0)
                    if fish_sold_count > 0:
                        est_avg = weight_sold / fish_sold_count
                        st.caption(f"💡 估算单条重量: {est_avg:.3f} 公斤/条")
                    price_per_kg = st.number_input("单价（元/公斤）", min_value=0.0, value=50.0)
                    buyer = st.text_input("买家")
                    sale_date = st.date_input("销售日期", value=date.today())
                    notes = st.text_area("备注（可选）")
                    if st.form_submit_button("💰 记录销售"):
                        execute_query("""
                            INSERT INTO sales (pond_id, fish_sold_count, weight_sold_kg, price_per_kg, buyer, sale_date, notes)
                            VALUES (%s, %s, %s, %s, %s, %s, %s)
                        """, (pond_id, fish_sold_count, weight_sold, price_per_kg, buyer, sale_date, notes))
                        st.success("销售记录已保存！")

                # 显示历史销售
                st.subheader("历史销售记录")
                df = execute_query("""
                    SELECT s.sale_id, p.pond_name, 
                        s.fish_sold_count, 
                        s.weight_sold_kg, 
                        s.weight_sold_kg / NULLIF(s.fish_sold_count, 0) AS avg_weight_sold_kg,
                        s.price_per_kg, 
                        (s.weight_sold_kg * s.price_per_kg) AS revenue, 
                        s.buyer, s.sale_date, s.notes
                    FROM sales s
                    JOIN ponds p ON s.pond_id = p.pond_id
                    ORDER BY s.sale_date DESC
                """, fetch=True)
                if df is not None and len(df) > 0:  # 修复：使用 len() 而不是 empty
                    df_display = df.rename(columns={
                        'sale_id': '记录ID',
                        'pond_name': '养殖池',
                        'fish_sold_count': '销售条数',
                        'weight_sold_kg': '销售重量(公斤)',
                        'avg_weight_sold_kg': '平均单重(公斤)',
                        'price_per_kg': '单价(元/公斤)',
                        'revenue': '销售收入(元)',
                        'buyer': '买家',
                        'sale_date': '销售日期',
                        'notes': '备注'
                    })
                    st.dataframe(df_display, use_container_width=True)

        # --- Subtab 4: 死亡/损耗 ---
        with subtab4:
            st.subheader("死亡或损耗记录")
            ponds_df = get_ponds()
            if ponds_df is None or len(ponds_df) == 0:  # 修复：使用 len() 而不是 empty
                st.warning("请先创建养殖池")
            else:
                with st.form("mortality_form"):
                    pond_id = st.selectbox("选择养殖池", ponds_df['pond_id'], format_func=lambda x: ponds_df[ponds_df['pond_id']==x]['pond_name'].iloc[0])
                    fish_count = st.number_input("死亡条数", min_value=1, value=10)
                    weight_kg = st.number_input("对应重量（公斤，可选）", min_value=0.0, value=0.0)
                    reason = st.text_input("原因（如：疾病、操作失误）")
                    mortality_date = st.date_input("日期", value=date.today())
                    notes = st.text_area("备注")
                    if st.form_submit_button("💀 记录死亡"):
                        execute_query("""
                            INSERT INTO mortalities (pond_id, fish_count, weight_kg, reason, mortality_date, notes)
                            VALUES (%s, %s, %s, %s, %s, %s)
                        """, (pond_id, fish_count, weight_kg or None, reason, mortality_date, notes))
                        st.success("死亡记录已保存！")

                st.subheader("历史死亡记录")
                df = execute_query("""
                    SELECT m.mortality_id, p.pond_name, m.fish_count, m.weight_kg, m.reason, m.mortality_date, m.notes
                    FROM mortalities m
                    JOIN ponds p ON m.pond_id = p.pond_id
                    ORDER BY m.mortality_date DESC
                """, fetch=True)
                if df is not None and len(df) > 0:  # 修复：使用 len() 而不是 empty
                    df_display = df.rename(columns={
                        'mortality_id': '记录ID',
                        'pond_name': '养殖池',
                        'fish_count': '死亡条数',
                        'weight_kg': '死亡重量(公斤)',
                        'reason': '原因',
                        'mortality_date': '日期',
                        'notes': '备注'
                    })
                    st.dataframe(df_display, use_container_width=True)

    # ============================= Tab 2: 经营成本管理 =============================
    with tab2:
        st.header("经营成本记录")
        ponds_df = get_ponds()
        if ponds_df is None or len(ponds_df) == 0:  # 修复：使用 len() 而不是 empty
            st.warning("请先创建养殖池")
        else:
            with st.form("cost_form"):
                pond_id = st.selectbox("养殖池", ponds_df['pond_id'], format_func=lambda x: ponds_df[ponds_df['pond_id']==x]['pond_name'].iloc[0])
                cost_type = st.selectbox("成本类型", ["电费", "水费", "人工", "饲料", "药品", "其他"])
                amount = st.number_input("金额（元）", min_value=0.0, value=100.0)
                cost_date = st.date_input("发生日期", value=date.today())
                notes = st.text_area("备注")
                if st.form_submit_button("💰 记录成本"):
                    # 映射中文回英文存入数据库（可选，也可直接存中文）
                    type_map = {"电费": "electricity", "水费": "water", "人工": "labor", "饲料": "feed", "药品": "medicine", "其他": "other"}
                    db_type = type_map.get(cost_type, "other")
                    execute_query("""
                        INSERT INTO operating_costs (pond_id, cost_type, amount, cost_date, notes)
                        VALUES (%s, %s, %s, %s, %s)
                    """, (pond_id, db_type, amount, cost_date, notes))
                    st.success("成本记录已保存！")

            st.subheader("历史成本记录")
            df = execute_query("""
                SELECT oc.cost_id, p.pond_name, oc.cost_type, oc.amount, oc.cost_date, oc.notes
                FROM operating_costs oc
                JOIN ponds p ON oc.pond_id = p.pond_id
                ORDER BY oc.cost_date DESC
            """, fetch=True)
            if df is not None and len(df) > 0:  # 修复：使用 len() 而不是 empty
                # 中文显示成本类型
                type_map_rev = {"electricity": "电费", "water": "水费", "labor": "人工", "feed": "饲料", "medicine": "药品", "other": "其他"}
                df['cost_type'] = df['cost_type'].map(type_map_rev).fillna(df['cost_type'])
                df_display = df.rename(columns={
                    'cost_id': '记录ID',
                    'pond_name': '养殖池',
                    'cost_type': '成本类型',
                    'amount': '金额(元)',
                    'cost_date': '日期',
                    'notes': '备注'
                })
                st.dataframe(df_display, use_container_width=True)

    # ============================= Tab 3: 数据可视化分析 =============================
    with tab3:
        st.header("📊 数据可视化分析")

        # 安全获取数据：确保返回 DataFrame 而非 None
        df_stock = execute_query("""
            SELECT p.pond_name, s.stocking_date, s.fish_count, s.total_weight_kg, s.avg_weight_kg, s.purchase_price_per_kg
            FROM stocking s
            JOIN ponds p ON s.pond_id = p.pond_id
        """, fetch=True)
        df_stock = df_stock if df_stock is not None else pd.DataFrame()

        df_sales = execute_query("""
            SELECT p.pond_name, s.sale_date, s.fish_sold_count, s.weight_sold_kg, s.price_per_kg, (s.weight_sold_kg * s.price_per_kg) AS revenue
            FROM sales s
            JOIN ponds p ON s.pond_id = p.pond_id
        """, fetch=True)
        df_sales = df_sales if df_sales is not None else pd.DataFrame()

        df_mort = execute_query("""
            SELECT p.pond_name, m.mortality_date, m.fish_count AS dead_fish, m.weight_kg AS dead_weight
            FROM mortalities m
            JOIN ponds p ON m.pond_id = p.pond_id
        """, fetch=True)
        df_mort = df_mort if df_mort is not None else pd.DataFrame()

        df_costs = execute_query("""
            SELECT p.pond_name, oc.cost_type, oc.amount, oc.cost_date
            FROM operating_costs oc
            JOIN ponds p ON oc.pond_id = p.pond_id
        """, fetch=True)
        df_costs = df_costs if df_costs is not None else pd.DataFrame()

        # 修复：使用 len() 而不是 empty 属性来判断 DataFrame
        if df_stock is None or len(df_stock) == 0:
            st.info("暂无进货数据，无法进行分析。请先录入养殖池和进货记录。")
        else:
            # --- 1. 处理进货数据 ---
            df_stock = df_stock.copy()
            df_stock['total_weight_kg'] = pd.to_numeric(df_stock['total_weight_kg'], errors='coerce')
            df_stock['purchase_price_per_kg'] = pd.to_numeric(df_stock['purchase_price_per_kg'], errors='coerce')
            df_stock['purchase_cost'] = (df_stock['total_weight_kg'] * df_stock['purchase_price_per_kg']).fillna(0)

            summary = df_stock.groupby('pond_name').agg(
                total_stock_weight=('total_weight_kg', 'sum'),
                total_stock_count=('fish_count', 'sum'),
                total_purchase_cost=('purchase_cost', 'sum')
            ).reset_index()

            # --- 2. 合并销售数据 ---
            if df_sales is not None and len(df_sales) > 0:  # 修复：使用 len() 而不是 empty
                df_sales = df_sales.copy()
                df_sales['weight_sold_kg'] = pd.to_numeric(df_sales['weight_sold_kg'], errors='coerce')
                df_sales['price_per_kg'] = pd.to_numeric(df_sales['price_per_kg'], errors='coerce')
                df_sales['revenue'] = (df_sales['weight_sold_kg'] * df_sales['price_per_kg']).fillna(0)
                sales_summary = df_sales.groupby('pond_name').agg(
                    total_sales_weight=('weight_sold_kg', 'sum'),
                    total_revenue=('revenue', 'sum')
                ).reset_index()
                summary = summary.merge(sales_summary, on='pond_name', how='left')
            else:
                summary['total_sales_weight'] = 0.0
                summary['total_revenue'] = 0.0

            # --- 3. 合并死亡数据 ---
            if df_mort is not None and len(df_mort) > 0:  # 修复：使用 len() 而不是 empty
                df_mort = df_mort.copy()
                df_mort['dead_fish'] = pd.to_numeric(df_mort['dead_fish'], errors='coerce')
                df_mort['dead_weight'] = pd.to_numeric(df_mort['dead_weight'], errors='coerce')
                mort_summary = df_mort.groupby('pond_name').agg(
                    total_dead_fish=('dead_fish', 'sum'),
                    total_dead_weight=('dead_weight', 'sum')
                ).reset_index()
                summary = summary.merge(mort_summary, on='pond_name', how='left')
            else:
                summary['total_dead_fish'] = 0.0
                summary['total_dead_weight'] = 0.0

            # --- 4. 合并经营成本 ---
            if df_costs is not None and len(df_costs) > 0:  # 修复：使用 len() 而不是 empty
                df_costs = df_costs.copy()
                df_costs['amount'] = pd.to_numeric(df_costs['amount'], errors='coerce')
                cost_summary = df_costs.groupby('pond_name')['amount'].sum().reset_index(name='total_operating_cost')
                summary = summary.merge(cost_summary, on='pond_name', how='left')
            else:
                summary['total_operating_cost'] = 0.0

            # --- 5. 填充缺失值为 0 ---
            numeric_cols = [
                'total_stock_weight', 'total_stock_count', 'total_purchase_cost',
                'total_sales_weight', 'total_revenue',
                'total_dead_fish', 'total_dead_weight',
                'total_operating_cost'
            ]
            for col in numeric_cols:
                if col in summary.columns:
                    summary[col] = pd.to_numeric(summary[col], errors='coerce').fillna(0).astype(float)
                else:
                    summary[col] = 0.0

            # --- 6. 计算衍生指标 ---
            summary['total_cost'] = summary['total_purchase_cost'] + summary['total_operating_cost']
            summary['profit'] = summary['total_revenue'] - summary['total_cost']
            summary['remaining_weight'] = (
                summary['total_stock_weight'] 
                - summary['total_sales_weight'] 
                - summary['total_dead_weight']
            )
            summary['survival_rate'] = (
                (summary['total_stock_count'] - summary['total_dead_fish']) 
                / summary['total_stock_count'].replace(0, 1) * 100
            )

            # --- 7. 显示汇总表（中文列名）---
            summary_display = summary.rename(columns={
                'pond_name': '养殖池',
                'total_stock_weight': '总进货重量(公斤)',
                'total_stock_count': '总进货条数',
                'total_purchase_cost': '总采购成本(元)',
                'total_sales_weight': '总销售重量(公斤)',
                'total_revenue': '总收入(元)',
                'total_dead_fish': '总死亡条数',
                'total_dead_weight': '总死亡重量(公斤)',
                'total_operating_cost': '总运营成本(元)',
                'total_cost': '总成本(元)',
                'profit': '利润(元)',
                'remaining_weight': '剩余重量(公斤)',
                'survival_rate': '存活率(%)'
            })
            st.subheader("各养殖池经营汇总")
            st.dataframe(summary_display, use_container_width=True)

            # --- 8. 可视化：利润对比 ---
            if len(summary) > 0:  # 确保有数据再绘图
                fig1 = px.bar(
                    summary, 
                    x='pond_name', 
                    y='profit', 
                    title="各养殖池利润对比（元）",
                    color='profit',
                    color_continuous_scale='RdYlGn',
                    labels={'pond_name': '养殖池', 'profit': '利润(元)'}
                )
                st.plotly_chart(fig1, use_container_width=True)

            # --- 9. 成本构成 ---
            if df_costs is not None and len(df_costs) > 0:  # 修复：使用 len() 而不是 empty
                type_map_rev = {"electricity": "电费", "water": "水费", "labor": "人工", "feed": "饲料", "medicine": "药品", "other": "其他"}
                df_costs['cost_type'] = df_costs['cost_type'].map(type_map_rev).fillna(df_costs['cost_type'])
                cost_by_type = df_costs.groupby('cost_type')['amount'].sum().reset_index()
                if len(cost_by_type) > 0:
                    fig2 = px.pie(
                        cost_by_type, 
                        values='amount', 
                        names='cost_type', 
                        title="总成本构成",
                        labels={'cost_type': '成本类型', 'amount': '金额(元)'}
                    )
                    st.plotly_chart(fig2, use_container_width=True)

            # --- 10. 销售平均单重 ---
            if df_sales is not None and len(df_sales) > 0 and 'fish_sold_count' in df_sales.columns:  # 修复：使用 len() 而不是 empty
                df_sales = df_sales.dropna(subset=['fish_sold_count'])
                df_sales['fish_sold_count'] = pd.to_numeric(df_sales['fish_sold_count'], errors='coerce')
                df_sales = df_sales[df_sales['fish_sold_count'] > 0]
                if len(df_sales) > 0:
                    df_sales['avg_weight_sold'] = df_sales['weight_sold_kg'] / df_sales['fish_sold_count']
                    avg_weight_by_pond = df_sales.groupby('pond_name')['avg_weight_sold'].mean().reset_index()
                    if len(avg_weight_by_pond) > 0:
                        fig_weight = px.bar(
                            avg_weight_by_pond, 
                            x='pond_name', 
                            y='avg_weight_sold',
                            title="各池塘销售时平均单条重量（公斤）", 
                            labels={'pond_name': '养殖池', 'avg_weight_sold': '平均单条重量(公斤)'}
                        )
                        st.plotly_chart(fig_weight, use_container_width=True)

            # --- 11. 存活率 ---
            if len(summary) > 0:  # 确保有数据再绘图
                fig4 = px.bar(
                    summary, 
                    x='pond_name', 
                    y='survival_rate', 
                    title="各池塘存活率（%）",
                    range_y=[0, 100], 
                    color='survival_rate', 
                    color_continuous_scale='Blues',
                    labels={'pond_name': '养殖池', 'survival_rate': '存活率(%)'}
                )
                st.plotly_chart(fig4, use_container_width=True)

# ----------------------------- 启动入口 -----------------------------
if __name__ == "__main__":
    run()