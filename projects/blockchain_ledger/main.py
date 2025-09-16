# projects/blockchain_ledger/main.py
import streamlit as st
import psycopg2
from psycopg2.extras import RealDictCursor, Json  # 👈 修复关键：导入 Json
from urllib.parse import urlparse
import os
from datetime import datetime, timedelta
import pandas as pd  # 👈 新增
import plotly.express as px  # 👈 新增
from dotenv import load_dotenv

# -----------------------------
# 加载环境变量
# -----------------------------
load_dotenv()

DATABASE_LEDGER_URL = os.getenv("DATABASE_LEDGER_URL")
if not DATABASE_LEDGER_URL:
    st.error("❌ DATABASE_LEDGER_URL 未设置，请检查 .env 文件。")
    st.stop()

# -----------------------------
# 数据库连接函数
# -----------------------------
def get_ledger_db_connection():
    try:
        url = urlparse(DATABASE_LEDGER_URL)
        conn = psycopg2.connect(
            host=url.hostname,
            port=url.port or 5432,
            database=url.path[1:],
            user=url.username,
            password=url.password,
        )
        return conn
    except Exception as e:
        st.error(f"🔗 数据库连接失败: {e}")
        return None


# -----------------------------
# 初始化数据库
# -----------------------------
def init_db():
    conn = get_ledger_db_connection()
    if not conn:
        return

    try:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id SERIAL PRIMARY KEY,
                    username VARCHAR(50) UNIQUE NOT NULL,
                    role VARCHAR(20) NOT NULL CHECK (role IN ('cashier', 'approver')),
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)

            cur.execute("SELECT id FROM users WHERE username = 'cashier'")
            if not cur.fetchone():
                cur.execute("INSERT INTO users (username, role) VALUES ('cashier', 'cashier')")
            cur.execute("SELECT id FROM users WHERE username = 'boss'")
            if not cur.fetchone():
                cur.execute("INSERT INTO users (username, role) VALUES ('boss', 'approver')")

            cur.execute("""
                CREATE TABLE IF NOT EXISTS transactions (
                    id SERIAL PRIMARY KEY,
                    description TEXT NOT NULL,
                    source TEXT NOT NULL,
                    amount DECIMAL(12, 2) NOT NULL,
                    category VARCHAR(50),
                    trans_type VARCHAR(10) NOT NULL CHECK (trans_type IN ('income', 'expense')),
                    need_approval BOOLEAN DEFAULT FALSE,
                    approved BOOLEAN DEFAULT FALSE,
                    approved_by INTEGER REFERENCES users(id) ON DELETE SET NULL,
                    cashier_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    approved_at TIMESTAMP
                );
            """)

            try:
                cur.execute("ALTER TABLE transactions ADD COLUMN IF NOT EXISTS source TEXT NOT NULL DEFAULT '未指定来源'")
            except:
                pass

            cur.execute("""
                CREATE TABLE IF NOT EXISTS audit_log (
                    id SERIAL PRIMARY KEY,
                    action VARCHAR(50) NOT NULL,
                    user_id INTEGER REFERENCES users(id),
                    transaction_id INTEGER REFERENCES transactions(id) ON DELETE CASCADE,
                    details JSONB,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)

            conn.commit()
            st.success("✅ 数据库初始化完成")
    except Exception as e:
        st.error(f"❌ 初始化数据库失败: {e}")
    finally:
        if conn:
            conn.close()


# -----------------------------
# 获取用户ID
# -----------------------------
def get_user_id_by_role(role: str) -> int:
    conn = get_ledger_db_connection()
    if not conn:
        return -1
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id FROM users WHERE username = %s", ("cashier" if role == "cashier" else "boss",))
            row = cur.fetchone()
            return row[0] if row else -1
    except Exception as e:
        st.error(f"❌ 获取用户ID失败: {e}")
        return -1
    finally:
        if conn:
            conn.close()


# -----------------------------
# 创建交易记录
# -----------------------------
def create_transaction(description, source, amount, category, trans_type, cashier_id):
    conn = get_ledger_db_connection()
    if not conn:
        return None

    need_approval = abs(amount) >= 100000

    try:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO transactions (description, source, amount, category, trans_type, need_approval, cashier_id)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                RETURNING id
            """, (description, source, amount, category, trans_type, need_approval, cashier_id))
            trans_id = cur.fetchone()[0]

            # ✅ 修复：用 Json 包装字典
            cur.execute("""
                INSERT INTO audit_log (action, user_id, transaction_id, details)
                VALUES (%s, %s, %s, %s)
            """, ('create', cashier_id, trans_id, Json({
                'description': description,
                'source': source,
                'amount': float(amount),
                'category': category,
                'trans_type': trans_type,
                'need_approval': need_approval
            })))
            conn.commit()
            return trans_id
    except Exception as e:
        st.error(f"❌ 创建交易失败: {e}")
        return None
    finally:
        if conn:
            conn.close()


