#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""明远阁统一数据底座 —— 基于 akshare（免费开源）。

四类数据，统一 JSON 输出：
  quote       实时行情（现价、涨跌幅、成交量/额、买一卖一）
  kline       历史 K 线（日/周/月，前复权，可指定区间）
  financial   财务数据（财务摘要 + 估值指标）
  macro       宏观经济（GDP、CPI、PPI、M2、LPR）

用法：
  python market_data.py quote 000001 600519
  python market_data.py kline 000001 --period daily --start 20250101 --end 20251020 --adjust qfq
  python market_data.py financial 000001
  python market_data.py macro --items gdp,cpi,ppi,m2,lpr

约定：
  - 成功：{"ok": true, "kind": "...", "data": ..., "akshare_version": "..."}
  - 失败：{"ok": false, "kind": "...", "error": {"type": "...", "message": "..."}}
    type ∈ interface_change | rate_limited | no_data | network | bad_request | unknown
  - 绝不静默返回空：无数据也报 no_data。

已知限制（实测于 akshare 1.19.1，2026-10-23 复核）：
  - stock_zh_a_spot_em / stock_bid_ask_em（东方财富实时）在本机被断连，改用新浪 stock_zh_a_spot。
  - stock_a_indicator_lg 已不存在，估值改用 stock_value_em。
  - stock_zh_a_spot 的代码带市场前缀（sh/sz/bj），筛选时要剥掉。
  - K 线源单位不统一（修复点 1）：
      成交量：东财 stock_zh_a_hist = 手；新浪 stock_zh_a_daily = 股；腾讯 stock_zh_a_hist_tx = 股。
      换手率：东财 = 百分比（如 2.34）；新浪/腾讯 = 小数（如 0.0234）。
      fetch_kline 已统一：volume 一律 = 股，volume_lots = 手，turnover 一律 = 百分比。
  - 新浪/腾讯 K 线源不认 period 参数，永远返回日线（修复点 2）。周/月线由 fetch_kline
    按日线本地聚合（前复权日线可直接聚合成周/月 OHLC，涨跌幅按周期重算）。
