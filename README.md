<p align="center">
  <img src="assets/banner.png" alt="Hermemes Agent" width="100%">
</p>

<h1 align="center">Hermemes ☤</h1>

<p align="center">
  <strong>BSC 链上 KOL 行为智能画像与跟单决策 AI 代理</strong><br/>
  <em>Autonomous BSC KOL Intelligence Brain — Built on Nous Research Hermes Agent</em>
</p>

<p align="center">
  <a href="https://hermemes.xyz"><img src="https://img.shields.io/badge/Website-hermemes.xyz-FFD700?style=for-the-badge" alt="Website"></a>
  <a href="https://x.com/hermemes_"><img src="https://img.shields.io/badge/X-@hermemes__-000000?style=for-the-badge&logo=x&logoColor=white" alt="X"></a>
  <a href="https://github.com/hermemes/hermes-agent/blob/main/LICENSE"><img src="https://img.shields.io/badge/License-MIT-green?style=for-the-badge" alt="License: MIT"></a>
  <img src="https://img.shields.io/badge/Chain-BSC-F0B90B?style=for-the-badge&logo=binance&logoColor=black" alt="BSC">
</p>

---

## 产品定位 · What is Hermemes?

**Hermemes 是一款完全自主、自进化的 BSC 链上 KOL 情报大脑。**

