"""Dev backend'i Gemini DNS yamasıyla başlat (yalnız BU makine için).

Bu ağın DNS'i generativelanguage.googleapis.com'u çözmüyor (aile filtresi).
Rehber çekimlerinde PDF içe aktarma GERÇEK Gemini çağrısı yaptığından, sunucu
süreci de yamalı başlatılmalı. Prod'u etkilemez.

  python -m scripts.run_dev_patched          # :8081
"""
from __future__ import annotations

import sys

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import socket as _socket

_GEMINI_HOST = "generativelanguage.googleapis.com"
_GEMINI_IPS = ["172.217.113.4", "172.217.114.4", "172.217.117.4"]
_orig_gai = _socket.getaddrinfo


def _patched_gai(host, *args, **kwargs):
    if host == _GEMINI_HOST:
        last_err = None
        for ip in _GEMINI_IPS:
            try:
                return _orig_gai(ip, *args, **kwargs)
            except OSError as e:
                last_err = e
        raise last_err
    return _orig_gai(host, *args, **kwargs)


_socket.getaddrinfo = _patched_gai

import uvicorn

if __name__ == "__main__":
    uvicorn.run("app.main:app", host="127.0.0.1", port=8081, access_log=False)
