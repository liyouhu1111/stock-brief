# -*- coding: utf-8 -*-
"""采集「重点提醒」股票的近期公告（东方财富公告接口，宁缺毋滥）

输出 data/news_data.json：code -> [[日期, 标题], ...]（最多 3 条/只）
"""
import json
import os
import urllib.parse
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BOLL_FILE = os.path.join(ROOT, "data", "boll_result.json")
NEWS_FILE = os.path.join(ROOT, "data", "news_data.json")

UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
      "Referer": "https://data.eastmoney.com/"}

import time

_last_req = [0.0]


def _get_json(url, timeout=30):
    for attempt in range(5):
        wait = time.time() - _last_req[0]
        if wait < 0.6:
            time.sleep(0.6 - wait)
        _last_req[0] = time.time()
        try:
            req = urllib.request.Request(url, headers=UA)
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return json.loads(r.read().decode("utf-8"))
        except Exception:
            if attempt == 4:
                raise
            time.sleep(1.5 * (2 ** attempt))


def fetch_announcements(code, page_size=3):
    req_url = (
        "https://np-anotice-stock.eastmoney.com/api/security/ann"
        f"?sr=-1&page_size={page_size}&page_index=1&ann_type=A"
        f"&client_source=web&stock_list={urllib.parse.quote(code)}"
    )
    js = _get_json(req_url)
    out = []
    for it in ((js or {}).get("data") or {}).get("list") or []:
        title = (it.get("title") or it.get("art_title") or "").strip()
        title = title.split(":", 1)[-1] if title[:6].isascii() else title  # 去掉"公司名:"前缀
        date = (it.get("notice_date") or "")[:10]
        if title:
            out.append([date, title])
    return out


def main():
    with open(BOLL_FILE, encoding="utf-8") as f:
        boll = json.load(f)
    targets = {c: v["name"] for c, v in boll["result"].items() if v["tag"] == "重点提醒"}
    print(f"公告采集目标（重点提醒）：{len(targets)} 只")

    news = {}
    ok = 0
    for code, name in targets.items():
        try:
            items = fetch_announcements(code)
            news[code] = items
            ok += 1
            print(f"[OK  ] {code} {name}: {len(items)} 条")
        except Exception as e:
            news[code] = []
            print(f"[FAIL] {code} {name}: {e}")

    with open(NEWS_FILE, "w", encoding="utf-8") as f:
        json.dump(news, f, ensure_ascii=False)
    print(f"公告采集完成 {ok}/{len(targets)}")


if __name__ == "__main__":
    main()
