# -*- coding: utf-8 -*-
"""Minimal DeepSeek API smoke test for TKGQA experiments.

Usage:
  python scripts/deepseek_smoke.py

Optional environment variables:
  DEEPSEEK_API_KEY    required
  DEEPSEEK_BASE_URL   default: https://api.deepseek.com
  DEEPSEEK_MODEL      default: deepseek-chat  (historical comparability)
  DEEPSEEK_TIMEOUT    default: 30
"""
import os
import socket
import sys
from urllib.parse import urlparse

try:
    from openai import OpenAI
except Exception as exc:  # pragma: no cover
    print(f"[FAIL] openai package import failed: {type(exc).__name__}: {exc}")
    print("Install dependencies first, e.g. `pip install openai` or your project requirements file.")
    sys.exit(2)


def mask_key(key: str) -> str:
    if not key:
        return "<missing>"
    if len(key) <= 10:
        return "<present, too short to mask safely>"
    return key[:4] + "..." + key[-4:] + f" (len={len(key)})"


def main() -> int:
    api_key = os.environ.get("DEEPSEEK_API_KEY")
    base_url = os.environ.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
    model = os.environ.get("DEEPSEEK_MODEL", "deepseek-chat")
    timeout = float(os.environ.get("DEEPSEEK_TIMEOUT", "30"))

    print("DeepSeek smoke test")
    print(f"  base_url: {base_url}")
    print(f"  model:    {model}")
    print(f"  api_key:  {mask_key(api_key or '')}")

    if not api_key:
        print("[FAIL] DEEPSEEK_API_KEY is not set in this process.")
        print("PowerShell current terminal:  $env:DEEPSEEK_API_KEY = \"sk-...\"")
        print("PowerShell persistent user env: [Environment]::SetEnvironmentVariable('DEEPSEEK_API_KEY','sk-...','User')")
        return 2

    host = urlparse(base_url).hostname
    if not host:
        print(f"[FAIL] Cannot parse host from DEEPSEEK_BASE_URL={base_url!r}")
        return 2

    try:
        addrs = socket.getaddrinfo(host, 443)
        print(f"[OK] DNS resolved {host}: {len(addrs)} address record(s)")
    except Exception as exc:
        print(f"[FAIL] DNS/network cannot resolve {host}: {type(exc).__name__}: {exc}")
        print("This is a local network/proxy/DNS problem, not an experiment-code problem.")
        return 3

    client = OpenAI(api_key=api_key, base_url=base_url)
    try:
        resp = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": "Reply exactly: ok"}],
            temperature=0,
            max_tokens=8,
            timeout=timeout,
        )
        content = (resp.choices[0].message.content or "").strip()
        print(f"[OK] API call succeeded. response={content!r}")
        return 0
    except Exception as exc:
        name = type(exc).__name__
        print(f"[FAIL] API call failed: {name}: {exc}")
        if name in {"AuthenticationError", "PermissionDeniedError"}:
            print("Likely causes: invalid key, wrong account/project, or key lacks permission.")
        elif name in {"APIConnectionError", "APITimeoutError", "TimeoutError"}:
            print("Likely causes: proxy/firewall/DNS/TLS issue, corporate network block, or transient DeepSeek endpoint problem.")
        elif name == "RateLimitError":
            print("Likely causes: quota exhausted, rate limit, or insufficient balance.")
        print("For historical comparability keep DEEPSEEK_MODEL=deepseek-chat; for fresh runs try deepseek-v4-flash or deepseek-v4-pro.")
        return 4


if __name__ == "__main__":
    raise SystemExit(main())
