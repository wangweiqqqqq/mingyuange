# -*- coding: utf-8 -*-
"""查 300287 在同行业里的股价分位，以及低价是否等于便宜。"""
import akshare as ak
import pandas as pd

CODE = "300287"

pd.set_option("display.unicode.east_asian_width", True)


def main():
    # 1) 个股基本信息 / 行业
    try:
        info = ak.stock_individual_info_em(symbol=CODE)
        print("== 个股信息 ==")
        print(info.to_string(index=False))
    except Exception as e:
        print("stock_individual_info_em failed:", e)

    # 2) 申万二级行业与成分
    try:
        sw = ak.sw_index_second_info()
        print("\n== 申万二级行业数 ==", len(sw))
        print(sw.head(3).to_string(index=False))
    except Exception as e:
        print("sw_index_second_info failed:", e)

    # 3) 全市场快照（新浪），用于价位分位
    try:
        spot = ak.stock_zh_a_spot()
        print("\n== 全市场快照 ==", len(spot), "只")
        print(spot.columns.tolist()[:12])
        spot.to_csv(r"D:\明远阁\samples\spot_all.csv", index=False, encoding="utf-8-sig")
    except Exception as e:
        print("stock_zh_a_spot failed:", e)


if __name__ == "__main__":
    main()