# -----------------------------
# 获取待审批交易
# -----------------------------
def get_pending_transactions():
    conn = get_ledger_db_connection()
    if not conn:
        return []
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT t.*, u.username as cashier_name
                FROM transactions t
                JOIN users u ON t.cashier_id = u.id
                WHERE t.need_approval = TRUE AND t.approved = FALSE
                ORDER BY t.created_at DESC
            """)
            return cur.fetchall()
    except Exception as e:
        st.error(f"❌ 获取待审批交易失败: {e}")
        return []
    finally:
        if conn:
            conn.close()


# -----------------------------
# 审批交易
# -----------------------------
def approve_transaction(trans_id, approver_id):
    conn = get_ledger_db_connection()
    if not conn:
        return False
    try:
        with conn.cursor() as cur:
            cur.execute("""
                UPDATE transactions
                SET approved = TRUE, approved_by = %s, approved_at = NOW()
                WHERE id = %s AND need_approval = TRUE AND approved = FALSE
                RETURNING id
            """, (approver_id, trans_id))
            if cur.fetchone():
                # ✅ 修复：用 Json 包装字典
                cur.execute("""
                    INSERT INTO audit_log (action, user_id, transaction_id, details)
                    VALUES (%s, %s, %s, %s)
                """, ('approve', approver_id, trans_id, Json({
                    'approved_at': str(datetime.now())
                })))
                conn.commit()
                return True
            else:
                st.warning("⚠️ 该记录已被审批或不存在。")
                return False
    except Exception as e:
        st.error(f"❌ 审批失败: {e}")
        return False
    finally:
        if conn:
            conn.close()


# -----------------------------
# 获取所有交易（按角色）
# -----------------------------
def get_all_transactions(user_role, user_id):
    conn = get_ledger_db_connection()
    if not conn:
        return []
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            if user_role == "approver":
                cur.execute("""
                    SELECT t.*, u.username as cashier_name, a.username as approver_name
                    FROM transactions t
                    JOIN users u ON t.cashier_id = u.id
                    LEFT JOIN users a ON t.approved_by = a.id
                    ORDER BY t.created_at DESC
                """)
            else:
                cur.execute("""
                    SELECT t.*, u.username as cashier_name, a.username as approver_name
                    FROM transactions t
                    JOIN users u ON t.cashier_id = u.id
                    LEFT JOIN users a ON t.approved_by = a.id
                    WHERE t.cashier_id = %s
                    ORDER BY t.created_at DESC
                """, (user_id,))
            return cur.fetchall()
    except Exception as e:
        st.error(f"❌ 获取交易记录失败: {e}")
        return []
    finally:
        if conn:
            conn.close()


# -----------------------------
# 🆕 获取时间段内交易数据（用于图表）
# -----------------------------
def get_filtered_transactions_for_charts(start_date, end_date):
    conn = get_ledger_db_connection()
    if not conn:
        return []
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT 
                    DATE(created_at) as date,
                    category,
                    trans_type,
                    SUM(amount) as daily_total
                FROM transactions
                WHERE created_at >= %s AND created_at <= %s
                GROUP BY DATE(created_at), category, trans_type
                ORDER BY date
            """, (start_date, end_date))
            return cur.fetchall()
    except Exception as e:
        st.error(f"❌ 获取图表数据失败: {e}")
        return []
    finally:
        if conn:
            conn.close()


