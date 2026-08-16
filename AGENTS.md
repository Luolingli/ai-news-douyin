# ai-news-douyin 项目交接文档

> 本文件供任何接手此项目的 agent/开发者快速理解项目。先通读，再动手。

## 1. 项目是什么

AI 新闻自动搬运流水线：抓取（Telegram 频道 / Google News / RSSHub-Twitter / X 直抓）→ 内容检测（AI 相关性、敏感过滤、去重）→ DeepSeek 总结 → 封面生成 → 抖音开放平台图文发布。支持本地 `loop`/launchd 定时和 GitHub Actions 云端定时（云端走网页版发布：secret 里放 `DOUYIN_WEB_COOKIES_B64`，工作流解码→无头发布→回写 cookies）。

## 2. 关键入口

- `main.py`：CLI（run/loop/crawl/drafts/publish/douyin auth|callback|whoami|renew|tokens/init）
- `ai_news/pipeline.py`：主流水线（crawl → process_item：相关性→敏感→去重→LLM→出图→发布）
- `ai_news/publisher/douyin_open.py`：开放平台 API 客户端（需企业资质；OAuth + 上传图文 + 创建图文，modern/legacy 自动回退）
- `ai_news/publisher/douyin_web.py`：创作者中心网页版发布器（Playwright + cookies，个人账号主路线；选择器基于 2026 界面，改版失败会截图存档）
- `ai_news/crawlers/`：内容源（tme 免登录最稳；rsshub_twitter/twitter_x 需自备实例/cookies）
- `config.yaml` + `.env`：配置与密钥；`data/app.db`：SQLite 全链路状态（items/posts/kv）

## 3. 已知约束与坑

0. **LLM 用 ModelScope 免费 API**（key 在 .env，凌晨时段拥堵严重会空响应/空输出，deferred 机制兜底）：主 `deepseek-ai/DeepSeek-V4-Flash-0731`，fallbacks `Qwen/Qwen3-Next-80B-A3B-Instruct,Qwen/Qwen3.5-27B,deepseek-ai/DeepSeek-V4-Pro`（实测这三枚在高峰时段可响应；2026-08-17 已成功发布首条）。免费档**限流时会返回 200 + choices:null**——客户端已实现空响应重试（5/10/20s）+ 多模型切换；全部失败时条目标 `deferred` 下轮重试（不发布原文降级文案）。换模型改 .env 的 LLM_MODEL。
1. **Twitter 免费通道实测全挂**（2026-08）：公共 RSSHub 实例 twitter 路由、Nitter（Cloudflare 验证）、syndication API（空响应）均不可用；默认源是 t.me 频道 + Google News。真实 Twitter 抓取只能靠自建 RSSHub（需 twitter cookies）或 X 直抓后端。
2. **抖音发布双路线**：API 路线需要企业资质（个人开发者实测无法创建应用）；网页版路线（`douyin.mode: auto/web`）用 Playwright 模拟操作 creator.douyin.com 发布图文，cookies 复用 `~/.config/douyin_keepalive/cookies.json`（用户已有 launchd keepalive 设施自动续期）。网页发布 UI 可能改版，失败会自动截图到 `data/logs/screenshots/` 便于适配。**关键**：keepalive 的 cookies 只对 www.douyin.com 有效，creator.douyin.com 必须让用户执行 `python main.py douyin web login` 扫码一次，cookies 存到独立的 `data/web_cookies.json`（避免被 keepalive 覆盖）；check 失败就提示重新 login。
3. **令牌生命周期**：access_token 自动刷新重试；refresh_token 30 天需 `douyin renew` 续期（GH Actions 工作流已内置）。可选 `GH_WRITEBACK_REPO/TOKEN` 用 `gh secret set` 回写云端 secrets（复用 DouYinSparkFlow 的 PAT 思路）。
4. **封面字体**：macOS 用 PingFang；Linux CI 需 `fonts-noto-cjk`（工作流已装）。无中文字体时封面会出方块并告警。
5. **去重**：URL 精确去重（DB UNIQUE）+ 文本相似度（0.82，仅与最近 30 篇已发布对比，标题/正文分开比较，拼接会稀释相似度——踩过坑）。
6. **敏感词表**在 `ai_news/detection/blocklist.py`，可在 config.yaml `detection.sensitive.extra_terms` 追加，不要删除政治红线项（保护账号）。
7. **发布幂等**：每轮只处理新条目；`posts.status` 记录 skipped/ready/published/failed，已处理条目不会重跑。

## 4. 状态（2026-08-17）

- **已成功发布两条**（私人号方案A，用户自删测试内容）：`AI 数学再突破！…` 与 `Anthropic CEO：我没看衰AI`
- **发布策略（2026-08-17 调整）**：私人号低频——每天 2 轮（12:10/20:10）每轮 1 条；正文深度模式 600-800 字（抓取原文全文最多 8000 字喂 LLM）；文末自动加 `—— 本文由 AI 转录整理，仅供参考 ——`（config `llm.ai_footer` 可关）；LLM 空输出按 deferred 重试而非永久跳过
- 发布成功判定已兼容 `content/manage` URL 跳转（不再误报 unknown）
- `run` 会处理历史未处理条目与 deferred 重试（不只本轮新抓）
- 旧演示草稿（俄语/英文）已标记 skipped 弃用，不会被误发

## 5. 验证方式

```bash
.venv/bin/python tests/run_all.py          # 24 个离线测试（解析/检测/去重/封面/DB/流水线/发布器）
.venv/bin/python main.py run --dry-run --skip-llm --limit 3   # 真网冒烟（不发布）
.venv/bin/python main.py drafts            # 看处理记录
```

## 5. 调试规范（用户要求）

- 未获用户确认前，**不要用真实抖音凭据执行正式发布**；先 `--dry-run`。
- 不要打印/泄露 .env 中的密钥与令牌。
- 修改行为后同步更新本文件和 README。
- 需要用户配合的事项（开放平台资质、RSSHub 部署、X cookies）不要自行假设，明确告知用户。
