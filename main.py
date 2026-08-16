"""
AI News → 抖音 自动搬运流水线

用法示例:
  python main.py init                  # 生成 config.yaml
  python main.py run --limit 5 --dry-run   # 试跑一轮（不发布）
  python main.py run --limit 5             # 跑一轮并发布
  python main.py loop --interval 3600      # 定时循环（无人值守）
  python main.py crawl                    # 只抓取入库
  python main.py drafts                   # 查看草稿/记录
  python main.py publish --dry-run        # 发布 ready 草稿
  python main.py douyin auth              # 打印抖音授权链接
  python main.py douyin callback <code>   # 用授权 code 换取令牌
  python main.py douyin whoami            # 查看当前授权账号
  python main.py douyin renew             # 续期 refresh_token
"""
from __future__ import annotations

import argparse
import json
import logging
import re
import sys
from pathlib import Path

from ai_news import config as cfg_mod
from ai_news.config import get
from ai_news.db import DB
from ai_news.logging_setup import setup_logging
from ai_news.pipeline import Pipeline
from ai_news.publisher import DouyinOpenClient, DouyinError, TokenStore
from ai_news.scheduler import LoopRunner
from ai_news.utils import publish_ready, show_posts

log = logging.getLogger("ai_news.cli")


def cmd_init(args) -> int:
    target = Path("config.yaml")
    if target.exists():
        print(f"config.yaml 已存在: {target.resolve()}")
        return 0
    example = Path(__file__).parent.parent / "config.yaml.example"
    target.write_text(example.read_text(encoding="utf-8"), encoding="utf-8")
    print(f"已生成 {target.resolve()}，请编辑后使用；密钥填入 .env（参考 .env.example）")
    return 0


def _load() -> tuple[dict, DB, Pipeline]:
    cfg = cfg_mod.load_config()
    data_dir = Path(get(cfg, "data_dir", "data"))
    db = DB(data_dir / "app.db")
    setup_logging(get(cfg, "log_level", "INFO"), log_dir=str(data_dir / "logs"))
    return cfg, db, Pipeline(cfg, db)


def cmd_run(args) -> int:
    cfg, db, pipe = _load()
    sources = args.sources.split(",") if args.sources else None
    stats = pipe.run(limit=args.limit, sources=sources, dry_run=args.dry_run, skip_llm=args.skip_llm)
    print(json.dumps(stats, ensure_ascii=False, indent=2))
    db.close()
    return 0 if stats["failed"] == 0 else 1


def cmd_loop(args) -> int:
    cfg, db, pipe = _load()
    runner = LoopRunner(pipe, interval=args.interval, limit=args.limit, dry_run=args.dry_run,
                        skip_llm=args.skip_llm)
    try:
        runner.run_forever()
    finally:
        db.close()
    return 0


def cmd_crawl(args) -> int:
    cfg, db, pipe = _load()
    new_ids = pipe.crawl(sources_filter=args.sources.split(",") if args.sources else None)
    print(f"新增 {len(new_ids)} 条")
    if args.json:
        items = [db.get_item(i) for i in new_ids]
        print(json.dumps(items, ensure_ascii=False, indent=2))
    db.close()
    return 0


def cmd_drafts(args) -> int:
    cfg, db, pipe = _load()
    posts = db.get_posts(status=None, limit=args.limit)
    print(show_posts(posts))
    db.close()
    return 0


def cmd_publish(args) -> int:
    cfg, db, pipe = _load()
    stats = publish_ready(pipe, dry_run=args.dry_run, limit=args.limit)
    print(json.dumps(stats, ensure_ascii=False))
    db.close()
    return 0


def _douyin_client(cfg: dict, db: DB) -> DouyinOpenClient:
    return DouyinOpenClient(get(cfg, "douyin", {}), TokenStore(db))


def cmd_douyin_auth(args) -> int:
    cfg, db, _ = _load()
    client = _douyin_client(cfg, db)
    if not client.client_key:
        print("未配置 DOUYIN_CLIENT_KEY（见 .env）", file=sys.stderr)
        return 1
    print("请在浏览器打开以下链接并授权：")
    print(client.authorize_url())
    print("\n授权后浏览器会跳转到回调地址，把 URL 里的 code 参数值拿来执行：")
    print("  python main.py douyin callback <code>")
    db.close()
    return 0


