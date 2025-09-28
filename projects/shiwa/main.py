import streamlit as st
import os, psycopg2, pandas as pd, plotly.express as px, plotly.graph_objects as go
from datetime import datetime, timedelta, time
from dotenv import load_dotenv
import uuid
from sqlalchemy import create_engine
import json
# ----------------------------- 环境 & 引擎 ----------------------------- #
load_dotenv()
DATABASE_URL = os.getenv("DATABASE_SHIWA_URL")
if not DATABASE_URL:
    st.error("❌ 未设置数据库连接URL"); st.stop()
SQLALCHEMY_URL = DATABASE_URL.replace("postgres://", "postgresql://") if DATABASE_URL.startswith("postgres://") else DATABASE_URL
engine = create_engine(SQLALCHEMY_URL)
# ----------------------------- 连接上下文 ----------------------------- #
class DatabaseConnection:
    def __enter__(self):
        try:
            self.conn = psycopg2.connect(DATABASE_URL); return self.conn
        except Exception as e:
            st.error(f"🔗 数据库连接失败: {e}"); return None
    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.conn: self.conn.close()
# ----------------------------- 缓存查询（保持不变）----------------------------- #
@st.cache_data(show_spinner=False)
def fetch_frog_types():
    with DatabaseConnection() as conn:
        if not conn: return []
        with conn.cursor() as cur:
            cur.execute("SELECT type_code, description FROM t_frog_type_dict WHERE is_active = true ORDER BY type_code")
            return cur.fetchall()
@st.cache_data(show_spinner=False)
def fetch_material_types():
    with DatabaseConnection() as conn:
        if not conn: return []
        with conn.cursor() as cur:
            cur.execute("SELECT type_code, name, unit FROM t_material_type_dict WHERE is_active = true ORDER BY name")
            return cur.fetchall()
@st.cache_data(show_spinner=False)
def fetch_incubation_pools(status=None):
    with DatabaseConnection() as conn:
        if not conn: return []
        with conn.cursor() as cur:
            if status:
                cur.execute("SELECT pool_no, location_info, current_status, current_batch_no FROM t_incubation_pool WHERE current_status = %s ORDER BY pool_no", (status,))
            else:
                cur.execute("SELECT pool_no, location_info, current_status, current_batch_no FROM t_incubation_pool ORDER BY pool_no")
            return cur.fetchall()
@st.cache_data(show_spinner=False)
def fetch_active_batches():
    with DatabaseConnection() as conn:
        if not conn: return []
        with conn.cursor() as cur:
            cur.execute("""SELECT batch_no, pool_no, input_type, input_time, initial_input, input_unit
                           FROM t_incubation_batch WHERE batch_status = '使用中' ORDER BY input_time DESC""")
            return cur.fetchall()
# ----------------------------- 分析数据缓存查询（保持不变）----------------------------- #
@st.cache_data(show_spinner=False)
def get_batch_conversion_data(start_date=None, end_date=None):
    try:
        sql = """
            SELECT batch_no, pool_no, input_type, initial_input, input_unit,
                   input_time::date AS input_date, total_sorted_frog, conversion_rate, batch_status
            FROM   v_batch_conversion
            WHERE  1=1
        """
        params = []
        if start_date:
            sql += " AND input_time >= %s"
            params.append(start_date)
        if end_date:
            sql += " AND input_time <= %s"
            params.append(end_date)
        sql += " ORDER BY input_time DESC"
        return pd.read_sql(sql, engine, params=tuple(params))
    except Exception as e:
        st.error(f"获取批次转化率数据失败: {e}")
        return pd.DataFrame()
@st.cache_data(show_spinner=False)
def get_material_consumption_data(start_date=None, end_date=None):
    try:
        sql = """
            SELECT b.related_entity_id material_type, m.name material_name, m.unit material_unit,
                   SUM(b.operation_value) total_consumption,
                   DATE_TRUNC('day', b.operation_time) operation_date
            FROM   t_business_behavior_record b
            JOIN   t_material_type_dict m ON b.related_entity_id = m.type_code
            WHERE  b.behavior_type = '喂食'
        """
        params = []
        if start_date:
            sql += " AND b.operation_time >= %s"
            params.append(start_date)
        if end_date:
            sql += " AND b.operation_time <= %s"
            params.append(end_date)
        sql += " GROUP BY material_type, material_name, material_unit, operation_date ORDER BY operation_date"
        return pd.read_sql(sql, engine, params=tuple(params))
    except Exception as e:
        st.error(f"获取物资消耗数据失败: {e}")
        return pd.DataFrame()
@st.cache_data(show_spinner=False)
def get_frog_inventory_data():
    try:
        sql = """SELECT i.frog_type_code, t.description frog_type, i.quantity, i.pool_area, i.last_update_time
                 FROM t_frog_inventory i
                 JOIN t_frog_type_dict t ON i.frog_type_code = t.type_code
                 ORDER BY t.parent_type, t.description, i.pool_area"""
        return pd.read_sql(sql, engine)
    except Exception as e:
        st.error(f"获取成蛙库存数据失败: {e}")
        return pd.DataFrame()
@st.cache_data(show_spinner=False)
def get_sales_data(start_date=None, end_date=None):
    try:
        sql = """
            SELECT b.related_entity_id frog_type_code, t.description frog_type,
                   SUM(b.operation_value) total_sold,
                   DATE_TRUNC('day', b.operation_time) sale_date,
                   b.remarks
            FROM   t_business_behavior_record b
            JOIN   t_frog_type_dict t ON b.related_entity_id = t.type_code
            WHERE  b.behavior_type = '销售成蛙'
        """
        params = []
        if start_date:
            sql += " AND b.operation_time >= %s"
            params.append(start_date)
        if end_date:
            sql += " AND b.operation_time <= %s"
            params.append(end_date)
        sql += " GROUP BY frog_type_code, frog_type, sale_date, b.remarks ORDER BY sale_date"
        return pd.read_sql(sql, engine, params=tuple(params))
    except Exception as e:
        st.error(f"获取销售数据失败: {e}")
        return pd.DataFrame()
@st.cache_data(ttl=10, show_spinner=False)
def get_pool_frog_inventory(pool_area: str):
    """
    查询指定池区中各蛙类型的库存数量
    返回: List[Tuple[type_code, description, quantity]]
    """
    with DatabaseConnection() as conn:
        if not conn:
            return []
        with conn.cursor() as cur:
            cur.execute("""
                SELECT i.frog_type_code, t.description, i.quantity
                FROM t_frog_inventory i
                JOIN t_frog_type_dict t ON i.frog_type_code = t.type_code
                WHERE i.pool_area = %s AND i.quantity > 0
                ORDER BY t.description
            """, (pool_area,))
            return cur.fetchall()
@st.cache_data(show_spinner=False)
def get_sorted_frog_total_by_source(source_cn: str):
    """
    source_cn: '自养卵' / '外购蝌蚪' / '外购幼蛙' / '外购成蛙'
    根据 batch_no 前缀统计已分拣总量
    """
    prefix_map = {
        "自养卵": "自养卵-%",
        "外购蝌蚪": "外购蝌蚪-%",
        "外购幼蛙": "外购幼蛙-%",
        "外购成蛙": "外购成蛙-%",
    }
    pattern = prefix_map.get(source_cn, "自养卵-%")

    with DatabaseConnection() as conn:
        if not conn:
            return 0
        with conn.cursor() as cur:
            cur.execute("""
                SELECT COALESCE(SUM(total_frog), 0)
                FROM t_batch_sorting_record
                WHERE batch_no LIKE %s
            """, (pattern,))
            return int(cur.fetchone()[0])
@st.cache_data(ttl=10, show_spinner=False)
def get_frog_pools(pool_type=None, skin_type=None, purpose=None):
    try:
        base_sql = """
        SELECT
            p.pool_code,
            p.pool_type,
            p.skin_type,
            p.max_capacity,
            p.remark,
            COALESCE(SUM(i.quantity), 0) as current_qty,
            (p.max_capacity - COALESCE(SUM(i.quantity), 0)) as free_space
        FROM t_frog_pool p
        LEFT JOIN t_frog_inventory i ON p.pool_code = i.pool_area
        WHERE 1=1
        """
        params = []
        if purpose == "sale":
            base_sql += """
            AND p.pool_type IN ('三年蛙','四年蛙','五年蛙','种蛙','试验蛙')
            """
        elif purpose == "year":
            base_sql += " AND p.pool_type IN ('三年蛙','四年蛙','五年蛙','种蛙','试验蛙') "
        else:
            if pool_type:
                base_sql += " AND p.pool_type = %s"
                params.append(pool_type)
            if skin_type:
                base_sql += " AND p.skin_type = %s"
                params.append(skin_type)
        base_sql += " GROUP BY p.pool_code, p.pool_type, p.skin_type, p.max_capacity, p.remark ORDER BY p.pool_code"
        
        # 👇 关键修复：只有有参数时才传 params
        if params:
            df = pd.read_sql(base_sql, engine, params=tuple(params))
        else:
            df = pd.read_sql(base_sql, engine)
            
        if not df.empty:
            df = df.rename(columns={
                'pool_code': '池编号',
                'pool_type': '来源/年限',
                'skin_type': '皮型',
                'max_capacity': '最大容量',
                'current_qty': '当前数量',
                'free_space': '剩余空间',
                'remark': '备注'
            })
        return df
    except Exception as e:
        st.error(f"查询成蛙池失败: {e}")
        return pd.DataFrame(columns=['池编号', '来源/年限', '皮型', '最大容量', '当前数量', '剩余空间'])

@st.cache_data(show_spinner=False)
def get_sales_statistics(start_date=None, end_date=None, group_by="day"):
    """
    获取销售统计信息
    group_by: 'day'按天, 'month'按月, 'source'按来源, 'type'按蛙类型
    """
    try:
        sql = """
            SELECT 
                b.related_entity_id frog_type_code,
                t.description frog_type,
                SUM(b.operation_value) total_sold,
                DATE_TRUNC(%s, b.operation_time) as period,
                b.remarks,
                b.operation_time
            FROM t_business_behavior_record b
            JOIN t_frog_type_dict t ON b.related_entity_id = t.type_code
            WHERE b.behavior_type = '销售成蛙'
        """
        params = [group_by]
        
        if start_date:
            sql += " AND b.operation_time >= %s"
            params.append(start_date)
        if end_date:
            sql += " AND b.operation_time <= %s"
            params.append(end_date)
            
        sql += " GROUP BY frog_type_code, frog_type, period, b.remarks, b.operation_time"
        sql += " ORDER BY period DESC, total_sold DESC"
        
        df = pd.read_sql(sql, engine, params=tuple(params))
        
        # 提取来源池区信息
        def extract_source_pool(remark):
            if pd.isna(remark) or not isinstance(remark, str):
                return '未知'
            if '从' in remark and '销售' in remark:
                # 格式: "从 自养卵细皮商品蛙池-001 销售"
                parts = remark.split(' ')
                return parts[1] if len(parts) > 1 else '未知'
            return '未知'
        
        if not df.empty:
            df['来源池区'] = df['remarks'].apply(extract_source_pool)
            df['销售日期'] = df['operation_time'].dt.date
            df['销售时间'] = df['operation_time'].dt.time
            
        return df
        
    except Exception as e:
        st.error(f"获取销售统计数据失败: {e}")
        return pd.DataFrame()
