#!/usr/bin/env python3
# build_hot.py — 產生「熱議榜」hot.json
# 資料源：FinMind
#   聲量   = 近 WINDOW_DAYS 天，該檔的新聞則數 (TaiwanStockNews)
#   熱度   = 最近一個交易日的成交金額 (TaiwanStockPrice.Trading_money)
#   標題   = 近期新聞標題＋出處＋連結（讓你看到大家在討論什麼）
#   正負   = 用中文關鍵字粗估每則標題偏正/偏負（僅供參考，不影響排名）
# 分數 = 聲量(標準化)*NEWS_WEIGHT + 熱度(標準化)*TURNOVER_WEIGHT
#
# 只用 Python 標準函式庫（urllib），不需 pip install。在 GitHub Actions 裡跑。

import os, json, time, datetime, urllib.parse, urllib.request

TOKEN           = os.environ.get("FINMIND_TOKEN", "")
API             = "https://api.finmindtrade.com/api/v4/data"
WINDOW_DAYS     = 30
NEWS_WEIGHT     = 0.6
TURNOVER_WEIGHT = 0.4
TOP_N           = 20
HEADLINES_PER   = 6      # 每檔存幾則標題
SLEEP           = 0.4

CANDIDATES = [
    "0050","006208","009816","0056","00878","00919","00713","00929","00981A","00940",
    "2330","2454","2317","2308","2382","2303","2412","2881","2882","2891",
    "3231","3711","2379","3034","3008","2357","2603","2609","2615","1301",
    "1303","2002","2886","2884","5880","3661","6488","3443","2345","4938",
]

# 粗略中文情緒關鍵字（可自行增修）。這只是關鍵字命中，不是真正的語意分析。
POS = ["大漲","漲停","創新高","新高","獲利","成長","看好","樂觀","買超","利多","訂單","營收創",
       "飆","強勢","回升","突破","受惠","加碼","調升","超預期","亮眼","熱賣","擴產","填息",
       "走高","勁揚","攻頂","增溫","樂觀","轉單","題材","衝高","上修"]
NEG = ["大跌","跌停","重挫","暴跌","虧損","下滑","看壞","悲觀","賣超","利空","示警","下修",
       "衰退","破底","跳水","警訊","調降","不如預期","裁員","停產","違約","踩雷","走弱",
       "摜","殺盤","崩","認賠","示弱","降評","賣壓","停損","疲弱","拖累"]

def api_get(params):
    p = dict(params)
    if TOKEN:
        p["token"] = TOKEN
    url = API + "?" + urllib.parse.urlencode(p)
    with urllib.request.urlopen(url, timeout=30) as r:
        return json.load(r)

def tone(title):
    p = any(k in title for k in POS)
    n = any(k in title for k in NEG)
    if p and not n: return "pos"
    if n and not p: return "neg"
    return "neu"

def stock_names():
    try:
        j = api_get({"dataset": "TaiwanStockInfo"})
        return {row["stock_id"]: row["stock_name"] for row in j.get("data", [])}
    except Exception as e:
        print("names failed:", e); return {}

def news_items(code, start):
    try:
        j = api_get({"dataset": "TaiwanStockNews", "data_id": code, "start_date": start})
        return j.get("data", [])
    except Exception as e:
        print("news failed", code, e); return []

def turnover(code, start):
    try:
        j = api_get({"dataset": "TaiwanStockPrice", "data_id": code, "start_date": start})
        data = j.get("data", [])
        return float(data[-1].get("Trading_money", 0) or 0) if data else 0.0
    except Exception as e:
        print("price failed", code, e); return 0.0

def main():
    today      = datetime.date.today()
    start_news = (today - datetime.timedelta(days=WINDOW_DAYS)).isoformat()
    start_px   = (today - datetime.timedelta(days=10)).isoformat()
    names = stock_names()

    rows = []
    for code in CANDIDATES:
        news = news_items(code, start_news); time.sleep(SLEEP)
        news.sort(key=lambda x: x.get("date",""), reverse=True)
        pos = sum(1 for it in news if tone(it.get("title","")) == "pos")
        neg = sum(1 for it in news if tone(it.get("title","")) == "neg")
        headlines = [{
            "title":  it.get("title",""),
            "url":    it.get("link",""),
            "source": it.get("source",""),
            "date":   (it.get("date","") or "")[5:10],   # MM-DD
            "tone":   tone(it.get("title","")),
        } for it in news[:HEADLINES_PER]]
        t = turnover(code, start_px); time.sleep(SLEEP)
        rows.append({"code":code, "name":names.get(code,code), "news":len(news),
                     "pos":pos, "neg":neg, "turnover":t, "headlines":headlines})
        print(f"{code:<7} news={len(news):<4} pos={pos:<3} neg={neg:<3} turnover={t:,.0f}")

    max_n = max((r["news"] for r in rows), default=1) or 1
    max_t = max((r["turnover"] for r in rows), default=1) or 1
    for r in rows:
        r["score"] = round(NEWS_WEIGHT*(r["news"]/max_n)*100 + TURNOVER_WEIGHT*(r["turnover"]/max_t)*100)
    rows.sort(key=lambda r: r["score"], reverse=True)

    out = {
        "updated":     today.isoformat(),
        "source":      f"FinMind 新聞({WINDOW_DAYS}天)＋成交熱度",
        "window_days": WINDOW_DAYS,
        "sentiment_note": "正/負為新聞標題關鍵字粗估，僅供參考，不影響排名",
        "items": [{"code":r["code"], "name":r["name"], "score":r["score"],
                   "news":r["news"], "pos":r["pos"], "neg":r["neg"],
                   "headlines":r["headlines"]} for r in rows[:TOP_N]],
    }
    with open("hot.json", "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print(f"\nwrote hot.json with {len(out['items'])} items")

if __name__ == "__main__":
    main()
