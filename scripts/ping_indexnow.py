#!/usr/bin/env python3
"""Avisa o IndexNow (Bing/Yandex/seurat) sobre as URLs do site. Roda no CI a cada push."""
import json
import pathlib
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parent.parent
CFG = json.loads((ROOT / "site.json").read_text(encoding="utf-8"))
BASE = CFG["base_url"].rstrip("/")
KEY = (ROOT / "indexnow.key").read_text().strip()

urls = [f"{BASE}/", f"{BASE}/privacidade.html", f"{BASE}/sobre.html"]
td = ROOT / "tools"
if td.exists():
    urls += [f"{BASE}/tools/{d.name}/" for d in sorted(td.iterdir()) if (d / "index.html").is_file()]

body = json.dumps(
    {
        "host": BASE.split("//", 1)[1],
        "key": KEY,
        "keyLocation": f"{BASE}/{KEY}.txt",
        "urlList": urls,
    }
).encode("utf-8")
req = urllib.request.Request(
    "https://api.indexnow.org/IndexNow",
    data=body,
    headers={"Content-Type": "application/json; charset=utf-8"},
)
try:
    with urllib.request.urlopen(req, timeout=15) as r:
        print(f"indexnow: HTTP {r.status} ({len(urls)} urls)")
except Exception as e:  # falha de ping não pode derrubar o deploy
    print(f"indexnow: falhou ({e}) — ignorado")
