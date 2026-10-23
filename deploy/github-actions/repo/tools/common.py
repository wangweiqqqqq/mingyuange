# -*- coding: utf-8 -*-
"""统一路径解析：本地（Windows）与云端（Linux）通用。

本机默认 BASE = 上一级目录（D:\\明远阁）。
云端部署时设环境变量 MY_BASE=/path/to/repo 即可。
"""
import os
import sys

TOOLS_DIR = os.path.dirname(os.path.abspath(__file__))
BASE = os.environ.get("MY_BASE") or os.path.dirname(TOOLS_DIR)

PY = os.environ.get("MY_PY") or sys.executable
SCRIPT = os.path.join(BASE, "market_data.py")

REPORT_DIR = os.path.join(BASE, "reports")
HIST_DIR = os.path.join(BASE, "history")
SAMPLES_DIR = os.path.join(BASE, "samples")
AVATAR_DIR = os.path.join(BASE, "avatars")
BASELINE = os.path.join(BASE, "watch_baseline.json")
MAIL_CONFIG = os.path.join(BASE, "mail_config.json")
MAIL_SCRIPT = os.path.join(TOOLS_DIR, "mail_report.py")


def ensure_dirs():
    for d in (REPORT_DIR, HIST_DIR, SAMPLES_DIR):
        os.makedirs(d, exist_ok=True)
