# -*- coding: utf-8 -*-
"""明远阁 · 把当日收盘总结发到邮箱。

用法：
  python tools/mail_daily.py              # 发送 reports/<今天>.md（不存在则先生成）
  python tools/mail_daily.py --gen        # 强制先重新生成再发
  python tools/mail_daily.py --file x.md  # 指定文件
  python tools/mail_daily.py --tag 周报   # 邮件标题后缀
"""
import argparse
import datetime as dt
import os
import pathlib
import subprocess
import sys

BASE = pathlib.Path(__file__).resolve().parent.parent
PY = BASE / ".venv" / "Scripts" / "python.exe"
MAILER = BASE / "tools" / "send_mail.py"
REPORT = BASE / "tools" / "daily_report.py"


def gen():
    env = {**os.environ, "PYTHONUTF8": "1", "PYTHONIOENCODING": "utf-8"}
    p = subprocess.run([str(PY), str(REPORT)], capture_output=True, text=True,
                       encoding="utf-8", errors="replace", env=env, timeout=300)
    return p.returncode


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--gen", action="store_true")
    ap.add_argument("--file", default="")
    ap.add_argument("--tag", default="收盘总结")
    a = ap.parse_args()

    path = pathlib.Path(a.file) if a.file else BASE / "reports" / f"{dt.date.today():%Y-%m-%d}.md"
    if a.gen or not path.exists():
        print(f"GENERATING (existing={path.exists()})")
        gen()
    if not path.exists():
        print(f"MISSING_REPORT {path}")
        return 2

    title = f"{dt.date.today():%Y-%m-%d} {a.tag}"
    env = {**os.environ}
    p = subprocess.run([str(PY), str(MAILER), "--subject", f"Mingyuan | {title}",
                        "--body-file", str(path)], capture_output=True, text=True,
                       encoding="utf-8", errors="replace", env=env, timeout=180)
    print((p.stdout or "").strip() or (p.stderr or "")[:200])
    return p.returncode


if __name__ == "__main__":
    sys.exit(main())
