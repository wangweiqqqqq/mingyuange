# -*- coding: utf-8 -*-
"""用 Windows DPAPI 在本机加密保存邮箱授权码。

加密后的文件只有「当前 Windows 用户」能解开，拷到别的机器或别的账户下都用不了。
这样计划任务不依赖 DSH 的环境变量，也不把密码明文写进配置文件。

用法：
    写入：python tools/secret_store.py --save        （从环境变量 DSH_SECRET_MAIL_PASS / DSH_SECRET_SMTP_PASSWORD 读）
    查看：python tools/secret_store.py --check       （只报告是否存在、能否解密，不打印内容）
    清除：python tools/secret_store.py --clear
"""
import ctypes
import ctypes.wintypes as wt
import os
import sys

SECRET_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".mail_secret.dpapi")
ENV_NAMES = ["DSH_SECRET_MAIL_PASS", "DSH_SECRET_SMTP_PASSWORD", "DSH_SECRET_MAIL_PASSWORD"]

CRYPTPROTECT_UI_FORBIDDEN = 0x01


class DATA_BLOB(ctypes.Structure):
    _fields_ = [("cbData", wt.DWORD), ("pbData", ctypes.POINTER(ctypes.c_char))]


def _blob(data: bytes) -> DATA_BLOB:
    buf = ctypes.create_string_buffer(data, len(data))
    return DATA_BLOB(len(data), ctypes.cast(buf, ctypes.POINTER(ctypes.c_char)))


def _blob_bytes(blob: DATA_BLOB) -> bytes:
    return ctypes.string_at(blob.pbData, blob.cbData)


def protect(data: bytes) -> bytes:
    inb, outb = _blob(data), DATA_BLOB()
    ok = ctypes.windll.crypt32.CryptProtectData(
        ctypes.byref(inb), None, None, None, None, CRYPTPROTECT_UI_FORBIDDEN, ctypes.byref(outb))
    if not ok:
        raise OSError("CryptProtectData failed")
    try:
        return _blob_bytes(outb)
    finally:
        ctypes.windll.kernel32.LocalFree(outb.pbData)


def unprotect(data: bytes) -> bytes:
    inb, outb = _blob(data), DATA_BLOB()
    ok = ctypes.windll.crypt32.CryptUnprotectData(
        ctypes.byref(inb), None, None, None, None, CRYPTPROTECT_UI_FORBIDDEN, ctypes.byref(outb))
    if not ok:
        raise OSError("CryptUnprotectData failed")
    try:
        return _blob_bytes(outb)
    finally:
        ctypes.windll.kernel32.LocalFree(outb.pbData)


def load_secret():
    """返回授权码字符串；文件不存在或解不开返回 None。"""
    if not os.path.exists(SECRET_FILE):
        return None
    try:
        with open(SECRET_FILE, "rb") as f:
            return unprotect(f.read()).decode("utf-8")
    except Exception:
        return None


def main():
    args = sys.argv[1:]
    if "--save" in args:
        val = None
        for n in ENV_NAMES:
            val = val or os.environ.get(n)
        if not val:
            print("环境变量里没有找到授权码，未保存")
            sys.exit(1)
        with open(SECRET_FILE, "wb") as f:
            f.write(protect(val.encode("utf-8")))
        print(f"已加密保存到 {SECRET_FILE}（长度 {len(val)}，仅当前 Windows 用户可解）")
    elif "--check" in args:
        s = load_secret()
        print(f"文件存在：{os.path.exists(SECRET_FILE)}｜可解密：{s is not None}｜长度：{len(s) if s else 0}")
    elif "--clear" in args:
        if os.path.exists(SECRET_FILE):
            os.remove(SECRET_FILE)
            print("已删除")
        else:
            print("文件不存在")
    else:
        print(__doc__)


if __name__ == "__main__":
    main()
