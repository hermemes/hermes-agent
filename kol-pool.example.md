# Hermemes KOL Pool — 钱包池配置模板

> 将此文件复制为 `kol-pool.md`，填入你要监控的 BSC 钱包地址。
> Hermemes 会自动为每个地址建立动态画像档案，并通过 Cron 任务持续更新。

---

## Tier A+ — 顶级狙击手（最高优先级跟单）

| 地址 | 备注 | 入场风格 |
|------|------|----------|
| 0xAAAA...1111 | 早期狙击型，历史胜率 80%+ | MCAP <100k |
| 0xBBBB...2222 | 低 MCAP 布局，平均 10x+ 出场 | MCAP <200k |

## Tier A — 稳定高胜率（推荐跟单）

| 地址 | 备注 | 入场风格 |
|------|------|----------|
| 0xCCCC...3333 | 中期入场，持仓稳定，分批出场 | MCAP 100k–500k |
| 0xDDDD...4444 | BSC 蓝筹系，持仓周期 3–7 天 | MCAP 300k–1M |
| 0xEEEE...5555 | 多链 KOL，BSC 专注度 70%+ | 混合 |

## Tier B — 参考跟单（选择性跟）

| 地址 | 备注 | 入场风格 |
|------|------|----------|
| 0xFFFF...6666 | 中后期入场，胜率中等 | MCAP 500k–2M |
| 0x1111...7777 | 波段选手，持仓 1–3 天 | 任意 |

## Tier C — 观察池（仅监控，不跟单）

| 地址 | 备注 |
|------|------|
| 0x2222...8888 | 新钱包，数据积累中 |
| 0x3333...9999 | 历史有 rug 嫌疑，需持续观察 |

---

## 配置说明

```yaml
# kol-pool-config.yaml（可选）
scan_interval_hours: 4        # Cron 扫描间隔（小时）
min_trades_for_profile: 10   # 最少历史交易数才建立档案
lookback_days: 90             # 分析历史数据天数
alert_on_new_buy: true        # 发现新买入时立即推送
alert_chains:                 # 推送到的平台
  - telegram
  - discord
min_confidence_to_alert: 70  # 置信度 ≥70 才发送跟单建议
```

---

## 启动监控

将此文件保存为 `kol-pool.md` 后，在 Hermes 中输入：

```
读取 kol-pool.md，为所有钱包建立初始 KOL 画像档案，
启动每 4 小时的 Cron 扫描任务，并在 Telegram 推送新买入警报。
```
