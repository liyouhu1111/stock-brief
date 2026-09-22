# -*- coding: utf-8 -*-
"""WxPusher 全员群发（云端版）

- 优先动态拉取应用下全部订阅者（V2 接口），失败回退 WXPUSHER_UIDS 环境变量
- WXPUSHER_TOKEN / WXPUSHER_UIDS 来自 GitHub Secrets
"""
import json
import os
import time
import urllib.request

API = "https://wxpusher.zjiecode.com/api/send/message"
SUB_API = "https://wxpusher.zjiecode.com/api/fun/wxuser/v2"


def http_json(url, payload=None):
    data = None
    headers = {"Content-Type": "application/json"}
    if payload is not None:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers=headers)
    for _ in range(3):  # 网络抖动重试
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                return json.loads(r.read().decode("utf-8"))
        except Exception:
            time.sleep(2)
    return None


def get_uids(token, fallback):
    uids = []
    for page in (1, 2):
        js = http_json(f"{SUB_API}?appToken={token}&page={page}&pageSize=100&type=0")
        records = ((js or {}).get("data") or {}).get("records") or []
        uids += [u["uid"] for u in records if u.get("uid") and not u.get("remove")]
        if len(records) < 100:
            break
    if uids:
        return uids
    return [u.strip() for u in (fallback or "").split(",") if u.strip()]


def main():
    token = os.environ.get("WXPUSHER_TOKEN", "").strip()
    if not token:
        print("SKIP_PUSH: 未配置 WXPUSHER_TOKEN（GitHub Secrets），跳过推送")
        return

    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    with open(os.path.join(root, "data", "boll_result.json"), encoding="utf-8") as f:
        payload = json.load(f)
    date, result = payload["date"], payload["result"]

    brief_file = ""
    latest = os.path.join(root, "data", "latest_brief.txt")
    if os.path.exists(latest):
        brief_file = open(latest, encoding="utf-8").read().strip()
    repo = os.environ.get("GITHUB_REPOSITORY", "")
    url = f"https://{repo.split('/')[0]}.github.io/{repo.split('/')[1]}/{brief_file}" if repo and brief_file else ""

    def side_of(v):
        return "上" if v["dist_up"] <= v["dist_low"] else "下"

    def dist_of(v):
        return v["dist_up"] if v["dist_up"] <= v["dist_low"] else v["dist_low"]

    alerts = sorted(((c, v) for c, v in result.items() if v["tag"] == "重点提醒"),
                    key=lambda kv: (0 if side_of(kv[1]) == "上" else 1, dist_of(kv[1])))
    watch = sorted(((c, v) for c, v in result.items() if v["tag"] == "关注"),
                   key=lambda kv: dist_of(kv[1]))
    n_up = sum(1 for _, v in alerts if side_of(v) == "上")

    parts = [f"<h3>📈 自选股简报｜{date}</h3>",
             f"<p>监控 {len(result)} 只 · 🔴重点提醒 {len(alerts)}"
             f"（🔺近上轨 {n_up} / 🔻近下轨 {len(alerts) - n_up}）· 🟠关注 {len(watch)}</p>",
             "<h4>🔴 重点提醒（距 BOLL 轨道 &lt;2%，由近到远）</h4><ul>"]
    for c, v in alerts:
        side = side_of(v)
        icon = "🔺" if side == "上" else "🔻"
        dist = dist_of(v)
        parts.append(f"<li style='color:#c0392b'>{icon}{c} {v['name']}｜收盘 {v['close']:.2f}｜"
                     f"距{side}轨 {dist:.2f}%</li>")
    parts.append("</ul><h4>🟠 关注（由近到远）</h4><ul>")
    for c, v in watch:
        parts.append(f"<li style='color:#8a6d1a'>{c} {v['name']}｜收盘 {v['close']:.2f}｜"
                     f"距上 {v['dist_up']:.2f}% / 距下 {v['dist_low']:.2f}%</li>")
    parts.append("</ul>")

    try:
        with open(os.path.join(root, "data", "news_data.json"), encoding="utf-8") as f:
            news = json.load(f)
        items = [(c, its) for c, its in news.items() if its]
        if items:
            parts.append("<h4>📢 重点提醒股票 · 近期公告</h4><ul>")
            for c, its in items:
                name = result.get(c, {}).get("name", c)
                parts.append(f"<li><b>{c} {name}</b>：" +
                             "；".join(t for _, t in its[:2]) + "</li>")
            parts.append("</ul>")
    except FileNotFoundError:
        pass

    if url:
        parts.append(f"<p><a href='{url}'>点击查看完整简报</a></p>")
    parts.append("<p style='color:#95a5a6;font-size:12px'>以上内容基于公开数据和量化分析，仅供参考，不构成投资建议。市场有风险，投资需谨慎。</p>")

    uids = get_uids(token, os.environ.get("WXPUSHER_UIDS", ""))
    if not uids:
        print("SKIP_PUSH: 未获取到任何订阅者")
        return
    body = {
        "appToken": token, "content": "".join(parts), "summary":
        f"自选股简报 {date}：重点提醒 {len(alerts)} 只，关注 {len(watch)} 只", "contentType": 2,
        "uids": uids,
    }
    if url:
        body["url"] = url

    for attempt in (1, 2):
        js = http_json(API, body)
        code = (js or {}).get("code")
        print(f"push attempt {attempt}: code={code} msg={(js or {}).get('msg')}")
        if code == 1000:
            print(f"PUSH_OK uids={len(uids)}")
            return
        time.sleep(3)
    print("PUSH_FAIL: 重试后仍失败（简报本身已生成，不受影响）")


if __name__ == "__main__":
    main()