def cmd_douyin_callback(args) -> int:
    cfg, db, _ = _load()
    client = _douyin_client(cfg, db)
    code = args.code.strip()
    m = re.search(r"code=([^&]+)", code)
    if m:
        code = m.group(1)
    try:
        d = client.exchange_code(code)
        try:
            info = client.userinfo()
        except Exception:
            info = {}
        print("授权成功：")
        print("  open_id:", d.get("open_id"))
        print("  昵称:", (info or {}).get("nickname") or (info or {}).get("e_account_role") or "未知")
        print("  access_token 有效期:", d.get("expires_in"), "秒")
        print("令牌已保存到数据库；如需 GitHub Actions 云端运行，请把令牌复制到仓库 secrets（见 .env.example）")
    except DouyinError as e:
        print(f"授权失败: {e}", file=sys.stderr)
        return 1
    finally:
        db.close()
    return 0



def cmd_douyin_tokens(args) -> int:
    """打印当前授权令牌；--gh 直接写入 GitHub secrets"""
    import shutil
    import subprocess

    cfg, db, _ = _load()
    store = TokenStore(db)
    vals = {
        "DOUYIN_ACCESS_TOKEN": store.get("access_token"),
        "DOUYIN_REFRESH_TOKEN": store.get("refresh_token"),
        "DOUYIN_OPEN_ID": store.get("open_id"),
    }
    missing = [k for k, v in vals.items() if not v]
    if missing:
        print("以下令牌为空（请先执行: python main.py douyin auth → callback <code>）:",
              ", ".join(missing), file=sys.stderr)
    if args.gh:
        repo = args.repo or cfg_mod.env("GH_WRITEBACK_REPO")
        if not repo or not shutil.which("gh"):
            print("需要 --repo <owner/repo> 参数（或 GH_WRITEBACK_REPO 环境变量）且已安装 gh", file=sys.stderr)
            return 1
        for k, v in vals.items():
            if not v:
                continue
            r = subprocess.run(["gh", "secret", "set", k, "--repo", repo, "--body", v],
                               capture_output=True, text=True, timeout=30)
            print(f"{k}: {'已写入 ' + repo if r.returncode == 0 else '写入失败: ' + r.stderr.strip()}")
        return 0
    for k, v in vals.items():
        print(f"{k}={v}" if v else f"{k}=(空)")
    print("\n复制以上三个值到 GitHub 仓库: Settings → Secrets and variables → Actions")
    print("或直接执行: python main.py douyin tokens --gh --repo Luolingli/ai-news-douyin")
    return 0


def pub_try_text(cfg: dict, post: dict, tags: list[str]) -> str:
    prefix = (get(cfg, "douyin.text_prefix", "") or "")
    parts = [prefix, post.get("title", ""), "", post.get("body", "")]
    if tags:
        parts += ["", " ".join("#" + t for t in tags)]
    return "\n".join(p for p in parts if p or p == "" or p is None)[:1000]


def cmd_douyin_web(args) -> int:
    """网页版发布器：login=扫码登录；check=检查登录态；try=试发布（不点发布）；publish=发布指定草稿"""
    from ai_news.publisher.douyin_web import DouyinWebPublisher

    cfg, db, _ = _load()
    web_action = (args.code or "check").strip().lower()
    post_id = int(args.post_id) if getattr(args, "post_id", "") else 0
    web_cfg = dict(get(cfg, "douyin.web", {}))
    if args.headless:
        web_cfg["headless"] = True
    web_cfg["data_dir"] = str(Path(get(cfg, "data_dir", "data")))
    web_cfg["screenshot_dir"] = str(Path(get(cfg, "data_dir", "data")) / "logs" / "screenshots")
    pub = DouyinWebPublisher(web_cfg)
    if web_action == "login":
        res = pub.login_interactive(wait_minutes=5)
        print(res)
    elif web_action == "try":
        if not post_id:
            print("用法: python main.py douyin web try --post-id <ID>  （先 python main.py drafts 看 ID）", file=sys.stderr)
            db.close()
            return 1
        all_posts = db.get_posts(status=None, limit=1000)
        post = next((p for p in all_posts if p["id"] == post_id), None)
        if not post:
            print(f"找不到草稿 {post_id}", file=sys.stderr)
            db.close()
            return 1
        import json as _json
        images = _json.loads(post.get("images") or "[]")
        tags = _json.loads(post.get("hashtags") or "[]")
        text = pub_try_text(cfg, post, tags)
        res = pub.upload_only(images, text)
        print(res)
    elif web_action == "publish":
        if not post_id:
            print("用法: python main.py douyin web publish --post-id <ID>", file=sys.stderr)
            db.close()
            return 1
        import json as _json
        from datetime import datetime, timezone
        ready_posts = db.get_posts("ready", limit=1000)
        post = next((p for p in ready_posts if p["id"] == post_id), None)
        if not post:
            print(f"找不到 ready 草稿 {post_id}", file=sys.stderr)
            db.close()
            return 1
        images = _json.loads(post.get("images") or "[]")
        tags = _json.loads(post.get("hashtags") or "[]")
        text = pub_try_text(cfg, post, tags)
        r = pub.publish(images, text, dry_run=False)
        print(r)
        db.close()
        if r.get("ok"):
            db.update_post(post_id, status="published", douyin_item_id=r.get("item_id", ""),
                           published_at=datetime.now(timezone.utc).isoformat(timespec="seconds"))
            return 0
        db.update_post(post_id, status="failed", error=r.get("message", "")[:500])
        return 1
    else:
        res = pub.check_login()
        if res["logged_in"]:
            print(f"登录正常：{res['account'] or '账号已登录'} | {res['url'][:80]}")
        else:
            print(f"未登录（cookies 失效）：{res['url'][:80]}")
            print("请执行: python main.py douyin web login")
        db.close()
        return 0 if res["logged_in"] else 1
    db.close()
    return 0 if res.get("ok") else 1


