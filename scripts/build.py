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
        f'      <a class="card" href="./tools/{t["slug"]}/" '
        f'data-nome="{t["h1"] or t["slug"]} {t["slug"]} {t["desc"]}">'
        f"<h2>{t['h1'] or t['slug']}</h2></a>"
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
<meta property="og:title" content="{CFG['site_name']} — calculadoras, geradores e conversores grátis">
<meta property="og:description" content="{CFG['site_description']}">
<meta property="og:type" content="website">
<meta property="og:url" content="{BASE}/">
<script type="application/ld+json">
{{"@context":"https://schema.org","@type":"WebSite","name":"{CFG['site_name']}","url":"{BASE}/","description":"{CFG['site_description']}","potentialAction":{{"@type":"SearchAction","target":"{BASE}/?q={{search_term_string}}","query-input":"required name=search_term_string"}}}}
</script>
<meta name="google-adsense-account" content="ca-pub-1801908225638213">
<script async src="https://pagead2.googlesyndication.com/pagead/js/adsbygoogle.js?client=ca-pub-1801908225638213" crossorigin="anonymous"></script>
<script>document.documentElement.setAttribute("data-theme",function(){{try{{return localStorage.getItem("theme")||"light"}}catch(e){{return"light"}}}}());</script>
<link rel="stylesheet" href="./style.css">
</head>
<body data-footer>
<main>
  <input id="tool-search" class="search-box" type="search"
         placeholder="buscar ferramenta…" autocomplete="off">
  <p class="hub-intro">Cada página aqui é uma calculadora que roda inteira no seu
  navegador: você digita as medidas do seu caso, ela mostra o número e explica a
  conta por trás dele — com a fórmula, um exemplo resolvido e o que o cálculo
  não considera. Sem cadastro, sem instalar nada e sem enviar seus dados para
  lugar nenhum.</p>
  <div class="grid" id="tool-list">
{cards}
  </div>
</main>
<script src="./config.js"></script>
<script src="./chrome.js"></script>
<script src="./search.js"></script>
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
        # ads.txt exige o publisher ID no formato "pub-XXXX", SEM o prefixo
        # "ca-" — esse prefixo só existe na tag de anúncio (ca-pub-XXXX no
        # script/data-ad-client). O parser do Google faz match exato do
        # token "pub-XXXX"; com "ca-pub-XXXX" ele não reconhece e o painel
        # do AdSense mostra "Unauthorized: publisher ID wasn't found" mesmo
        # com o número certo dentro do arquivo (bug real, achado 15/09/2026).
        pub_id = client[3:] if client.startswith("ca-pub-") else client
        destino.write_text(f"google.com, {pub_id}, DIRECT, f08c47fec0942fa0\n", encoding="utf-8")
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
