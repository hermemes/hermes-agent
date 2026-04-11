<p align="center">
  <img src="assets/banner.png" alt="Hermemes Agent" width="100%">
</p>

<h1 align="center">Hermemes ☤</h1>

<p align="center">
  <strong>Autonomous BSC KOL Intelligence & Copy-Trade Decision Agent</strong><br/>
  <em>Built on Nous Research Hermes Agent — Self-improving · Always-on · Fully Private</em>
</p>

<p align="center">
  <a href="https://hermemes.xyz"><img src="https://img.shields.io/badge/Website-hermemes.xyz-FFD700?style=for-the-badge" alt="Website"></a>
  <a href="https://x.com/hermemes_"><img src="https://img.shields.io/badge/X-@hermemes__-000000?style=for-the-badge&logo=x&logoColor=white" alt="X / Twitter"></a>
  <a href="https://dorahacks.io/hacker/hermemes"><img src="https://img.shields.io/badge/DoraHacks-hermemes-6C3CE1?style=for-the-badge" alt="DoraHacks"></a>
  <a href="https://github.com/hermemes/hermes-agent/blob/main/LICENSE"><img src="https://img.shields.io/badge/License-MIT-green?style=for-the-badge" alt="MIT License"></a>
  <img src="https://img.shields.io/badge/Chain-BSC-F0B90B?style=for-the-badge&logo=binance&logoColor=black" alt="BNB Smart Chain">
</p>

---

## What is Hermemes?

**Hermemes is a fully autonomous, self-evolving on-chain KOL intelligence brain for BSC.**

