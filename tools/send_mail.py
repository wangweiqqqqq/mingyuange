# -*- coding: utf-8 -*-
"""明远阁发信工具（SMTP）。

密码从环境变量读，绝不出现在命令行或日志里：
  DSH_SECRET_SMTP_PASSWORD

其余参数：
  SMTP_HOST  SMTP_PORT(默认 465)  SMTP_USER(发件地址，也是默认收件人)

用法：
  & python send_mail.py --to someone@example.com --subject "标题" --body "正文" [--attach 文件]

例子（明远阁日报）：
  $env:DSH_SECRET_SMTP_PASSWORD = $env:DSH_SECRET_SMTP_PASSWORD
  & 'D:\\明远阁\\.venv\\Scripts\\python.exe' 'D:\\明远阁\\tools\\send_mail.py' `
      --to user@qq.com --subject "2026-10-23 收盘摘要" --body-file report.md --attach samples/quote.json
"""
import argparse
import json
import os
import smtplib
import ssl
import sys
from email.message import EmailMessage
from pathlib import Path

CONFIG_PATH = Path(__file__).resolve().parent.parent / "mail_config.json"
_CFG = {}
try:
    if CONFIG_PATH.exists():
        _CFG = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
except Exception:  # noqa: BLE001
    _CFG = {}

HOST = os.environ.get("SMTP_HOST") or _CFG.get("host", "")
PORT = int(os.environ.get("SMTP_PORT") or _CFG.get("port", 465))
USER = os.environ.get("SMTP_USER") or _CFG.get("user", "")
DEFAULT_TO = os.environ.get("SMTP_TO") or _CFG.get("to", USER)
if isinstance(DEFAULT_TO, (list, tuple)):
    DEFAULT_TO = ",".join(str(x) for x in DEFAULT_TO)
PASSWORD = os.environ.get("DSH_SECRET_SMTP_PASSWORD", "")


def main() -> int:
    ap = argparse.ArgumentParser(description="明远阁发信（SMTP）")
    ap.add_argument("--to", required=False, default=DEFAULT_TO, help="收件人，多个用逗号分隔")
    ap.add_argument("--subject", required=True)
    ap.add_argument("--body", default="")
    ap.add_argument("--body-file", default="")
    ap.add_argument("--attach", nargs="*", default=[])
    args = ap.parse_args()

    missing = [n for n, v in
               (("SMTP_HOST", HOST), ("SMTP_USER", USER), ("DSH_SECRET_SMTP_PASSWORD", PASSWORD)) if not v]
    if missing:
        print("MISSING_CONFIG " + ",".join(missing))
        return 2
    if not args.to:
        print("MISSING_TO")
        return 2

    body = args.body
    if args.body_file:
        body = Path(args.body_file).read_text(encoding="utf-8")
    if not body:
        print("EMPTY_BODY")
        return 2

    msg = EmailMessage()
    msg["From"] = USER
    msg["To"] = args.to
    msg["Subject"] = args.subject
    msg.set_content(body, subtype="plain", charset="utf-8")
    msg.add_alternative(f"<pre style=\"font-family:Consolas,monospace\">{body}</pre>",
                        subtype="html", charset="utf-8")

    for path in args.attach:
        p = Path(path)
        if not p.exists():
            print(f"SKIP_MISSING_ATTACH {path}")
            continue
        msg.add_attachment(p.read_bytes(), maintype="application", subtype="octet-stream",
                           filename=p.name)

    try:
        context = ssl.create_default_context()
        if PORT == 465:
            with smtplib.SMTP_SSL(HOST, PORT, context=context, timeout=30) as s:
                s.login(USER, PASSWORD)
                s.send_message(msg)
        else:
            with smtplib.SMTP(HOST, PORT, timeout=30) as s:
                s.ehlo()
                s.starttls(context=context)
                s.login(USER, PASSWORD)
                s.send_message(msg)
        print(f"SENT to={args.to} subject={args.subject}")
        return 0
    except smtplib.SMTPAuthenticationError as exc:
        print(f"AUTH_FAILED {exc.smtp_code} {exc.smtp_error!r}")
        return 3
    except Exception as exc:  # noqa: BLE001
        print(f"SEND_FAILED {type(exc).__name__}: {exc}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
