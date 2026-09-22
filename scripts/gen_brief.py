# -*- coding: utf-8 -*-
"""生成简报网页：site/briefs/brief-YYYY-MM-DD.html + site/index.html（最新版入口）"""
import json
import os
import shutil

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BOLL_FILE = os.path.join(ROOT, "data", "boll_result.json")
NEWS_FILE = os.path.join(ROOT, "data", "news_data.json")
SITE = os.path.join(ROOT, "site")

HTML_HEAD = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>自选股简报｜{date}</title>
<script src="https://cdn.jsdelivr.net/npm/echarts@5.5.0/dist/echarts.min.js"></script>
<style>
  body {{ font-family:"Microsoft YaHei","PingFang SC",sans-serif; background:#f7f8fa;
         color:#2c3e50; margin:0; padding:24px; }}
  .wrap {{ max-width:1080px; margin:0 auto; }}
  h1 {{ font-size:24px; margin:0 0 4px; }}
  .sub {{ color:#7a8794; font-size:13px; margin-bottom:20px; }}
  .cards {{ display:flex; gap:12px; flex-wrap:wrap; margin-bottom:20px; }}
  .card {{ flex:1; min-width:140px; background:#fff; border-radius:10px;
          box-shadow:0 1px 4px rgba(0,0,0,.06); padding:16px 20px; }}
  .card .num {{ font-size:26px; font-weight:700; }}
  .card .lab {{ font-size:12px; color:#7a8794; }}
  .c-red {{ color:#c0392b; }} .c-orange {{ color:#d68910; }} .c-gray {{ color:#5d6d7e; }}
  table {{ width:100%; border-collapse:collapse; background:#fff; font-size:13px;
          border-radius:10px; overflow:hidden; box-shadow:0 1px 4px rgba(0,0,0,.06); }}
  th {{ background:#eef1f5; color:#34495e; padding:9px 8px; text-align:right; white-space:nowrap; }}
  th:nth-child(1),th:nth-child(2),th:nth-child(10) {{ text-align:center; }}
  td {{ padding:8px; border-top:1px solid #f0f2f5; text-align:right; font-variant-numeric:tabular-nums; }}
  td:nth-child(1),td:nth-child(2),td:nth-child(10) {{ text-align:center; }}
  tr.alert {{ background:#fdecea; }}
  tr.watch {{ background:#fef7e6; }}
  .up {{ color:#c0392b; }} .down {{ color:#1e8449; }}
  .tag {{ display:inline-block; padding:1px 8px; border-radius:10px; font-size:12px; }}
  .tag.alert {{ background:#f5b7b1; color:#7b241c; }}
  .tag.watch {{ background:#f9e79f; color:#7d6608; }}
  .tag.norm {{ background:#d5dbdb; color:#424949; }}
  #chart {{ width:100%; height:520px; background:#fff; border-radius:10px;
           box-shadow:0 1px 4px rgba(0,0,0,.06); margin:20px 0; }}
  .news {{ background:#fff; border-radius:10px; box-shadow:0 1px 4px rgba(0,0,0,.06);
          padding:16px 22px; margin-bottom:20px; }}
  .news h2 {{ font-size:16px; margin:0 0 10px; }}
  .news li {{ font-size:13px; line-height:1.9; color:#4a5763; }}
  .news b {{ color:#2c3e50; }}
  .news .empty {{ color:#95a5a6; font-size:13px; }}
  .disclaimer {{ font-size:12px; color:#8a97a5; line-height:1.8; background:#eef1f5;
                border-radius:10px; padding:14px 18px; }}
</style>
</head>
<body>
<div class="wrap">
  <h1>📊 自选股简报｜{date}</h1>
  <div class="sub">数据时点：{date} A股收盘 · 前复权 · BOLL(20,2) · 数据源：东方财富公开行情接口 · 由 GitHub Actions 自动生成</div>

  <div class="cards">
    <div class="card"><div class="num">{total}</div><div class="lab">监控股票</div></div>
    <div class="card"><div class="num c-red">{n_alert}</div><div class="lab">🔴 重点提醒（距轨道 &lt;2%）</div></div>
    <div class="card"><div class="num c-orange">{n_watch}</div><div class="lab">🟠 关注（&lt;5%）</div></div>
    <div class="card"><div class="num c-gray">{n_norm}</div><div class="lab">⚪ 正常</div></div>
  </div>

  <table>
    <tr><th>代码</th><th>名称</th><th>收盘价</th><th>涨跌幅</th><th>上轨</th><th>中轨</th><th>下轨</th><th>距上轨</th><th>距下轨</th><th>档位</th></tr>
    {table_rows}
  </table>

  <div id="chart"></div>

  <div class="news">
    <h2>📢 重点提醒股票 · 近期公告</h2>
    {news_html}
  </div>

  <div class="disclaimer">
    <b>免责声明：</b>以上内容基于公开数据和量化分析，仅供参考，不构成投资建议。市场有风险，投资需谨慎。
    任何投资决策应结合个人风险承受能力、资金状况和投资目标独立判断，必要时咨询持牌专业机构。过往表现不预示未来收益。
  </div>
</div>

<script>
var names = {chart_names};
var up = {chart_up};
var low = {chart_low};
var colors = {chart_colors};
var chart = echarts.init(document.getElementById('chart'));
chart.setOption({{
  title: {{ text: '距 BOLL 轨道距离（%）— 上轨为正/下轨为负，越接近 0 越需关注', left: 10, top: 6, textStyle: {{ fontSize: 14, color: '#34495e' }} }},
  tooltip: {{ trigger: 'axis', axisPointer: {{ type: 'shadow' }},
    formatter: function (ps) {{
      var i = ps[0].dataIndex, s = names[i] + '<br>';
      s += '距上轨: ' + (up[i] == null ? '—' : up[i].toFixed(2) + '%') + '<br>';
      s += '距下轨: ' + (low[i] == null ? '—' : low[i].toFixed(2) + '%');
      return s;
    }} }},
  grid: {{ left: 10, right: 20, top: 48, bottom: 110, containLabel: true }},
  xAxis: {{ type: 'category', data: names,
    axisLabel: {{ rotate: 90, fontSize: 10, interval: 0, color: '#5d6d7e' }} }},
  yAxis: {{ type: 'value', name: '%', axisLabel: {{ formatter: '{{value}}%' }} }},
  series: [
    {{ name: '距上轨', type: 'bar', stack: 'd', data: up, itemStyle: {{ color: function(p) {{ return colors[p.dataIndex][0]; }} }} }},
    {{ name: '距下轨', type: 'bar', stack: 'd', data: low, itemStyle: {{ color: function(p) {{ return colors[p.dataIndex][1]; }} }} }}
  ]
}});
window.addEventListener('resize', function () {{ chart.resize(); }});
</script>
</body>
</html>"""


def main():
    with open(BOLL_FILE, encoding="utf-8") as f:
        payload = json.load(f)
    date = payload["date"]
    result = payload["result"]
    try:
        with open(NEWS_FILE, encoding="utf-8") as f:
            news = json.load(f)
    except FileNotFoundError:
        news = {}

    order = sorted(result.items(),
                   key=lambda kv: ({"重点提醒": 0, "关注": 1}.get(kv[1]["tag"], 2),
                                   min(kv[1]["dist_up"], kv[1]["dist_low"])))
    n_alert = sum(1 for v in result.values() if v["tag"] == "重点提醒")
    n_watch = sum(1 for v in result.values() if v["tag"] == "关注")
    n_norm = len(result) - n_alert - n_watch

    rows = []
    chart_names, chart_up, chart_low, chart_colors = [], [], [], []
    for code, v in order:
        tr_cls = {"重点提醒": "alert", "关注": "watch"}.get(v["tag"], "")
        tag_cls = {"重点提醒": "alert", "关注": "watch"}.get(v["tag"], "norm")
        pct_cls = "up" if v["pct"] >= 0 else "down"
        rows.append(
            f'<tr class="{tr_cls}"><td>{code}</td><td>{v["name"]}</td>'
            f'<td>{v["close"]:.2f}</td><td class="{pct_cls}">{v["pct"]:+.2f}%</td>'
            f'<td>{v["upper"]:.2f}</td><td>{v["mid"]:.2f}</td><td>{v["lower"]:.2f}</td>'
            f'<td>{v["dist_up"]:.2f}%</td><td>{v["dist_low"]:.2f}%</td>'
            f'<td><span class="tag {tag_cls}">{v["tag"]}</span></td></tr>')
        chart_names.append(code + " " + v["name"])
        chart_up.append(round(v["dist_up"], 2))
        chart_low.append(-round(v["dist_low"], 2))
        if v["tag"] == "重点提醒":
            chart_colors.append(["#e74c3c", "#e74c3c"])
        elif v["tag"] == "关注":
            chart_colors.append(["#f39c12", "#f39c12"])
        else:
            chart_colors.append(["#95a5a6", "#95a5a6"])

    parts = []
    for code, items in news.items():
        name = result.get(code, {}).get("name", code)
        if items:
            lis = "".join(f"<li>【{d}】<b>{t}</b></li>" for d, t in items)
            parts.append(f"<p><b>{code} {name}</b></p><ul>{lis}</ul>")
        else:
            parts.append(f"<p><b>{code} {name}</b></p><ul><li class='empty'>近期无重大公告</li></ul>")
    news_html = "".join(parts) if parts else "<p class='empty'>本期无重点提醒股票公告数据</p>"

    html = HTML_HEAD.format(
        date=date, total=len(result), n_alert=n_alert, n_watch=n_watch, n_norm=n_norm,
        table_rows="\n".join(rows), news_html=news_html,
        chart_names=json.dumps(chart_names, ensure_ascii=False),
        chart_up=json.dumps(chart_up), chart_low=json.dumps(chart_low),
        chart_colors=json.dumps(chart_colors),
    )

    briefs_dir = os.path.join(SITE, "briefs")
    os.makedirs(briefs_dir, exist_ok=True)
    fname = f"brief-{date}.html"
    path = os.path.join(briefs_dir, fname)
    with open(path, "w", encoding="utf-8") as f:
        f.write(html)
    shutil.copyfile(path, os.path.join(SITE, "index.html"))
    with open(os.path.join(ROOT, "data", "latest_brief.txt"), "w", encoding="utf-8") as f:
        f.write(fname)
    print("BRIEF_OK", path)


if __name__ == "__main__":
    main()
