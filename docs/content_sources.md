# 内容源配置指南

编辑 `config.yaml` 的 `sources` 列表，多源并行抓取，按 URL 自动去重合并。

## 实测现状（2026-08，重要）

Twitter/X 的免费通道目前几乎全部失效，本项目做了多后端设计，按可用性排序：

| 方式 | 状态 | 说明 |
|---|---|---|
| t.me 频道预览页 | ✅ 可用 | 免登录抓 Telegram 频道，很多 AI 频道在镜像 Twitter 账号 |
| Google News RSS | ✅ 可用 | 免登录关键词搜索，覆盖主流科技媒体 |
| 自建 RSSHub twitter 路由 | ⚠️ 需自部署 | 公共实例的 twitter 路由基本都被关停 |
| X.com 直抓（Playwright+cookies） | ⚠️ 实验性 | 需自备 X 账号 cookies，未在受限网络验证 |
| 公共 Nitter / rsshub.app / syndication API | ❌ 已失效 | 403/Cloudflare/空响应 |

## 1. Telegram 频道（tme）——推荐默认

```yaml
sources:
  - type: tme
    name: tg_ai_news
    channel: AI_News_Official   # https://t.me/s/<channel> 的频道名
    enabled: true
    max_items: 20
```

找频道：Telegram 搜索 AI / OpenAI 等关键词，进入频道后在浏览器打开 `https://t.me/s/<频道名>`，能正常看到消息即可被本项目抓取。

## 2. Google News（googlenews）

```yaml
  - type: googlenews
    name: google_ai
    query: '"OpenAI" OR "Anthropic" OR "Google DeepMind" OR "Meta AI" OR "大模型"'
    lang: en-US
    enabled: true
```

query 语法与 Google News 搜索一致，支持 `OR`、引号精确匹配。

## 3. 自建 RSSHub 的 Twitter 路由

公共 RSSHub 实例基本不可用，推荐用 Docker 自建：

```bash
docker run -d --name rsshub -p 1200:1200 diygod/rsshub
```

然后启用 twitter 路由的认证配置（RSSHub 官方文档搜索 `twitter` 环境变量，配置 cookies 或 app key），最后在 `config.yaml`：

```yaml
  - type: rsshub_twitter
    name: twitter_via_rsshub
    base_url: http://localhost:1200
    accounts: [OpenAI, AnthropicAI, GoogleDeepMind, MetaAI, karpathy]
    enabled: true
```

## 4. X.com 直抓（实验性）

```bash
pip install playwright && playwright install chromium
```

浏览器登录 x.com 后把 cookies 导出为 JSON 数组文件（与 DouYinSparkFlow 的 cookies 格式一致），在 `config.yaml`：

```yaml
  - type: twitter_x
    name: twitter_x
    accounts: [OpenAI, AnthropicAI]
    cookies_path: /path/to/x_cookies.json
    enabled: true
```

⚠️ 该后端未在受限网络环境验证，风控可能要求人工验证；长期大批量抓取有封号风险，建议低频使用。

## 5. 验证源是否工作

```bash
python main.py crawl --json   # 看每个源抓了多少条、内容是否正常
```
