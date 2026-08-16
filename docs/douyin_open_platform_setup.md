# 抖音开放平台图文发布接入指南

本项目的发布端走官方「抖音开放平台」API，需要你完成以下一次性配置（约 30 分钟~几天，取决于资质审核）。

## 1. 注册开发者并创建应用

1. 打开 https://developer.open-douyin.com ，用抖音号登录，完成**开发者认证**（个人实名即可，部分权限要求企业认证，以官方提示为准）。
2. 进入「控制台 → 应用管理 → 创建应用」。
   - 应用类型选 **网站应用**（或移动应用，都可以走 OAuth 授权）。
   - 拿到 `Client Key` 和 `Client Secret`。
3. 在应用「开发配置」里设置**授权回调地址**，例如 `https://localhost/callback`（本地授权用）或你的服务器地址；把同样的地址填进项目的 `.env` 的 `DOUYIN_REDIRECT_URI`。

## 2. 申请「内容发布」权限

1. 进入应用的「权限管理 / 能力管理」，找到 **内容发布 → 图文发布**（有的页面叫「视频发布」，图文同属内容发布组）。
2. 点击申请，按表单填写用途说明（例如：自动发布 AI 行业资讯图文，遵守平台规范，不涉及违规内容）。
3. 等待审核（通常 1~3 个工作日）。**审核通过前调用发布接口会报无权限错误。**

## 3. 配置项目

编辑项目根目录 `.env`（复制 `.env.example`）：

```
DOUYIN_CLIENT_KEY=你的ClientKey
DOUYIN_CLIENT_SECRET=你的ClientSecret
DOUYIN_REDIRECT_URI=https://localhost/callback
```

## 4. 授权账号

```bash
python main.py douyin auth      # 打印授权链接
python main.py douyin callback <code>   # 授权后把回调URL里的code粘进来
python main.py douyin whoami    # 确认授权账号
```

授权成功后令牌会存入 `data/app.db`；如果要用 GitHub Actions 云端运行，把 `DOUYIN_ACCESS_TOKEN / DOUYIN_REFRESH_TOKEN / DOUYIN_OPEN_ID` 复制到仓库 secrets（本项目支持用 `GH_WRITEBACK_REPO`+`GH_WRITEBACK_TOKEN` 自动回写，见 `.env.example`）。

## 5. 令牌生命周期（自动处理）

| 令牌 | 有效期 | 处理方式 |
|---|---|---|
| access_token | 约 15 天 | 过期/无效时自动用 refresh_token 刷新后重试（代码内置） |
| refresh_token | 约 30 天 | 每次刷新时若返回新值自动保存；建议每天 `python main.py douyin renew` 一次续期（GH Actions 工作流已内置该步骤） |

## 6. 发布接口说明

发布走「图文上传 + 创建图文」两步：

```
POST https://open.douyin.com/api/douyin/v1/image/upload_image/   # 上传图片(multipart,字段image)，返回image_id
POST https://open.douyin.com/api/douyin/v1/image/create_image/  # 创建图文(body: image_ids + text)，返回item_id
```

旧版路径 `/api/douyin/v1/video/upload_image/` + `/api/douyin/v1/video/create_image_text/`（body 用 `image_list`）也做了兼容：`config.yaml` 的 `douyin.api_style` 可设为 `modern` / `legacy` / `auto`（auto 会先试 modern，404 自动回退 legacy）。

## 7. 常见问题

- **error_code=10008 / 提示 token 无效**：代码会自动刷新重试一次；持续失败请重新执行第 4 步授权。
- **无权限错误**：内容发布权限未通过审核，见第 2 步。
- **图文至少 1 张图**：项目默认自动生成 1080x1440 封面，保证有图。
- **文案长度**：图文正文限制约 1000 字，代码会自动截断。
- **话题审核**：`#话题` 仍走抖音审核逻辑，避免使用导流类话题。
