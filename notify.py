# -*- coding: utf-8 -*-
"""邮件通知（预约演示等）：SMTP 环境变量驱动，发送失败绝不抛出影响主流程。

环境变量：SMTP_HOST(默认 smtp.qq.com) SMTP_PORT(默认 465/SSL)
          SMTP_USER SMTP_PASS(授权码，非登录密码) NOTIFY_TO(默认=SMTP_USER)
"""
import os
import smtplib
import ssl
from email.header import Header
from email.mime.text import MIMEText
from email.utils import formataddr


def _conf():
    user = (os.environ.get("SMTP_USER") or "").strip()
    pwd = (os.environ.get("SMTP_PASS") or "").strip()
    host = (os.environ.get("SMTP_HOST") or "smtp.qq.com").strip()
    try:
        port = int((os.environ.get("SMTP_PORT") or "465").strip() or 465)
    except ValueError:
        port = 465
    to = (os.environ.get("NOTIFY_TO") or user).strip()
    return host, port, user, pwd, to


def email_ready():
    host, port, user, pwd, to = _conf()
    return bool(user and pwd and to)


def send_email(subject, body):
    """返回 (ok, detail)。任何异常都收敛为 (False, 原因短句)。"""
    host, port, user, pwd, to = _conf()
    if not (user and pwd and to):
        return False, "SMTP 未配置（SMTP_USER/SMTP_PASS）"
    try:
        msg = MIMEText(body, "plain", "utf-8")
        msg["Subject"] = Header(subject, "utf-8")
        msg["From"] = formataddr(("智能制造专区", user))
        msg["To"] = to
        ctx = ssl.create_default_context()
        if port == 465:
            with smtplib.SMTP_SSL(host, port, timeout=20, context=ctx) as s:
                s.login(user, pwd)
                s.sendmail(user, [to], msg.as_string())
        else:
            with smtplib.SMTP(host, port, timeout=20) as s:
                s.starttls(context=ctx)
                s.login(user, pwd)
                s.sendmail(user, [to], msg.as_string())
        return True, "已发送至 %s" % to
    except Exception as e:
        return False, "发送失败：%s" % str(e)[:160]
