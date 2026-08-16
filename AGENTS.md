# ai-news-douyin 项目交接文档

> 本文件供任何接手此项目的 agent/开发者快速理解项目。先通读，再动手。

## 1. 项目是什么

AI 新闻自动搬运流水线：抓取（Telegram 频道 / Google News / RSSHub-Twitter / X 直抓）→ 内容检测（AI 相关性、敏感过滤、去重）→ DeepSeek 总结 → 封面生成 → 抖音开放平台图文发布。支持本地 `loop` 定时和 GitHub Actions 云端定时。

## 2. 关键入口

- `main.py`：CLI（run/loop/crawl/drafts/publish/douyin auth|callback|whoami|renew/init）
- `ai_news/pipeline.py`：主流水线（crawl → process_item：相关性→敏感→去重→LLM→出图→发布）
- `ai_news/publisher/douyin_open.py`：抖音客户端（OAuth + 上传图文 + 创建图文，modern/legacy 双路径自动回退）
- `ai_news/crawlers/`：内容源（tme 免登录最稳；rsshub_twitter/twitter_x 需自备实例/cookies）
- `config.yaml` + `.env`：配置与密钥；`data/app.db`：SQLite 全链路状态（items/posts/kv）

## 3. 已知约束与坑

1. **Twitter 免费通道实测全挂**（2026-08）：公共 RSSHub 实例 twitter 路由、Nitter（Cloudflare 验证）、syndication API（空响应）均不可用；默认源是 t.me 频道 + Google News。真实 Twitter 抓取只能靠自建 RSSHub（需 twitter cookies）或 X 直抓后端。
2. **抖音发布需要开放平台权限**：图文发布能力要申请审核（个人开发者可申请，资质以官方为准）；未配置凭据时流水线会以 dry-run 记录 ready 草稿，不报错。
3. **令牌生命周期**：access_token 自动刷新重试；refresh_token 30 天需 `douyin renew` 续期（GH Actions 工作流已内置）。可选 `GH_WRITEBACK_REPO/TOKEN` 用 `gh secret set` 回写云端 secrets（复用 DouYinSparkFlow 的 PAT 思路）。
4. **封面字体**：macOS 用 PingFang；Linux CI 需 `fonts-noto-cjk`（工作流已装）。无中文字体时封面会出方块并告警。
5. **去重**：URL 精确去重（DB UNIQUE）+ 文本相似度（0.82，仅与最近 30 篇已发布对比，标题/正文分开比较，拼接会稀释相似度——踩过坑）。
6. **敏感词表**在 `ai_news/detection/blocklist.py`，可在 config.yaml `detection.sensitive.extra_terms` 追加，不要删除政治红线项（保护账号）。
7. **发布幂等**：每轮只处理新条目；`posts.status` 记录 skipped/ready/published/failed，已处理条目不会重跑。

## 4. 验证方式

```bash
.venv/bin/python tests/run_all.py          # 17 个离线测试（解析/检测/去重/封面/DB/流水线）
.venv/bin/python main.py run --dry-run --skip-llm --limit 3   # 真网冒烟（不发布）
.venv/bin/python main.py drafts            # 看处理记录
```

## 5. 调试规范（用户要求）

- 未获用户确认前，**不要用真实抖音凭据执行正式发布**；先 `--dry-run`。
- 不要打印/泄露 .env 中的密钥与令牌。
- 修改行为后同步更新本文件和 README。
- 需要用户配合的事项（开放平台资质、RSSHub 部署、X cookies）不要自行假设，明确告知用户。