# -----------------------------
# 🆕 领导专属图表面板
# -----------------------------
def _show_approver_charts(approver_id):
    st.header("📊 财务可视化分析")

    # 时间范围选择
    col1, col2 = st.columns(2)
    with col1:
        start_date = st.date_input("开始日期", value=datetime.now() - timedelta(days=30))
    with col2:
        end_date = st.date_input("结束日期", value=datetime.now())

    if start_date > end_date:
        st.error("❌ 开始日期不能晚于结束日期")
        return

    # 获取数据
    rows = get_filtered_transactions_for_charts(start_date, end_date + timedelta(days=1))  # 包含结束日
    if not rows:
        st.info("📈 所选时间段内无数据")
        return

    # 转为 DataFrame
    df = pd.DataFrame(rows)

    # 按日汇总收入/支出
    df_income = df[df['trans_type'] == 'income'].groupby('date')['daily_total'].sum().reset_index()
    df_expense = df[df['trans_type'] == 'expense'].groupby('date')['daily_total'].sum().reset_index()
    df_income.rename(columns={'daily_total': 'income'}, inplace=True)
    df_expense.rename(columns={'daily_total': 'expense'}, inplace=True)

    # 合并 + 计算余额
    df_daily = df_income.merge(df_expense, on='date', how='outer').fillna(0)
    df_daily['expense'] = -df_daily['expense']  # 支出显示为负
    df_daily['balance'] = (df_daily['income'] + df_daily['expense']).cumsum()  # 累计余额

    # ===== 折线图：收支趋势 + 余额 =====
    st.subheader("📈 收支趋势与余额变化")
    fig_line = px.line(
        df_daily.melt(id_vars='date', value_vars=['income', 'expense', 'balance'],
                      var_name='类型', value_name='金额'),
        x='date',
        y='金额',
        color='类型',
        markers=True,
        title="每日收支与累计余额",
        labels={'date': '日期', '金额': '金额（元）'},
        height=500,
        color_discrete_map={
            'income': '#28a745',   # 绿色收入
            'expense': '#dc3545', # 红色支出
            'balance': '#007bff'  # 蓝色余额
        }
    )
    fig_line.update_traces(line=dict(width=3))
    st.plotly_chart(fig_line, use_container_width=True)

    # ===== 饼图：支出分类 =====
    expense_data = df[df['trans_type'] == 'expense']
    if not expense_data.empty:
        st.subheader("📉 支出分类占比")
        expense_by_cat = expense_data.groupby('category')['daily_total'].sum().abs().reset_index()
        expense_by_cat = expense_by_cat.sort_values('daily_total', ascending=False)
        fig_pie_expense = px.pie(
            expense_by_cat,
            names='category',
            values='daily_total',
            title='支出分类占比',
            hole=0.4,
            height=400
        )
        st.plotly_chart(fig_pie_expense, use_container_width=True)

    # ===== 饼图：收入分类（可选）=====
    income_data = df[df['trans_type'] == 'income']
    if not income_data.empty:
        st.subheader("💹 收入来源占比")
        income_by_source = income_data.groupby('category')['daily_total'].sum().reset_index()
        income_by_source = income_by_source.sort_values('daily_total', ascending=False)
        fig_pie_income = px.pie(
            income_by_source,
            names='category',
            values='daily_total',
            title='收入分类占比',
            hole=0.4,
            height=400
        )
        st.plotly_chart(fig_pie_income, use_container_width=True)


# -----------------------------
# Streamlit 主函数
# -----------------------------
def run():
    st.set_page_config(page_title="🏗️ 建筑单位现金账目系统", layout="wide")
    init_db()

    if "ledger_role" not in st.session_state:
        _show_role_selector()
    else:
        _show_main_app()


def _show_role_selector():
    st.title("🏗️ 建筑单位现金账目系统")
    st.markdown("请选择您的角色进入系统 👇")

    col1, col2 = st.columns(2)
    with col1:
        if st.button("📒 出纳", use_container_width=True, type="primary"):
            st.session_state.ledger_role = "cashier"
            st.session_state.user_id = get_user_id_by_role("cashier")
            st.rerun()
    with col2:
        if st.button("👔 领导", use_container_width=True, type="primary"):
            st.session_state.ledger_role = "approver"
            st.session_state.user_id = get_user_id_by_role("approver")
            st.rerun()

    st.markdown("---")
    st.info("💡 出纳：录入收支记录，大额自动提交审批\n💡 领导：审批大额支出，查看全部账目 + 可视化分析")


