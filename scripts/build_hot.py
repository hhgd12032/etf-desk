#!/usr/bin/env python3
# build_hot.py — 產生「熱議榜」hot.json
# 資料源：FinMind
#   聲量  = 近 WINDOW_DAYS 天，該檔的新聞則數 (TaiwanStockNews)
#   熱度  = 最近一個交易日的成交金額 (TaiwanStockPrice.Trading_money)
# 分數 = 聲量(標準化)*NEWS_WEIGHT + 熱度(標準化)*TURNOVER_WEIGHT
#
# 只用 Python 標準函式庫（urllib），不需要 pip install。
# 在 GitHub Actions 裡跑，把輸出的 hot.json commit 回 repo，前端直接讀。

import os, json, time, datetime, urllib.parse, urllib.request

TOKEN          = os.environ.get("FINMIND_TOKEN", "")   # GitHub secret
API            = "https://api.finmindtrade.com/api/v4/data"
WINDOW_DAYS    = 30
NEWS_WEIGHT    = 0.6      # 想更偏「社群/新聞聲量」就把這個調高
TURNOVER_WEIGHT= 0.4
TOP_N          = 20
SLEEP          = 0.4      # 對 API 客氣一點，避免撞到流量上限

# 候選池：想追蹤誰就放誰（熱門 ETF + 大型權值/熱門個股）。可自由增減。
CANDIDATES = [
    "0050","006208","009816","0056","00878","00919","00713","00929","00981A","00940",
    "2330","2454","2317","2308","2382","2303","2412","2881","2882","2891",
    "3231","3711","2379","3034","3008","2357","2603","2609","2615","1301",
    "1303","2002","2886","2884","5880","3661","6488","3443","2345","4938",
]

def api_get(params):
    p = dict(params)
    if TOKEN:
        p["token"] = TOKEN
    url = API + "?" + urllib.parse.urlencode(p)
    with urllib.request.urlopen(url, timeout=30) as r:
        return json.load(r)

def stock_names():
    try:
        j = api_get({"dataset": "TaiwanStockInfo"})
        return {row["stock_id"]: row["stock_name"] for row in j.get("data", [])}
    except Exception as e:
        print("names failed:", e)
        return {}

def news_count(code, start):
    try:
        j = api_get({"dataset": "TaiwanStockNews", "data_id": code, "start_date": start})
        return len(j.get("data", []))
    except Exception as e:
        print("news failed", code, e)
        return 0

def turnover(code, start):
    try:
        j = api_get({"dataset": "TaiwanStockPrice", "data_id": code, "start_date": start})
        data = j.get("data", [])
        return float(data[-1].get("Trading_money", 0) or 0) if data else 0.0
    except Exception as e:
        print("price failed", code, e)
        return 0.0

def main():
    today      = datetime.date.today()
    start_news = (today - datetime.timedelta(days=WINDOW_DAYS)).isoformat()
    start_px   = (today - datetime.timedelta(days=10)).isoformat()

    names = stock_names()
    rows = []
    for code in CANDIDATES:
        n = news_count(code, start_news); time.sleep(SLEEP)
        t = turnover(code, start_px);     time.sleep(SLEEP)
        rows.append({"code": code, "name": names.get(code, code), "news": n, "turnover": t})
        print(f"{code:<7} news={n:<4} turnover={t:,.0f}")

    max_n = max((r["news"] for r in rows), default=1) or 1
    max_t = max((r["turnover"] for r in rows), default=1) or 1
    for r in rows:
        r["score"] = round(NEWS_WEIGHT * (r["news"] / max_n) * 100
                           + TURNOVER_WEIGHT * (r["turnover"] / max_t) * 100)
    rows.sort(key=lambda r: r["score"], reverse=True)

    out = {
        "updated":     today.isoformat(),
        "source":      f"FinMind 新聞({WINDOW_DAYS}天)＋成交熱度",
        "window_days": WINDOW_DAYS,
        "items":       [{"code": r["code"], "name": r["name"],
                         "score": r["score"], "news": r["news"]}
                        for r in rows[:TOP_N]],
    }
    with open("hot.json", "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print(f"\nwrote hot.json with {len(out['items'])} items")

if __name__ == "__main__":
    main()
