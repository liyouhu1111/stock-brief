# 自选股每日收盘简报（GitHub Actions 云端版）

工作日 16:05（北京时间）自动运行：采集 93 只自选股收盘行情 → 计算 BOLL(20,2) →
按"距轨道 2%/5%"分档 → 拉取重点提醒股票公告 → 生成研报风网页（GitHub Pages）→
WxPusher 微信推送全员。**全程在 GitHub 云端执行，与本地电脑无关。**

## 一次性部署步骤

1. **创建仓库**：GitHub 右上角 + → New repository → 命名如 `stock-brief` → Private（推荐）。
2. **推送代码**（在本地 `github-stock-brief` 目录）：
   ```bash
   git init && git add -A && git commit -m "init: 自选股简报云端版"
   git branch -M main
   git remote add origin https://<你的用户名>:<PAT>@github.com/<你的用户名>/stock-brief.git
   git push -u origin main
   ```
   PAT 获取：GitHub → Settings → Developer settings → Personal access tokens →
   Tokens (classic) → Generate new token → 勾选 `repo` + `workflow` 两个权限。
3. **配置 Secrets**（仓库 Settings → Secrets and variables → Actions → New repository secret）：
   | 名称 | 值 |
   |---|---|
   | `WXPUSHER_TOKEN` | WxPusher 应用的 appToken（AT_ 开头） |
   | `WXPUSHER_UIDS` | 兜底收件 UID，逗号分隔（如 `UID_xxx,UID_yyy`） |
4. **首次测试**：仓库 Actions 页 → 选"自选股每日收盘简报" → Run workflow。
   首次运行会为缺数据的股票全量补采（约 2~3 分钟）。
5. **网页**：workflow 会自动启用 GitHub Pages。地址：
   `https://<用户名>.github.io/<仓库名>/`，每次运行后 index.html 指向最新简报。

## 日常使用

- **增删股票**：直接在 GitHub 网页/App 上编辑 `stocks.csv`（手机浏览器也可以），
  格式：`代码,名称,市场`。新股票下次运行自动全量补采。
- **手动触发**：Actions → Run workflow（随时补跑）。
- **定时**：GitHub cron 为 UTC，`5 8 * * 1-5` = 北京时间周一至五 16:05。
  注意 GitHub 定时任务可能有几分钟到半小时的延迟，属正常现象。
- **行情历史**：滚动行情库在 `data/kline_data.json`，每次运行自动 commit 回仓库，
  永不丢失。**每周五自动全量刷新**，消除前复权平移导致的累计误差。

## 防呆机制

- 增量追加前校验"昨日收盘"与本地末位（误差 <0.5%），不一致（除权除息）自动全量重拉。
- 当日无新 K 线（休市）自动跳过，不产生脏数据。
- 单只股票采集失败不影响其余股票；推送失败不影响简报生成。
- 东方财富接口限流：请求间 0.6s 限速 + 5 次指数退避重试。

## 数据口径

- 中轨 = 最近 20 日收盘均线；上/下轨 = 中轨 ± 2 倍总体标准差（pstdev）。
- 距任一轨道 <2% → 🔴重点提醒；<5% → 🟠关注；其余 ⚪正常。
- 涨跌颜色遵循 A 股惯例：涨红、跌绿。

## 免责声明

以上内容基于公开数据和量化分析，仅供参考，不构成投资建议。市场有风险，投资需谨慎。