def cmd_douyin_whoami(args) -> int:
    cfg, db, _ = _load()
    client = _douyin_client(cfg, db)
    try:
        info = client.userinfo()
        print(json.dumps(info, ensure_ascii=False, indent=2))
    except DouyinError as e:
        print(f"获取失败（可能需要先授权/刷新）: {e}", file=sys.stderr)
        return 1
    finally:
        db.close()
    return 0


def cmd_douyin_renew(args) -> int:
    cfg, db, _ = _load()
    client = _douyin_client(cfg, db)
    try:
        client.renew_refresh_token()
        print("refresh_token 续期成功（已保存）")
    except DouyinError as e:
        print(f"续期失败: {e}", file=sys.stderr)
        return 1
    finally:
        db.close()
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="AI 新闻 → 抖音 自动搬运流水线")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("init", help="生成 config.yaml")
    p.set_defaults(fn=cmd_init)

    p = sub.add_parser("run", help="跑一轮完整流水线")
    p.add_argument("--limit", type=int, default=5)
    p.add_argument("--sources", default=None, help="逗号分隔的源名称，如 tg_ai_news,google_ai")
    p.add_argument("--dry-run", action="store_true", help="不真正发布")
    p.add_argument("--skip-llm", action="store_true", help="跳过 LLM（用本地降级）")
    p.set_defaults(fn=cmd_run)

    p = sub.add_parser("loop", help="定时循环运行")
    p.add_argument("--interval", type=int, default=3600, help="间隔秒数")
    p.add_argument("--limit", type=int, default=5)
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--skip-llm", action="store_true")
    p.set_defaults(fn=cmd_loop)

    p = sub.add_parser("crawl", help="只抓取入库")
    p.add_argument("--sources", default=None)
    p.add_argument("--json", action="store_true", help="打印条目详情")
    p.set_defaults(fn=cmd_crawl)

    p = sub.add_parser("drafts", help="查看处理记录")
    p.add_argument("--limit", type=int, default=20)
    p.set_defaults(fn=cmd_drafts)

    p = sub.add_parser("publish", help="发布 ready 草稿")
    p.add_argument("--limit", type=int, default=10)
    p.add_argument("--dry-run", action="store_true")
    p.set_defaults(fn=cmd_publish)

    p = sub.add_parser("douyin", help="抖音授权管理")
    p.add_argument("action", choices=["auth", "callback", "whoami", "renew", "tokens", "web"])
    p.add_argument("code", nargs="?", default="", help="callback 用的授权 code 或回调 URL；web 子命令用 login/check")
    p.add_argument("--gh", action="store_true", help="tokens 直接写入 GitHub secrets")
    p.add_argument("--repo", default="", help="tokens --gh 时指定 owner/repo")
    p.add_argument("--headless", action="store_true", help="web 子命令无头模式（不弹窗）")
    p.add_argument("--post-id", default="", help="web try/publish 时指定草稿 ID")
    p.set_defaults(fn=lambda a: {"auth": cmd_douyin_auth, "callback": cmd_douyin_callback,
                                "whoami": cmd_douyin_whoami, "renew": cmd_douyin_renew,
                                "tokens": cmd_douyin_tokens, "web": cmd_douyin_web}[a.action](a))

    args = parser.parse_args()
    return args.fn(args)


if __name__ == "__main__":
    sys.exit(main())
