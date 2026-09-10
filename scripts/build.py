#!/usr/bin/env python3
"""Regenera config.js, hub (index.html), sitemap.xml, robots.txt e llms.txt a partir de tools/.

Rode sempre antes de commitar. Idempotente.
"""
import datetime
import json
import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parent.parent
CFG = json.loads((ROOT / "site.json").read_text(encoding="utf-8"))
BASE = CFG["base_url"].rstrip("/")
TOOLS_DIR = ROOT / "tools"
HOJE = datetime.date.today().isoformat()


def _meta(html: str, pattern: str) -> str:
    m = re.search(pattern, html)
    return m.group(1).strip() if m else ""


def ferramentas() -> list[dict]:
    saida = []
    if TOOLS_DIR.exists():
        for d in sorted(TOOLS_DIR.iterdir()):
            f = d / "index.html"
            if f.is_file():
                html = f.read_text(encoding="utf-8")
                saida.append(
                    {
                        "slug": d.name,
                        "url": f"{BASE}/tools/{d.name}/",
                        "title": _meta(html, r"<title>(.*?)</title>"),
                        "desc": _meta(html, r'name="description" content="(.*?)"'),
                        "h1": _meta(html, r"<h1[^>]*>(.*?)</h1>"),
                        "lastmod": datetime.date.fromtimestamp(f.stat().st_mtime).isoformat(),
                    }
                )
    return saida


def config_js() -> None:
    (ROOT / "config.js").write_text(
        "window.SITE = "
        + json.dumps(
            {
                "base": BASE,
                "adClient": CFG.get("adsense_client", ""),
                "adSlot": CFG.get("adsense_slot", ""),
            }
        )
        + ";\n",
        encoding="utf-8",
    )


def hub(tools: list[dict]) -> None:
    cards = "\n".join(
        f'      <a class="card" href="./tools/{t["slug"]}/"><h2>{t["h1"] or t["slug"]}</h2>'
        f"<p>{t['desc']}</p></a>"
        for t in tools
    )
    (ROOT / "index.html").write_text(
        f"""<!doctype html>
<html lang="pt-BR">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{CFG['site_name']} — calculadoras, geradores e conversores grátis</title>
<meta name="description" content="{CFG['site_description']}">
<link rel="canonical" href="{BASE}/">
<script>document.documentElement.setAttribute("data-theme",function(){{try{{return localStorage.getItem("theme")||"light"}}catch(e){{return"light"}}}}());</script>
<link rel="stylesheet" href="./style.css">
</head>
<body>
<nav class="top-nav"><div class="nav-container">
  <a class="nav-title" href="./">Ferramentas</a>
  <button id="theme-toggle" class="theme-toggle" aria-label="Alternar tema"></button>
</div></nav>
<main>
  <h1>{CFG['site_name']}</h1>
  <p class="lead">{CFG['site_description']}</p>
  <div class="grid">
{cards}
  </div>
</main>
<footer><a href="./sobre.html">Sobre</a> · <a href="./privacidade.html">Privacidade</a> · <a href="https://github.com/Hashino/ferramentas">GitHub</a></footer>
<script src="./config.js"></script>
<script src="./ads.js"></script>
<script src="./theme.js"></script>
</body>
</html>
""",
        encoding="utf-8",
    )


def sitemap(tools: list[dict]) -> None:
    paginas = [
        (f"{BASE}/", HOJE),
        (f"{BASE}/privacidade.html", HOJE),
        (f"{BASE}/sobre.html", HOJE),
    ] + [(t["url"], t["lastmod"]) for t in tools]
    itens = "\n".join(
        f"  <url><loc>{u}</loc><lastmod>{m}</lastmod></url>" for u, m in paginas
    )
    (ROOT / "sitemap.xml").write_text(
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        f"{itens}\n</urlset>\n",
        encoding="utf-8",
    )


def robots() -> None:
    (ROOT / "robots.txt").write_text(
        f"""User-agent: *
Allow: /

# crawlers de IA: bem-vindos (o objetivo é ser citado)
User-agent: GPTBot
Allow: /
User-agent: ClaudeBot
Allow: /
User-agent: PerplexityBot
Allow: /
User-agent: Google-Extended
Allow: /

Sitemap: {BASE}/sitemap.xml
""",
        encoding="utf-8",
    )


def llms_txt(tools: list[dict]) -> None:
    lista = "\n".join(f"- [{t['title']}]({t['url']}): {t['desc']}" for t in tools)
    (ROOT / "llms.txt").write_text(
        f"# {CFG['site_name']}\n\n> {CFG['site_description']}\n\n## Ferramentas\n\n{lista}\n",
        encoding="utf-8",
    )


def ads_txt() -> None:
    client = CFG.get("adsense_client", "")
    destino = ROOT / "ads.txt"
    if client:
        destino.write_text(f"google.com, {client}, DIRECT, f08c47fec0942fa0\n", encoding="utf-8")
    elif destino.exists():
        destino.unlink()


if __name__ == "__main__":
    ts = ferramentas()
    config_js()
    hub(ts)
    sitemap(ts)
    robots()
    llms_txt(ts)
    ads_txt()
    print(f"build ok: {len(ts)} ferramentas indexadas")
