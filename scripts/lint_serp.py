#!/usr/bin/env python3
"""Gate de saturação de SERP: a keyword só vale se NINGUÉM já ranqueia uma
ferramenta dedicada para ela.

Esse é o critério (a) da pipeline — o que dá razão de existir ao projeto
inteiro: achar busca de ferramenta que AINDA NÃO EXISTE. Até set/2026 ele
era só uma instrução em prosa no CLAUDE.md, julgada no olho, e vazou: foram
publicadas calculadoras de salário/CLT cuja SERP tinha 8 de 8 resultados
sendo calculadoras dedicadas de globo/serasa/idinheiro. Página nova em SERP
assim nunca ranqueia — é trabalho jogado fora, e ainda dilui o site.

Detecção de "resultado é ferramenta dedicada": título OU caminho da URL
denuncia (calculadora, conversor, gerador, simulador, ferramenta...). É
deliberadamente generoso: falso positivo aqui só custa uma keyword
descartada (há milhares no backlog); falso negativo custa uma página morta.

Veredito (qualquer um reprova):
  - alguma ferramenta dedicada no TOP-3  → a zona de clique já é de outro
  - 3+ ferramentas dedicadas no TOP-10   → nicho saturado, sem brecha

Uso:
  python3 scripts/lint_serp.py <keyword>...        # do cache backlog/serp.json
  python3 scripts/lint_serp.py --tools             # audita tools/ publicadas (Serper, 1 crédito cada)
  python3 scripts/lint_serp.py --tools --limite 20 # audita só as N primeiras
"""
import json
import pathlib
import re
import sys
import time
import unicodedata
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parent.parent
SERP_PATH = ROOT / "backlog" / "serp.json"
TOOLS_DIR = ROOT / "tools"

NOSSO_DOMINIO = "hashino.github.io"

# Palavras que, no título, denunciam que o resultado É a ferramenta.
TITULO_FERRAMENTA = re.compile(
    r"\b(calculadora|calculadoras|calcular|calculo|conversor|converter|"
    r"conversao|gerador|gerar|simulador|simular|ferramenta|ferramentas|"
    r"calculator|generator|converter|planilha|contador)\b",
    re.I,
)

# Caminhos de URL típicos de página-ferramenta (mais forte que o título:
# o site organizou uma seção inteira para isso).
URL_FERRAMENTA = re.compile(
    r"/(calculadora|calculadoras|calculo|calculos|calc|conversor|conversores|"
    r"converter|gerador|geradores|simulador|simuladores|ferramenta|ferramentas|"
    r"tools|calculator)s?[/-]",
    re.I,
)


def _sem_acento(s: str) -> str:
    return "".join(
        c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn"
    )


def normalizar(item) -> dict:
    """Aceita os dois formatos de resultado que existem em serp.json: o antigo
    (string "titulo :: link", gravado antes de set/2026) e o atual (dict com
    title/link/snippet). Entradas antigas simplesmente não têm snippet."""
    if isinstance(item, dict):
        return {"title": item.get("title", ""), "link": item.get("link", ""),
                "snippet": item.get("snippet", "")}
    titulo, _, link = str(item).partition(" :: ")
    return {"title": titulo, "link": link, "snippet": ""}


def eh_ferramenta_dedicada(item) -> bool:
    r = normalizar(item)
    titulo, link = r["title"], r["link"]
    if NOSSO_DOMINIO in link:
        return False  # nós mesmos não contamos como concorrência
    alvo = _sem_acento(titulo)
    if TITULO_FERRAMENTA.search(alvo):
        return True
    return bool(URL_FERRAMENTA.search(_sem_acento(link)))


