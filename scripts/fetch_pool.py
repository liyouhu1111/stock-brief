# -*- coding: utf-8 -*-
"""股票池同步：从腾讯文档智能表格「自选股股票池」拉取最新名单，写入 stocks.csv

原理：文档已设为"所有人可编辑"（链接公开），
1) GET 智能表格页面获取匿名 cookie
2) GET dop-api/opendoc 导出接口（带 cookie + des 形式文档 ID）拿全量快照
3) 解析 protobuf 风格 JSON：字段定义在 schema op，记录值在 cell op
失败时不中断流程：保留仓库内现有 stocks.csv 作为兜底（上一轮运行会自动提交最新快照）。
"""
import csv
import http.cookiejar
import json
import os
import re
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CSV_FILE = os.path.join(ROOT, "stocks.csv")

DOC_URL = "https://docs.qq.com/smartsheet/DSmtBdmxOeVBTTFRJ"
EXPORT_URL = "https://docs.qq.com/dop-api/opendoc?id=DSmtBdmxOeVBTTFRJ&normal=1&outformat=1"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0 Safari/537.36")


def fetch_dump():
    cj = http.cookiejar.CookieJar()
    op = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))
    h = {"User-Agent": UA}
    op.open(urllib.request.Request(DOC_URL, headers=h), timeout=40).read()
    h2 = {"User-Agent": UA, "Referer": DOC_URL}
    body = op.open(urllib.request.Request(EXPORT_URL, headers=h2), timeout=40).read()
    return json.loads(body.decode("utf-8"))


def cell_text(cell):
    """文本/数字单元格 -> 字符串；单选单元格 -> 选项标签"""
    if not isinstance(cell, dict):
        return ""
    if isinstance(cell.get("1"), list) and cell["1"]:
        return str(cell["1"][0].get("2", "")).strip()
    return ""


def main():
    js = fetch_dump()
    ops = js["clientVars"]["collab_client_vars"]["initialAttributedText"]["text"][0]["smartsheet"]
    data = json.loads(ops) if isinstance(ops, str) else ops

    # 在 op 序列中定位：字段定义（含"30"标题键的字典）与记录值（c.2.1）
    fields, records, options = {}, {}, {}
    for inner in data:
        if not isinstance(inner, list):
            continue
        for op in inner:
            if not isinstance(op, dict):
                continue
            c = op.get("c") or {}
            if not isinstance(c, dict):
                continue
            cand = c.get("3")
            if isinstance(cand, dict):
                sub = cand.get("3")
                if isinstance(sub, dict) and all(
                        isinstance(v, dict) and "30" in v for v in sub.values()):
                    fields, fopts = sub, options
                    for fid, fd in sub.items():
                        o = fd.get("17")
                        if isinstance(o, dict):
                            for it in o.get("3") or []:
                                if isinstance(it, dict) and it.get("1"):
                                    options[fid + "|" + str(it["1"])] = str(it.get("2", ""))
            rec = c.get("2")
            if isinstance(rec, dict) and isinstance(rec.get("1"), dict):
                records = rec["1"]

    # 字段 id -> 标题
    id2title = {fid: str(fd.get("30", "")) for fid, fd in fields.items()}
    def fid_of(title):
        for fid, t in id2title.items():
            if t == title:
                return fid
        return None

    f_code, f_name, f_mkt = fid_of("股票代码"), fid_of("股票名称"), fid_of("市场")
    if not f_code:
        raise RuntimeError("未在文档中找到「股票代码」字段")

    stocks = []
    for rid, rcell in records.items():
        try:
            cells = (rcell or {}).get("1") or {}
            code = cell_text(cells.get(f_code))
            if not re.fullmatch(r"\d{5,6}", code):
                continue
            name = cell_text(cells.get(f_name)) if f_name else ""
            mkt = ""
            if f_mkt and f_mkt in cells:
                sel = cells[f_mkt].get("17")
                if isinstance(sel, list) and sel:
                    mkt = options.get(f_mkt + "|" + str(sel[0]), "")
            if not mkt:
                mkt = "A股"
            stocks.append({"code": code, "name": name, "market": mkt})
        except Exception:
            continue

    if not stocks:
        raise RuntimeError("文档解析得到 0 条记录")

    with open(CSV_FILE, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["code", "name", "market"])
        w.writeheader()
        w.writerows(stocks)
    print(f"POOL_OK 从腾讯文档拉取 {len(stocks)} 只股票 -> stocks.csv")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        # 兜底：保留仓库内现有 stocks.csv，不中断流水线
        n = sum(1 for _ in csv.DictReader(open(CSV_FILE, encoding="utf-8-sig"))) \
            if os.path.exists(CSV_FILE) else 0
        print(f"POOL_FALLBACK 腾讯文档拉取失败（{e}），沿用仓库内 stocks.csv（{n} 只）")