@st.cache_data(ttl=30, show_spinner=False)
def get_pool_source_and_skin(pool_code: str):
    """
    通过查询最近一次「成蛙再分类」行为，反推该年限池的来源和皮型
    适用于：三年蛙池-001, 四年蛙池-001 等
    返回: (source, skin) 例如 ("自养卵", "细皮")
    """
    with DatabaseConnection() as conn:
        if not conn:
            return "未知", "未知"
        with conn.cursor() as cur:
            # 查询最近一次向该池的再分类记录（通过 remarks 中的来源池）
            cur.execute("""
                SELECT remarks
                FROM t_business_behavior_record
                WHERE behavior_type = '成蛙再分类'
                  AND remarks LIKE %s
                ORDER BY operation_time DESC
                LIMIT 1
            """, (f'%{pool_code}%',))
            row = cur.fetchone()
            if not row:
                return "未知", "未知"
            remarks = row[0]
            # 格式: "从 自养卵细皮成蛙池-001 拆分 15 只"
            if remarks.startswith("从 ") and " 拆分 " in remarks:
                source_pool = remarks.split(" ")[1]
                if "自养卵" in source_pool:
                    source = "自养卵"
                    skin = "细皮" if "细皮" in source_pool else "粗皮"
                elif "外购蝌蚪" in source_pool:
                    source = "外购蝌蚪"
                    skin = "细皮" if "细皮" in source_pool else "粗皮"
                elif "外购幼蛙" in source_pool:
                    source = "外购幼蛙"
                    skin = "细皮" if "细皮" in source_pool else "粗皮"
                elif "外购成蛙" in source_pool:
                    source = "外购成蛙"
                    skin = "细皮" if "细皮" in source_pool else "粗皮"
                else:
                    source, skin = "未知", "未知"
                return source, skin
            return "未知", "未知"
# ----------------------------- 多媒体溯源：本地存储（调试版） ----------------------------- #
import os, stat
from pathlib import Path
import streamlit as st

# 1. 统一路径：保证读写都基于 MEDIA_ROOT 绝对路径
SCRIPT_DIR = Path(__file__).parent.resolve()
MEDIA_ROOT = SCRIPT_DIR / "media"
MEDIA_ROOT.mkdir(exist_ok=True)
# 2. 保证目录可写（Linux/Docker 场景）
try:
    os.chmod(MEDIA_ROOT, stat.S_IRWXU | stat.S_IRWXG | stat.S_IRWXO)
except Exception as e:
    st.warning(f"[DEBUG] 修改 media 目录权限失败：{e}")

def save_uploaded_media(uploaded_files, record_id: str, record_type: str,
                        pool_no: str = None, batch_no: str = None,
                        source_override: str = None) -> list:
    """
    保存上传的多媒体文件到本地，返回相对 MEDIA_ROOT 的路径列表
    文件名采用中文可读模板，无空格、无特殊符号
    """
    if not uploaded_files:
        return []

    # 业务环节中文映射
    stage_ch = {
        "batch_input": "批次投入",
        "sorting": "分拣",
        "reclass": "再分类",
        "sale": "销售",
        "feeding": "喂食",
        "purchase": "采购",
        "batch_complete": "批次完成",
        "direct_input": "外购入库"
    }
    # 来源中文映射（仅作 fallback）
    source_ch = {
        "batch_input": "自养卵",
        "sorting": "外购蝌蚪",
        "reclass": "自养卵",
        "sale": "外购幼蛙",
        "feeding": "自养卵",
        "purchase": "通用",
        "batch_complete": "自养卵",
        "direct_input": "外购幼蛙"
    }

    stage = stage_ch.get(record_type, "其他")
    # 👇 关键：优先使用传入的 source_override（如“外购蝌蚪”），否则用默认映射
    source = source_override if source_override is not None else source_ch.get(record_type, "通用")

    # 主对象：优先池号，其次批次号，否则用 record_id 前 8 位
    main_obj = (pool_no or batch_no or record_id[:8]).replace("-", "_")

    date_str = datetime.now().strftime("%Y%m%d")
    time_str = datetime.now().strftime("%H%M")

    # 构建保存目录
    save_dir = MEDIA_ROOT / record_type / str(record_id)
    save_dir.mkdir(parents=True, exist_ok=True)
    os.chmod(save_dir, stat.S_IRWXU | stat.S_IRWXG | stat.S_IRWXO)

    saved_paths = []
    for i, file in enumerate(uploaded_files):
        ext = file.name.split('.')[-1].lower()
        # 中文文件名：环节_来源_池对象_批次片段_日期_时间_序号
        safe_name = f"{stage}_来源{source}_池{main_obj}_批次{record_id[:8]}_日期{date_str}_时间{time_str}_序号{i:02d}.{ext}"
        file_path = save_dir / safe_name
        with open(file_path, "wb") as f:
            f.write(file.getbuffer())
        saved_paths.append(str(file_path.relative_to(MEDIA_ROOT)))

    return saved_paths

def render_media_traceability():
    from pathlib import Path
    from datetime import datetime, timedelta
    import re
    st.header("🔍 多媒体溯源")
    st.markdown("按批次、操作类型或日期查询现场图片/视频")

    col1, col2 = st.columns(2)
    with col1:
        record_type = st.selectbox("操作类型", [
            "全部", "批次投入", "分批分拣", "成蛙再分类", "销售成蛙", "喂食", "采购物资"
        ])
    with col2:
        date_range = st.date_input("日期范围", [datetime.now() - timedelta(days=7), datetime.now()])

    # 映射中文到英文目录名
    type_map = {
        "全部": None,
        "批次投入": "batch_input",
        "分批分拣": "sorting",
        "成蛙再分类": "reclass",
        "销售成蛙": "sale",
        "喂食": "feeding",
        "采购物资": "purchase",
        "外购幼蛙入库": "direct_input",
        "批次完成": "batch_complete"
    }
    target_dir = type_map.get(record_type)

    base_path = MEDIA_ROOT
    media_files = []

    if base_path.exists():
        for record_type_dir in base_path.iterdir():
            if not record_type_dir.is_dir():
                continue
            if target_dir and record_type_dir.name != target_dir:
                continue
            for record_id_dir in record_type_dir.iterdir():
                if not record_id_dir.is_dir():
                    continue
                for file in record_id_dir.iterdir():
                    if file.is_file():
                        mtime = datetime.fromtimestamp(file.stat().st_mtime)
                        if date_range[0] <= mtime.date() <= date_range[1]:
                            media_files.append(file)

    if not media_files:
        st.info("未找到多媒体文件")
        return

    # 按修改时间倒序
    media_files.sort(key=lambda f: f.stat().st_mtime, reverse=True)

    # 解析文件元信息
    parsed_files = []
    for fp in media_files:
        filename = fp.name
        info = {
            "path": fp,
            "filename": filename,
            "suffix": fp.suffix.lower(),
            "mtime": datetime.fromtimestamp(fp.stat().st_mtime),
            "desc": f"📁 {filename}",
            "pool_no": "未知",
            "stage": "未知",
            "source": "未知",
            "time_str": "未知时间"
        }
        try:
            match = re.search(
                r'(.+)_来源(.+)_池([^_]+)_批次[^_]*_日期(\d{8})_时间(\d{4})',
                filename
            )
            if match:
                stage, source, pool_raw, date_str, time_str = match.groups()
                pool_no = pool_raw.replace('_', '-')
                try:
                    dt = datetime.strptime(date_str + time_str, "%Y%m%d%H%M")
                    time_formatted = dt.strftime("%Y年%m月%d日 %H:%M")
                except:
                    time_formatted = f"{date_str[:4]}年{date_str[4:6]}月{date_str[6:8]}日 {time_str[:2]}:{time_str[2:4]}"
                info.update({
                    "stage": stage,
                    "source": source,
                    "pool_no": pool_no,
                    "time_str": time_formatted,
                    "desc": f"📸 {time_formatted} 在 **{pool_no}** 池进行 **{stage}（来源：{source}）**"
                })
        except Exception:
            pass
        parsed_files.append(info)

    # ===== 新增：缩略图网格展示 =====
    st.subheader("📸 多媒体缩略图")
    cols = st.columns(4)  # 每行4个缩略图
    for idx, item in enumerate(parsed_files):
        col = cols[idx % 4]
        suffix = item["suffix"]
        with col:
            # 缩略图点击事件：通过按钮设置 session_state
            if suffix in ['.jpg', '.jpeg', '.png']:
                try:
                    col.image(str(item["path"]), use_container_width=True)
                except:
                    col.write("🖼️ 图片加载失败")
            elif suffix in ['.mp4', '.mov']:
                thumb_path = MEDIA_ROOT / "video_thumb.png"
                if thumb_path.exists():
                    col.image(str(thumb_path), use_container_width=True)
                else:
                    col.image("https://via.placeholder.com/160x120/333333/FFFFFF?text=  ▶+视频", use_container_width=True)
            else:
                col.image("https://via.placeholder.com/150?text=  📄+文件", use_container_width=True)

            # 小字描述（可选）
            col.caption(f"{item['pool_no']} | {item['stage']}")
            
            # 点击按钮触发预览
            if col.button("🔍 查看", key=f"btn_{idx}", use_container_width=True):
                st.session_state["preview_media"] = item

    st.divider()

    # ===== 预览区 =====
    if "preview_media" in st.session_state:
        item = st.session_state["preview_media"]
        st.subheader("📌 文件详情")
        st.markdown(item["desc"])
        try:
            if item["suffix"] in ['.jpg', '.jpeg', '.png']:
                st.image(str(item["path"]), width=600)
            elif item["suffix"] in ['.mp4', '.mov']:
                st.video(str(item["path"]))
            with open(item["path"], "rb") as f:
                st.download_button("⬇️ 下载原文件", data=f, file_name=item["filename"])
        except Exception as e:
            st.error(f"加载文件失败：{e}")
# ----------------------------- 业务操作函数（已支持 media_files） ----------------------------- #
def create_batch(pool_no, input_type, initial_input, input_unit, input_time, operator, media_files=None):
    try:
        with DatabaseConnection() as conn:
            if not conn:
                return False, "数据库连接失败"
            with conn.cursor() as cur:
                timestamp = input_time.strftime('%Y%m%d_%H%M%S')
                # 中文来源映射
                source_cn = {
                    "自养卵": "自养卵",
                    "外购蝌蚪": "外购蝌蚪",
                    "外购幼蛙": "外购幼蛙",
                    "外购成蛙": "外购成蛙",
                }.get(input_type, "其他")

                # 新批号：来源-月日-时分-池号
                mmdd = input_time.strftime("%m%d")
                hhmm = input_time.strftime("%H%M")
                batch_no = f"{source_cn}-{mmdd}-{hhmm}-{pool_no}"
                cur.execute("BEGIN")
                cur.execute("""INSERT INTO t_incubation_batch
                               (batch_no, pool_no, input_type, initial_input, input_unit, input_time, batch_status)
                               VALUES (%s, %s, %s, %s, %s, %s, '使用中')""",
                            (batch_no, pool_no, input_type, initial_input, input_unit, input_time))
                cur.execute("""UPDATE t_incubation_pool
                               SET current_status = '使用中', current_batch_no = %s, update_time = CURRENT_TIMESTAMP
                               WHERE pool_no = %s""", (batch_no, pool_no))
                if cur.rowcount == 0:
                    conn.rollback()
                    return False, f"❌ 严重错误：未能更新池子 {pool_no} 的状态。"
                record_id = str(uuid.uuid4())
                cur.execute("""INSERT INTO t_business_behavior_record
                               (record_id, behavior_type, related_batch_no, operation_value, operation_time, operator, remarks)
                               VALUES (%s, '批次投入', %s, %s, %s, %s, %s)""",
                            (record_id, batch_no, initial_input, input_time, operator.strip(),
                             f"{input_type}投入{initial_input}{input_unit}到{pool_no}"))
                conn.commit()
                if media_files:
                    # 👇 关键：将 input_type（如“外购蝌蚪”）作为 source_override 传入
                    save_uploaded_media(media_files, record_id, "batch_input", pool_no=pool_no, source_override=input_type)
                fetch_incubation_pools.clear()
                fetch_active_batches.clear()
                return True, f"✅ 批次创建成功: {batch_no}"
    except Exception as e:
        return False, f"❌ 创建批次失败: {e}"
    
