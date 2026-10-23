# -*- coding: utf-8 -*-
"""通过 GitHub Contents API 把本地仓库文件推上去（绕过 git 443 被切断的问题）。

用法：
  python tools/push_to_github.py --repo wangweiqqqqq/mingyuange            # 推送 git 已跟踪的文件
  python tools/push_to_github.py --repo owner/name --dry-run              # 只列出不推送

Token 从环境变量 DSH_SECRET_GITHUB_TOKEN 读，不落盘、不打印。
"""
import argparse
import base64
import json
import os
import pathlib
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request

BASE = pathlib.Path(__file__).resolve().parent.parent
API = "https://api.github.com"


def token():
    for name in ("GITHUB_PUSH_TOKEN", "DSH_SECRET_GITHUB_TOKEN", "GITHUB_TOKEN"):
        val = os.environ.get(name) or os.environ.get(f"DSH_SECRET_{name}")
        if val and val.strip():
            return val.strip()
    sys.exit("TOKEN_MISSING: 需要 DSH_SECRET_GITHUB_PUSH_TOKEN 或 DSH_SECRET_GITHUB_TOKEN")


def request(method, path, tok, payload=None):
    url = API + path
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(url, data=data, method=method, headers={
        "Authorization": f"Bearer {tok}",
        "Accept": "application/vnd.github+json",
        "User-Agent": "dsh-mingyuange",
        "Content-Type": "application/json",
    })
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            return resp.status, json.loads(resp.read().decode() or "{}")
    except urllib.error.HTTPError as exc:
        body = exc.read().decode()[:300]
        return exc.code, {"error": body}
    except Exception as exc:  # noqa: BLE001
        return 0, {"error": f"{type(exc).__name__}: {exc}"}


def tracked_files():
    out = subprocess.run(["git", "ls-files"], cwd=BASE, capture_output=True, text=True,
                         encoding="utf-8", errors="replace")
    return [line.strip() for line in out.stdout.splitlines() if line.strip()]


def remote_sha(repo, path, tok, branch="main"):
    status, body = request("GET", f"/repos/{repo}/contents/{urllib.parse.quote(path)}?ref={branch}", tok)
    if status == 200 and isinstance(body, dict):
        return body.get("sha")
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", required=True, help="owner/name")
    ap.add_argument("--branch", default="main")
    ap.add_argument("--message", default="同步明远阁脚本与文档")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    tok = token()
    files = tracked_files()
    if not files:
        sys.exit("NO_TRACKED_FILES")

    ok = fail = 0
    for rel in files:
        p = BASE / rel
        if not p.exists() or p.is_dir():
            continue
        if p.stat().st_size > 900_000:
            print(f"SKIP_BIG {rel} {p.stat().st_size}")
            continue
        if args.dry_run:
            print(f"DRY {rel}")
            continue
        content = base64.b64encode(p.read_bytes()).decode()
        sha = remote_sha(args.repo, rel, tok, args.branch)
        payload = {"message": f"{args.message}: {rel}", "content": content, "branch": args.branch}
        if sha:
            payload["sha"] = sha
        status, body = request("PUT", f"/repos/{args.repo}/contents/{urllib.parse.quote(rel)}", tok, payload)
        if status in (200, 201):
            ok += 1
            print(f"OK {rel}")
        else:
            fail += 1
            print(f"FAIL {rel} status={status} {body.get('error','')[:160]}")

    print(f"SUMMARY ok={ok} fail={fail}")
    return 0 if fail == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
