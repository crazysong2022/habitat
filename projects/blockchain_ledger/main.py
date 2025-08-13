# projects/blockchain_ledger/main.py
"""
项目：区块链防篡改记账系统（修复哈希校验逻辑）
功能：收入/支出记录，通过哈希链保证不可篡改，支持完整性验证
"""

import streamlit as st
import pandas as pd
import hashlib
import json
import os
from datetime import datetime
from typing import Dict, List

# -----------------------------
# 命名空间（防止组件 key 冲突）
# -----------------------------
NS = "ledger_blockchain"

# -----------------------------
# 区块类定义（不信任任何外部 hash）
# -----------------------------
class Block:
    def __init__(self, index: int, timestamp: str, data: Dict, previous_hash: str, stored_hash: str = None):
        self.index = index
        self.timestamp = timestamp
        self.data = data
        self.previous_hash = previous_hash
        self.stored_hash = stored_hash  # 文件中保存的 hash（仅用于对比）

    def compute_hash(self) -> str:
        """根据当前内容计算 SHA-256 哈希"""
        block_content = f"{self.index}{self.timestamp}{json.dumps(self.data, sort_keys=True)}{self.previous_hash}"
        return hashlib.sha256(block_content.encode('utf-8')).hexdigest()

    def to_dict(self) -> dict:
        """导出为字典（用于保存）"""
        return {
            "index": self.index,
            "timestamp": self.timestamp,
            "data": self.data,
            "previous_hash": self.previous_hash,
            "hash": self.stored_hash or self.compute_hash()
        }