def record_sorting(batch_no, round_no, sorting_time, total_frog, frog_details: dict, operator, pool_area="总成蛙池", media_files=None):
    try:
        with DatabaseConnection() as conn:
            if not conn:
                return False, "数据库连接失败"
            with conn.cursor() as cur:
                cur.execute("BEGIN")
                record_id = str(uuid.uuid4())
                cur.execute("""
                    INSERT INTO t_batch_sorting_record
                    (record_id, batch_no, round_no, sorting_time, total_frog, frog_detail, operator)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                """, (record_id, batch_no, round_no, sorting_time, total_frog,
                      json.dumps(frog_details),
                      operator.strip()))
                cur.execute("""
                    UPDATE t_incubation_batch
                       SET total_sorted_frog = total_sorted_frog + %s,
                           update_time = CURRENT_TIMESTAMP
                     WHERE batch_no = %s
                """, (total_frog, batch_no))
                for frog_type, quantity in frog_details.items():
                    cur.execute("""
                        INSERT INTO t_frog_inventory (frog_type_code, quantity, pool_area)
                        VALUES (%s, %s, %s)
                        ON CONFLICT (frog_type_code, pool_area)
                        DO UPDATE SET quantity = t_frog_inventory.quantity + EXCLUDED.quantity,
                                      last_update_time = CURRENT_TIMESTAMP
                    """, (frog_type, quantity, pool_area))
                behavior_id = str(uuid.uuid4())
                cur.execute("""
                    INSERT INTO t_business_behavior_record
                    (record_id, behavior_type, related_batch_no, operation_value, operation_time, operator, remarks)
                    VALUES (%s, '分批分拣', %s, %s, %s, %s, %s)
                """, (behavior_id, batch_no, total_frog, sorting_time,
                      operator.strip(), f"第{round_no}轮分拣到{pool_area}"))
                conn.commit()
                if media_files:
                    save_uploaded_media(media_files, record_id, "sorting", batch_no=batch_no)
                return True, f"第{round_no}轮分拣记录成功"
    except Exception as e:
        return False, f"记录分拣失败: {e}"
def complete_batch(batch_no, complete_time, operator, media_files=None):
    try:
        with DatabaseConnection() as conn:
            if not conn: return False, "数据库连接失败"
            with conn.cursor() as cur:
                cur.execute("SELECT pool_no FROM t_incubation_batch WHERE batch_no = %s", (batch_no,))
                result = cur.fetchone()
                if not result: return False, "批次不存在"
                pool_no = result[0]
                cur.execute("BEGIN")
                cur.execute("""UPDATE t_incubation_batch
                               SET batch_status = '已完成', complete_time = %s, update_time = CURRENT_TIMESTAMP
                               WHERE batch_no = %s""", (complete_time, batch_no))
                cur.execute("""UPDATE t_incubation_pool
                               SET current_status = '空闲', current_batch_no = NULL, update_time = CURRENT_TIMESTAMP
                               WHERE pool_no = %s""", (pool_no,))
                record_id = str(uuid.uuid4())
                cur.execute("""INSERT INTO t_business_behavior_record
                               (record_id, behavior_type, related_batch_no, operation_time, operator, remarks)
                               VALUES (%s, '批次完成', %s, %s, %s, '批次结束，孵化池已空闲')""",
                            (record_id, batch_no, complete_time, operator.strip()))
                conn.commit()
                if media_files:
                    save_uploaded_media(media_files, record_id, "batch_complete", batch_no=batch_no)
                fetch_incubation_pools.clear()
                return True, f"批次{batch_no}已标记为完成"
    except Exception as e:
        return False, f"完成批次失败: {e}"
def record_material_purchase(material_type, quantity, purchase_time, operator, remarks="", 
                             frog_type=None, target_pool=None, media_files=None):
    try:
        with DatabaseConnection() as conn:
            if not conn: return False, "数据库连接失败"
            with conn.cursor() as cur:
                cur.execute("BEGIN")
                cur.execute("SELECT id FROM t_material_inventory WHERE material_type_code = %s", (material_type,))
                inventory_id = cur.fetchone()
                if inventory_id:
                    cur.execute("""UPDATE t_material_inventory
                                   SET remaining_quantity = remaining_quantity + %s, last_update_time = CURRENT_TIMESTAMP
                                   WHERE id = %s""", (quantity, inventory_id[0]))
                else:
                    cur.execute("""INSERT INTO t_material_inventory (material_type_code, remaining_quantity)
                                   VALUES (%s, %s)""", (material_type, quantity))
                if material_type in ["TADPOLE", "YOUNG_FROG", "ADULT_FROG"]:
                    if not frog_type or not target_pool:
                        return False, "蛙类采购必须指定蛙类型和目标池区"
                    cur.execute("""
                        INSERT INTO t_frog_inventory (frog_type_code, quantity, pool_area)
                        VALUES (%s, %s, %s)
                        ON CONFLICT (frog_type_code, pool_area)
                        DO UPDATE SET quantity = t_frog_inventory.quantity + EXCLUDED.quantity,
                                      last_update_time = CURRENT_TIMESTAMP
                    """, (frog_type, quantity, target_pool))
                record_id = str(uuid.uuid4())
                cur.execute("""INSERT INTO t_business_behavior_record
                               (record_id, behavior_type, related_entity_id, operation_value, operation_time, operator, remarks)
                               VALUES (%s, '采购物资', %s, %s, %s, %s, %s)""",
                            (record_id, material_type, quantity, purchase_time, operator.strip(), remarks or '采购物资'))
                conn.commit()
                if media_files:
                    save_uploaded_media(media_files, record_id, "purchase")
                return True, f"物资采购记录成功"
    except Exception as e:
        return False, f"记录采购失败: {e}"
def record_feeding(material_type, quantity, feeding_time, target, operator, media_files=None):
    try:
        with DatabaseConnection() as conn:
            if not conn: return False, "数据库连接失败"
            with conn.cursor() as cur:
                cur.execute("SELECT remaining_quantity FROM t_material_inventory WHERE material_type_code = %s", (material_type,))
                result = cur.fetchone()
                if not result or result[0] < quantity:
                    return False, "物资库存不足"
                cur.execute("BEGIN")
                cur.execute("""UPDATE t_material_inventory
                               SET remaining_quantity = remaining_quantity - %s, last_update_time = CURRENT_TIMESTAMP
                               WHERE material_type_code = %s""", (quantity, material_type))
                record_id = str(uuid.uuid4())
                cur.execute("""INSERT INTO t_business_behavior_record
                               (record_id, behavior_type, related_entity_id, operation_value, operation_time, operator, remarks)
                               VALUES (%s, '喂食', %s, %s, %s, %s, %s)""",
                            (record_id, material_type, quantity, feeding_time, operator.strip(), f"喂食对象: {target}"))
                conn.commit()
                if media_files:
                    save_uploaded_media(media_files, record_id, "feeding")
                return True, f"喂食记录成功"
    except Exception as e:
        return False, f"记录喂食失败: {e}"
# 同时需要更新销售函数，支持从具体商品蛙池销售
def record_frog_sale_from_pool(frog_type, quantity, sale_time, operator, pool_area, remarks="", media_files=None):
    """
    优化版：支持从具体商品蛙池销售，确保溯源
    """
    try:
        with DatabaseConnection() as conn:
            if not conn: 
                return False, "数据库连接失败"
            
            with conn.cursor() as cur:
                # 检查库存
                cur.execute("""SELECT id, quantity FROM t_frog_inventory
                               WHERE frog_type_code = %s AND pool_area = %s""", 
                           (frog_type, pool_area))
                result = cur.fetchone()
                
                if not result or result[1] < quantity:
                    return False, f"{pool_area} 中 {frog_type} 库存不足"
                
                inventory_id = result[0]
                
                cur.execute("BEGIN")
                
                # 扣减库存
                cur.execute("""UPDATE t_frog_inventory
                               SET quantity = quantity - %s, last_update_time = CURRENT_TIMESTAMP
                               WHERE id = %s""", (quantity, inventory_id))
                
                # 记录销售行为，包含详细的池区信息用于溯源
                record_id = str(uuid.uuid4())
                cur.execute("""INSERT INTO t_business_behavior_record
                               (record_id, behavior_type, related_entity_id, operation_value, operation_time, operator, remarks)
                               VALUES (%s, '销售成蛙', %s, %s, %s, %s, %s)""",
                          (record_id, frog_type, quantity, sale_time, operator.strip(), remarks))
                
                conn.commit()
                
                if media_files:
                    save_uploaded_media(media_files, record_id, "sale", pool_no=pool_area)
                
                return True, f"✅ 成功从 {pool_area} 销售 {quantity} 只 {frog_type}"
                
    except Exception as e:
        return False, f"记录销售失败: {e}"
def record_direct_frog_input(frog_type, quantity, input_time, operator, target_pool_area, remarks="", media_files=None):
    try:
        with DatabaseConnection() as conn:
            if not conn:
                return False, "数据库连接失败"
            with conn.cursor() as cur:
                cur.execute("BEGIN")
                cur.execute("""
                    INSERT INTO t_frog_inventory (frog_type_code, quantity, pool_area)
                    VALUES (%s, %s, %s)
                    ON CONFLICT (frog_type_code, pool_area)
                    DO UPDATE SET quantity = t_frog_inventory.quantity + EXCLUDED.quantity,
                                  last_update_time = CURRENT_TIMESTAMP
                """, (frog_type, quantity, target_pool_area))
                record_id = str(uuid.uuid4())
                cur.execute("""
                    INSERT INTO t_business_behavior_record
                    (record_id, behavior_type, related_entity_id, operation_value, operation_time, operator, remarks)
                    VALUES (%s, '外购幼蛙入库', %s, %s, %s, %s, %s)
                """, (record_id, frog_type, quantity, input_time, operator.strip(), remarks))
                conn.commit()
                if media_files:
                    save_uploaded_media(media_files, record_id, "direct_input", pool_no=target_pool_area)
                return True, f"成功将 {quantity} 只外购幼蛙入库到 {target_pool_area}"
    except Exception as e:
        return False, f"记录外购幼蛙入库失败: {e}"