def _show_main_app():
    role = st.session_state.ledger_role
    user_id = st.session_state.user_id

    # 主界面顶部：标题 + 切换角色按钮
    col_title, col_switch = st.columns([4, 1])
    with col_title:
        st.title(f"🏗️ 建筑单位现金账目系统 - {'出纳' if role == 'cashier' else '领导'}")
    with col_switch:
        st.write("")  # 微调垂直对齐
        st.write("")
        if st.button("🔄 切换角色", use_container_width=True, type="secondary"):
            for key in ["ledger_role", "user_id"]:
                st.session_state.pop(key, None)
            st.rerun()

    st.markdown("---")

    if role == "cashier":
        _show_cashier_ui(user_id)
    else:
        _show_approver_ui(user_id)
        st.markdown("---")
        _show_approver_charts(user_id)

    st.markdown("---")
    _show_transaction_list(role, user_id)


def _show_cashier_ui(cashier_id):
    st.header("📝 录入新交易")

    with st.form("new_transaction"):
        col1, col2 = st.columns(2)
        with col1:
            source = st.text_input("💰 资金来源*", placeholder="如：甲方拨款、银行贷款、项目回款等")
        with col2:
            description = st.text_input("📌 用途描述*", placeholder="如：购买钢筋、支付工资等")

        col3, col4, col5 = st.columns(3)
        with col3:
            trans_type = st.selectbox("📊 类型", ["income", "expense"], format_func=lambda x: "收入" if x == "income" else "支出")
        with col4:
            amount = st.number_input("💵 金额*", min_value=0.01, step=0.01, format="%.2f")
            if trans_type == "expense":
                amount = -amount
        with col5:
            category = st.text_input("🏷️ 分类", placeholder="如：材料、工资、差旅")

        submitted = st.form_submit_button("💾 保存交易", type="primary")

        if submitted:
            if not source.strip():
                st.error("请填写资金来源")
            elif not description.strip():
                st.error("请填写用途描述")
            else:
                trans_id = create_transaction(description, source, amount, category, trans_type, cashier_id)
                if trans_id:
                    need_approval = abs(amount) >= 100000
                    if need_approval:
                        st.warning(f"⚠️ 金额 ¥{abs(amount):,.2f} ≥ 10万元，已自动提交领导审批！")
                    else:
                        st.success("✅ 交易已保存！")
                    st.balloons()


def _show_approver_ui(approver_id):
    st.header("📬 待审批交易（≥10万元）")
    pending = get_pending_transactions()
    if not pending:
        st.info("🎉 暂无待审批交易")
    else:
        for trans in pending:
            with st.expander(f"ID {trans['id']}: {trans['description']} ({'收入' if trans['amount'] > 0 else '支出'} ¥{abs(trans['amount']):,.2f})"):
                st.write(f"**资金来源**: {trans['source']}")
                st.write(f"**用途**: {trans['description']}")
                st.write(f"**分类**: {trans['category'] or '—'}")
                st.write(f"**出纳**: {trans['cashier_name']}")
                st.write(f"**时间**: {trans['created_at']}")
                if st.button(f"✅ 批准此笔 (ID: {trans['id']})", key=f"approve_{trans['id']}", type="primary"):
                    if approve_transaction(trans['id'], approver_id):
                        st.success("✅ 已批准！")
                        st.rerun()


def _show_transaction_list(user_role, user_id):
    st.header("📋 所有交易记录")
    transactions = get_all_transactions(user_role, user_id)
    if not transactions:
        st.info("暂无交易记录")
        return

    total_income = sum(t['amount'] for t in transactions if t['amount'] > 0)
    total_expense = abs(sum(t['amount'] for t in transactions if t['amount'] < 0))
    balance = total_income - total_expense

    col1, col2, col3 = st.columns(3)
    col1.metric("💰 总收入", f"¥{total_income:,.2f}")
    col2.metric("💸 总支出", f"¥{total_expense:,.2f}")
    col3.metric("📊 当前结余", f"¥{balance:,.2f}")

    display_data = []
    for t in transactions:
        display_data.append({
            "ID": t["id"],
            "时间": t["created_at"].strftime("%Y-%m-%d %H:%M"),
            "资金来源": t["source"],
            "用途": t["description"],
            "分类": t["category"] or "—",
            "类型": "收入" if t["amount"] > 0 else "支出",
            "金额": f"¥{abs(t['amount']):,.2f}",
            "状态": "🟢 已批" if t["approved"] else ("🟡 待批" if t["need_approval"] else "⚪ 无需审批"),
            "出纳": t["cashier_name"],
            "审批人": t["approver_name"] or "—"
        })

    st.dataframe(display_data, use_container_width=True, hide_index=True)


# -----------------------------
# 入口点
# -----------------------------
if __name__ == "__main__":
    run()