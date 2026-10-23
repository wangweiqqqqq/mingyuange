# -*- coding: utf-8 -*-
"""今日板块强弱：多个数据源依次尝试，输出涨幅前/后板块与涨停个股名单。"""
import pandas as pd

pd.set_option("display.unicode.east_asian_width", True)
pd.set_option("display.width", 200)


def try_ths():
    import akshare as ak
    df = ak.stock_board_industry_summary_ths()
    return "同花顺行业", df


def try_em():
    import akshare as ak
    df = ak.stock_board_industry_name_em()
    return "东财行业", df


def main():
    for fn in (try_ths, try_em):
        try:
            name, df = fn()
            print(f"== {name} ==")
            print(df.columns.tolist())
            print(df.head(3).to_string(index=False))
            df.to_csv(rf"D:\明远阁\samples\sector_{name}.csv", index=False, encoding="utf-8-sig")
            return
        except Exception as e:
            print(f"{fn.__name__} failed: {type(e).__name__}: {e}")


if __name__ == "__main__":
    main()