def record_frog_reclassification_to_target(from_pool_area, to_details: dict, reclass_time, operator, media_files=None):
    """
    优化版：根据来源池区自动分配到对应的商品蛙池
    """
    try:
        with DatabaseConnection() as conn:
            if not conn: 
                return False, "数据库连接失败"
            
            with conn.cursor() as cur:
                cur.execute("BEGIN")
                
                # 计算总需求量
                total_requested = sum(to_details.values())
                
                # 检查库存是否足够
                cur.execute("SELECT COALESCE(SUM(quantity), 0) FROM t_frog_inventory WHERE pool_area = %s", (from_pool_area,))
                total_available = cur.fetchone()[0] or 0
                
                if total_available < total_requested:
                    return False, f"库存不足！{from_pool_area} 当前只有 {int(total_available)} 只"
                
                # 从原池区扣除
                cur.execute("UPDATE t_frog_inventory SET quantity = quantity - %s WHERE pool_area = %s", 
                           (total_requested, from_pool_area))
                
                # 解析来源信息，构建目标池区映射
                if "细皮" in from_pool_area:
                    skin_type = "细皮"
                elif "粗皮" in from_pool_area:
                    skin_type = "粗皮"
                else:
                    skin_type = "未知"
                
                # 根据来源池区确定来源类型
                if "自养卵" in from_pool_area:
                    source_type = "自养卵"
                elif "外购蝌蚪" in from_pool_area:
                    source_type = "外购蝌蚪"
                elif "外购幼蛙" in from_pool_area:
                    source_type = "外购幼蛙"
                elif "外购成蛙" in from_pool_area:
                    source_type = "外购成蛙"
                else:
                    source_type = "未知"
                
                for frog_type, qty in to_details.items():
                    if qty <= 0:
                        continue
                        
                    # 根据蛙类型确定目标池区
                    if frog_type.startswith("SP_"):  # 商品蛙
                        # 构建对应的商品蛙池名称
                        target_pool_area = f"{source_type}{skin_type}商品蛙池-001"
                        
                        # 检查目标池是否存在
                        cur.execute("SELECT COUNT(*) FROM t_frog_pool WHERE pool_code = %s", (target_pool_area,))
                        if cur.fetchone()[0] == 0:
                            # 如果池子不存在，使用通用商品蛙池
                            target_pool_area = "商品蛙池"
                            
                    elif frog_type.startswith("ZB_"):  # 种蛙
                        target_pool_area = "种蛙池"
                    elif frog_type.startswith("SY_"):  # 试验蛙
                        target_pool_area = "试验蛙池"
                    else:
                        target_pool_area = "默认池区"
                    
                    # 插入或更新目标池区库存
                    cur.execute("""
                        INSERT INTO t_frog_inventory (frog_type_code, quantity, pool_area)
                        VALUES (%s, %s, %s)
                        ON CONFLICT (frog_type_code, pool_area)
                        DO UPDATE SET quantity = t_frog_inventory.quantity + EXCLUDED.quantity,
                                      last_update_time = CURRENT_TIMESTAMP
                    """, (frog_type, qty, target_pool_area))
                
                # 记录业务行为
                record_id = str(uuid.uuid4())
                cur.execute("""
                    INSERT INTO t_business_behavior_record
                    (record_id, behavior_type, operation_value, operation_time, operator, remarks)
                    VALUES (%s, '成蛙再分类', %s, %s, %s, %s)
                """, (record_id, total_requested, reclass_time, operator.strip(), 
                      f"从 {from_pool_area} 细分到对应商品蛙池"))
                
                conn.commit()
                
                if media_files:
                    save_uploaded_media(media_files, record_id, "reclass", pool_no=from_pool_area)
                
                return True, f"成功从 {from_pool_area} 分拣 {total_requested} 只到对应商品蛙池"
                
    except Exception as e:
        return False, f"记录再分类失败: {e}"
def record_inventory_operation(
    item_type: str,
    item_code: str,
    operation: str,
    quantity: float,
    pool_or_warehouse: str = "",
    operation_time: datetime = None,
    operator: str = "admin",
    remarks: str = ""
):
    if not operation_time:
        operation_time = datetime.now()
    try:
        with DatabaseConnection() as conn:
            if not conn:
                return False, "数据库连接失败"
            with conn.cursor() as cur:
                cur.execute("BEGIN")
                if item_type == "frog":
                    if operation == "盘点":
                        cur.execute("""
                            INSERT INTO t_frog_inventory (frog_type_code, quantity, pool_area)
                            VALUES (%s, %s, %s)
                            ON CONFLICT (frog_type_code, pool_area)
                            DO UPDATE SET quantity = EXCLUDED.quantity, last_update_time = CURRENT_TIMESTAMP
                        """, (item_code, quantity, pool_or_warehouse or "默认池区"))
                    else:
                        delta = quantity if operation == "入库" else -quantity
                        cur.execute("""
                            INSERT INTO t_frog_inventory (frog_type_code, quantity, pool_area)
                            VALUES (%s, %s, %s)
                            ON CONFLICT (frog_type_code, pool_area)
                            DO UPDATE SET quantity = t_frog_inventory.quantity + %s, last_update_time = CURRENT_TIMESTAMP
                        """, (item_code, max(0, delta), pool_or_warehouse or "默认池区", delta))
                        cur.execute("SELECT quantity FROM t_frog_inventory WHERE frog_type_code = %s AND pool_area = %s", 
                                   (item_code, pool_or_warehouse or "默认池区"))
                        if cur.fetchone()[0] < 0:
                            conn.rollback()
                            return False, "出库数量超过库存！"
                else:
                    if operation == "盘点":
                        cur.execute("""
                            INSERT INTO t_material_inventory (material_type_code, remaining_quantity)
                            VALUES (%s, %s)
                            ON CONFLICT (material_type_code)
                            DO UPDATE SET remaining_quantity = EXCLUDED.remaining_quantity, last_update_time = CURRENT_TIMESTAMP
                        """, (item_code, quantity))
                    else:
                        delta = quantity if operation == "入库" else -quantity
                        cur.execute("""
                            INSERT INTO t_material_inventory (material_type_code, remaining_quantity)
                            VALUES (%s, %s)
                            ON CONFLICT (material_type_code)
                            DO UPDATE SET remaining_quantity = t_material_inventory.remaining_quantity + %s, last_update_time = CURRENT_TIMESTAMP
                        """, (item_code, max(0, delta), delta))
                        cur.execute("SELECT remaining_quantity FROM t_material_inventory WHERE material_type_code = %s", (item_code,))
                        if cur.fetchone()[0] < 0:
                            conn.rollback()
                            return False, "出库数量超过库存！"
                behavior_map = {
                    ("frog", "入库"): "进销存-蛙类入库",
                    ("frog", "出库"): "进销存-蛙类出库",
                    ("frog", "盘点"): "进销存-盘点",
                    ("material", "入库"): "进销存-物资入库",
                    ("material", "出库"): "进销存-物资出库",
                }
                behavior_type = behavior_map.get((item_type, operation), "进销存-其他")
                cur.execute("""
                    INSERT INTO t_business_behavior_record
                    (record_id, behavior_type, related_entity_id, operation_value, operation_time, operator, remarks)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                """, (str(uuid.uuid4()), behavior_type, item_code, quantity, operation_time, operator, remarks))
                conn.commit()
                return True, f"{operation}成功"
    except Exception as e:
        return False, f"操作失败: {e}"
