"""抖音开放平台客户端：OAuth 授权 + 图文发布"""
from __future__ import annotations

import logging
import time

import requests

from .token_store import TokenStore

log = logging.getLogger("ai_news.douyin")

BASE = "https://open.douyin.com"

# 常见错误码：access_token 无效/过期 等需要刷新重试的
TOKEN_ERROR_CODES = {10008, 10012, 11010, 2190008}

# 图文接口路径（modern=官方现行 /api/douyin/v1/image/*；legacy=旧版 /api/douyin/v1/video/*）
ENDPOINTS = {
    "modern": {"upload": "/api/douyin/v1/image/upload_image/", "create": "/api/douyin/v1/image/create_image/"},
    "legacy": {"upload": "/api/douyin/v1/video/upload_image/", "create": "/api/douyin/v1/video/create_image_text/"},
}


class DouyinError(Exception):
    pass


class DouyinOpenClient:
    def __init__(self, cfg: dict, token_store: TokenStore):
        self.cfg = cfg
        self.tokens = token_store
        self.client_key = token_store.get("CLIENT_KEY")
        self.client_secret = token_store.get("CLIENT_SECRET")
        self.redirect_uri = token_store.get("REDIRECT_URI") or "https://localhost/callback"
        self.scope = (cfg.get("scope") or "user_info,video.create").strip()
        self.api_style = (cfg.get("api_style") or "auto").lower()

    # ---------- OAuth ----------
    def authorize_url(self, state: str = "ai_news") -> str:
        params = {
            "client_key": self.client_key,
            "response_type": "code",
            "scope": self.scope,
            "redirect_uri": self.redirect_uri,
            "state": state,
        }
        import urllib.parse

        return f"{BASE}/platform/oauth/connect/?" + urllib.parse.urlencode(params)

    def _post_form(self, path: str, data: dict, timeout: int = 30) -> dict:
        resp = requests.post(f"{BASE}{path}", data=data, timeout=timeout)
        try:
            j = resp.json()
        except Exception:
            raise DouyinError(f"接口 {path} 返回非 JSON: HTTP {resp.status_code} {resp.text[:200]}") from None
        data_ = j.get("data") or {}
        err_code = data_.get("error_code", j.get("extra", {}).get("error_code", 0))
        if err_code not in (0, None, ""):
            raise DouyinError(f"接口 {path} 失败: error_code={err_code} {data_.get('description') or j.get('extra', {}).get('description')}")
        return j

    def exchange_code(self, code: str) -> dict:
        j = self._post_form("/oauth/access_token/", {
            "client_key": self.client_key,
            "client_secret": self.client_secret,
            "code": code.strip(),
            "grant_type": "authorization_code",
        })
        d = j["data"]
        self.tokens.set("access_token", d.get("access_token", ""))
        self.tokens.set("refresh_token", d.get("refresh_token", ""))
        self.tokens.set("open_id", d.get("open_id", ""))
        self.tokens.set("access_expires_at", str(int(time.time()) + int(d.get("expires_in", 0))))
        return d

    def refresh_access_token(self) -> dict:
        rt = self.tokens.get("refresh_token")
        if not rt:
            raise DouyinError("没有 refresh_token，请重新执行 douyin auth 授权")
        j = self._post_form("/oauth/refresh_token/", {
            "client_key": self.client_key,
            "grant_type": "refresh_token",
            "refresh_token": rt,
        })
        d = j["data"]
        self.tokens.set("access_token", d.get("access_token", ""))
        # 部分场景会返回新的 refresh_token
        if d.get("refresh_token"):
            self.tokens.set("refresh_token", d["refresh_token"])
        self.tokens.set("open_id", d.get("open_id", ""))
        self.tokens.set("access_expires_at", str(int(time.time()) + int(d.get("expires_in", 0))))
        return d

    def renew_refresh_token(self) -> dict:
        rt = self.tokens.get("refresh_token")
        if not rt:
            raise DouyinError("没有 refresh_token")
        j = self._post_form("/oauth/renew_refresh_token/", {
            "client_key": self.client_key,
            "grant_type": "refresh_token",
            "refresh_token": rt,
        })
        d = j["data"]
        if d.get("refresh_token"):
            self.tokens.set("refresh_token", d["refresh_token"])
        if d.get("open_id"):
            self.tokens.set("open_id", d["open_id"])
        log.info("refresh_token 已续期")
        return d

    def userinfo(self) -> dict:
        at = self.tokens.get("access_token")
        resp = requests.get(f"{BASE}/oauth/userinfo/", params={"access_token": at}, timeout=30)
        j = resp.json()
        return j.get("data") or {}

    def ensure_access_token(self) -> str:
        at = self.tokens.get("access_token")
        if at:
            return at
        self.refresh_access_token()
        at = self.tokens.get("access_token")
        if not at:
            raise DouyinError("无法获取 access_token")
        return at

    # ---------- 图文发布 ----------
    def _endpoint(self, kind: str) -> tuple[str, dict]:
        """返回 (路径, body字段名映射)，api_style=auto 时先 modern 再 legacy"""
        if self.api_style == "legacy":
            return ENDPOINTS["legacy"][kind], {"images": "image_list"}
        return ENDPOINTS["modern"][kind], {"images": "image_ids"}

    def _call_with_token_retry(self, fn):
        """token 失效自动刷新重试一次"""
        try:
            return fn()
        except DouyinError as e:
            msg = str(e)
            if any(str(c) in msg for c in TOKEN_ERROR_CODES) or "token" in msg.lower():
                log.info("token 可能失效，尝试刷新: %s", msg[:120])
                self.refresh_access_token()
                return fn()
            raise

    def upload_image(self, image_path: str) -> str:
        at = self.ensure_access_token()
        open_id = self.tokens.get("open_id")
        if not open_id:
            raise DouyinError("缺少 open_id，请重新授权")

        def _upload(path: str) -> str:
            with open(image_path, "rb") as f:
                resp = requests.post(
                    f"{BASE}{path}",
                    params={"access_token": at, "open_id": open_id},
                    files={"image": f},
                    timeout=120,
                )
            try:
                j = resp.json()
            except Exception:
                raise DouyinError(f"上传图片失败: HTTP {resp.status_code} {resp.text[:200]}") from None
            d = j.get("data") or {}
            if d.get("error_code") not in (0, None, ""):
                raise DouyinError(f"上传图片失败: error_code={d.get('error_code')} {d.get('description')}")
            image_id = (d.get("image") or {}).get("image_id") or d.get("image_id") or ""
            if not image_id:
                raise DouyinError(f"上传图片响应缺少 image_id: {j}")
            return image_id

        def _upload_try() -> str:
            if self.api_style == "legacy":
                return _upload(ENDPOINTS["legacy"]["upload"])
            try:
                return _upload(ENDPOINTS["modern"]["upload"])
            except DouyinError as e:
                if self.api_style == "auto" and ("404" in str(e) or "405" in str(e) or "endpoint" in str(e).lower()):
                    log.info("modern 路径不可用，回退 legacy 路径: %s", e)
                    return _upload(ENDPOINTS["legacy"]["upload"])
                raise

        return self._call_with_token_retry(_upload_try)

    def create_image_text(self, image_ids: list[str], text: str) -> str:
        at = self.ensure_access_token()
        open_id = self.tokens.get("open_id")
        if not open_id:
            raise DouyinError("缺少 open_id，请重新授权")

        def _create(path: str, body: dict) -> str:
            resp = requests.post(
                f"{BASE}{path}",
                params={"access_token": at, "open_id": open_id},
                json=body,
                timeout=60,
            )
            try:
                j = resp.json()
            except Exception:
                raise DouyinError(f"发布图文失败: HTTP {resp.status_code} {resp.text[:200]}") from None
            d = j.get("data") or {}
            if d.get("error_code") not in (0, None, ""):
                raise DouyinError(f"发布图文失败: error_code={d.get('error_code')} {d.get('description')}")
            item_id = d.get("item_id") or d.get("item_id_str") or ""
            if not item_id:
                raise DouyinError(f"发布图文响应缺少 item_id: {j}")
            return str(item_id)

        def _create_try() -> str:
            if self.api_style == "legacy":
                return _create(ENDPOINTS["legacy"]["create"], {"image_list": image_ids, "text": text})
            try:
                return _create(ENDPOINTS["modern"]["create"], {"image_ids": image_ids, "text": text})
            except DouyinError as e:
                if self.api_style == "auto" and ("404" in str(e) or "405" in str(e) or "endpoint" in str(e).lower()):
                    log.info("modern 路径不可用，回退 legacy 路径: %s", e)
                    return _create(ENDPOINTS["legacy"]["create"], {"image_list": image_ids, "text": text})
                raise

        return self._call_with_token_retry(_create_try)

    def publish(self, image_paths: list[str], text: str, dry_run: bool = False) -> str:
        """发布图文：上传全部图片 → 创建图文。返回抖音 item_id"""
        if dry_run:
            log.info("[dry-run] 将发布图文：图片 %d 张，文案 %d 字", len(image_paths), len(text))
            return "dry-run"
        if not image_paths:
            raise DouyinError("图文至少需要 1 张图片")
        image_ids = []
        for p in image_paths:
            try:
                iid = self.upload_image(p)
                image_ids.append(iid)
                log.info("图片上传成功: %s -> %s", p, iid)
            except Exception as e:
                log.warning("图片上传失败 %s: %s", p, e)
        if not image_ids:
            raise DouyinError("所有图片上传失败，放弃发布")
        return self.create_image_text(image_ids, text)
