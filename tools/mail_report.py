# -*- coding: utf-8 -*-
"""把每日收盘总结发到邮箱。

配置读取顺序：
1. D:\\明远阁\\mail_config.json   （host / port / user / to，不含密码）
2. 密码从环境变量 DSH_SECRET_MAIL_PASS 读（由 request_secret 注入，不落盘）

mail_config.json 示例：
{
  "host": "smtp.qq.com",
  "port": 465,
  "user": "you@qq.com",
  "to": ["you@qq.com"],
  "subject_prefix": "明远阁 | 收盘总结"
}

用法：
    python tools/mail_report.py                    # 发当天报告
    python tools/mail_report.py --file 报告路径      # 发指定文件
    python tools/mail_report.py --test             # 只测试连通性
"""
import argparse
import datetime
import os
import smtplib
import ssl
import sys
from email.header import Header
from email.mime.text import MIMEText
from email.utils import formataddr

CONFIG = None  # 由 common 解析
REPORT_DIR = None
try:
    import os as _os
    import sys as _sys
    _sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))
    from common import MAIL_CONFIG as CONFIG, REPORT_DIR  # noqa: F811
except Exception:
    CONFIG = r"D:\明远阁\mail_config.json"
    REPORT_DIR = r"D:\明远阁\reports"
SECRET_ENV = "DSH_SECRET_MAIL_PASS"
SECRET_ENV_ALT = ["DSH_SECRET_SMTP_PASSWORD", "DSH_SECRET_MAIL_PASSWORD"]


def load_config():
    import json
    if not os.path.exists(CONFIG):
        sys.exit(f"缺少配置文件：{CONFIG}")
    with open(CONFIG, encoding="utf-8") as f:
        return json.load(f)


def send(cfg, subject, body):
    pwd = os.environ.get(SECRET_ENV)
    for alt in SECRET_ENV_ALT:
        if not pwd:
            pwd = os.environ.get(alt)
    if not pwd:
        # 计划任务场景下没有 DSH 环境变量，改从本机 DPAPI 加密文件读
        try:
            sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
            from secret_store import load_secret
            pwd = load_secret()
        except Exception:
            pwd = None
    if not pwd:
        sys.exit(f"缺少邮箱授权码：环境变量 {SECRET_ENV} / {' / '.join(SECRET_ENV_ALT)} 均未设置，"
                 f"且本机加密文件不可用")

    msg = MIMEText(body, "plain", "utf-8")
    msg["Subject"] = Header(subject, "utf-8")
    msg["From"] = formataddr(("明远阁分析团队", cfg["user"]))
    msg["To"] = ", ".join(cfg["to"])

    host, port = cfg["host"], int(cfg.get("port", 465))
    if port == 465:
        server = smtplib.SMTP_SSL(host, port, timeout=30, context=ssl.create_default_context())
    else:
        server = smtplib.SMTP(host, port, timeout=30)
        server.starttls(context=ssl.create_default_context())
    try:
        server.login(cfg["user"], pwd)
        server.sendmail(cfg["user"], cfg["to"], msg.as_string())
    finally:
        try:
            server.quit()
        except Exception:
            pass
    print(f"[OK] 已发送：{subject} → {cfg['to']}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--file")
    ap.add_argument("--body")
    ap.add_argument("--subject")
    ap.add_argument("--test", action="store_true")
    a = ap.parse_args()

    cfg = load_config()
    today = datetime.date.today().isoformat()

    if a.test:
        send(cfg, f"{cfg.get('subject_prefix','明远阁')} | 连通性测试 {today}",
             "这是一封测试邮件，收到说明 SMTP 配置可用。")
        return

    if a.body:
        send(cfg, a.subject or f"{cfg.get('subject_prefix','明远阁')} | {today}", a.body)
        return

    if a.file:
        path = a.file
    else:
        cand = [
            os.path.join(REPORT_DIR, f"premarket-{today}.md"),
            os.path.join(REPORT_DIR, f"{today}.md"),
        ]
        path = next((p for p in cand if os.path.exists(p)), cand[-1])
    if not os.path.exists(path):
        sys.exit(f"报告不存在：{path}（先跑 premarket.py 或 daily_report.py）")
    with open(path, encoding="utf-8") as f:
        body = f.read()

    send(cfg, a.subject or f"{cfg.get('subject_prefix','明远阁')} | {today}", body)


if __name__ == "__main__":
    main()