# ----------------------------- 页面渲染：四来源分离版 ----------------------------- #
# ----------------------------- 页面渲染：四来源分离版 ----------------------------- #
def render_operation_module():
    import time
    ts = lambda: str(int(time.time()))  # 秒级时间戳

    st.header("现场操作记录")
    st.markdown("---")
    operator = st.text_input("操作员", value="admin", key="operator_input")
    if not operator.strip():
        st.warning("请输入操作员姓名")
        return

    st.markdown("📍 当前孵化池占用情况（仅供参考）")
    pools = fetch_incubation_pools()
    if pools:
        df_pools = pd.DataFrame(pools, columns=["池号", "位置", "状态", "批次"])
        df_pools["状态"] = df_pools["状态"].map({"空闲": "🟢 空闲", "使用中": "🔴 使用中"})
        st.dataframe(df_pools, use_container_width=True, hide_index=True)
    else:
        st.info("暂无孵化池数据")

    tab_egg, tab_tadpole, tab_young, tab_adult = st.tabs([
        "🐣 自养卵流程", "🪷 外购蝌蚪流程", "🐸 外购幼蛙流程", "🛒 外购成蛙流程"
    ])

    # ========== 1. 自养卵 ==========
    with tab_egg:
        st.subheader("1. 批次投入（自养卵）")
        free_pools = fetch_incubation_pools("空闲")
        if not free_pools:
            st.warning("没有可用的空闲孵化池")
        else:
            with st.form("batch_egg"):
                col1, col2 = st.columns(2)
                with col1:
                    pool_opts = [f"{p[0]} ({p[1]})" for p in free_pools]
                    sel = st.selectbox("选择孵化池", pool_opts)
                    pool_no = sel.split()[0]
                    board = st.number_input("投入板数（1板=1000颗）", min_value=0.0, step=0.1)
                    qty = int(board * 1000)
                with col2:
                    dt = st.date_input("日期", datetime.now())
                    tm = st.time_input("时间", datetime.now().time())
                    input_time = datetime.combine(dt, tm)
                uploaded = st.file_uploader(
                    "📸 上传现场图片/视频（可多选）",
                    type=["jpg", "jpeg", "png", "mp4", "mov"],
                    accept_multiple_files=True,
                    key=f"up_egg_batch_{pool_no}"
                )
                if st.form_submit_button("提交") and qty > 0:
                    ok, msg = create_batch(pool_no, "自养卵", qty, "颗", input_time,
                                           operator.strip(), media_files=uploaded)
                    if ok:
                        st.success(msg)
                        st.rerun()
                    else:
                        st.error(msg)

        st.markdown("---")
        # ========== 自养卵分拣部分 ==========
        st.subheader("2. 分批分拣（自养卵 → 成蛙池）")
        sorted_total = get_sorted_frog_total_by_source("自养卵")
        st.info(f"📊 自养卵流程已分拣到成蛙池累计：**{sorted_total} 只**")

        active = [b for b in fetch_active_batches() if b[2] == "自养卵"]
        if not active:
            st.info("暂无自养卵活跃批次")
        else:
            batch_opts = [f"{b[0]} ({b[1]})" for b in active]
            sel = st.selectbox("选择批次", batch_opts)
            batch_no = sel.split()[0]

            # 👇 把 radio 和池子概览移到 form 外面！
            skin = st.radio("皮型", ["细皮", "粗皮"], horizontal=True, key=f"egg_skin_radio_{batch_no}")

            # 实时显示成蛙池容量（不依赖表单提交）
            pool_df = get_frog_pools(pool_type='自养卵', skin_type=skin)
            pool_df = pool_df[~pool_df['池编号'].str.contains('商品蛙池')] 
            if pool_df.empty:
                st.error('暂无对应成蛙池，请先联系管理员建池')
            else:
                st.write("📍 成蛙池容量概览")
                st.dataframe(pool_df, use_container_width=True)
                full_pools = pool_df[pool_df['剩余空间'] <= 0]['池编号'].tolist()
                if full_pools:
                    st.error(f"池子 {full_pools} 已满 500 只，请先增加新池再分拣！")

            # 表单内只保留输入和提交
            with st.form("sort_egg"):
                col1, col2 = st.columns(2)
                with col1:
                    with DatabaseConnection() as conn:
                        with conn.cursor() as cur:
                            cur.execute("SELECT COALESCE(MAX(round_no),0)+1 FROM t_batch_sorting_record WHERE batch_no=%s", (batch_no,))
                            rnd = cur.fetchone()[0]
                    total = st.number_input("分拣数量（只）", min_value=1)
                    avg_w = st.number_input("平均重量（克）", min_value=0.1, value=25.0)
                with col2:
                    dt = st.date_input("分拣日期", datetime.now(), key="sort_egg_d")
                    tm = st.time_input("分拣时间", datetime.now().time(), key="sort_egg_t")

                # 目标池选择（基于已加载的 pool_df）
                if not pool_df.empty and not full_pools:
                    target_pool = st.selectbox(
                        "请选择目标成蛙池",
                        pool_df['池编号'].tolist(),
                        format_func=lambda x: f"{x}（余 {pool_df.set_index('池编号').at[x, '剩余空间']} 只）"
                    )
                else:
                    target_pool = None

                uploaded = st.file_uploader(
                    "📸 上传现场图片/视频（可多选）",
                    type=["jpg", "jpeg", "png", "mp4", "mov"],
                    accept_multiple_files=True,
                    key=f"up_sort_egg_{batch_no}_{rnd}"
                )

                if st.form_submit_button("提交分拣") and avg_w >= 20 and target_pool and total > 0:
                    # ✅ 统一用「成蛙」过渡类型，不再挑 SP_xxx
                    frog_details = {"成蛙": total}
                    ok, msg = record_sorting(
                        batch_no, rnd, datetime.combine(dt, tm),
                        total, frog_details, operator.strip(),
                        target_pool, media_files=uploaded
                    )
                    if ok:
                        st.success(f"✅ 已分拣 {total} 只到 {target_pool}")
                        get_sorted_frog_total_by_source.clear()
                        st.rerun()
                    else:
                        st.error(msg)

        st.markdown("---")
        st.subheader("3. 成蛙再分类（自养卵）")
        skin = st.radio("选择皮型", ["细皮", "粗皮"], key="reclass_egg_skin", horizontal=True)

        # 获取该来源+皮型下的所有具体成蛙池
        pool_df = get_frog_pools(pool_type='自养卵', skin_type=skin)
        pool_df = pool_df[~pool_df['池编号'].str.contains('商品蛙池')] 
        if pool_df.empty:
            st.warning("暂无可用成蛙池")
        else:
            pool_options = pool_df['池编号'].tolist()
            selected_pool = st.selectbox("选择要再分类的成蛙池", pool_options, key=f"reclass_pool_egg_{skin}")
            _show_reclass_ui(selected_pool, operator)

        st.markdown("---")
        st.subheader("4. 销售（自养卵）")
        skin = st.radio("选择皮型", ["细皮", "粗皮"], key="sale_egg_skin", horizontal=True)

        # 获取所有可销售池（商品蛙池 + 年限池）
        sale_pools = get_frog_pools(purpose="sale")
        if sale_pools.empty:
            st.warning("暂无可售池，请先初始化池区信息")
        else:
            # 为年限池补充来源和皮型
            def enrich_pool_info(row):
                pool_code = row['池编号']
                if row['来源/年限'] in ['三年蛙', '四年蛙', '五年蛙', '种蛙', '试验蛙']:
                    source, skin_type = get_pool_source_and_skin(pool_code)
                    return pd.Series([source, skin_type])
                else:
                    # 商品蛙池：直接用 pool_type 和 skin_type
                    return pd.Series([row['来源/年限'], row['皮型']])
            
            sale_pools[['推断_来源', '推断_皮型']] = sale_pools.apply(enrich_pool_info, axis=1)
            
            # 筛选：来源=自养卵 且 皮型=用户选择
            filtered_pools = sale_pools[
                (sale_pools['推断_来源'] == '自养卵') &
                (sale_pools['推断_皮型'] == skin)
            ]
            
            if filtered_pools.empty:
                st.warning(f"暂无 自养卵-{skin} 的可销售池（包括商品蛙池和年限池）")
            else:
                selected_pool = st.selectbox(
                    "选择销售池区",
                    filtered_pools['池编号'].tolist(),
                    format_func=lambda x: f"{x}（当前数量：{int(filtered_pools.set_index('池编号').loc[x, '当前数量'])}只）"
                )
                _show_sale_ui(selected_pool, operator)

    # ========== 2. 外购蝌蚪 ==========
    with tab_tadpole:
        st.subheader("1. 批次投入（外购蝌蚪）")
        free = fetch_incubation_pools("空闲")
        if not free:
            st.warning("没有可用的空闲孵化池")
        else:
            with st.form("batch_tad"):
                col1, col2 = st.columns(2)
                with col1:
                    opts = [f"{p[0]} ({p[1]})" for p in free]
                    sel = st.selectbox("选择孵化池", opts)
                    pool_no = sel.split()[0]
                    unit = st.radio("单位", ["只", "斤"])
                    qty = st.number_input("数量", min_value=0.01)
                with col2:
                    dt = st.date_input("日期", datetime.now(), key="tad_d")
                    tm = st.time_input("时间", datetime.now().time(), key="tad_t")
                    input_time = datetime.combine(dt, tm)
                uploaded = st.file_uploader(
                    "📸 上传现场图片/视频（可多选）",
                    type=["jpg", "jpeg", "png", "mp4", "mov"],
                    accept_multiple_files=True,
                    key=f"up_tad_batch_{pool_no}"
                )
                if st.form_submit_button("提交"):
                    ok, msg = create_batch(pool_no, "外购蝌蚪", qty, unit, input_time,
                                           operator.strip(), media_files=uploaded)
                    if ok:
                        st.success(msg)
                        st.rerun()
                    else:
                        st.error(msg)

        st.markdown("---")
        st.subheader("2. 分批分拣（外购蝌蚪 → 成蛙池）")

        sorted_total = get_sorted_frog_total_by_source("外购蝌蚪")
        st.info(f"📊 外购蝌蚪流程已分拣到成蛙池累计：**{sorted_total} 只**")

        active = [b for b in fetch_active_batches() if b[2] == "外购蝌蚪"]
        if not active:
            st.info("暂无外购蝌蚪活跃批次")
        else:
            batch_opts = [f"{b[0]} ({b[1]})" for b in active]
            sel = st.selectbox("选择批次", batch_opts)
            batch_no = sel.split()[0]

            # 把 radio 放在表单外，切换立即刷新池数据
            skin = st.radio("皮型", ["细皮", "粗皮"], horizontal=True, key="tad_skin_radio")

            with st.form("sort_tad"):
                col1, col2 = st.columns(2)
                with col1:
                    with DatabaseConnection() as conn:
                        with conn.cursor() as cur:
                            cur.execute("SELECT COALESCE(MAX(round_no),0)+1 FROM t_batch_sorting_record WHERE batch_no=%s",(batch_no,))
                            rnd = cur.fetchone()[0]
                    total = st.number_input("分拣数量（只）", min_value=1)
                    avg_w = st.number_input("平均重量（克）", min_value=0.1, value=25.0)
                with col2:
                    dt = st.date_input("分拣日期", datetime.now(), key="sort_tad_d")
                    tm = st.time_input("分拣时间", datetime.now().time(), key="sort_tad_t")

                # ===== 成蛙池选择 =====================================
                pool_df = get_frog_pools(pool_type='外购蝌蚪', skin_type=skin)
                pool_df = pool_df[~pool_df['池编号'].str.contains('商品蛙池')]
                if pool_df.empty:
                    st.error('暂无对应成蛙池，请先联系管理员建池')
                    st.stop()

                st.write("📍 成蛙池容量概览")
                st.dataframe(pool_df, use_container_width=True)

                full_pools = pool_df[pool_df['剩余空间'] <= 0]['池编号'].tolist()
                if full_pools:
                    st.error(f"池子 {full_pools} 已满 500 只，请先增加新池再分拣！")
                    st.stop()

                target_pool = st.selectbox(
                    "请选择目标成蛙池",
                    pool_df['池编号'].tolist(),
                    format_func=lambda x: f"{x}（余 {pool_df.set_index('池编号').at[x, '剩余空间']} 只）"
                )
                # ======================================================

                uploaded = st.file_uploader(
                    "📸 上传现场图片/视频（可多选）",
                    type=["jpg", "jpeg", "png", "mp4", "mov"],
                    accept_multiple_files=True,
                    key=f"up_sort_tad_{batch_no}_{rnd}"
                )
                if st.form_submit_button("提交分拣") and avg_w >= 20:
                    frog_types = fetch_frog_types()
                    use_type = next((c for c, _ in frog_types if c.startswith("SP_") and c != "SP"), "SP_商品蛙")
                    ok, msg = record_sorting(batch_no, rnd, datetime.combine(dt, tm),
                                             total, {use_type: total}, operator.strip(),
                                             target_pool, media_files=uploaded)
                    if ok:
                        st.success(f"✅ 分拣到 {target_pool}")
                        st.rerun()
                    else:
                        st.error(msg)

        st.markdown("---")
        st.subheader("3. 成蛙再分类（外购蝌蚪）")
        skin = st.radio("选择皮型", ["细皮", "粗皮"], key="reclass_tad_skin", horizontal=True)
        pool_df = get_frog_pools(pool_type='外购蝌蚪', skin_type=skin)
        pool_df = pool_df[~pool_df['池编号'].str.contains('商品蛙池')]
        if pool_df.empty:
            st.warning("暂无可用的外购蝌蚪成蛙池")
        else:
            selected_pool = st.selectbox("选择要再分类的成蛙池", pool_df['池编号'].tolist(), key=f"reclass_pool_tad_{skin}")
            _show_reclass_ui(selected_pool, operator)

        st.markdown("---")
        st.subheader("4. 销售（外购蝌蚪）")
        skin = st.radio("选择皮型", ["细皮", "粗皮"], key="sale_tad_skin", horizontal=True)

        # 获取所有可销售池（商品蛙池 + 年限池）
        sale_pools = get_frog_pools(purpose="sale")
        if sale_pools.empty:
            st.warning("暂无可售池，请先初始化池区信息")
        else:
            def enrich_pool_info(row):
                pool_code = row['池编号']
                if row['来源/年限'] in ['三年蛙', '四年蛙', '五年蛙', '种蛙', '试验蛙']:
                    source, skin_type = get_pool_source_and_skin(pool_code)
                    return pd.Series([source, skin_type])
                else:
                    return pd.Series([row['来源/年限'], row['皮型']])
            
            sale_pools[['推断_来源', '推断_皮型']] = sale_pools.apply(enrich_pool_info, axis=1)
            filtered_pools = sale_pools[
                (sale_pools['推断_来源'] == '外购蝌蚪') &
                (sale_pools['推断_皮型'] == skin)
            ]
            
            if filtered_pools.empty:
                st.warning(f"暂无 外购蝌蚪-{skin} 的可销售池（包括商品蛙池和年限池）")
            else:
                selected_pool = st.selectbox(
                    "选择销售池区",
                    filtered_pools['池编号'].tolist(),
                    format_func=lambda x: f"{x}（当前数量：{int(filtered_pools.set_index('池编号').loc[x, '当前数量'])}只）"
                )
                _show_sale_ui(selected_pool, operator)

    # ========== 3. 外购幼蛙 ==========
    with tab_young:
        st.markdown("---")
        st.subheader("1. 外购幼蛙入库（直接进成蛙池）")

        sorted_total = get_sorted_frog_total_by_source("外购幼蛙")
        st.info(f"📊 外购幼蛙流程已分拣到成蛙池累计：**{sorted_total} 只**")

        frog_types = fetch_frog_types()
        valid_sp = [c for c, _ in frog_types if c.startswith("SP_") and c != "SP"]
        if not valid_sp:
            st.warning("未定义商品蛙子类型")
        else:
            # 把 radio 放在表单外，切换立即刷新池数据
            skin = st.radio("皮型", ["细皮", "粗皮"], horizontal=True, key="young_skin_radio")

            with st.form("direct_young"):
                col1, col2 = st.columns(2)
                with col1:
                    opts = [f"{c} - {d}" for c, d in frog_types if c in valid_sp]
                    sel = st.selectbox("幼蛙类型", opts)
                    frog_type = sel.split(" - ")[0]
                    qty = st.number_input("数量", min_value=1)
                with col2:
                    dt = st.date_input("日期", datetime.now(), key="young_d")
                    tm = st.time_input("时间", datetime.now().time(), key="young_t")
                    input_time = datetime.combine(dt, tm)

                # ===== 成蛙池选择 =====================================
                pool_df = get_frog_pools(pool_type='外购幼蛙', skin_type=skin)
                pool_df = pool_df[~pool_df['池编号'].str.contains('商品蛙池')]
                if pool_df.empty:
                    st.error('暂无对应成蛙池，请先联系管理员建池')
                    st.stop()

                st.write("📍 成蛙池容量概览")
                st.dataframe(pool_df, use_container_width=True)

                full_pools = pool_df[pool_df['剩余空间'] <= 0]['池编号'].tolist()
                if full_pools:
                    st.error(f"池子 {full_pools} 已满 500 只，请先增加新池再入库！")
                    st.stop()

                target_pool = st.selectbox(
                    "请选择目标成蛙池",
                    pool_df['池编号'].tolist(),
                    format_func=lambda x: f"{x}（余 {pool_df.set_index('池编号').at[x, '剩余空间']} 只）"
                )
                # ======================================================

                uploaded = st.file_uploader(
                    "📸 上传现场图片/视频（可多选）",
                    type=["jpg", "jpeg", "png", "mp4", "mov"],
                    accept_multiple_files=True,
                    key=f"up_young_direct_{frog_type}"
                )
                if st.form_submit_button("提交入库"):
                    ok, msg = record_direct_frog_input(frog_type, qty, input_time,
                                                       operator.strip(), target_pool,
                                                       "外购幼蛙入库", media_files=uploaded)
                    if ok:
                        st.success(msg)
                        st.rerun()
                    else:
                        st.error(msg)

        st.markdown("---")
        st.subheader("2. 成蛙再分类（外购幼蛙）")
        skin = st.radio("选择皮型", ["细皮", "粗皮"], key="reclass_young_skin", horizontal=True)
        pool_df = get_frog_pools(pool_type='外购幼蛙', skin_type=skin)
        pool_df = pool_df[~pool_df['池编号'].str.contains('商品蛙池')]
        if pool_df.empty:
            st.warning("暂无可用的外购幼蛙成蛙池")
        else:
            selected_pool = st.selectbox("选择要再分类的成蛙池", pool_df['池编号'].tolist(), key=f"reclass_pool_young_{skin}")
            _show_reclass_ui(selected_pool, operator)

        st.markdown("---")
        st.subheader("3. 销售（外购幼蛙）")
        skin = st.radio("选择皮型", ["细皮", "粗皮"], key="sale_young_skin", horizontal=True)

        # 获取所有可销售池（商品蛙池 + 年限池）
        sale_pools = get_frog_pools(purpose="sale")
        if sale_pools.empty:
            st.warning("暂无可售池，请先初始化池区信息")
        else:
            def enrich_pool_info(row):
                pool_code = row['池编号']
                if row['来源/年限'] in ['三年蛙', '四年蛙', '五年蛙', '种蛙', '试验蛙']:
                    source, skin_type = get_pool_source_and_skin(pool_code)
                    return pd.Series([source, skin_type])
                else:
                    return pd.Series([row['来源/年限'], row['皮型']])
            
            sale_pools[['推断_来源', '推断_皮型']] = sale_pools.apply(enrich_pool_info, axis=1)
            filtered_pools = sale_pools[
                (sale_pools['推断_来源'] == '外购幼蛙') &
                (sale_pools['推断_皮型'] == skin)
            ]
            
            if filtered_pools.empty:
                st.warning(f"暂无 外购幼蛙-{skin} 的可销售池（包括商品蛙池和年限池）")
            else:
                selected_pool = st.selectbox(
                    "选择销售池区",
                    filtered_pools['池编号'].tolist(),
                    format_func=lambda x: f"{x}（当前数量：{int(filtered_pools.set_index('池编号').loc[x, '当前数量'])}只）"
                )
                _show_sale_ui(selected_pool, operator)

    # ========== 4. 外购成蛙 ==========
    with tab_adult:
        st.subheader("1. 外购成蛙入库（直接进商品蛙池）")
        frog_types = fetch_frog_types()
        valid_sp = [c for c, _ in frog_types if c.startswith("SP_") and c != "SP"]
        if not valid_sp:
            st.warning("未定义商品蛙子类型")
        else:
            with st.form("direct_adult"):
                col1, col2 = st.columns(2)
                with col1:
                    opts = [f"{c} - {d}" for c, d in frog_types if c in valid_sp]
                    sel = st.selectbox("成蛙类型", opts)
                    frog_type = sel.split(" - ")[0]
                    target_pool = "外购成蛙-商品蛙池"
                    qty = st.number_input("数量", min_value=1)
                with col2:
                    dt = st.date_input("日期", datetime.now(), key="adult_d")
                    tm = st.time_input("时间", datetime.now().time(), key="adult_t")
                    input_time = datetime.combine(dt, tm)
                uploaded = st.file_uploader(
                    "📸 上传现场图片/视频（可多选）",
                    type=["jpg", "jpeg", "png", "mp4", "mov"],
                    accept_multiple_files=True,
                    key=f"up_adult_direct_{frog_type}"
                )
                if st.form_submit_button("提交入库"):
                    ok, msg = record_direct_frog_input(frog_type, qty, input_time,
                                                       operator.strip(), target_pool,
                                                       "外购成蛙入库", media_files=uploaded)
                    if ok:
                        st.success(msg)
                        st.rerun()
                    else:
                        st.error(msg)

        st.markdown("---")
        st.subheader("2. 销售（外购成蛙）")
        skin = st.radio("选择皮型", ["细皮", "粗皮"], key="sale_adult_skin", horizontal=True)

        # 获取所有可销售池（商品蛙池 + 年限池）
        sale_pools = get_frog_pools(purpose="sale")
        if sale_pools.empty:
            st.warning("暂无可售池，请先初始化池区信息")
        else:
            def enrich_pool_info(row):
                pool_code = row['池编号']
                if row['来源/年限'] in ['三年蛙', '四年蛙', '五年蛙', '种蛙', '试验蛙']:
                    source, skin_type = get_pool_source_and_skin(pool_code)
                    return pd.Series([source, skin_type])
                else:
                    return pd.Series([row['来源/年限'], row['皮型']])
            
            sale_pools[['推断_来源', '推断_皮型']] = sale_pools.apply(enrich_pool_info, axis=1)
            filtered_pools = sale_pools[
                (sale_pools['推断_来源'] == '外购成蛙') &
                (sale_pools['推断_皮型'] == skin)
            ]
            
            if filtered_pools.empty:
                st.warning(f"暂无 外购成蛙-{skin} 的可销售池（包括商品蛙池和年限池）")
            else:
                selected_pool = st.selectbox(
                    "选择销售池区",
                    filtered_pools['池编号'].tolist(),
                    format_func=lambda x: f"{x}（当前数量：{int(filtered_pools.set_index('池编号').loc[x, '当前数量'])}只）"
                )
                _show_sale_ui(selected_pool, operator)

    # ========== 通用折叠区 ==========
    st.markdown("---")
    st.subheader("通用操作（所有来源共享）")

    # ---- 批次完成 ----
    with st.expander("批次完成"):
        active = fetch_active_batches()
        if active:
            with st.form("complete_batch"):
                opts = [f"{b[0]} ({b[2]})" for b in active]
                sel = st.selectbox("选择批次", opts)
                batch_no = sel.split()[0]
                dt = st.date_input("完成日期", datetime.now(), key="comp_d")
                tm = st.time_input("完成时间", datetime.now().time(), key="comp_t")
                uploaded = st.file_uploader(
                    "📸 上传完成凭证（可多选）",
                    type=["jpg", "jpeg", "png"],
                    accept_multiple_files=True,
                    key=f"up_complete_{batch_no}"
                )
                if st.form_submit_button("完成批次"):
                    ok, msg = complete_batch(batch_no, datetime.combine(dt, tm),
                                             operator.strip(), media_files=uploaded)
                    if ok:
                        st.success(msg)
                        st.rerun()
                    else:
                        st.error(msg)
