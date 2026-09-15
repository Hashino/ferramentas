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
import unicodedata

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

Resultados orgânicos do top-10 (título :: url, e o resumo que o Google mostra):
{resultados}

Ao julgar se um resultado é ferramenta, use o resumo: quando ele lista campos
de formulário ("Data inicial; Valor a ser corrigido; % do CDI") ou convida a
preencher algo, é ferramenta interativa. Quando ele conta/explica em prosa
("veja como calcular", "entenda a diferença"), é artigo.

Responda em JSON com estas chaves:

"quer_ferramenta": true se quem digitou isso quer USAR uma calculadora e
  receber um número calculado a partir de dados DELE. false se quer outra
  coisa: saber um valor de mercado ou média ("salário de programador",
  "preço do m² em SP"), comprar um produto, achar uma vaga de emprego, uma
  notícia, uma definição, ou uma cotação que muda sozinha (dólar, bitcoin —
  o Google já mostra no topo). Na dúvida, false.
"ferramentas_top3": quantos dos 3 PRIMEIROS resultados são uma FERRAMENTA
  INTERATIVA de verdade — página onde o usuário digita valores e recebe um
  resultado calculado. Um artigo/post/vídeo que só EXPLICA como calcular NÃO
  conta, mesmo que o título diga "como calcular". Fórum também não conta.
"ferramentas_top10": o mesmo, considerando os 10.
"respondida_por_ia": true se um resumo de IA de 2-3 frases no topo do Google
  já responderia essa busca por completo SEM precisar de nenhum dado que só o
  usuário sabe. Inclui qualquer pergunta cuja resposta é um número fixo, uma
  média, uma regra ou uma tabela: "quanto custa pintar uma casa", "quantos ml
  tem uma xícara", "com quantos anos me aposento", "quanto rende 1kg de
  carne" -> true. false só quando a resposta útil não existe até o usuário
  informar dados próprios: "gasto do MEU chuveiro de X kW ligado Y horas a
  R$Z o kWh", "quantos sacos de cimento pra MINHA laje de X m²" -> false.
"veredito": "CONSTRUIR" somente se quer_ferramenta == true E
  ferramentas_top3 == 0 E respondida_por_ia == false. Senão "DESCARTAR".
"motivo": uma frase curta explicando, em português."""


def _fmt(resultados: list) -> str:
    linhas = []
    for i, item in enumerate(resultados[:10]):
        r = lint_serp.normalizar(item)
        linhas.append(f'{i+1}. {r["title"]} :: {r["link"]}')
        # o snippet frequentemente lista os próprios campos do formulário
        # ("Data inicial; Valor a ser corrigido; % do CDI") — é o sinal mais
        # forte de que a página é ferramenta e não artigo. Vem de graça na
        # mesma chamada da Serper; entradas antigas do cache não têm.
        if r["snippet"]:
            linhas.append(f'   resumo: {r["snippet"]}')
    return "\n".join(linhas)


def avaliar_ia(kw: str, resultados: list[str]) -> dict:
    # modelo robusto: o volume é baixo (dezenas por leva) e um erro aqui custa
    # uma página publicada que nunca vai ranquear
    return perguntar_json(MOLDE.format(kw=kw, resultados=_fmt(resultados)),
                          sistema=SISTEMA, robusto=True)


# suba quando mudar MOLDE/critérios: invalida vereditos julgados pela regra velha
VERSAO = 3


def triar(kw: str, resultados: list[str], cache: dict) -> dict:
    anterior = cache.get(kw)
    if anterior and anterior.get("v") == VERSAO:
        return anterior
    regex = lint_serp.avaliar(resultados)
    try:
        ia = avaliar_ia(kw, resultados)
    except (SemIA, ValueError, KeyError) as e:
        return {"veredito": "SEM_IA", "motivo": f"IA indisponível ({e}); regex diz {regex['veredito']}",
                "regex": regex["veredito"]}
    # o veredito é recalculado aqui, não confiado ao modelo: modelo free erra
    # a conjunção ("existem ferramentas, mas..." e ainda assim aprova)
    r = {
        "veredito": "CONSTRUIR" if (
            ia.get("quer_ferramenta", False)
            and ia.get("ferramentas_top3", 9) == 0
            and not ia.get("respondida_por_ia", True)
        ) else "DESCARTAR",
        "motivo": ia.get("motivo", ""),
        "quer_ferramenta": ia.get("quer_ferramenta"),
        "top3": ia.get("ferramentas_top3"),
        "top10": ia.get("ferramentas_top10"),
        "ia_overview": ia.get("respondida_por_ia"),
        "regex": regex["veredito"],
        "v": VERSAO,
    }
    cache[kw] = r
    return r


# ── corte por família: não gastar crédito de SERP em nicho já condenado ──────
# Família = primeira palavra de conteúdo da keyword ("calculadora de bitcoin
# lucro" -> "bitcoin"; "quanto gasta um freezer" -> "gasta"). Grosseiro de
# propósito: o que protege as famílias boas não é a precisão do agrupamento,
# é a regra exigir ZERO aprovadas para condenar. Medido em 15/09/2026 sobre
# os vereditos reais: "gasta" tinha 17 aprovadas em 24 e sobrevive; "gerador"
# (0 de 11) e "salario" (0 de 4) morrem, que é exatamente o desejado.
MIN_REJEICOES = 4       # com nenhuma aprovada, isso já basta para condenar
MIN_AMOSTRA_TAXA = 10   # com amostra grande, uma taxa péssima também condena
TAXA_MINIMA = 0.15      # "aposentadoria": 1 aprovada em 19 = 19 créditos por ferramenta

PARAR = {"de", "da", "do", "das", "dos", "para", "por", "em", "um", "uma", "o", "a",
         "e", "com", "quanto", "quantos", "quantas", "calculadora", "calcular",
         "tem", "que", "no", "na", "meu", "minha", "online", "gratis"}


def familia(kw: str) -> str:
    s = unicodedata.normalize("NFD", kw.lower())
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    tokens = [t for t in re.split(r"[^a-z0-9]+", s) if t and t not in PARAR]
    return tokens[0] if tokens else ""


def familias_condenadas(cache: dict | None = None) -> dict[str, str]:
    """Famílias que não merecem mais crédito de Serper -> motivo."""
    if cache is None:
        cache = json.loads(CACHE_PATH.read_text(encoding="utf-8")) if CACHE_PATH.exists() else {}
    placar: dict[str, list[int]] = {}
    for kw, v in cache.items():
        p = placar.setdefault(familia(kw), [0, 0])
        p[0 if v.get("veredito") == "CONSTRUIR" else 1] += 1

    mortas = {}
    for fam, (ok, rej) in placar.items():
        if not fam:
            continue
        if ok == 0 and rej >= MIN_REJEICOES:
            mortas[fam] = f"{rej} rejeitadas, nenhuma aprovada"
        elif ok + rej >= MIN_AMOSTRA_TAXA and ok / (ok + rej) < TAXA_MINIMA:
            mortas[fam] = f"só {ok} aprovada(s) em {ok + rej}"
    return mortas


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