# -----------------------------
# 账本区块链类（强化校验逻辑）
# -----------------------------
class BlockchainLedger:
    def __init__(self, data_file: str = "data/blockchain_ledger.json"):
        self.data_file = data_file
        self.chain: List[Block] = []
        self._ensure_data_dir()
        self.load_chain()

    def _ensure_data_dir(self):
        os.makedirs(os.path.dirname(self.data_file), exist_ok=True)

    def create_genesis_block(self) -> Block:
        data = {
            "type": "系统",
            "amount": 0.0,
            "account": "系统",
            "desc": "创世区块，链的起点"
        }
        computed_hash = hashlib.sha256(
            f"0{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}{json.dumps(data, sort_keys=True)}0".encode('utf-8')
        ).hexdigest()
        return Block(
            index=0,
            timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            data=data,
            previous_hash="0",
            stored_hash=computed_hash
        )

    def load_chain(self):
        if not os.path.exists(self.data_file):
            self.chain = [self.create_genesis_block()]
            self.save_chain()
            st.info("📘 新账本已创建：创世区块已生成。")
            return

        try:
            with open(self.data_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            self.chain = []

            for item in data: 
                block = Block(
                    index=item["index"],
                    timestamp=item["timestamp"],
                    data=item["data"],
                    previous_hash=item["previous_hash"],
                    stored_hash=item["hash"]
                )
                computed = block.compute_hash()
                if computed != item["hash"]:
                    st.error(f"🚨 区块 {block.index} 的哈希不匹配！内容可能已被篡改！")
                self.chain.append(block)

            st.success(f"✅ 已加载 {len(self.chain) - 1} 条账目记录。")

        except Exception as e:
            st.error(f"❌ 加载账本失败：{e}")

    def save_chain(self):
        try:
            with open(self.data_file, 'w', encoding='utf-8') as f:
                json.dump([b.to_dict() for b in self.chain], f, ensure_ascii=False, indent=2)
        except Exception as e:
            st.error(f"❌ 保存账本失败：{e}")

    def add_entry(self, entry_data: Dict) -> bool:
        last_block = self.chain[-1]
        new_index = last_block.index + 1
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # 创建新区块（stored_hash 由 compute_hash 生成）
        new_block = Block(
            index=new_index,
            timestamp=timestamp,
            data=entry_data,
            previous_hash=last_block.compute_hash()  # 使用真实计算的哈希
        )
        # 注意：stored_hash 就是 compute_hash() 的结果
        new_block.stored_hash = new_block.compute_hash()

        self.chain.append(new_block)
        self.save_chain()
        return True

    def is_intact(self) -> bool:
        """完全重新验证账本完整性，不依赖任何缓存值"""
        if not self.chain:
            return True

        # 1. 验证创世块
        genesis = self.chain[0]
        if genesis.index != 0 or genesis.previous_hash != "0":
            st.error("❌ 创世区块结构异常：index 不为 0 或 previous_hash 不为 '0'")
            return False

        computed_genesis_hash = genesis.compute_hash()
        if computed_genesis_hash != genesis.stored_hash:
            st.error("❌ 创世区块存储的哈希与内容不匹配")
            return False

        # 2. 验证后续区块（链式校验）
        prev_computed_hash = computed_genesis_hash  # 上一个区块实际计算出的哈希

        for i in range(1, len(self.chain)):
            block = self.chain[i]

            # 检查前向链接
            if block.previous_hash != prev_computed_hash:
                st.error(f"❌ 区块 {i} 的 previous_hash 不等于前一个区块的实际哈希")
                return False

            # 检查当前区块哈希一致性
            computed_hash = block.compute_hash()
            if computed_hash != block.stored_hash:
                st.error(f"❌ 区块 {i} 存储的哈希与内容不匹配")
                return False

            # 更新 prev_computed_hash
            prev_computed_hash = computed_hash

        return True

    def to_dataframe(self) -> pd.DataFrame:
        records = []
        for block in self.chain:
            if block.index == 0:
                continue  # 跳过创世块
            records.append({
                "序号": block.index,
                "时间": block.timestamp,
                "类别": block.data["type"],
                "账户": block.data["account"],
                "金额": f"¥ {block.data['amount']:,.2f}",
                "说明": block.data["desc"],
                "哈希片段": block.stored_hash[:8] + "..." if block.stored_hash else "?"
            })
        return pd.DataFrame(records)


# -----------------------------
# 入口函数（被 client.py 调用）
# -----------------------------
def run():
    st.subheader("🔐 区块链记账系统 | 防篡改 · 可追溯 · 可验证")
    st.markdown("""
    > 每一笔账目都通过 **密码学哈希链** 连接，任何修改都会破坏链条，立即暴露。
    >
    > 📌 本系统不提供删除或编辑功能 —— 因为真实世界中的审计，不该允许“擦掉历史”。
    """)
    st.warning("⚠️ 提示：账本存储于服务器端文件，防篡改基于哈希链。建议定期导出并离线备份。")

    # 初始化账本
    ledger = BlockchainLedger(data_file="data/blockchain_ledger.json")

    # -----------------------------
    # 添加新账目
    # -----------------------------
    st.markdown("### 📝 添加新账目")
    col1, col2 = st.columns(2)
    with col1:
        trans_type = st.selectbox("类型", ["收入", "支出", "转账", "其他"], key=f"{NS}_type")
        account = st.text_input("账户/来源", placeholder="如：现金、招商银行、支付宝", key=f"{NS}_account")
    with col2:
        amount = st.number_input("金额", min_value=0.01, step=0.01, format="%.2f", key=f"{NS}_amount")
        desc = st.text_input("说明", placeholder="例如：客户A付款、办公用品采购", key=f"{NS}_desc")

    if st.button("✅ 提交记账", key=f"{NS}_submit"):
        if not account.strip():
            st.error("请填写账户信息")
        elif amount <= 0:
            st.error("金额必须大于 0")
        else:
            data = {
                "type": trans_type,
                "amount": round(float(amount), 2),
                "account": account.strip(),
                "desc": desc.strip() or "无说明"
            }
            if ledger.add_entry(data):
                st.success(f"✅ 第 {ledger.chain[-1].index} 笔账目已上链！")
                st.balloons()

    st.markdown("---")

    # -----------------------------
    # 查看账本
    # -----------------------------
    st.markdown("### 📚 账本记录")
    df = ledger.to_dataframe()

    if df.empty:
        st.info("暂无账目记录，请添加第一笔。")
    else:
        st.dataframe(df, use_container_width=True)

        # 统计
        raw_data = pd.DataFrame([
            {**b.data, "amount": float(b.data["amount"])}
            for b in ledger.chain[1:]
        ])
        total_in = raw_data[raw_data["type"] == "收入"]["amount"].sum()
        total_out = raw_data[raw_data["type"] == "支出"]["amount"].sum()
        balance = total_in - total_out

        c1, c2, c3 = st.columns(3)
        c1.metric("总收入", f"¥ {total_in:,.2f}")
        c2.metric("总支出", f"¥ {total_out:,.2f}")
        c3.metric("当前余额", f"¥ {balance:,.2f}")

    st.markdown("---")

    # -----------------------------
    # 完整性验证
    # -----------------------------
    st.markdown("### 🔍 安全验证")
    if st.button("🔍 立即验证账本完整性", key=f"{NS}_validate"):
        with st.spinner("正在逐块校验..."):
            if ledger.is_intact():
                st.success("✅ 账本完整：所有区块哈希匹配，未发现篡改！")
            else:
                st.error("💥 警告：账本已被篡改！请立即审计数据源！")

    # -----------------------------
    # 数据导出（只读）
    # -----------------------------
    if not df.empty:
        csv = df.to_csv(index=False)
        st.download_button(
            label="📤 导出账本（CSV，仅查看用）",
            data=csv,
            file_name=f"ledger_export_{datetime.now().strftime('%Y%m%d_%H%M')}.csv",
            mime="text/csv",
            key=f"{NS}_export_csv"
        )

    st.caption("💡 提示：即使手动修改 JSON 文件中的金额，验证功能也会立刻发现哈希断裂。")