# ----------------------------- 辅助 UI 函数（已支持上传） ----------------------------- #
def _show_reclass_ui(from_pool_area: str, operator: str):
    from datetime import datetime

    st.info(f"📍 来源池区：{from_pool_area}")

    # 1. 当前库存（统一用“成蛙”类型）
    with DatabaseConnection() as conn:
        if conn:
            with conn.cursor() as cur:
                cur.execute(
                    """SELECT COALESCE(SUM(quantity),0)
                       FROM t_frog_inventory
                       WHERE pool_area = %s AND frog_type_code = '成蛙'""",
                    (from_pool_area,),
                )
                current_qty = int(cur.fetchone()[0])
    if current_qty <= 0:
        st.warning("成蛙池无商品蛙库存，无法拆分")
        return

    st.success(f"当前“成蛙”库存：{current_qty} 只")

    # 2. 列出所有年限细分池
    year_df = get_frog_pools(purpose="year")          # ← 关键调用
    if year_df.empty:
        st.error("未找到任何年限细分池，请先初始化数据库")
        return

    st.write("📊 目标池容量概览")
    st.dataframe(year_df, use_container_width=True)

    # 3. 动态输入拆分数量
    with st.form(key=f"reclass_{from_pool_area}"):
        qty_map = {}
        cols = st.columns(3)
        for idx, row in year_df.iterrows():
            col = cols[idx % 3]
            max_val = int(row['剩余空间'])
            if max_val <= 0:
                col.warning(f"{row['池编号']} 已满")
                continue
            qty = col.number_input(
                f"拆到 {row['池编号']}",
                min_value=0,
                max_value=max_val,
                step=1,
                key=f"qty_{row['池编号']}"
            )
            if qty:
                qty_map[row['池编号']] = qty

        dt = st.date_input("日期", datetime.now())
        tm = st.time_input("时间", datetime.now().time())
        reclass_time = datetime.combine(dt, tm)

        uploaded = st.file_uploader(
            "📸 上传现场图片/视频（可多选）",
            type=["jpg", "jpeg", "png", "mp4", "mov"],
            accept_multiple_files=True,
            key=f"media_reclass_{from_pool_area}"
        )

        submitted = st.form_submit_button("提交拆分")
        if submitted:
            total_out = sum(qty_map.values())
            if total_out == 0:
                st.error("至少拆 1 只")
            elif total_out > current_qty:
                st.error(f"拆分总量 {total_out} 超过库存 {current_qty}")
            else:
                # 构造 to_details：{frog_type: qty}
                # 这里统一用“SP_三年蛙”这类编码，后续可再细化
                type_map = {
                    "三年蛙池-001": "SP_三年蛙",
                    "四年蛙池-001": "SP_四年蛙",
                    "五年蛙池-001": "SP_五年蛙",
                    "种蛙池-001":   "ZB_母种",
                    "试验蛙池-001": "SY_对照组",
                }
                to_details = {type_map[pool]: q for pool, q in qty_map.items() if q > 0}

                ok, msg = record_frog_reclassification_to_target(
                    from_pool_area, to_details, reclass_time, operator.strip(), media_files=uploaded
                )
                if ok:
                    st.success(msg)
                    st.rerun()
                else:
                    st.error(msg)