"""
import argparse
import json
import sys
import time

import pandas as pd

try:
    import akshare as ak
except Exception as exc:  # noqa: BLE001
    print(json.dumps({"ok": False, "kind": "import", "error": {
        "type": "interface_change", "message": f"akshare 导入失败: {exc}"}}, ensure_ascii=False))
    sys.exit(2)

COLUMN_MAP = {
    "代码": "code", "名称": "name", "最新价": "price", "涨跌幅": "pct_chg",
    "涨跌额": "change", "成交量": "volume", "成交额": "amount",
    "买入": "bid1", "卖出": "ask1", "昨收": "prev_close", "今开": "open",
    "最高": "high", "最低": "low", "时间戳": "time",
    "开盘": "open", "收盘": "close", "振幅": "amplitude",
    "换手率": "turnover", "量比": "volume_ratio",
    "股票代码": "code", "日期": "date",
    "总市值": "total_mv", "流通市值": "float_mv", "PE(TTM)": "pe_ttm",
    "PE(静)": "pe_static", "市净率": "pb", "PEG值": "peg",
    "市销率": "ps", "市现率": "pcf", "当日收盘价": "close", "当日涨跌幅": "pct_chg",
}

MACRO_FUNCS = {
    "gdp": ("macro_china_gdp", "国内生产总值(GDP)"),
    "cpi": ("macro_china_cpi", "居民消费价格指数(CPI)"),
    "ppi": ("macro_china_ppi", "工业生产者出厂价格指数(PPI)"),
    "m2": ("macro_china_money_supply", "货币供应量(M2)"),
    "lpr": ("macro_china_lpr", "贷款市场报价利率(LPR)"),
}


class DataError(Exception):
    def __init__(self, etype, message):
        super().__init__(message)
        self.etype = etype


def _classify(exc):
    msg = str(exc)
    low = msg.lower()
    if any(k in low for k in ("timeout", "timed out", "max retries", "connection",
                              "ssl", "proxy", "remote disconnected", "aborted")):
        return "network"
    if any(k in low for k in ("429", "too many requests", "限流", "频繁")):
        return "rate_limited"
    if any(k in low for k in ("json", "expecting value", "parse", "decode", "keyerror")):
        return "interface_change"
    return "unknown"


def _rename(df):
    df = df.copy()
    df.columns = [str(c) for c in df.columns]
    df = df.rename(columns={k: v for k, v in COLUMN_MAP.items() if k in df.columns})
    # 兜底：不同接口的日期/代码列名不统一（如「数据日期」「股票代码」）
    for col in list(df.columns):
        if col in COLUMN_MAP.values():
            continue
        if "日期" in col and "date" not in df.columns:
            df = df.rename(columns={col: "date"})
        elif "代码" in col and "code" not in df.columns:
            df = df.rename(columns={col: "code"})
    return df


_DATE_COLS = ("date", "TRADE_DATE", "月份", "季度", "统计时间", "数据日期")


def _period_key(series):
    """把各种中文期间（2026年02月份 / 2024年第1-4季度 / 时间戳）转成可比较的数字键。"""
    import re

    def one(v):
        if isinstance(v, (int, float)) and not pd.isna(v):
            return float(v)
        s = str(v)
        if s.isdigit() and len(s) >= 10:
            return float(s)
        m = re.search(r"(\d{4})", s)
        if not m:
            return 0.0
        year = int(m.group(1))
        rest = s[m.end():]
        sub = re.search(r"(\d{1,2})", rest)
        return year * 100 + (int(sub.group(1)) if sub else 0)

    try:
        return series.map(one)
    except Exception:  # noqa: BLE001
        return pd.Series([0.0] * len(series), index=series.index)


def _find_date_col(df):
    for cand in _DATE_COLS:
        if cand in df.columns:
            return cand
    return None


def _format_dates(df):
    """把日期列统一成 YYYY-MM-DD 字符串（兼容 datetime、date、毫秒时间戳）。"""
    for col in list(df.columns):
        if str(col) not in _DATE_COLS and str(col) != "date":
            continue
        series = df[col]
        try:
            if str(series.dtype).startswith("datetime"):
                df[col] = pd.to_datetime(series).dt.strftime("%Y-%m-%d")
                continue
            num = pd.to_numeric(series, errors="coerce")
            if num.notna().mean() > 0.7 and num.dropna().abs().max() > 1e11:
                df[col] = pd.to_datetime(num, unit="ms").dt.strftime("%Y-%m-%d")
                continue
            parsed = pd.to_datetime(series, errors="coerce")
            if parsed.notna().mean() > 0.7:
                df[col] = parsed.dt.strftime("%Y-%m-%d")
        except Exception:  # noqa: BLE001
            continue
    return df


def _records(df, latest=None):
    """统一成 records。latest=N 时按期间倒序取最新 N 条；否则保持接口原顺序。"""
    if df is None:
        raise DataError("no_data", "接口返回 None")
    if len(df) == 0:
        raise DataError("no_data", "接口返回空表")
    df = _rename(df)
    if latest:
        date_col = _find_date_col(df)
        if date_col is not None:
            key = _period_key(df[date_col])
            df = df.assign(**{"_sort": key}).sort_values("_sort", ascending=False)
            df = df.drop(columns=["_sort"])
        df = df.head(latest).reset_index(drop=True)
    df = _format_dates(df)
    return json.loads(df.to_json(orient="records", force_ascii=False))


def _strip_prefix(code):
    code = str(code).strip()
    for p in ("sh", "sz", "bj", "SH", "SZ", "BJ"):
        if code.startswith(p):
            return code[len(p):]
    return code


def fetch_quote(codes):
    wanted = {_strip_prefix(c) for c in codes}
    last_err = None
    # 主：新浪全市场快照（东财实时接口在本机被断连）
    for label, fn in (("sina", ak.stock_zh_a_spot), ("em", ak.stock_zh_a_spot_em)):
        try:
            df = fn()
            if df is None or len(df) == 0:
                raise DataError("no_data", f"{label} 实时行情返回空表")
            df = _rename(df)
            if "code" not in df.columns:
                raise DataError("interface_change", f"{label} 缺少代码列: {list(df.columns)}")
            df["code"] = df["code"].map(_strip_prefix)
            sub = df[df["code"].isin(wanted)]
            if len(sub) == 0:
                raise DataError("no_data", f"{label} 快照里没有: {sorted(wanted)}")
            out = _records(sub)
            for item in out:
                item["source"] = label
                # 盘前/停牌时新浪快照会给 0，用昨收兜底并标记，避免误读成跌停
                try:
                    if float(item.get("price") or 0) == 0 and item.get("prev_close"):
                        item["price_raw"] = item.get("price")
                        item["price"] = item["prev_close"]
                        item["session"] = "pre_open_or_suspended"
                except (TypeError, ValueError):
                    pass
            return out
        except DataError as exc:
            last_err = exc
        except Exception as exc:  # noqa: BLE001
            last_err = DataError(_classify(exc), f"{label}: {type(exc).__name__}: {exc}")
    raise last_err


def _market_prefix(code):
    code = str(code).strip()
    if code.startswith(("sh", "sz", "bj", "SH", "SZ", "BJ")):
        return code.lower()
    if code.startswith(("6", "9")):
        return "sh" + code
    if code.startswith(("4", "8")):
        return "bj" + code
    return "sz" + code


# K 线源成交量单位：em=手，sina/tx=股（实测 amt/(vol*close)：em≈100，sina/tx≈1）
SOURCE_VOL_LOTS = {"em": True, "sina": False, "tx": False}
# K 线源换手率单位：em=百分比(2.34)，sina/tx=小数(0.0234)
SOURCE_TURNOVER_DECIMAL = {"em": False, "sina": True, "tx": True}


def _normalize_kline(rows, source):
    """统一 K 线单位：volume→股（附 volume_lots=手），turnover→百分比。
    单位是源相关的，绝不能按区间长度猜。"""
    vol_lots = SOURCE_VOL_LOTS.get(source, False)
    turn_dec = SOURCE_TURNOVER_DECIMAL.get(source, False)
    for row in rows:
        vol = row.get("volume")
        try:
            vol = float(vol)
        except (TypeError, ValueError):
            vol = None
        if vol is not None:
            row["volume_lots"] = vol if vol_lots else vol / 100.0   # 手
            row["volume"] = vol * 100.0 if vol_lots else vol         # 股
        row["volume_unit"] = "股"
        row["volume_lots_unit"] = "手"
        turn = row.get("turnover")
        try:
            turn = float(turn)
        except (TypeError, ValueError):
            turn = None
        if turn is not None:
            row["turnover"] = turn * 100.0 if turn_dec else turn      # 百分比
        row["turnover_unit"] = "%"
        row["source"] = source
    # 新浪/腾讯源没有 涨跌幅/涨跌额/振幅 列，这里按前后收盘补齐，保证字段齐全
    prev_close = None
    for row in rows:
        clo = row.get("close")
        try:
            clo = float(clo)
        except (TypeError, ValueError):
            clo = None
        if clo is not None and prev_close:
            if row.get("pct_chg") is None:
                row["pct_chg"] = (clo / prev_close - 1.0) * 100.0
            if row.get("change") is None:
                row["change"] = clo - prev_close
            if row.get("amplitude") is None:
                hi, lo = row.get("high"), row.get("low")
                try:
                    row["amplitude"] = (float(hi) - float(lo)) / prev_close * 100.0
                except (TypeError, ValueError, ZeroDivisionError):
                    pass
        prev_close = clo
    return rows


def _resample(rows, freq):
    """把日线聚合成周/月线。open=首 high=高 low=低 close=末，volume/amount/turnover 求和，
    涨跌幅与涨跌额、振幅按周期重算（避免把日线涨跌幅相加）。
    date 取该周期内最后一个实际交易日（避免把不完整的当前周期标成月末/周末的未来日期），
    period_label 保留周期末标签便于核对。"""
    import pandas as pd

    df = pd.DataFrame(rows)
    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values("date").set_index("date")
    period_freq = "W" if freq.startswith("W") else "M"
    df["_td"] = df.index
    per = df.index.to_period(period_freq)
    grp = df.groupby(per)
    agg = grp.agg({"open": "first", "high": "max", "low": "min", "close": "last",
                   "volume": "sum", "amount": "sum", "turnover": "sum"})
    agg["last_trade_date"] = grp["_td"].max()
    agg = agg.dropna(subset=["close"])
    prev_close = agg["close"].shift(1)
    agg["change"] = agg["close"] - prev_close
    agg["pct_chg"] = (agg["close"] / prev_close - 1.0) * 100.0
    agg["amplitude"] = (agg["high"] - agg["low"]) / prev_close * 100.0
    out = []
    for idx, r in agg.iterrows():
        td = r["last_trade_date"]
        td = td.strftime("%Y-%m-%d") if hasattr(td, "strftime") else str(td)[:10]
        item = {
            "date": td,
            "period_label": str(idx),
            "open": None if pd.isna(r["open"]) else float(r["open"]),
            "close": None if pd.isna(r["close"]) else float(r["close"]),
            "high": None if pd.isna(r["high"]) else float(r["high"]),
            "low": None if pd.isna(r["low"]) else float(r["low"]),
            "volume": None if pd.isna(r["volume"]) else float(r["volume"]),
            "volume_lots": None if pd.isna(r["volume"]) else float(r["volume"]) / 100.0,
            "volume_unit": "股", "volume_lots_unit": "手",
            "amount": None if pd.isna(r["amount"]) else float(r["amount"]),
            "turnover": None if pd.isna(r["turnover"]) else float(r["turnover"]),
            "turnover_unit": "%",
            "change": None if pd.isna(r["change"]) else float(r["change"]),
            "pct_chg": None if pd.isna(r["pct_chg"]) else float(r["pct_chg"]),
            "amplitude": None if pd.isna(r["amplitude"]) else float(r["amplitude"]),
        }
        out.append(item)
    return out


def fetch_kline(code, period, start, end, adjust):
    """日/周/月 K 线。统一策略：先取日线（三源回退），需要周/月时本地聚合。
    三源回退：东方财富 → 新浪 → 腾讯（东财偶发断连）。
    修复点：1) 单位统一为股/百分比；2) 新浪/腾讯不认 period，周月由日线聚合。"""
    clean = _strip_prefix(code)
    prefixed = _market_prefix(clean)
    last_err = None
    rows = None
    source = None

    for attempt in range(2):
        try:
            df = ak.stock_zh_a_hist(symbol=clean, period="daily",
                                    start_date=start, end_date=end, adjust=adjust)
            rows, source = _records(df), "em"
            break
        except Exception as exc:  # noqa: BLE001
            last_err = DataError(_classify(exc), f"em: {type(exc).__name__}: {exc}")
            time.sleep(1.0)

    if rows is None:
        for label, func_name in (("sina", "stock_zh_a_daily"), ("tx", "stock_zh_a_hist_tx")):
            fn = getattr(ak, func_name, None)
            if fn is None:
                continue
            try:
                df = fn(symbol=prefixed, start_date=start, end_date=end,
                        adjust=adjust or "qfq")
                rows, source = _records(df), label
                break
            except Exception as exc:  # noqa: BLE001
                last_err = DataError(_classify(exc), f"{label}: {type(exc).__name__}: {exc}")
                time.sleep(1.0)

    if rows is None:
        raise last_err

    _normalize_kline(rows, source)
    if period == "weekly":
        rows = _resample(rows, "W-FRI")
    elif period == "monthly":
        rows = _resample(rows, "ME")
    for row in rows:
        row["period"] = period
        row["source"] = source      # 聚合后 source 会被丢掉，这里补回
    return rows


def fetch_financial(code):
    code = _strip_prefix(code)
    result = {"code": code}
    ok_count = 0
    try:
        result["abstract"] = _records(ak.stock_financial_abstract(symbol=code))
        ok_count += 1
    except DataError as exc:
        result["abstract"] = {"error": {"type": exc.etype, "message": str(exc)}}
    try:
        result["valuation"] = _records(ak.stock_value_em(symbol=code), latest=1)
        ok_count += 1
    except DataError as exc:
        result["valuation"] = {"error": {"type": exc.etype, "message": str(exc)}}
    if ok_count == 0:
        raise DataError("no_data", "财务摘要与估值指标都取不到")
    return result


def fetch_macro(items):
    out = {}
    for key in items:
        func_name, title = MACRO_FUNCS[key]
        fn = getattr(ak, func_name, None)
        if fn is None:
            out[key] = {"error": {"type": "interface_change", "message": f"akshare 没有 {func_name}"}}
            continue
        try:
            out[key] = {"title": title, "rows": _records(fn(), latest=8)}
        except DataError as exc:
            out[key] = {"error": {"type": exc.etype, "message": str(exc)}}
    return out


def main(argv=None):
    parser = argparse.ArgumentParser(description="明远阁统一数据底座 (akshare)")
    sub = parser.add_subparsers(dest="kind", required=True)

    p = sub.add_parser("quote", help="实时行情")
    p.add_argument("codes", nargs="+", help="股票代码，如 000001 600519")

    p = sub.add_parser("kline", help="历史K线")
    p.add_argument("code")
    p.add_argument("--period", default="daily", choices=["daily", "weekly", "monthly"])
    p.add_argument("--start", default="20240101")
    p.add_argument("--end", default="20500101")
    p.add_argument("--adjust", default="qfq", choices=["", "qfq", "hfq"])

    p = sub.add_parser("financial", help="财务与估值")
    p.add_argument("code")

    p = sub.add_parser("macro", help="宏观经济数据")
    p.add_argument("--items", default="gdp,cpi,ppi,m2,lpr")

    args = parser.parse_args(argv)

    try:
        if args.kind == "quote":
            data = fetch_quote(args.codes)
        elif args.kind == "kline":
            data = fetch_kline(args.code, args.period, args.start, args.end, args.adjust)
        elif args.kind == "financial":
            data = fetch_financial(args.code)
        else:
            items = [x.strip() for x in args.items.split(",") if x.strip()]
            unknown = [x for x in items if x not in MACRO_FUNCS]
            if unknown:
                raise DataError("bad_request", f"未知宏观项: {unknown}，可选: {list(MACRO_FUNCS)}")
            data = fetch_macro(items)
        print(json.dumps({"ok": True, "kind": args.kind, "data": data,
                          "akshare_version": ak.__version__}, ensure_ascii=False, default=str))
        return 0
    except DataError as exc:
        print(json.dumps({"ok": False, "kind": args.kind,
                          "error": {"type": exc.etype, "message": str(exc)}}, ensure_ascii=False))
        return 1
    except Exception as exc:  # noqa: BLE001
        print(json.dumps({"ok": False, "kind": args.kind,
                          "error": {"type": _classify(exc),
                                    "message": f"{type(exc).__name__}: {exc}"}}, ensure_ascii=False))
        return 1


if __name__ == "__main__":
    sys.exit(main())
