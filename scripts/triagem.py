#!/usr/bin/env python3
"""Triagem de keyword por IA grátis — o portão que decide o que vale construir.

Substitui os dois julgamentos que regex não consegue fazer e que, até
set/2026, eram feitos "no olho" e falharam na prática:

  1. SATURAÇÃO REAL. `lint_serp.py` marca por padrão de título/URL e é
     generoso de propósito, então confunde ARTIGO com FERRAMENTA: reprovou
     "quanto rende 1kg de carne cozida" porque o top-3 tinha "Como calcular
     rendimento de alimentos" — que é um post de blog, ou seja, exatamente o
     sinal de OPORTUNIDADE que o projeto procura (tem demanda, tem gente
     explicando na mão, e ninguém fez a ferramenta). A IA lê título+URL e diz
     se aquilo é uma página onde o usuário DIGITA e RECEBE resultado, ou um
     texto que só explica.

  2. AI OVERVIEW. Se um resumo de IA responde a busca inteira sem precisar de
     nenhum dado que só o usuário tem, a página perde o clique por mais boa
     que seja (lição do cleanup de 212 ferramentas). Isso é semântico: a
     mesma frase "valor da hora" é pergunta de mercado num caso e variável de
     input no outro. Regex errou nos dois sentidos; a IA acerta.

Usa provider free (ver scripts/ai.py). Se a IA cair, o veredito da IA é
omitido e vale só o sinal do regex — nunca aprova silenciosamente.

Uso:
  python3 scripts/triagem.py <keyword>...          # do cache backlog/serp.json
  python3 scripts/triagem.py --tools               # audita tools/ publicadas
  python3 scripts/triagem.py --tools --so-suspeitas  # só as que lint_serp reprovou
"""
import json
import pathlib
import re
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from ai import SemIA, perguntar_json  # noqa: E402
import lint_serp  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parent.parent
SERP_PATH = ROOT / "backlog" / "serp.json"
TOOLS_DIR = ROOT / "tools"
CACHE_PATH = ROOT / "backlog" / "triagem.json"

SISTEMA = (
    "Você avalia oportunidades de SEO para um site de micro-ferramentas em "
    "português. Seja rigoroso e honesto: aprovar uma keyword ruim custa caro, "
    "rejeitar uma boa não custa quase nada (há milhares no backlog)."
)

MOLDE = """Keyword pesquisada no Google (Brasil): "{kw}"

Resultados orgânicos do top-10 (título :: url):
{resultados}

Responda em JSON com estas chaves:

"ferramentas_top3": quantos dos 3 PRIMEIROS resultados são uma FERRAMENTA
  INTERATIVA de verdade — página onde o usuário digita valores e recebe um
  resultado calculado. Um artigo/post/vídeo que só EXPLICA como calcular NÃO
  conta, mesmo que o título diga "como calcular". Fórum também não conta.
"ferramentas_top10": o mesmo, considerando os 10.
"respondida_por_ia": true se um resumo de IA de 2-3 frases no topo do Google
  já responderia essa busca por completo SEM precisar de nenhum dado que só o
  usuário sabe (ex.: "quanto custa pintar uma casa", "quantos ml tem uma
  xícara" -> true). false se a resposta útil só existe DEPOIS de um cálculo
  com dados específicos do usuário (ex.: "calcular bhaskara com meus
  coeficientes", "gasto de energia do MEU chuveiro em kW por X horas") -> false.
"veredito": "CONSTRUIR" se ferramentas_top3 == 0 e respondida_por_ia == false;
  senão "DESCARTAR".
"motivo": uma frase curta explicando, em português."""


def _fmt(resultados: list[str]) -> str:
    return "\n".join(f"{i+1}. {l}" for i, l in enumerate(resultados[:10]))


def avaliar_ia(kw: str, resultados: list[str]) -> dict:
    return perguntar_json(MOLDE.format(kw=kw, resultados=_fmt(resultados)), sistema=SISTEMA)


def triar(kw: str, resultados: list[str], cache: dict) -> dict:
    if kw in cache:
        return cache[kw]
    regex = lint_serp.avaliar(resultados)
    try:
        ia = avaliar_ia(kw, resultados)
    except (SemIA, ValueError, KeyError) as e:
        return {"veredito": "SEM_IA", "motivo": f"IA indisponível ({e}); regex diz {regex['veredito']}",
                "regex": regex["veredito"]}
    r = {
        "veredito": "CONSTRUIR" if (
            ia.get("ferramentas_top3", 9) == 0 and not ia.get("respondida_por_ia", True)
        ) else "DESCARTAR",
        "motivo": ia.get("motivo", ""),
        "top3": ia.get("ferramentas_top3"),
        "top10": ia.get("ferramentas_top10"),
        "ia_overview": ia.get("respondida_por_ia"),
        "regex": regex["veredito"],
    }
    cache[kw] = r
    return r


H1_RE = re.compile(r"<h1[^>]*>(.*?)</h1>", re.S)


def _query_do_tool(slug: str) -> str:
    html = (TOOLS_DIR / slug / "index.html").read_text(encoding="utf-8")
    m = H1_RE.search(html)
    return re.sub(r"<[^>]+>", "", m.group(1)).strip() if m else slug.replace("-", " ")


def main() -> None:
    args = sys.argv[1:]
    cache = json.loads(CACHE_PATH.read_text(encoding="utf-8")) if CACHE_PATH.exists() else {}

    if "--tools" in args:
        serp_tools = json.loads((ROOT / "backlog" / "serp_tools.json").read_text(encoding="utf-8"))
        so_suspeitas = "--so-suspeitas" in args
        slugs = sorted(d.name for d in TOOLS_DIR.iterdir() if (d / "index.html").is_file())
        descartar = []
        for slug in slugs:
            q = _query_do_tool(slug)
            if q not in serp_tools:
                print(f"? {slug}: sem SERP — rode lint_serp.py --tools")
                continue
            if so_suspeitas and lint_serp.avaliar(serp_tools[q])["veredito"] != "REPROVA":
                continue
            r = triar(q, serp_tools[q], cache)
            marca = {"CONSTRUIR": "✓", "DESCARTAR": "✗"}.get(r["veredito"], "?")
            print(f'{marca} {slug}  [{q}]')
            print(f'      top3={r.get("top3")} ia_overview={r.get("ia_overview")} '
                  f'regex={r.get("regex")} — {r["motivo"]}')
            if r["veredito"] == "DESCARTAR":
                descartar.append(slug)
            CACHE_PATH.write_text(json.dumps(cache, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"\n{len(descartar)} ferramentas publicadas reprovadas pela triagem:")
        for s in descartar:
            print(s)
        return

    if not args:
        sys.exit(__doc__)

    serp = json.loads(SERP_PATH.read_text(encoding="utf-8")) if SERP_PATH.exists() else {}
    falhou = False
    for kw in args:
        if kw not in serp:
            print(f"? {kw}: sem SERP no cache — rode `mine.py check` antes")
            falhou = True
            continue
        r = triar(kw, serp[kw], cache)
        marca = {"CONSTRUIR": "✓", "DESCARTAR": "✗"}.get(r["veredito"], "?")
        print(f'{marca} {kw}: {r["motivo"]}')
        if r["veredito"] != "CONSTRUIR":
            falhou = True
    CACHE_PATH.write_text(json.dumps(cache, ensure_ascii=False, indent=1), encoding="utf-8")
    sys.exit(1 if falhou else 0)


if __name__ == "__main__":
    main()