def record_frog_reclassification_to_target(
    from_pool_area: str,
    to_details: dict,  # {SP_三年蛙: 2, ZB_母种: 1, ...}
    reclass_time: datetime,
    operator: str,
    media_files=None,
):
    """
    再分类：从成蛙池扣「成蛙」类型，按 to_details 拆插到年限/种/试验池
    每个目标池单独记录一条行为日志，便于销售模块溯源
    """
    try:
        with DatabaseConnection() as conn:
            if not conn:
                return False, "数据库连接失败"
            with conn.cursor() as cur:
                cur.execute("BEGIN")
                total_need = sum(to_details.values())
                if total_need <= 0:
                    conn.rollback()
                    return False, "拆分数量为 0"
                # 1. 检查成蛙池「成蛙」库存
                cur.execute(
                    """SELECT quantity
                       FROM t_frog_inventory
                       WHERE pool_area = %s AND frog_type_code = '成蛙'""",
                    (from_pool_area,),
                )
                row = cur.fetchone()
                if not row or row[0] < total_need:
                    return False, f"{from_pool_area} 中 成蛙 库存不足（需 {total_need}，实有 {row[0] if row else 0}）"
                # 2. 扣减成蛙池「成蛙」
                cur.execute(
                    """UPDATE t_frog_inventory
                       SET quantity = quantity - %s, last_update_time = CURRENT_TIMESTAMP
                       WHERE pool_area = %s AND frog_type_code = '成蛙'""",
                    (total_need, from_pool_area),
                )
                # 3. 目标池映射
                target_pool_map = {
                    "SP_三年蛙":  "三年蛙池-001",
                    "SP_四年蛙":  "四年蛙池-001",
                    "SP_五年蛙":  "五年蛙池-001",
                    "ZB_母种":   "种蛙池-001",
                    "ZB_公种":   "种蛙池-001",
                    "SY_对照组": "试验蛙池-001",
                }
                # 4. 为每个目标池插入库存 + 行为记录
                for frog_type, qty in to_details.items():
                    if qty <= 0:
                        continue
                    target_pool = target_pool_map.get(frog_type)
                    if not target_pool:
                        continue
                    # 插入/更新库存
                    cur.execute(
                        """INSERT INTO t_frog_inventory (frog_type_code, quantity, pool_area)
                           VALUES (%s, %s, %s)
                           ON CONFLICT (frog_type_code, pool_area)
                           DO UPDATE SET
                               quantity = t_frog_inventory.quantity + EXCLUDED.quantity,
                               last_update_time = CURRENT_TIMESTAMP""",
                        (frog_type, qty, target_pool),
                    )
                    # 👇 关键：为每个目标池单独记录一条行为日志
                    record_id = str(uuid.uuid4())
                    cur.execute(
                        """INSERT INTO t_business_behavior_record
                           (record_id, behavior_type, operation_value, operation_time, operator, remarks)
                           VALUES (%s, '成蛙再分类', %s, %s, %s, %s)""",
                        (record_id, qty, reclass_time, operator.strip(), 
                         f"从 {from_pool_area} 拆分 {qty} 只到 {target_pool}"),
                    )
                conn.commit()
                if media_files:
                    save_uploaded_media(media_files, str(uuid.uuid4()), "reclass", pool_no=from_pool_area)
                return True, f"✅ 已从 {from_pool_area} 拆分 {total_need} 只到对应池"
    except Exception as e:
        return False, f"拆分失败: {e}"
def _show_sale_ui(pool_area: str, operator: str):
    """
    销售统一入口：支持所有可售池（来源商品蛙池 + 三年/四年/五年/种/试验池）
    功能：
    1. 销售统计（按天/月/来源/类型）
    2. 新增销售表单（带客户、单价、备注、多媒体）
    3. 导出详细销售记录 CSV
    """
    from datetime import datetime, timedelta
    import plotly.express as px

    st.subheader(f"📦 销售操作 - {pool_area}")

    # ┌------------------------- 销售统计区域 -------------------------┐
    st.markdown("---")
    st.subheader("📊 销售统计")

    col1, col2, col3 = st.columns([1, 1, 2])
    with col1:
        stat_start = st.date_input("开始日期",
                                   value=datetime.now() - timedelta(days=30),
                                   key=f"stat_start_{pool_area}")
    with col2:
        stat_end = st.date_input("结束日期",
                                 value=datetime.now(),
                                 key=f"stat_end_{pool_area}")
    with col3:
        group_by = st.selectbox("分组方式",
                                ["按天", "按月", "按来源池区", "按蛙类型"],
                                key=f"group_by_{pool_area}")

    # 刷新按钮
    if st.button("🔄 刷新销售统计", key=f"refresh_stats_{pool_area}"):
        get_sales_statistics.clear()

    # 查询销售数据
    sales_df = get_sales_statistics(
        start_date=datetime.combine(stat_start, datetime.min.time()),
        end_date=datetime.combine(stat_end, datetime.max.time()),
        group_by={"按天": "day", "按月": "month", "按来源池区": "source", "按蛙类型": "type"}[group_by]
    )

    if not sales_df.empty:
        # 根据分组展示
        if group_by == "按天":
            display_df = (sales_df
                          .groupby(["销售日期", "frog_type", "来源池区"])["total_sold"]
                          .sum().reset_index()
                          .rename(columns={"销售日期": "日期", "frog_type": "蛙类型",
                                           "total_sold": "销售数量", "来源池区": "来源池区"}))
        elif group_by == "按月":
            sales_df["月份"] = sales_df["operation_time"].dt.to_period("M")
            display_df = (sales_df
                          .groupby(["月份", "frog_type"])["total_sold"]
                          .sum().reset_index()
                          .rename(columns={"月份": "月份", "frog_type": "蛙类型",
                                           "total_sold": "销售数量"}))
        elif group_by == "按来源池区":
            display_df = (sales_df
                          .groupby(["来源池区", "frog_type"])["total_sold"]
                          .sum().reset_index()
                          .rename(columns={"来源池区": "来源池区", "frog_type": "蛙类型",
                                           "total_sold": "销售数量"}))
        else:  # 按蛙类型
            display_df = (sales_df
                          .groupby("frog_type")["total_sold"]
                          .sum().reset_index()
                          .rename(columns={"frog_type": "蛙类型", "total_sold": "销售数量"}))

        st.dataframe(display_df, use_container_width=True, hide_index=True)

        # 图表
        col_chart1, col_chart2 = st.columns(2)
        with col_chart1:
            if group_by in ("按天", "按月"):
                time_df = (sales_df.groupby("period")["total_sold"]
                           .sum().reset_index())
                fig_trend = px.line(time_df, x="period", y="total_sold",
                                    title="销售趋势", markers=True)
                fig_trend.update_layout(xaxis_title="时间", yaxis_title="数量（只）")
                st.plotly_chart(fig_trend, use_container_width=True,
                                key=f"trend_{pool_area}_{group_by}")
        with col_chart2:
            if group_by == "按蛙类型":
                fig_pie = px.pie(display_df, values="销售数量", names="蛙类型",
                                 title="各蛙类型销售占比")
                st.plotly_chart(fig_pie, use_container_width=True,
                                key=f"pie_{pool_area}")
            else:
                source_df = (sales_df.groupby("来源池区")["total_sold"]
                             .sum().reset_index())
                fig_bar = px.bar(source_df, x="来源池区", y="total_sold",
                                 title="各来源池区销售情况")
                st.plotly_chart(fig_bar, use_container_width=True,
                                key=f"bar_{pool_area}")

        # 详细记录 & 导出
        with st.expander("📋 查看详细销售记录", expanded=False):
            detail_df = (sales_df[["operation_time", "frog_type", "total_sold",
                                   "来源池区", "remarks"]]
                         .rename(columns={"operation_time": "销售时间",
                                          "frog_type": "蛙类型",
                                          "total_sold": "销售数量",
                                          "来源池区": "来源池区",
                                          "remarks": "备注"})
                         .assign(销售时间=lambda df: df["销售时间"].dt.strftime("%Y-%m-%d %H:%M")))
            st.dataframe(detail_df, use_container_width=True, hide_index=True)
            csv = detail_df.to_csv(index=False, encoding="utf-8-sig")
            st.download_button("📥 导出CSV", data=csv,
                               file_name=f"销售记录_{pool_area}_{datetime.now():%Y%m%d}.csv",
                               mime="text/csv",
                               key=f"download_sales_{pool_area}")
    else:
        st.info("在选定时间段内无销售记录")

    # ┌------------------------- 新增销售区域 -------------------------┐
    st.markdown("---")
    st.subheader("💰 新增销售记录")

    # 获取当前池的库存
    inventory = get_pool_frog_inventory(pool_area)
    if not inventory:
        st.warning(f"池区 {pool_area} 暂无库存")
        return

    inventory_dict = {code: qty for code, desc, qty in inventory}

    # 仅显示有库存的可售类型
    frog_types = fetch_frog_types()
    saleable = [(c, d) for c, d in frog_types if c.startswith(("SP_", "ZB_", "SY_"))]
    available_types = [(c, d) for c, d in saleable if inventory_dict.get(c, 0) > 0]
    if not available_types:
        st.warning("该池区无可销售蛙类")
        st.caption("当前库存详情：")
        for code, desc, qty in inventory:
            st.caption(f"- {desc}: {int(qty)} 只")
        return

    with st.form(key=f"sale_form_{pool_area}"):
        col1, col2 = st.columns(2)
        with col1:
            opts = [f"{c} - {d}" for c, d in available_types]
            sel = st.selectbox("成蛙类型", opts, key=f"frog_type_select_{pool_area}")
            selected_frog_type = sel.split(" - ")[0]
            current_stock = inventory_dict[selected_frog_type]
            st.caption(f"📌 当前库存：**{int(current_stock)} 只**")
            qty = st.number_input("销售数量", min_value=1,
                                  max_value=int(current_stock),
                                  key=f"sale_qty_{pool_area}")
            unit_price = st.number_input("单价（元/只）", min_value=0.0, value=0.0,
                                         key=f"unit_price_{pool_area}")
        with col2:
            dt = st.date_input("销售日期", datetime.now(), key=f"sale_date_{pool_area}")
            tm = st.time_input("销售时间", datetime.now().time(), key=f"sale_time_{pool_area}")
            customer = st.text_input("客户", key=f"customer_{pool_area}")
            remarks = st.text_area("备注", placeholder="如：客户特殊要求、运输方式等",
                                   key=f"remarks_{pool_area}")

        uploaded_files = st.file_uploader(
            "📸 上传销售凭证（可多选）",
            type=["jpg", "jpeg", "png", "mp4", "mov"],
            accept_multiple_files=True,
            key=f"media_sale_{pool_area}"
        )

        submitted = st.form_submit_button("销售")
        if submitted:
            if not customer.strip():
                st.error("请输入客户")
            elif qty > current_stock:
                st.error(f"销售数量超过库存！当前最多可售 {int(current_stock)} 只")
            else:
                sale_remarks = f"从 {pool_area} 销售给 {customer}"
                if unit_price > 0:
                    total_amount = qty * unit_price
                    sale_remarks += f"，单价{unit_price}元，总金额{total_amount}元"
                if remarks.strip():
                    sale_remarks += f"。备注：{remarks}"
                ok, msg = record_frog_sale_from_pool(
                    selected_frog_type, qty,
                    datetime.combine(dt, tm),
                    operator.strip(),
                    pool_area,
                    remarks=sale_remarks,
                    media_files=uploaded_files
                )
                if ok:
                    st.success(msg)
                    # 清缓存
                    get_pool_frog_inventory.clear()
                    get_frog_inventory_data.clear()
                    get_sales_statistics.clear()
                    get_sales_data.clear()
                    st.rerun()
                else:
                    st.error(msg)
