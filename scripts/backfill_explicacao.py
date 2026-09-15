#!/usr/bin/env python3
"""Backfill retroativo: insere <details class="explicacao"> (texto SEO + links
relacionados, colapsado por padrão), FAQPage JSON-LD e data-footer em todo
tools/*/index.html que ainda não tem. Idempotente — rodar de novo não duplica.

Reaproveita a própria meta description de cada ferramenta (já única e
keyword-rich) como texto da explicação — zero conteúdo novo a escrever,
zero risco de duplicar texto entre as 296 páginas.

Uso: python3 scripts/backfill_explicacao.py [--dry-run]
"""
import html
import pathlib
import random
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
TOOLS_DIR = ROOT / "tools"

TITLE_RE = re.compile(r"<title>(.*?)</title>")
DESC_RE = re.compile(r'name="description" content="(.*?)"')
H1_RE = re.compile(r"<h1[^>]*>(.*?)</h1>")


def carregar_tools() -> dict:
    tools = {}
    for d in sorted(TOOLS_DIR.iterdir()):
        f = d / "index.html"
        if not f.is_file():
            continue
        html_txt = f.read_text(encoding="utf-8")
        m_desc = DESC_RE.search(html_txt)
        m_h1 = H1_RE.search(html_txt)
        if not m_desc or not m_h1:
            print(f"aviso: {d.name} sem description/h1, pulando", file=sys.stderr)
            continue
        tools[d.name] = {
            "path": f,
            "html": html_txt,
            "desc": html.unescape(m_desc.group(1)).strip(),
            "h1": html.unescape(m_h1.group(1)).strip(),
        }
    return tools


def bucket_key(slug: str) -> str:
    return slug.split("-")[0]


def relacionadas(slug: str, tools: dict, buckets: dict) -> list[str]:
    rng = random.Random(slug)  # determinístico por slug: reprodutível entre runs
    bucket = [s for s in buckets[bucket_key(slug)] if s != slug]
    escolhidos = list(bucket)
    rng.shuffle(escolhidos)
    escolhidos = escolhidos[:3]
    if len(escolhidos) < 3:
        resto = [s for s in tools if s != slug and s not in escolhidos]
        rng.shuffle(resto)
        escolhidos += resto[: 3 - len(escolhidos)]
    return escolhidos


def montar_related_html(slugs: list[str], tools: dict) -> str:
    return " · ".join(
        f'<a href="../{s}/">{tools[s]["h1"]}</a>' for s in slugs
    )


REL_RE = re.compile(r'<p class="relacionadas">Veja também: (.*?)</p>')


def reparar_relacionadas(nome: str, txt: str, tools: dict, buckets: dict) -> tuple[str, bool]:
    """Corrige o bloco 'Veja também' se algum link aponta pra ferramenta que
    não existe mais (ex: deletada num reaudit). Sem isso, apagar uma ferramenta
    deixa link quebrado em toda ferramenta que citava ela — achado real em
    15/09/2026: 38 de 45 links 'relacionadas' estavam 404 por causa disso.
    Roda em TODO run (não só na primeira vez), pra se autocurar sempre que o
    conjunto de ferramentas mudar."""
    m = REL_RE.search(txt)
    if not m:
        return txt, False
    slugs_atuais = re.findall(r'href="\.\./([^/]+)/"', m.group(1))
    if slugs_atuais and all(s in tools for s in slugs_atuais):
        return txt, False
    novos_slugs = relacionadas(nome, tools, buckets)
    novo_html = montar_related_html(novos_slugs, tools)
    novo_bloco = f'<p class="relacionadas">Veja também: {novo_html}</p>'
    txt = txt[: m.start()] + novo_bloco + txt[m.end() :]
    return txt, True


def aplicar(nome: str, meta: dict, tools: dict, buckets: dict) -> str | None:
    txt = meta["html"]
    mudou = False

    if "<body>" in txt and "data-footer" not in txt:
        txt = txt.replace("<body>", "<body data-footer>", 1)
        mudou = True

    how_text_html = html.escape(meta["desc"], quote=False)
    how_text_json = meta["desc"].replace("\\", "\\\\").replace('"', '\\"')

    if "FAQPage" not in txt:
        faq = (
            '<script type="application/ld+json">\n'
            '{"@context":"https://schema.org","@type":"FAQPage","mainEntity":'
            f'[{{"@type":"Question","name":"Como funciona {meta["h1"]}?",'
            f'"acceptedAnswer":{{"@type":"Answer","text":"{how_text_json}"}}}}]}}\n'
            "</script>\n"
        )
        marcador = re.search(r'<script type="application/ld\+json">.*?</script>\n', txt, re.S)
        if marcador:
            pos = marcador.end()
            txt = txt[:pos] + faq + txt[pos:]
            mudou = True

    if 'class="explicacao"' not in txt:
        rel_slugs = relacionadas(nome, tools, buckets)
        rel_html = montar_related_html(rel_slugs, tools)
        bloco = (
            '  <details class="explicacao">\n'
            "    <summary>Como funciona</summary>\n"
            f"    <p>{how_text_html}</p>\n"
            f'    <p class="relacionadas">Veja também: {rel_html}</p>\n'
            "  </details>\n"
        )
        if "</main>" in txt:
            txt = txt.replace("</main>", bloco + "</main>", 1)
            mudou = True
        else:
            print(f"aviso: {nome} sem </main>, pulando bloco de explicação", file=sys.stderr)

    txt, reparou = reparar_relacionadas(nome, txt, tools, buckets)
    mudou = mudou or reparou

    return txt if mudou else None


if __name__ == "__main__":
    dry = "--dry-run" in sys.argv
    tools = carregar_tools()
    buckets: dict[str, list[str]] = {}
    for slug in tools:
        buckets.setdefault(bucket_key(slug), []).append(slug)

    alterados = 0
    for nome, meta in tools.items():
        novo = aplicar(nome, meta, tools, buckets)
        if novo is None:
            continue
        alterados += 1
        if dry:
            if alterados <= 2:
                print(f"--- {nome} (prévia) ---")
                print(novo)
        else:
            meta["path"].write_text(novo, encoding="utf-8")

    print(f"{'[dry-run] ' if dry else ''}{alterados}/{len(tools)} ferramentas alteradas")
