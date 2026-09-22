# -*- coding: utf-8 -*-
"""行情采集 + BOLL(20,2) 计算（云端版，数据源：东方财富公开接口，前复权日线）

滚动行情库 data/kline_data.json：code -> 最近 21 个前复权收盘价。
- 新股票 / 周五：全量拉取 21 根
- 已有股票：增量拉取最近 2 根，昨日收盘与本地末位校验（<0.5%）才追加；
  不一致（除权除息导致前复权整体平移）自动全量重拉覆盖
- 当日无新 K 线（休市/数据未更新）：跳过追加，BOLL 用现有序列计算
"""
import csv
import json
import os
import statistics
import urllib.request
from datetime import datetime, timedelta, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(ROOT, "data")
KLINE_FILE = os.path.join(DATA_DIR, "kline_data.json")
BOLL_FILE = os.path.join(DATA_DIR, "boll_result.json")

CST = timezone(timedelta(hours=8))
TODAY = datetime.now(CST).strftime("%Y-%m-%d")
IS_FRIDAY = datetime.now(CST).weekday() == 4

UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
      "Referer": "https://quote.eastmoney.com/"}

import time

_last_req = [0.0]


def _get_json(url, timeout=30):
    """带限速与指数退避重试的 GET（东方财富接口对连续请求限流）"""
    for attempt in range(5):
        wait = time.time() - _last_req[0]
        if wait < 0.3:
            time.sleep(0.3 - wait)
        _last_req[0] = time.time()
        try:
            req = urllib.request.Request(url, headers=UA)
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return json.loads(r.read().decode("utf-8"))
        except Exception as e:
            if attempt == 4:
                raise
            time.sleep(1.5 * (2 ** attempt))  # 1.5s / 3s / 6s / 12s


def read_stocks():
    with open(os.path.join(ROOT, "stocks.csv"), encoding="utf-8-sig") as f:
        return [(r["code"].strip(), r["name"].strip()) for r in csv.DictReader(f) if r.get("code")]


def secid(code):
    # 6 开头=沪（含 688 科创板），其余（000/001/002/003/300/301）=深
    return ("1." if code.startswith("6") else "0.") + code


def fetch_kline_tencent(code, n):
    """腾讯行情：主数据源，返回 [(date, close), ...] 前复权日线"""
    symbol = ("sh" if code.startswith("6") else "sz") + code
    url = f"https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?param={symbol},day,,,{n},qfq"
    js = _get_json(url)
    d = ((js or {}).get("data") or {}).get(symbol) or {}
    rows = d.get("qfqday") or d.get("day") or []
    return [(r[0], float(r[2])) for r in rows[-n:]]


def fetch_kline_eastmoney(code, n):
    """东方财富：兜底数据源，返回 [(date, close), ...] 前复权日线"""
    url = (
        "https://push2his.eastmoney.com/api/qt/stock/kline/get"
        f"?secid={secid(code)}&fields1=f1,f2,f3&fields2=f51,f53"
        f"&klt=101&fqt=1&end=20500101&lmt={n}"
    )
    js = _get_json(url)
    data = (js or {}).get("data") or {}
    out = []
    for item in data.get("klines") or []:
        dd, c = item.split(",")
        out.append((dd, float(c)))
    return out[-n:]


def fetch_kline(code, n):
    try:
        rows = fetch_kline_tencent(code, n)
        if rows:
            return rows
    except Exception:
        pass
    return fetch_kline_eastmoney(code, n)


def main():
    os.makedirs(DATA_DIR, exist_ok=True)
    stocks = read_stocks()
    kline = {}
    if os.path.exists(KLINE_FILE):
        with open(KLINE_FILE, encoding="utf-8") as f:
            kline = json.load(f)

    n_full = n_inc = n_skip = n_fail = 0
    for code, name in stocks:
        try:
            if code not in kline or IS_FRIDAY:
                rows = fetch_kline(code, 25)[-21:]
                if not rows:
                    raise RuntimeError("empty klines")
                kline[code] = [c for _, c in rows]
                n_full += 1
                mode = "full"
            else:
                rows = fetch_kline(code, 2)
                if len(rows) < 2:
                    raise RuntimeError("increment klines < 2")
                (d1, c1), (d2, c2) = rows[-2], rows[-1]
                last = kline[code][-1]
                if d2 != TODAY:
                    n_skip += 1  # 今日尚无新K线（休市或数据未更新）
                    mode = "skip"
                elif abs(c2 - last) / c2 < 0.005:
                    n_skip += 1  # 本地已含今日收盘（重复运行），不重复追加
                    mode = "already"
                elif abs(c1 - last) / last < 0.005:
                    kline[code].append(c2)
                    kline[code] = kline[code][-21:]
                    n_inc += 1
                    mode = "inc"
                else:
                    rows = fetch_kline(code, 25)[-21:]  # 除权跳变 → 全量重拉
                    kline[code] = [c for _, c in rows]
                    n_full += 1
                    mode = "full-refetch"
            print(f"[{mode:12s}] {code} {name} last={kline[code][-1]}")
        except Exception as e:  # 单只失败不中断，保留旧序列
            n_fail += 1
            print(f"[FAIL        ] {code} {name}: {e}")

    boll = {}
    for code, name in stocks:
        closes = kline.get(code) or []
        if len(closes) < 20:
            continue
        c20 = closes[-20:]
        close = closes[-1]
        prev = closes[-2] if len(closes) >= 2 else close
        mid = sum(c20) / 20
        sd = statistics.pstdev(c20)
        upper, lower = mid + 2 * sd, mid - 2 * sd
        dist_up = (upper - close) / close * 100
        dist_low = (close - lower) / close * 100
        tag = "重点提醒" if (dist_up < 2 or dist_low < 2) else (
            "关注" if (dist_up < 5 or dist_low < 5) else "正常")
        boll[code] = {
            "name": name, "close": close, "pct": (close - prev) / prev * 100,
            "mid": mid, "upper": upper, "lower": lower,
            "dist_up": dist_up, "dist_low": dist_low, "tag": tag,
        }

    with open(KLINE_FILE, "w", encoding="utf-8") as f:
        json.dump(kline, f, ensure_ascii=False)
    with open(BOLL_FILE, "w", encoding="utf-8") as f:
        json.dump({"date": TODAY, "result": boll}, f, ensure_ascii=False)

    n_alert = sum(1 for v in boll.values() if v["tag"] == "重点提醒")
    n_watch = sum(1 for v in boll.values() if v["tag"] == "关注")
    print(f"DATE={TODAY} stocks={len(stocks)} full={n_full} inc={n_inc} "
          f"skip={n_skip} fail={n_fail} | 重点提醒={n_alert} 关注={n_watch} "
          f"正常={len(boll) - n_alert - n_watch}")


if __name__ == "__main__":
    main()