它以 [Nous Research Hermes Agent](https://github.com/NousResearch/hermes-agent) 为底层框架，在 BSC 上长期运行，通过**闭环学习机制**持续优化对每个 KOL 的行为标签、打分体系和 dump 习惯预测。

用户只需输入一个 KOL 钱包池（初始 200 个），Hermemes 就会自动：

- 📡 **实时/定时**拉取链上交易数据（每 4 小时 Cron 扫描）
- 🏷️ **精细化标签化**（25+ 量化维度，自动进化）
- 🎯 **给出量化跟单建议**（跟不跟、跟多少 BNB、止盈止损计划）
- 🧠 **越用越准**（闭环自我改进，每次分析后自动优化 KOL-Profiler 技能）

> Hermemes 不是一次性工具，而是越跑越聪明的个人专属 AI 伙伴，部署在云端后几乎零维护，闲置成本极低。

---

## 痛点与解决方案 · Problem & Solution

### 当前痛点

| 痛点 | 描述 |
|------|------|
| 🔒 行为透明度低 | 难判断哪些是真实早期买入、哪些是后期收割 |
| 🤔 靠感觉跟单 | 缺乏量化数据，"跟还是不跟"全凭经验 |
| ⏰ Dump 时机难预测 | KOL 历史清仓规律无法自动总结 |
| 📊 数据碎片化 | gmgn 等平台数据不全面，无长期个性化档案 |
| 👀 监控成本高 | 200 个 KOL 池子不可能 24/7 人工盯盘 |

### Hermemes 方案

Hermemes 将 Hermes Agent 的**闭环学习 + 持久记忆 + 子代理并行 + Cron 定时 + 代码执行能力**，完整适配到 BSC 生态：

- **自主运行**：部署到 Modal/Daytona/VPS 后 24/7 云端运行，无需本地常开
- **闭环学习**：每次分析新交易后，自动创建/优化 `KOL-Profiler` 技能，越用越准
- **个性化档案**：为池内每个 KOL 建立独立动态"行为画像文件"（25+ 维度）
- **量化决策**：一句提问，秒回清晰可执行的跟单建议

---

## 核心功能 · Core Features

### 4.1 KOL 池自主扫描与更新

- 支持 200+ 自定义 BSC 钱包地址池（`kol-pool.md`）
- Cron 定时（默认每 4 小时）批量拉取最新交易、持仓、PnL
- 子代理并行分析，高效处理大规模钱包池

### 4.2 精细化标签体系（25+ 量化维度 · 动态进化）

#### A. 性能表现指标（决定"该不该跟"）

| 维度 | 说明 |
|------|------|
| **胜率 Win Rate** | 过去 30/90 天盈利交易占比 |
| **平均 ROI** | 单笔交易平均回报倍数 |
| **总实现 PnL** | 累计已实现利润（BNB / USD）|
| **风险调整收益** | Sharpe / Sortino Ratio |
| **一致性得分** | Consistency Score（0–100）|
| **Rug Avoidance Rate** | 成功避开 rug 项目比例 |
| **未实现 PnL 比率** | 当前持仓浮盈/浮亏 |

#### B. 入场行为指标（评估信号质量）

| 维度 | 说明 |
|------|------|
| **入场 MCAP 偏好** | 平均/中位入场市值区间 |
| **入场时机** | 项目上线后平均小时数 |
| **仓位占用比例** | 单笔入场占用钱包总资产 % |
| **交易频率** | 过去 30 天活跃天数 / 日均交易笔数 |
| **专项偏好** | 对某类 meme 的历史胜率 |

#### C. 出场 / Dump 行为指标（回答"什么时候跑"）

| 维度 | 说明 |
|------|------|
| **平均出场倍数** | 历史平均卖出时的倍数 |
| **分批卖出模式** | 典型 tranche 比例 |
| **Dump MCAP 区间** | 70%+ 清仓最常出现的市值范围 |
| **最大持仓时长** | 买入到完成 70% 出货的平均/最长天数 |
| **峰值后回落阈值** | 历史最高点后平均回落 % 时开始大额卖出 |
| **Trailing Stop 习惯** | 回撤百分比触发清仓阈值 |

#### D. 风险 & 仓位管理指标（决定"跟多少"）

| 维度 | 说明 |
|------|------|
| **最大回撤** | Max Drawdown |
| **Kelly 仓位建议** | 基于历史胜率和赔率自动计算最优跟单仓位 % |
| **钱包相关性** | 与其他 KOL/鲸鱼的交易重合度 |
| **Gas / Slippage 效率** | BSC 特有执行力指标 |
| **跟单匹配度** | 与用户历史偏好匹配百分比（0–100%）|

#### E. 综合决策指标（最终输出）

| 维度 | 说明 |
|------|------|
| **跟单置信度** | Confidence Score（0–100）|
| **预期风险收益比** | RRR（Risk/Reward Ratio）|
| **整体 KOL 等级** | A+ / A / B / C |

> **标签进化机制**：每完成一次 Cron 扫描或用户反馈跟单结果，Hermemes 自动更新以上所有指标，形成专属 KOL 动态画像。

---

### 4.3 实时跟单决策引擎 · 示例输出

**用户输入：**
```
KOL 0xA1b2... 刚在 four.meme 买了 3 BNB 的 $HERMEMES（当前 MCAP 180k）
```

**Hermemes 输出：**

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🧬 KOL 画像快照（最新更新 2 小时前）
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
类型：早期狙击型（胜率 74%）
入场偏好：MCAP <250k（历史平均入场 92k）
Dump 习惯：平均 8.9x 出场，最常在 1.4M–2.9M 完成 68% 清仓
胜率 / 平均 ROI：过去 30 天 74% / +6.3x
一致性得分：91/100

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🎯 本单量化决策参考
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
✅ 该不该跟：强烈推荐跟单（置信度 87/100）
   历史类似入场场景胜率 81%，RRR 1:4.2

💰 跟多少：建议 1–1.5 BNB（占当前钱包约 30%）
   最优仓位建议：1 BNB（Kelly 公式）

📤 什么时候跑（详细止盈计划）：
   → 5x 前跑 40%（约 MCAP 900k）
   → 12x 前跑剩余 50%（约 MCAP 2.1M）
   → 剩余 10% 设 25% 回撤 trailing stop
   ⏰ 最大建议持仓：48 小时

⚠️ 风险预警：
   该 KOL 过去 3 次在 18x 后平均回落 62%
   当前与另一顶级 KOL 交易重合度 68%（共振风险中等）
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

### 4.4 多平台推送与交互

- Telegram / Discord / X 等 14+ 平台实时警报
- 支持语音模式、子代理并行分析
- 自然语言提问，即时返回结构化决策

### 4.5 记忆与报告

- 每个 KOL 一份持久档案（全文搜索可追溯历史）
- 自动生成「KOL 池周报 / 月报」
- 跟单结果反馈闭环，自动校准标签精度

### 4.6 技能自改进

Hermes Agent 原生能力：自动生成 BSC 专用 `KOL-Profiler` 技能，随每次分析不断优化标签精度和评分权重。

---

## 技术架构 · Tech Stack

```
┌─────────────────────────────────────────────────────────┐
│                    Hermemes Agent                       │
│  ┌─────────────────────────────────────────────────┐   │
│  │           Nous Research Hermes Agent             │   │
│  │   闭环学习 · 持久记忆 · 子代理并行 · Cron 定时  │   │
│  └─────────────────────────────────────────────────┘   │
│                                                         │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  │
│  │  BSC RPC     │  │ BscScan API  │  │DexScreener   │  │
│  │  数据采集     │  │  交易历史     │  │ 价格/MCAP    │  │
│  └──────────────┘  └──────────────┘  └──────────────┘  │
│                                                         │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  │
│  │KOL-Profiler  │  │ Web3 Tools   │  │  Memory DB   │  │
│  │  Skill (自进化)│  │  (EVM 查询)  │  │  持久画像档案  │  │
│  └──────────────┘  └──────────────┘  └──────────────┘  │
│                                                         │
│  ┌──────────────────────────────────────────────────┐   │
│  │  Deployment: Modal · Daytona · VPS ($5/mo)       │   │
│  │  Models: Nous Hermes-3 · Nomos · OpenRouter      │   │
│  └──────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────┘
```

| 组件 | 技术 |
|------|------|
| **底层框架** | [Hermes Agent](https://github.com/NousResearch/hermes-agent)（MIT 开源）|
| **区块链适配** | BSC RPC + web3.py + BscScan / DexScreener / PancakeSwap |
| **Web3 工具** | `web3_get_balance` · `web3_get_token_balance` · `web3_get_gas_price` · `web3_get_transaction` |
| **部署方式** | Modal / Daytona（Serverless）或低成本 VPS |
| **模型** | Nous Hermes-3 / Nomos 系列（优先）|
| **安全** | 容器隔离、命令审批、授权机制 |
| **推送** | Telegram · Discord · X 等 14+ 平台 |

---

## 快速上手 · Quick Start

### 1. 安装 Hermes Agent

```bash
curl -fsSL https://raw.githubusercontent.com/hermemes/hermes-agent/main/scripts/install.sh | bash
source ~/.zshrc   # 或 ~/.bashrc
hermes            # 启动
```

### 2. 配置 BSC 数据源

```bash
hermes config set BSC_RPC_URL https://bsc-dataseed.binance.org
hermes config set BSCSCAN_API_KEY your_api_key_here
hermes config set DEXSCREENER_ENABLED true
```

### 3. 导入 KOL 钱包池

创建 `kol-pool.md`（参考 [kol-pool.example.md](kol-pool.example.md)），然后：

```bash
hermes             # 进入对话
> 读取 kol-pool.md，为所有钱包创建初始 KOL 画像档案，并启动每 4 小时的 Cron 定时扫描任务
```

### 4. 开启自主运行

```bash
hermes gateway setup    # 配置 Telegram / Discord
hermes gateway start    # 启动消息网关
```

### 5. 日常决策

在 Telegram / Discord 直接发送：
```
KOL 0xA1b2... 刚买了 $XXX，现在 MCAP 150k，该跟吗？
```

---

## KOL 池配置 · KOL Pool Format

参考 [`kol-pool.example.md`](kol-pool.example.md)：

```markdown
# KOL Pool

## Tier A — 顶级狙击手
- 0xA1b2c3d4... | 备注: 早期狙击型，胜率高，低 MCAP 入场
- 0xB2c3d4e5... | 备注: 蓝筹系 KOL，稳健，持仓周期长

## Tier B — 稳定跟单
- 0xC3d4e5f6... | 备注: 中期入场，8-15x 出场习惯
```

---

## 竞争优势 · Why Hermemes

| 对比维度 | 传统工具（gmgn / debank） | Hermemes |
|----------|--------------------------|----------|
| 标签体系 | 固定，手动更新 | **25+ 维度，自动进化** |
| 链上专注 | 多链泛化 | **BSC 原生深度** |
| 决策输出 | "看数据"为主 | **量化建议：跟多少、什么时候跑** |
| 数据所有权 | 中心化平台 | **完全私有，数据不出本地** |
| 运行成本 | 月订阅费 | **Serverless，闲置几乎零费用** |
| 学习能力 | 无 | **闭环自改进，越用越准** |
| 监控规模 | 手动盯盘 | **24/7 自主，200+ KOL 并行** |

---

## Web3 集成 · Binance Web3 Connect

Hermemes 原生集成 [Binance Web3 Connect EVM-Compatible Provider](https://developers.binance.com/docs/binance-w3w/evm-compatible-provider)，支持：

- EIP-6963 标准钱包自动识别（Binance Web3 Wallet · MetaMask · 所有主流钱包）
- WalletConnect v2 — 无需专有 SDK
- 链上工具：`web3_get_balance` · `web3_get_token_balance` · `web3_get_gas_price` · `web3_get_transaction`
- 支持网络：Ethereum · BSC · Polygon · Arbitrum · Base

---

## 路线图 · Roadmap

- [x] 基础 EVM 链上查询工具（BSC / ETH / Polygon / Arbitrum / Base）
- [x] Landing Page Web3 Connect 集成
- [x] Binance Web3 EIP-6963 钱包连接
- [ ] KOL-Profiler Skill（BSC 专用，自改进）
- [ ] BscScan / DexScreener 数据适配器
- [ ] KOL 池批量分析 + Cron 自动扫描
- [ ] 量化决策引擎（25+ 维度打分模型）
- [ ] Telegram / Discord 实时警报推送
- [ ] 周报 / 月报自动生成
- [ ] KOL 等级动态排行榜（A+ / A / B / C）
- [ ] PancakeSwap 实时持仓追踪

---

## 许可证 · License

MIT License — 基于 [NousResearch/hermes-agent](https://github.com/NousResearch/hermes-agent) 构建

---

<p align="center">
  Built with ☤ by <a href="https://hermemes.xyz">Hermemes</a> · 
  <a href="https://x.com/hermemes_">@hermemes_</a> · 
  Powered by <a href="https://nousresearch.com">Nous Research</a>
</p>
