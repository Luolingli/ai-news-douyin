"""草稿就绪通知：Server酱（微信）优先，SMTP 邮件兜底；两者都未配置则仅记录"""
from __future__ import annotations

import logging

log = logging.getLogger("ai_news.notify")


def _serverchan(title: str, desp: str) -> bool:
    from .config import env

    key = env("SERVERCHAN_KEY")
    if not key:
        return False
    import requests

    url = f"https://sctapi.ftqq.com/{key}.send"
    try:
        r = requests.post(url, data={"title": title[:32], "desp": desp}, timeout=15)
        ok = r.status_code == 200 and r.json().get("code") == 0
        log.info("Server酱推送%s", "成功" if ok else "失败: " + r.text[:120])
        return ok
    except Exception as e:
        log.warning("Server酱推送异常: %s", e)
        return False


def _email(title: str, desp: str) -> bool:
    import smtplib
    from email.mime.text import MIMEText

    from .config import env

    host, port = env("SMTP_HOST"), env("SMTP_PORT", "465")
    user, pwd = env("SMTP_USER"), env("SMTP_PASSWORD")
    to = env("NOTIFY_EMAIL")
    if not (host and user and pwd and to):
        return False
    msg = MIMEText(desp, "plain", "utf-8")
    msg["Subject"] = title
    msg["From"] = user
    msg["To"] = to
    try:
        s = smtplib.SMTP_SSL(host, int(port), timeout=15)
        s.login(user, pwd)
        s.sendmail(user, [to], msg.as_string())
        s.quit()
        log.info("邮件通知已发送")
        return True
    except Exception as e:
        log.warning("邮件通知失败: %s", e)
        return False


def notify(title: str, desp: str) -> bool:
    """推送通知；返回是否真正送达"""
    if _serverchan(title, desp):
        return True
    if _email(title, desp):
        return True
    log.info("未配置通知渠道（SERVERCHAN_KEY 或 SMTP），仅记录: %s", title)
    return False