def avaliar(resultados: list[str]) -> dict:
    marcas = [eh_ferramenta_dedicada(l) for l in resultados[:10]]
    top3 = sum(marcas[:3])
    top10 = sum(marcas)
    if top3:
        veredito, motivo = "REPROVA", f"{top3} ferramenta(s) dedicada(s) no top-3"
    elif top10 >= 3:
        veredito, motivo = "REPROVA", f"{top10} ferramentas dedicadas no top-10"
    else:
        veredito, motivo = "OK", f"{top10} ferramenta(s) no top-10, nenhuma no top-3"
    return {
        "veredito": veredito,
        "motivo": motivo,
        "top3": top3,
        "top10": top10,
        "concorrentes": [f'{normalizar(l)["title"]} :: {normalizar(l)["link"]}'
                         for l, m in zip(resultados, marcas) if m],
    }


# ── modo --tools: audita o que já está publicado ─────────────────────────────
def _api_key() -> str:
    env = ROOT / ".env"
    if env.exists():
        for linha in env.read_text(encoding="utf-8").splitlines():
            if linha.startswith("SERPER_API_KEY="):
                return linha.split("=", 1)[1].strip()
    sys.exit("erro: SERPER_API_KEY ausente em .env")


def _serp_ao_vivo(query: str, api: str) -> list[dict]:
    req = urllib.request.Request(
        "https://google.serper.dev/search",
        data=json.dumps({"q": query, "gl": "br", "hl": "pt-br", "num": 10}).encode(),
        headers={"X-API-KEY": api, "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=20) as r:
        data = json.loads(r.read().decode("utf-8"))
    return [
        {"title": i.get("title", ""), "link": i.get("link", ""),
         "snippet": i.get("snippet", "")}
        for i in data.get("organic", [])
    ]


H1_RE = re.compile(r"<h1[^>]*>(.*?)</h1>", re.S)


def auditar_tools(limite: int | None) -> None:
    api = _api_key()
    cache_path = ROOT / "backlog" / "serp_tools.json"
    cache = json.loads(cache_path.read_text(encoding="utf-8")) if cache_path.exists() else {}
    slugs = sorted(d.name for d in TOOLS_DIR.iterdir() if (d / "index.html").is_file())
    if limite:
        slugs = slugs[:limite]

    reprovadas = []
    for slug in slugs:
        html = (TOOLS_DIR / slug / "index.html").read_text(encoding="utf-8")
        m = H1_RE.search(html)
        query = re.sub(r"<[^>]+>", "", m.group(1)).strip() if m else slug.replace("-", " ")
        if query not in cache:
            try:
                cache[query] = _serp_ao_vivo(query, api)
            except Exception as e:
                print(f"erro em {slug!r}: {e}", file=sys.stderr)
                continue
            time.sleep(1.2)
        r = avaliar(cache[query])
        marca = "✗" if r["veredito"] == "REPROVA" else "✓"
        print(f'{marca} {slug}  [{query}]  {r["motivo"]}')
        if r["veredito"] == "REPROVA":
            reprovadas.append(slug)
            for c in r["concorrentes"][:3]:
                print(f"      · {c[:110]}")

    cache_path.write_text(json.dumps(cache, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\n{len(reprovadas)}/{len(slugs)} ferramentas publicadas em SERP saturada:")
    for s in reprovadas:
        print(s)


if __name__ == "__main__":
    args = sys.argv[1:]
    if "--tools" in args:
        lim = None
        if "--limite" in args:
            lim = int(args[args.index("--limite") + 1])
        auditar_tools(lim)
        sys.exit(0)

    if not args:
        sys.exit(__doc__)

    serp = json.loads(SERP_PATH.read_text(encoding="utf-8")) if SERP_PATH.exists() else {}
    falhou = False
    for kw in args:
        if kw not in serp:
            print(f"? {kw}: sem SERP no cache — rode `mine.py check` antes")
            falhou = True
            continue
        r = avaliar(serp[kw])
        marca = "✗" if r["veredito"] == "REPROVA" else "✓"
        print(f'{marca} {kw}: {r["motivo"]}')
        for c in r["concorrentes"][:3]:
            print(f"    · {c[:110]}")
        if r["veredito"] == "REPROVA":
            falhou = True
    sys.exit(1 if falhou else 0)
