# KOL-Profiler Skill · BSC KOL 行为画像引擎

> **自改进 Skill** — Hermemes 在每次完成 KOL 分析后自动优化此技能的权重和阈值。
> 适用于 Nous Research Hermes Agent 框架。

---

## 技能定位

此技能让 Hermes Agent 具备对 BSC 链上 KOL 钱包进行**深度行为分析、25+ 维度标签化、量化跟单决策**的能力。

每次被调用后，Hermes 会根据实际结果反馈自动修正权重，实现闭环自我优化。

---

## 触发场景

以下任意情况时使用此技能：

- 用户提供一个 BSC 钱包地址，询问是否值得跟单
- 用户报告某 KOL 刚买入某 token，询问决策建议
- Cron 任务触发批量 KOL 池扫描更新
- 用户要求生成 KOL 周报 / 月报
- 系统检测到 KOL 钱包有新的大额买入（>0.5 BNB）

---

## 分析流程

### Step 1 — 数据采集

```python
# 使用 web3_get_balance 确认钱包活跃度
# 调用 BscScan API 拉取近 90 天交易历史
# 调用 DexScreener 获取每笔交易时的实时 MCAP
# 调用 PancakeSwap 获取流动性和价格数据

data_sources = [
    "BSC RPC (余额、持仓)",
    "BscScan API (交易历史、内部交易)",
    "DexScreener (MCAP、价格变化)",
    "PancakeSwap (流动性深度)",
    "four.meme (早期 meme 发行数据)",
]
```

### Step 2 — 25+ 维度计算

按以下顺序计算所有指标，保存到 KOL 档案文件：

**A. 性能表现**
- `win_rate_30d`, `win_rate_90d` — 胜率（盈利交易 / 总交易）
- `avg_roi` — 平均单笔 ROI（倍数）
- `total_pnl_bnb` — 累计已实现 PnL（BNB）
- `sharpe_ratio` — 风险调整收益
- `consistency_score` — 0–100，基于标准差和连续性
- `rug_avoidance_rate` — 成功避开 rug 比例
- `unrealized_pnl_ratio` — 浮盈/浮亏比率

**B. 入场行为**
- `avg_entry_mcap`, `median_entry_mcap` — 入场市值偏好
- `avg_entry_hours_after_launch` — 项目上线后平均入场时间
- `position_size_pct` — 单笔占钱包比例
- `trading_frequency_30d` — 月活跃天数
- `meme_category_winrate` — 分类胜率（animal / food / meta / etc.）

**C. 出场 / Dump 行为**
- `avg_exit_multiplier` — 平均出场倍数
- `typical_sell_tranches` — 分批卖出比例（e.g., 30% at 5x, 50% at 10x）
- `dump_mcap_range_p70` — 70% 清仓时的 MCAP 区间
- `max_hold_days` — 最大持仓时长
- `avg_drawdown_before_sell_pct` — 峰值后平均回落 % 触发大额卖出
- `trailing_stop_threshold` — 触发 trailing stop 的回撤 %

**D. 风险管理**
- `max_drawdown` — 最大历史回撤
- `kelly_position_pct` — Kelly 公式最优仓位比例
- `wallet_correlation` — 与其他 KOL 交易重合度
- `gas_efficiency_score` — BSC Gas/Slippage 执行效率
- `user_style_match_pct` — 与用户偏好的匹配度

**E. 综合决策**
- `confidence_score` — 0–100 跟单置信度
- `rrr` — 预期风险收益比
- `kol_grade` — A+ / A / B / C

### Step 3 — 档案保存

将所有指标保存到持久记忆，格式：

```markdown
# KOL Profile: 0xA1b2...

**最后更新**: 2026-04-11 08:00 UTC
**等级**: A+
**置信度**: 87/100

## 核心指标
- 胜率（30d）: 74%
- 平均 ROI: 6.3x
- 一致性得分: 91/100
...（所有 25+ 维度）

## Dump 行为规律
...

## 历史交易记录摘要（最近 10 笔）
...
```

### Step 4 — 量化决策输出

当用户询问某 KOL 的新买入时，输出以下结构：

```
KOL 画像快照 → 本单决策参考 → 止盈计划 → 风险预警
```

参考格式见主 README 的「示例输出」部分。

---

## 自改进机制

每次完成分析后，执行：

1. **结果追踪**：7/14/30 天后自动回查该 KOL 买入的 token 价格变化
2. **权重校准**：根据实际结果与预测的偏差，调整各维度权重
3. **阈值优化**：自动更新 Dump MCAP 区间、trailing stop 等阈值
4. **日志记录**：将校准记录保存到技能历史，形成进化轨迹

```python
# 自动触发的改进逻辑（伪代码）
def self_improve(kol_address, prediction, actual_result):
    delta = actual_result - prediction
    if abs(delta) > threshold:
        update_weights(kol_address, delta)
        log_improvement(kol_address, delta)
        update_skill_version()
```

---

## 数据源配置

```bash
# 在 hermes config 中设置
BSCSCAN_API_KEY=your_key
BSC_RPC_URL=https://bsc-dataseed.binance.org
DEXSCREENER_BASE_URL=https://api.dexscreener.com/latest/dex
FOUR_MEME_ENABLED=true
```

---

## 注意事项

- 本技能仅提供数据分析和量化参考，**不构成投资建议**
- BSC memecoin 风险极高，任何跟单操作需自行承担风险
- 建议初始跟单仓位不超过单次建议上限的 50%，待数据积累后再逐步调整
- KOL 画像需至少 10 笔历史交易才能形成有效分析

---

*Skill Version: 1.0.0 · Auto-improved by Hermemes*