# ----------------------------- 分析模块（保持不变）----------------------------- #
def render_analysis_module():
    st.header("数据分析与查询")
    st.markdown("---")
    col1, col2 = st.columns(2)
    with col1:
        start_date = st.date_input("开始日期", datetime.now() - timedelta(days=30), key="a_start")
    with col2:
        end_date = st.date_input("结束日期", datetime.now() + timedelta(days=365), key="a_end")  # 包含未来
    start_dt = datetime.combine(start_date, datetime.min.time())
    end_dt = datetime.combine(end_date, datetime.max.time())
    # 批次转化率
    with st.expander("1. 批次转化率分析", expanded=False):
        df = get_batch_conversion_data(start_dt, end_dt)
        if not df.empty:
            st.dataframe(df.rename(columns={
                'batch_no': '批次号', 'pool_no': '孵化池编号', 'input_type': '投入类型',
                'initial_input': '初始投入量', 'input_unit': '投入单位', 'input_date': '投入日期',
                'total_sorted_frog': '累计分拣成蛙', 'conversion_rate': '转化率(%)', 'batch_status': '批次状态'
            }))
            fig = px.bar(df, x='batch_no', y='conversion_rate', color='input_type', title='各批次转化率')
            st.plotly_chart(fig, use_container_width=True)
    # 成蛙库存
    with st.expander("3. 成蛙库存分析", expanded=False):
        df = get_frog_inventory_data()
        if not df.empty:
            st.dataframe(df.rename(columns={
                'frog_type_code': '类型代码', 'frog_type': '类型', 'quantity': '数量', 'pool_area': '池区'
            }))
            fig = px.bar(df, x='frog_type', y='quantity', color='pool_area', title='库存分布')
            st.plotly_chart(fig, use_container_width=True)
    # 销售分析
    with st.expander("4. 销售分析", expanded=False):
        if st.button("🔄 刷新销售数据", key="refresh_sales"):
            get_sales_data.clear()
            st.rerun()
        df = get_sales_data(start_dt, end_dt)
        if df.empty:
            st.info("在所选时间段内无销售记录")
        else:
            def extract_source(remark):
                if pd.isna(remark) or not isinstance(remark, str) or '来自' not in remark:
                    return '未知'
                parts = remark.split(' ')
                return parts[1] if len(parts) > 1 else '未知'
            df['来源'] = df['remarks'].apply(extract_source)
            st.dataframe(df.rename(columns={
                'frog_type_code': '蛙类型代码',
                'frog_type': '蛙类型',
                'total_sold': '销售数量',
                'sale_date': '销售日期',
                'remarks': '备注',
                '来源': '来源池区'
            }), use_container_width=True)
            fig = px.pie(df, values='total_sold', names='来源', title='各来源销售占比')
            st.plotly_chart(fig, use_container_width=True)
    # 孵化池状态
    with st.expander("5. 孵化池状态", expanded=False):
        pools = fetch_incubation_pools()
        if pools:
            df = pd.DataFrame(pools, columns=['池号', '位置', '状态', '批次'])
            st.dataframe(df)
            status_counts = df['状态'].value_counts().reset_index()
            status_counts.columns = ['状态', '数量']
            fig_pie = px.pie(
                status_counts,
                values='数量',
                names='状态',
                title='孵化池状态分布',
                color_discrete_sequence=px.colors.qualitative.Set3
            )
            st.plotly_chart(fig_pie, use_container_width=True)
            fig_bar = px.bar(
                status_counts,
                x='状态',
                y='数量',
                title='各状态池子数量',
                text='数量',
                color='状态',
                color_discrete_sequence=px.colors.qualitative.Pastel
            )
            fig_bar.update_traces(textposition='outside')
            st.plotly_chart(fig_bar, use_container_width=True)
        else:
            st.info("暂无孵化池数据")
def render_pool_detail_module():
    st.header("池区库存详情")
    st.markdown("查看各逻辑池区（如 `自养卵-细皮成蛙池`）的实时库存分布")
    if st.button("🔄 刷新数据"):
        get_frog_inventory_data.clear()
        st.rerun()
    df = get_frog_inventory_data()
    if df.empty:
        st.info("暂无库存数据")
        return
    def parse_pool_area(pool):
        if pool in ["种蛙池", "试验蛙池", "商品蛙池"]:
            return "通用", pool
        elif "-" in pool:
            parts = pool.split("-", 1)
            source = parts[0]
            stage = parts[1]
            return source, stage
        else:
            return "未知", pool
    df[['来源', '阶段']] = df['pool_area'].apply(lambda x: pd.Series(parse_pool_area(x)))
    col1, col2 = st.columns(2)
    with col1:
        sources = ["全部"] + sorted(df['来源'].unique().tolist())
        selected_source = st.selectbox("按来源筛选", sources)
    with col2:
        stages = ["全部"] + sorted(df['阶段'].unique().tolist())
        selected_stage = st.selectbox("按阶段筛选", stages)
    filtered_df = df.copy()
    if selected_source != "全部":
        filtered_df = filtered_df[filtered_df['来源'] == selected_source]
    if selected_stage != "全部":
        filtered_df = filtered_df[filtered_df['阶段'] == selected_stage]
    if filtered_df.empty:
        st.warning("无匹配数据")
        return
    for pool in filtered_df['pool_area'].unique():
        pool_data = filtered_df[filtered_df['pool_area'] == pool]
        total_qty = pool_data['quantity'].sum()
        last_update = pool_data['last_update_time'].max()
        with st.expander(f"📍 {pool} （总计：{int(total_qty)} 只，最后更新：{last_update.strftime('%Y-%m-%d %H:%M') if pd.notna(last_update) else 'N/A'}）", expanded=False):
            st.dataframe(
                pool_data[['frog_type', 'quantity']].rename(columns={
                    'frog_type': '蛙类型',
                    'quantity': '数量（只）'
                }),
                use_container_width=True,
                hide_index=True
            )
def render_inventory_module():
    st.header("📦 进销存管理（独立模式）")
    st.markdown("手动录入物资或蛙类的入库、出库、盘点，不依赖养殖流程")
    operator = st.text_input("操作员", value="admin", key="inv_operator")
    if not operator.strip():
        st.warning("请输入操作员")
        return
    obj_type = st.radio("操作对象", ["🐸 蛙类", "📦 物资"], horizontal=True)
    if obj_type == "🐸 蛙类":
        types = fetch_frog_types()
        type_options = [f"{c} - {d}" for c, d in types if c.startswith(("SP_", "ZB_", "SY_"))]
        item_label = "蛙类型"
        pool_label = "池区（可选）"
    else:
        types = fetch_material_types()
        type_options = [f"{c} - {d} ({u})" for c, d, u in types]
        item_label = "物资类型"
        pool_label = "仓库（可选）"
    if not type_options:
        st.warning(f"未定义{item_label}")
        return
    with st.form("inventory_form"):
        col1, col2 = st.columns(2)
        with col1:
            selected = st.selectbox(item_label, type_options)
            item_code = selected.split(" - ")[0]
            operation = st.selectbox("操作类型", ["入库", "出库", "盘点"])
            quantity = st.number_input("数量", min_value=0.01, step=0.1)
        with col2:
            pool_or_warehouse = st.text_input(pool_label, placeholder="如：自养卵-商品蛙池 或 饲料仓")
            dt = st.date_input("日期", datetime.now())
            tm = st.time_input("时间", datetime.now().time())
            remarks = st.text_area("备注")
        submitted = st.form_submit_button("提交记录")
        if submitted:
            item_type = "frog" if obj_type == "🐸 蛙类" else "material"
            ok, msg = record_inventory_operation(
                item_type=item_type,
                item_code=item_code,
                operation=operation,
                quantity=quantity,
                pool_or_warehouse=pool_or_warehouse,
                operation_time=datetime.combine(dt, tm),
                operator=operator.strip(),
                remarks=remarks
            )
            if ok:
                st.success(msg)
                st.rerun()
            else:
                st.error(msg)
    st.markdown("---")
    st.subheader("当前库存")
    if st.button("🔄 刷新库存"):
        get_frog_inventory_data.clear()
    frog_df = get_frog_inventory_data()
    if not frog_df.empty:
        st.write("🐸 蛙类库存")
        st.dataframe(frog_df.rename(columns={
            'frog_type_code': '类型代码', 'frog_type': '名称', 'quantity': '数量', 'pool_area': '池区'
        }), use_container_width=True)
    with DatabaseConnection() as conn:
        if conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT m.type_code, m.name, m.unit, i.remaining_quantity
                    FROM t_material_inventory i
                    JOIN t_material_type_dict m ON i.material_type_code = m.type_code
                    ORDER BY m.name
                """)
                mats = cur.fetchall()
                if mats:
                    mat_df = pd.DataFrame(mats, columns=['类型代码', '名称', '单位', '数量'])
                    st.write("📦 物资库存")
                    st.dataframe(mat_df, use_container_width=True)
# ----------------------------- 主入口 ----------------------------- #
def run():
    st.set_page_config(page_title="石蛙养殖管理系统", page_icon="🐸", layout="wide")
    st.title("🐸 石蛙养殖管理系统（四来源分离版）")
    if 'db_initialized' not in st.session_state:
        required_tables = ['t_incubation_pool', 't_frog_type_dict', 't_material_type_dict', 't_incubation_batch', 't_batch_sorting_record']
        try:
            with DatabaseConnection() as conn:
                if not conn: st.error("数据库连接失败"); st.stop()
                with conn.cursor() as cur:
                    for tbl in required_tables:
                        cur.execute("SELECT 1 FROM information_schema.tables WHERE table_name = %s", (tbl,))
                        if not cur.fetchone():
                            st.error(f"必要表 {tbl} 不存在"); st.stop()
            st.session_state['db_initialized'] = True
        except Exception as e:
            st.error(f"检查表失败: {e}"); st.stop()
    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "现场操作记录", 
        "数据分析与查询", 
        "📊 池区详情",
        "📦 进销存管理",
        "🔍 多媒体溯源"
    ])
    with tab1: render_operation_module()
    with tab2: render_analysis_module()
    with tab3: render_pool_detail_module()
    with tab4: render_inventory_module() 
    with tab5: render_media_traceability()
if __name__ == "__main__":
    run()