Built on the [Nous Research Hermes Agent](https://github.com/NousResearch/hermes-agent) framework, Hermemes runs 24/7 on the BNB Smart Chain, continuously profiling KOL wallets across **25+ quantitative dimensions** and delivering data-driven, actionable copy-trade decisions — not gut feelings.

> *"Stop guessing who to follow. Let the data decide."*

### The Problem

BSC memecoin traders face a consistent set of pain points:

- **Opacity** — no reliable way to distinguish genuine early buyers from coordinated pump-and-dump actors
- **Guesswork** — copy-trade decisions rely on reputation and intuition, not on-chain data
- **No dump prediction** — KOLs have predictable exit patterns; nobody tracks them systematically
- **Fragmented data** — gmgn, debank, and similar tools lack long-term, personalized KOL archives
- **Manual overload** — monitoring 200+ wallets 24/7 is humanly impossible

### The Solution

Hermemes turns the Hermes Agent's closed learning loop, persistent memory, parallel sub-agents, and cron scheduler into a dedicated BSC intelligence engine:

| Capability | Description |
|---|---|
| **Autonomous monitoring** | Deploy once to Modal / Daytona / VPS — runs forever, no laptop needed |
| **Closed learning loop** | After every scan, the KOL-Profiler skill auto-updates its weights and thresholds |
| **Persistent profiles** | Every KOL gets a private, searchable, ever-evolving behavioral archive |
| **Quantified decisions** | One question → structured answer: follow or not, how much BNB, when to exit |

---

## Core Features

### 1 · 25+ Quantitative Dimensions (Auto-Evolving)

#### A — Performance Metrics *(should I follow this KOL?)*

| Metric | Description |
|---|---|
| Win Rate (30d / 90d) | Profitable closed positions ÷ total closed positions |
| Average ROI Multiple | Mean return multiple per trade |
| Total Realized PnL | Cumulative profit in BNB and USD |
| Sharpe / Sortino Ratio | Risk-adjusted return quality |
| Consistency Score | 0–100 composite score penalizing high variance and loss streaks |
| Rug Avoidance Rate | % of positions closed profitably (proxy for rug detection) |
| Unrealized PnL Ratio | Current open position floating P&L |

#### B — Entry Behavior *(how early is this KOL?)*

| Metric | Description |
|---|---|
| Avg / Median Entry MCAP | Preferred market cap range at first buy |
| Hours After Launch | Average entry delay after four.meme token creation |
| Position Size % | Single trade as % of wallet balance |
| Trading Frequency | Active days and trades per day over 30 days |
| Pre-graduation Rate | % of entries made before DEX listing (bonding curve phase) |

#### C — Exit / Dump Behavior *(when will this KOL sell?)*

| Metric | Description |
|---|---|
| Avg / Median Exit Multiple | Mean multiplier at time of sell |
| Dump MCAP Range (P50 / P70) | Market cap range where 50–70%+ is typically sold |
| Avg / Max Hold Days | Typical and maximum position duration |
| First Sell Tranche % | Typical first sell as % of total position |
| Trailing Stop Threshold | Estimated drawdown % from peak that triggers full exit |

#### D — Risk & Position Sizing *(how much should I follow with?)*

| Metric | Description |
|---|---|
| Max Drawdown | Worst historical cumulative loss |
| Kelly Position % | Optimal follow-trade size from Kelly Criterion |
| Wallet Correlation | Trade overlap with other KOLs (co-movement / resonance) |
| Gas Efficiency Score | BSC execution quality metric |

#### E — Composite Decision Output

| Metric | Description |
|---|---|
| Confidence Score | 0–100 weighted composite |
| Risk/Reward Ratio (RRR) | Expected upside ÷ downside |
| KOL Grade | A+ / A / B / C / D |
| Type Label | Early Sniper · Scalper · Mid-Entry · Swing Holder · Momentum |

---

### 2 · Real-Time Decision Engine

**User input:**
```
KOL 0xA1b2... just bought 3 BNB of $HERMEMES on four.meme (current MCAP $180k)
```

**Hermemes output:**
```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🧬  KOL Snapshot  |  0xA1b2...  |  Updated 2h ago
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Type: Early Sniper  |  Grade: A+
Win Rate: 74% (30d) / 71% (90d)
Avg ROI: 6.3x  |  Consistency: 91/100
Preferred Entry MCAP: avg $92k / median $78k
Dump Pattern: avg 8.9x exit, 68% sold between $1.4M–$2.9M

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🎯  Decision  |  $HERMEMES @ $180k MCAP
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
✅ Follow:  STRONG BUY  (Confidence 87/100)
   Similar setups: 81% historical win rate  |  RRR 1:4.2

💰 Size:  1.0–1.5 BNB  (Kelly optimal: 1.0 BNB)

📤 Exit Plan:
   → Sell 40% at 5x  (~$900k MCAP)
   → Sell 50% at 12x (~$2.1M MCAP)
   → Trailing stop 25% on remaining 10%
   ⏰ Max hold: 48 hours

⚠️ Risks:
   • KOL dropped 62% avg after 18x in last 3 trades
   • 68% trade overlap with another top KOL (co-movement risk: medium)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

---

### 3 · Agent Tool Suite (10 Tools)

All tools are natively callable by the Hermes Agent during any conversation or scheduled cron run.

| Tool | Description |
|---|---|
| 🧬 `kol_analyze` | Full 25+ dimension profile for any BSC wallet |
| 🎯 `kol_decision` | Quantified copy-trade decision for a new KOL buy event |
| 📡 `kol_pool_scan` | Batch-scan all wallets in the KOL pool, ranked by confidence |
| 📋 `kol_pool_load` | Load and display the KOL pool by tier |
| 📊 `kol_report` | Generate weekly / monthly KOL pool summary report |
| 🔗 `kol_correlation_matrix` | Pairwise trading correlation across the KOL pool |
| ⚡ `kol_comovement_scan` | Smart-money convergence: tokens multiple KOLs bought together |
| 🔗 `kol_wallet_overlap` | Compare two wallets' trading overlap and time-correlation |
| 🛡️ `token_safety_check` | Full honeypot + rug + tax audit (honeypot.is + GoPlus Security) |
| ⚡ `token_quick_check` | Fast honeypot simulation only (< 2 seconds) |

Plus **4 Web3 EVM tools** via Binance Web3 Connect:
`web3_get_balance` · `web3_get_token_balance` · `web3_get_gas_price` · `web3_get_transaction`

---

### 4 · Token Safety — Pre-Trade Audit

Before generating any copy-trade recommendation, Hermemes automatically audits the target token:

- **honeypot.is** — buy/sell transaction simulation
- **GoPlus Security API** — mint function, pause function, blacklist, whitelist, ownership
- **On-chain** — owner renounced status, top-10 holder concentration, liquidity lock
- **Tax check** — buy tax and sell tax % from simulation

Risk scoring: **0–100** with severity-weighted flags and a plain-language recommendation.

---

### 5 · KOL Correlation & Smart-Money Convergence

```
"3 A+ KOLs all bought $HERMEMES within 4 hours of each other.
 Signal strength: 92/100. Combined: 8.3 BNB."
```

- **Jaccard similarity** — shared token overlap between any two KOL wallets
- **Time-correlation** — how often two KOLs buy within the same 24-hour window
- **Co-movement alerts** — automatically surfaced when 2+ KOLs converge on the same token

---

### 6 · four.meme Integration

Hermemes connects directly to [four.meme](https://four.meme) — the primary BSC meme launchpad:

- Token launch timestamp → compute exact **hours-after-launch** for each KOL entry
- Bonding curve progress at time of entry
- Pre-graduation vs. post-DEX-listing entry rate
- Creator wallet tracking
- Trending / graduating token feed

---

### 7 · Automated Monitoring & Alerts

```
# Register a cron job via the agent
"Scan kol-pool.md every 4 hours and alert me on Telegram when any A-grade
 KOL makes a new buy over 0.5 BNB with confidence > 70"
```

- Cron-based pool scanner (`cron/kol_pool_cron.py`) detects new buys vs. last known state
- Delivers structured alerts to **Telegram, Discord, X** and 11 other platforms
- Alert thresholds configurable via env vars (`KOL_ALERT_MIN_CONFIDENCE`, `KOL_ALERT_MIN_BNB`)

---

## Architecture

```
┌──────────────────────────────────────────────────────────────┐
│                       Hermemes Agent                         │
│  ┌──────────────────────────────────────────────────────┐    │
│  │          Nous Research Hermes Agent Core             │    │
│  │  Closed Loop · Persistent Memory · Cron · Sub-agents│    │
│  └──────────────────────────────────────────────────────┘    │
│                                                              │
│  Data Layer                                                  │
│  ┌─────────────┐ ┌─────────────┐ ┌───────────┐ ┌────────┐   │
│  │  BscScan    │ │DexScreener  │ │ four.meme │ │GoPlus  │   │
│  │  (tx data)  │ │(price/MCAP) │ │(launches) │ │(safety)│   │
│  └─────────────┘ └─────────────┘ └───────────┘ └────────┘   │
│                                                              │
│  Intelligence Layer                                          │
│  ┌─────────────┐ ┌─────────────┐ ┌───────────────────────┐  │
│  │KOL Profiler │ │ Correlation │ │   Token Safety        │  │
│  │25+ metrics  │ │ & Co-move   │ │   honeypot.is + GoPlus│  │
│  └─────────────┘ └─────────────┘ └───────────────────────┘  │
│                                                              │
│  Delivery Layer                                              │
│  ┌──────────────────────────────────────────────────────┐    │
│  │  Telegram · Discord · X · CLI  (14+ platforms)       │    │
│  └──────────────────────────────────────────────────────┘    │
│                                                              │
│  Deployment: Modal · Daytona · VPS ($5/mo)                   │
│  Models: Nous Hermes-3 · Nomos · OpenRouter (200+ models)    │
└──────────────────────────────────────────────────────────────┘
```

| Component | Technology |
|---|---|
| Agent Framework | [Hermes Agent](https://github.com/NousResearch/hermes-agent) (MIT) |
| On-chain Data | BscScan API + BSC JSON-RPC |
| Price & MCAP | DexScreener API |
| Launch Data | four.meme API + on-chain event logs |
| Safety Audit | honeypot.is + GoPlus Security |
| Web3 Connect | Binance Web3 EIP-6963 + WalletConnect v2 |
| Deployment | Modal / Daytona (serverless) or any VPS |
| Models | Nous Hermes-3 / Nomos (priority) · OpenRouter |

---

## Quick Start

### 1. Install Hermes Agent

```bash
curl -fsSL https://raw.githubusercontent.com/hermemes/hermes-agent/main/scripts/install.sh | bash
source ~/.zshrc
hermes
```

### 2. Configure BSC Data Sources

```bash
# Copy and fill in your keys
cp .env.example .env

# Required
BSCSCAN_API_KEY=your_key    # https://bscscan.com/myapikey (free)

# Optional — improves reliability
BSC_RPC_URL=https://bsc-mainnet.nodereal.io/v1/YOUR_KEY
```

### 3. Set Up Your KOL Pool

```bash
cp kol-pool.example.md kol-pool.md
# Edit kol-pool.md — add your KOL wallet addresses by tier
```

### 4. Start the Agent

```bash
hermes
```

Then tell it:
```
Load kol-pool.md, build profiles for all wallets, and set up a cron job
to scan every 4 hours and alert me on Telegram for any new A-grade KOL buy.
```

### 5. Query Decisions On-Demand

From Telegram, Discord, or CLI:
```
KOL 0xA1b2... just bought $HERMEMES on four.meme at $180k MCAP.
My wallet has 10 BNB. Should I follow?
```

---

## KOL Pool Format

See [`kol-pool.example.md`](kol-pool.example.md) for the full template.

```markdown
## Tier A+ — Elite Snipers
- 0xA1b2c3... | Early sniper, 80%+ win rate, sub-100k MCAP entries

## Tier A — Reliable Follow
- 0xB2c3d4... | Mid-entry, consistent 8–15x exits

## Tier B — Watch List
- 0xC3d4e5... | Moderate win rate, selective follow
```

---

## Environment Variables

| Variable | Required | Description |
|---|---|---|
| `BSCSCAN_API_KEY` | **Yes** | BscScan API key — [get free key](https://bscscan.com/myapikey) |
| `BSC_RPC_URL` | No | BSC RPC endpoint (default: public node) |
| `KOL_ALERT_MIN_CONFIDENCE` | No | Min confidence score to trigger alert (default: 65) |
| `KOL_ALERT_MIN_BNB` | No | Min BNB trade size to count as signal (default: 0.3) |
| `KOL_SCAN_INTERVAL_HOURS` | No | Cron scan frequency (default: 4) |

See [`.env.example`](.env.example) for the full list.

---

## Why Hermemes?

| | gmgn / debank | Hermemes |
|---|---|---|
| Dimensions | Static labels | **25+ auto-evolving metrics** |
| Chain focus | Multi-chain generic | **BSC native depth** |
| Decision output | View data only | **Actionable: how much, when to exit** |
| Data ownership | Centralized platform | **Fully private, local-first** |
| Running cost | Monthly subscription | **Serverless — near zero when idle** |
| Learning ability | None | **Closed loop, improves with every scan** |
| Scale | Manual | **200+ KOLs, 24/7 autonomous** |
| Safety checks | None | **Honeypot + rug + tax audit pre-trade** |
| Co-movement | None | **Smart-money convergence detection** |

---

## Web3 Integration

Hermemes integrates the [Binance Web3 Connect EVM-Compatible Provider](https://developers.binance.com/docs/binance-w3w/evm-compatible-provider):

- **EIP-6963** standard — auto-detects Binance Web3 Wallet, MetaMask, and any injected provider
- **WalletConnect v2** — no proprietary SDK required
- Supported networks: **Ethereum · BSC · Polygon · Arbitrum · Base**

---

## Roadmap

- [x] BscScan + DexScreener data pipeline
- [x] 25+ dimension KOL analysis engine
- [x] Quantified copy-trade decision output (Kelly sizing, TP targets, trailing stop)
- [x] four.meme launch timing integration
- [x] KOL correlation matrix & co-movement alerts
- [x] Token safety audit (honeypot.is + GoPlus)
- [x] Cron-based automated pool scanner
- [x] Binance Web3 Connect EIP-6963 wallet integration
- [ ] PancakeSwap v3 LP position tracking
- [ ] On-chain alert via BSC WebSocket subscriptions (real-time, sub-second)
- [ ] KOL leaderboard UI dashboard
- [ ] Community KOL pool sharing (opt-in)
- [ ] Automated backtesting against historical price data

---

## Links

- 🌐 Website: [hermemes.xyz](https://hermemes.xyz)
- 𝕏 Twitter / X: [@hermemes_](https://x.com/hermemes_)
- 🏆 DoraHacks: [dorahacks.io/hacker/hermemes](https://dorahacks.io/hacker/hermemes)
- 📦 Based on: [NousResearch/hermes-agent](https://github.com/NousResearch/hermes-agent)

---

## License

MIT — built on [NousResearch/hermes-agent](https://github.com/NousResearch/hermes-agent)

<p align="center">
  Built with ☤ by <a href="https://hermemes.xyz">Hermemes</a> ·
  <a href="https://x.com/hermemes_">@hermemes_</a> ·
  <a href="https://dorahacks.io/hacker/hermemes">DoraHacks</a>
</p>
