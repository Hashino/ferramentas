#!/usr/bin/env python3
"""Triagem sem IA — quando a cota grátis da Groq acaba, o julgamento é meu.

    python3 scripts/triagem_manual.py --listar 30 [--filtro agua]
    python3 scripts/triagem_manual.py --veredito "<keyword>" CONSTRUIR "motivo"
    python3 scripts/triagem_manual.py --veredito "<keyword>" DESCARTAR "motivo"

Por que existe (18/09/2026): a conta grátis tem 200.000 tokens por dia por
modelo e a triagem é a maior gastadora. Com a cota estourada, `proxima.py`
para o dia inteiro — mas a SERP já está em `backlog/serp.json` e a régua está
no MOLDE do `triagem.py`. Este script mostra a SERP para eu julgar e grava o
veredito no MESMO cache (`backlog/triagem.json`), com `manual: true` para
saber depois o que foi decidido sem IA.

Régua (idêntica à do MOLDE): só CONSTRUIR se as três forem verdade —
  1. quem buscou quer DIGITAR dados e receber um número (não preço de
     mercado, não cotação, não notícia, não comprar produto);
  2. nenhum dos 3 primeiros resultados é ferramenta interativa de verdade
     (artigo que explica "como calcular" NÃO conta como ferramenta);
  3. um AI Overview não resolve sozinho — falta um número que só o usuário
     tem (área do imóvel dele, volume da piscina dele), não um valor de
     faixa estreita e conhecida.
Mais três vetos que a IA não faz: marca de concorrente na keyword, terceira
variante do mesmo cálculo já publicado, e SERP de loja (intenção de compra).
"""
import csv
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import lint_serp  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parent.parent
SERP = ROOT / "backlog" / "serp.json"
CACHE = ROOT / "backlog" / "triagem.json"
CSV = ROOT / "backlog" / "keywords.csv"


def _cache() -> dict:
    return json.loads(CACHE.read_text(encoding="utf-8")) if CACHE.exists() else {}


def _salvar(c: dict) -> None:
    CACHE.write_text(json.dumps(c, ensure_ascii=False, indent=1), encoding="utf-8")


def listar(n: int, filtro: str = "") -> None:
    serp = json.loads(SERP.read_text(encoding="utf-8"))
    julgadas = {k.strip().lower() for k in _cache()}
    vistos = 0
    for row in csv.reader(CSV.open(encoding="utf-8")):
        if len(row) < 2 or row[1] != "candidata":
            continue
        kw = row[0].strip()
        if kw.lower() in julgadas or kw not in serp:
            continue
        if filtro and filtro.lower() not in kw.lower():
            continue
        print(f"\n# {kw}")
        for i, item in enumerate(serp[kw][:3]):
            r = lint_serp.normalizar(item)
            print(f"  {i+1}. {r['title'][:80]} :: {r['link'][:65]}")
            if r["snippet"]:
                print(f"     resumo: {r['snippet'][:150]}")
        vistos += 1
        if vistos >= n:
            break
    if not vistos:
        print("nada para julgar: ou tudo já tem veredito, ou falta SERP "
              "(rode `python3 scripts/mine.py check 40`)")


def veredito(kw: str, v: str, motivo: str) -> None:
    if v not in {"CONSTRUIR", "DESCARTAR"}:
        sys.exit("veredito tem de ser CONSTRUIR ou DESCARTAR")
    serp = json.loads(SERP.read_text(encoding="utf-8"))
    c = _cache()
    sinal = lint_serp.avaliar(serp[kw]) if kw in serp else {}
    c[kw] = {"veredito": v, "motivo": motivo, "manual": True,
             "top3": sinal.get("top3"), "top10": sinal.get("top10"),
             "ia_overview": None, "regex": sinal.get("veredito")}
    _salvar(c)
    print(f"{v}: {kw}")


if __name__ == "__main__":
    a = sys.argv[1:]
    if a and a[0] == "--listar":
        n = int(a[1]) if len(a) > 1 and a[1].isdigit() else 20
        f = a[a.index("--filtro") + 1] if "--filtro" in a else ""
        listar(n, f)
    elif a and a[0] == "--veredito" and len(a) >= 4:
        veredito(a[1], a[2].upper(), a[3])
    else:
        sys.exit(__doc__)
