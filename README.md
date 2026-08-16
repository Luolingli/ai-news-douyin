# AI News → 抖音 自动搬运流水线

把 Twitter/AI 资讯源上的 AI 新闻，全自动「检测 → 总结 → 配图 → 发布」到抖音（图文作品）。

> 本地跑一条命令即可无人值守运行；也支持 GitHub Actions 云端定时运行（参考你已有的 DouYinSparkFlow 部署方式）。

## 功能

- **内容爬取**：多后端内容源（Telegram 频道、Google News、自建 RSSHub 的 Twitter 路由、X.com 直抓），多源自动合并去重
- **内容检测**：
  - AI 相关性过滤（关键词打分 + DeepSeek 复核）
  - 敏感/违规内容过滤（硬词表 + 引流信号正则 + LLM 复核）
  - 重复内容去重（URL 精确去重 + 文本相似度去重，跨源同新闻只发一次）
- **内容总结**：DeepSeek 生成抖音风格标题/正文/话题标签（未配 key 时自动降级为本地裁剪，可先跑通全流程）
- **内容发布**：双路线——① 抖音开放平台 API（需企业资质，自动刷新令牌）；② **创作者中心网页版自动化（个人账号可用，Playwright 模拟操作，复用你已有的 keepalive cookies）**；自动生成 1080x1440 封面卡 + 下载原文配图
- **全自动**：`loop` 定时模式 / crontab / GitHub Actions，SQLite 记录全链路状态，幂等不重发

## 快速开始

```bash
cd ai-news-douyin
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt

cp config.yaml.example config.yaml   # 按需改内容源/检测参数
cp .env.example .env                 # 填 DeepSeek key；抖音凭据见下方

.venv/bin/python main.py douyin web login   # 首次：弹窗扫码登录抖音（个人账号路线）
.venv/bin/python main.py douyin web check    # 确认登录态
.venv/bin/python main.py run --dry-run --limit 3   # 试跑一轮（只生成不发布）
.venv/bin/python main.py drafts                    # 查看处理记录
.venv/bin/python main.py run --limit 5             # 正式跑（会发布到抖音）
.venv/bin/python main.py loop --interval 3600      # 无人值守循环
```

## 目录结构

```
main.py                     # CLI 入口
config.yaml.example         # 配置模板（内容源/检测/媒体/发布）
.env.example                # 密钥模板
ai_news/
  crawlers/                 # 内容源爬虫（tme/googlenews/rss/rsshub_twitter/twitter_x）
  detection/                # AI相关性 / 敏感过滤 / 去重
  llm/                      # DeepSeek 客户端 + Prompt
  media/                    # 封面生成 + 图片下载
  publisher/                # 抖音开放平台客户端 + 令牌管理
  pipeline.py               # 主流水线
  scheduler.py              # 定时循环
docs/                       # 抖音接入指南 / 内容源配置指南
tests/                      # 离线测试（python tests/run_all.py）
.github/workflows/auto_run.yml  # 可选：云端定时运行
```

## 完整配置步骤

1. **内容源**：编辑 `config.yaml`，详见 [docs/content_sources.md](docs/content_sources.md)（默认已启用 Telegram 频道 + Google News，开箱即可跑）
2. **DeepSeek**：`.env` 填 `DEEPSEEK_API_KEY`（https://platform.deepseek.com 创建）
3. **抖音发布**：个人账号走网页版路线（推荐）——`python main.py douyin web login` 扫码一次，之后自动复用 keepalive cookies；有企业资质可走 API 路线，见 [docs/douyin_open_platform_setup.md](docs/douyin_open_platform_setup.md)
4. **定时运行**（二选一）：
   - **GitHub Actions 云端自动**（推荐）：在仓库 Settings → Secrets and variables → Actions 配置 `DOUYIN_WEB_COOKIES_B64`（本地 `data/web_cookies.json` 的 base64，命令见下）和 `DEEPSEEK_API_KEY`，可选 `AI_NEWS_PAT`（cookies 自动回写续期）。之后每 4 小时自动抓取+发布，无需开电脑：
     ```bash
     base64 -i data/web_cookies.json | tr -d '\n'   # macOS 生成 secret 值
     ```
   - **本地无人值守**：`python main.py loop --interval 14400` 或 macOS launchd / crontab 定时

## 运行测试

```bash
.venv/bin/python tests/run_all.py
```

## 免责声明

本项目仅用于个人学习与自用。请遵守抖音社区规范与《用户服务协议》、遵守各内容源平台条款；抓取频率保持低频；发布前建议人工抽查内容质量。因使用本项目产生的账号处罚等风险由使用者自行承担。
