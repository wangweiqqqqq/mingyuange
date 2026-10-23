# 明远阁 · 数据底座（akshare）

一个统一入口，四类数据，全部输出 JSON。所有 Bot 都从这里取数，不要各写一套。

## 环境

- Python：`D:\明远阁\.venv\Scripts\python.exe`（Python 3.12，独立 venv，不动团队共用运行时）
- akshare：**1.19.1**（实测可用）
- 依赖：pandas 3.0.6 / numpy 2.5.4 / requests / lxml / beautifulsoup4 等，随 venv 安装

首次安装（已经装好，换机才需要）：

```powershell
$py = 'C:\Users\ZhuanZ1\.dsh\dsh-runtimes\dsh-primary-runtime\dependencies\python\python.exe'
& $py -m venv 'D:\明远阁\.venv'
& 'D:\明远阁\.venv\Scripts\python.exe' -m pip install akshare
```

## 用法

```powershell
$PY = 'D:\明远阁\.venv\Scripts\python.exe'
$S  = 'D:\明远阁\market_data.py'

# 1) 实时行情（可多只）
& $PY $S quote 000001 600519

# 2) 历史K线：日/周/月，前复权
& $PY $S kline 000001 --period daily --start 20250101 --end 20251020 --adjust qfq
& $PY $S kline 000001 --period weekly --start 20250101 --end 20251020 --adjust qfq   # 已是真周线
& $PY $S kline 000001 --period monthly --start 20250101 --end 20251020 --adjust qfq  # 已是真月线

# 3) 财务摘要 + 估值指标
& $PY $S financial 000001

# 4) 宏观：GDP / CPI / PPI / M2 / LPR
& $PY $S macro --items gdp,cpi,ppi,m2,lpr
```

输出约定：

```json
{"ok": true, "kind": "kline", "data": [...], "akshare_version": "1.19.1"}
{"ok": false, "kind": "kline", "error": {"type": "network", "message": "..."}}
```

`error.type` 取值：`interface_change`（接口改名/返回结构变了）、`rate_limited`（限流）、`no_data`（无数据）、`network`（网络/断连）、`bad_request`（参数错）、`unknown`。

**没有静默空返回**：取不到数据一定报错，不会给你一个空列表让你以为是「没有行情」。

## 数据源与坑（都是实测结论）

| 类别 | 用的接口 | 备注 |
|---|---|---|
| 实时行情 | `stock_zh_a_spot`（新浪全市场快照）→ 失败回落 `stock_zh_a_spot_em` | 东财实时接口在本机长期 `RemoteDisconnected`，新浪稳定 |
| 历史K线 | `stock_zh_a_hist`（东财）→ `stock_zh_a_daily`（新浪）→ `stock_zh_a_hist_tx`（腾讯） | 东财会间歇性断连，已做两级回退；周/月线由日线本地聚合 |
| 财务 | `stock_financial_abstract`（新浪，80 行 × 多报告期） | `stock_a_indicator_lg` 在 1.19.1 已删除 |
| 估值 | `stock_value_em`（取最新一行） | 含 PE(TTM)/PE(静)/PB/PS/PCF/PEG/总市值/流通市值 |
| 宏观 | `macro_china_gdp/cpi/ppi/money_supply/lpr` | 各取最新 8 期 |

字段单位（**脚本已归一化，跨源可直接比较**）：

- `volume`：**一律是股**。另有 `volume_lots`（手，1 手 = 100 股）与 `volume_unit`/`volume_lots_unit` 标注。
- `amount`：元。
- `turnover`：**一律是百分比**（2.34 表示 2.34%），另有 `turnover_unit="%"`。
- `pct_chg` / `change` / `amplitude`：百分比 / 元 / 百分比。新浪/腾讯源本身没有这三列，脚本按前后收盘补齐。
- 周/月线多两个字段：`period`（`daily|weekly|monthly`）、`period_label`（周期末标签，如 `2026-10-19/2026-10-25`）。`date` 取**该周期最后一个实际交易日**，不完整周/月不会标成未来日期。
- 周/月线 `volume`/`amount`/`turnover` 为周期内求和，`pct_chg`/`change`/`amplitude` 按周期重算（**不是日线值相加**）。
- `total_mv` / `float_mv`：元。
- 宏观：CPI/PPI 是「上年同月=100」的指数，同比增速在 `全国-同比增长` / `当月同比增长` 字段里。
- 宏观数据有发布滞后：本机实测 CPI/PPI/M2 最新只到 2026-02，GDP 最新是 2024 年年度值——**用之前先看日期，别当成当月数据**。

盘前/停牌的坑：

- 新浪快照在开盘前会给 `price=0`、`pct_chg=0`。脚本会把 `prev_close` 填进 `price`，并打上 `session: "pre_open_or_suspended"` 和 `price_raw: 0`。看到这个标记就说明这是昨收价，不是现价。

## 变更记录

- **2026-10-23（本次）**：修掉两个数据正确性 bug，原文件备份为 `market_data.py.bak-20261023`。
  1. **周/月线返回的是日线**：新浪/腾讯源不认 `period` 参数、永远返回日线。现在 `fetch_kline` 统一先取日线，需要周/月时本地聚合（聚合校验：同一区间周线 volume 合计 = 日线合计，相对差 0.000%）。
  2. **成交量/换手率单位随数据源漂移**：东财=手、新浪=股、**腾讯也是股**（原注释误写成手）；换手率东财=百分比、新浪/腾讯=小数。现在按源归一化：`volume`=股、`volume_lots`=手、`turnover`=百分比。
- 2026-10-23 早间：搭出四类数据 + 文档 + 样例。

## 改接口时改哪里

| 症状 | 改这里 |
|---|---|
| 某类数据整类报 `interface_change` | `market_data.py` 里 `fetch_*` 对应的 `ak.xxx` 函数名 |
| 字段名变了、输出里出现中文键 | `COLUMN_MAP`（顶部）加一条映射 |
| 加了新数据源的回退顺序 | 对应 `fetch_*` 里的 `for label, ...` 列表 |
| 某源成交量单位变了 | `fetch_kline` 上方的 `SOURCE_VOL_LOTS` / `SOURCE_TURNOVER_DECIMAL` 两个字典 |
| 周/月聚合口径要变 | `fetch_kline` 里的 `_resample()` |
| 新增一类数据 | 加 `fetch_xxx` + `sub.add_parser("xxx")` + `main()` 里的分支 |

## 样例

`samples/` 下是真实返回（2026-10-23 实测）：

- `quote.json`：600519 贵州茅台 1318.49（盘前为昨收）、000001 平安银行 11.30
- `kline.json`：000001 日线 30 根，2025-09-01 收 11.03 → 2025-10-20 收 10.82（新浪前复权）
- `financial.json`：平安银行财务摘要 80 行；估值 PE(TTM) 5.05、PB 0.468、总市值 2192.9 亿（2026-10-22）
- `macro.json`：GDP 2024 年 134.8 万亿（+5.0%）、CPI 2026-02 为 101.3（+1.3%）、PPI 99.1（-0.9%）、M2 349.2 万亿（+9.0%）、LPR 2026-03-20 一年 3.0% / 五年 3.5%

## 规矩

- 分析结论里引用的每个数字，都要能追到这里的哪条命令、哪一期数据。
- 数字查不到就说查不到，不许用「大概」「约」编。
- 只做分析研究，不给买卖指令，不承诺收益。