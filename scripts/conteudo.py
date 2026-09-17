#!/usr/bin/env python3
"""Escreve o CONTEÚDO de cada ferramenta — o texto que faz a página valer
uma visita mesmo sem clicar em calcular.

    python3 scripts/conteudo.py [slug ...] [--force] [--dry-run]

Por que existe (17/09/2026): o AdSense acusou violação de política e a
auditoria mostrou a causa provável — cada `tools/*/index.html` tinha 67 a 98
palavras visíveis, e o único bloco de texto (`<details class="explicacao">`)
repetia a meta description palavra por palavra em todas as páginas. Isso é
"conteúdo de baixo valor" no manual do revisor: molde repetido, nada que o
usuário não veja no snippet do Google. O FAQPage JSON-LD também era falso —
uma pergunta cuja resposta era a própria description.

O que este script gera por ferramenta (em pt-BR, via IA grátis, cacheado em
`backlog/conteudo/<slug>.json` para revisão e para não gastar chamada de novo):
  - como o cálculo é feito, com a fórmula real lida do JS da própria página
  - um exemplo resolvido passo a passo
  - uma tabela de valores de referência
  - o que a conta NÃO considera (limites honestos)
  - 4 perguntas frequentes de verdade — que também viram o FAQPage JSON-LD

Idempotente: pula quem já tem o marcador `<!-- conteudo:v1 -->` (use --force
para reescrever). Rodar DEPOIS de `backfill_explicacao.py` e ANTES de
`build.py`.
"""
import html
import json
import pathlib
import re
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import ai  # noqa: E402

RAIZ = pathlib.Path(__file__).resolve().parent.parent
TOOLS = RAIZ / "tools"
CACHE = RAIZ / "backlog" / "conteudo"
MARCADOR = "<!-- conteudo:v2 -->"

TITLE_RE = re.compile(r"<title>(.*?)</title>", re.S)
DESC_RE = re.compile(r'name="description" content="(.*?)"')
H1_RE = re.compile(r"<h1[^>]*>(.*?)</h1>", re.S)
APP_RE = re.compile(r'<section class="app">(.*?)</section>', re.S)
JS_RE = re.compile(r"<script>\n(.*?)</script>\s*</body>", re.S)
FAQ_RE = re.compile(r'<script type="application/ld\+json">\s*\{"@context":"https://schema\.org",'
                    r'"@type":"FAQPage".*?</script>\s*', re.S)
DETAILS_RE = re.compile(r'<(details|nav) class="explicacao">.*?</\\1>', re.S)
REL_RE = re.compile(r'<p class="relacionadas">.*?</p>', re.S)
# casa qualquer versão do marcador: re-renderizar uma página antiga é só
# trocar a MARCADOR acima (o texto vem do cache, sem gastar chamada de IA).
SECAO_RE = re.compile(r"<!-- conteudo:v\d+ -->.*?<!-- /conteudo -->\s*", re.S)

SISTEMA = (
    "Você escreve o texto de apoio de uma calculadora online brasileira, em "
    "português do Brasil. Escreve para quem vai usar a conta na vida real: "
    "direto, concreto, sem enrolação e sem promessa. Nunca cite inteligência "
    "artificial, nunca invente lei, norma técnica, preço nacional ou "
    "estatística — se precisar de um número de referência, use faixas típicas "
    "e deixe claro que é estimativa. Não use emoji nem exclamação."
)

MOLDE = """Ferramenta: {h1}
Descrição atual: {desc}

Campos que o usuário preenche (HTML):
{app}

Cálculo que a página executa (JavaScript):
{js}

Escreva o conteúdo de apoio dessa página em JSON, com este schema exato:
{{
 "intro": "1 parágrafo de 40 a 60 palavras: que decisão essa conta resolve e para quem",
 "formula": "a fórmula em uma linha, com as unidades, exatamente como o código calcula",
 "como": ["parágrafo 1 (40-70 palavras) explicando o caminho da conta",
          "parágrafo 2 (40-70 palavras) explicando de onde vem cada número que o usuário digita"],
 "exemplo": {{"cenario": "1 frase com valores concretos plausíveis",
              "passos": ["conta 1 com os números", "conta 2", "conta 3"],
              "resultado": "1 frase com o número final"}},
 "tabela": {{"titulo": "título curto", "colunas": ["col A", "col B"],
             "linhas": [["...", "..."], ["...", "..."], ["...", "..."], ["...", "..."]]}},
 "cuidados": ["limite real 1 do cálculo", "limite real 2", "limite real 3"],
 "faq": [{{"p": "pergunta que alguém digitaria no Google", "r": "resposta de 2 a 3 frases"}},
         {{"p": "...", "r": "..."}}, {{"p": "...", "r": "..."}}, {{"p": "...", "r": "..."}}]
}}

Regras: a tabela tem de ser útil de verdade (valores típicos, equivalências,
faixas) e coerente com os campos da ferramenta. As perguntas do FAQ não podem
repetir a descrição nem umas às outras. Responda só o JSON."""


REVISOR = (
    "Você confere contas. Recebe o JSON de apoio de uma calculadora e o código "
    "que ela executa. Recalcule TODO número citado no texto (exemplo, FAQ e "
    "tabela) usando a fórmula do código e corrija o que estiver errado, "
    "mantendo o mesmo schema, o mesmo idioma e o resto do texto intacto. "
    "Se um número não puder ser verificado pela fórmula, troque por uma faixa "
    "ou remova a afirmação numérica. Responda só o JSON corrigido."
)

# hífens e aspas tipográficas viram ASCII: o resto do site é monoespaçado e
# U+2011 aparece como caixinha em algumas fontes.
TIPOGRAFIA = {"\u2010": "-", "\u2011": "-", "\u2012": "-", "\u2013": "-",
              "\u2014": "-", "\u2015": "-", "\u00a0": " ", "\u2018": "'",
              "\u2019": "'", "\u201c": '"', "\u201d": '"', "\u2026": "..."}


def normaliza(obj):
    if isinstance(obj, str):
        for k, v in TIPOGRAFIA.items():
            obj = obj.replace(k, v)
        return obj
    if isinstance(obj, list):
        return [normaliza(x) for x in obj]
    if isinstance(obj, dict):
        return {k: normaliza(v) for k, v in obj.items()}
    return obj


def _texto(m, padrao=""):
    return html.unescape(m.group(1)).strip() if m else padrao


def extrai(slug):
    f = TOOLS / slug / "index.html"
    txt = f.read_text(encoding="utf-8")
    app = _texto(APP_RE.search(txt))
    js = _texto(JS_RE.search(txt))
    return {
        "path": f, "html": txt,
        "h1": _texto(H1_RE.search(txt)),
        "desc": _texto(DESC_RE.search(txt)),
        "app": re.sub(r"\n\s*\n", "\n", app)[:2500],
        "js": js[:3000],
    }


def gera(slug, dados, force=False):
    CACHE.mkdir(parents=True, exist_ok=True)
    cache = CACHE / f"{slug}.json"
    if cache.exists() and not force:
        return json.loads(cache.read_text(encoding="utf-8"))
    d = ai.perguntar_json(
        MOLDE.format(h1=dados["h1"], desc=dados["desc"], app=dados["app"], js=dados["js"]),
        sistema=SISTEMA, robusto=True, max_tokens=4000)
    # passo de revisão: o gerador erra conta (ex.: disse R$ 2,80 por banho onde
    # a própria fórmula dá R$ 1,05). Número errado na página é pior que página
    # curta — o revisor recalcula tudo contra o código da ferramenta.
    try:
        d = ai.perguntar_json(
            "Código da calculadora:\n" + dados["js"][:3000] +
            "\n\nJSON a conferir:\n" + json.dumps(d, ensure_ascii=False),
            sistema=REVISOR, robusto=True, max_tokens=4000) or d
    except Exception as ex:
        print(f"[aviso] {slug}: revisão falhou ({str(ex)[:80]}), mantendo original")
    d = normaliza(d)
    cache.write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")
    return d


def e(s):
    return html.escape(str(s), quote=False)


def render(c):
    linhas = "\n".join(
        "      <tr>" + "".join(f"<td>{e(v)}</td>" for v in linha) + "</tr>"
        for linha in c["tabela"]["linhas"])
    faq = "\n".join(
        f"  <h3>{e(q['p'])}</h3>\n  <p>{e(q['r'])}</p>" for q in c["faq"])
    return f"""{MARCADOR}
<details class="conteudo">
  <summary>Como a conta funciona, exemplo e perguntas frequentes</summary>
  <div class="conteudo-corpo">
  <p class="intro">{e(c['intro'])}</p>
  <h2>Como o cálculo é feito</h2>
  <p class="formula"><code>{e(c['formula'])}</code></p>
""" + "\n".join(f"  <p>{e(p)}</p>" for p in c["como"]) + f"""
  <h2>Exemplo</h2>
  <p>{e(c['exemplo']['cenario'])}</p>
  <ol>
""" + "\n".join(f"    <li>{e(p)}</li>" for p in c["exemplo"]["passos"]) + f"""
  </ol>
  <p><strong>{e(c['exemplo']['resultado'])}</strong></p>
  <h2>{e(c['tabela']['titulo'])}</h2>
  <table>
    <thead><tr>""" + "".join(f"<th>{e(x)}</th>" for x in c["tabela"]["colunas"]) + f"""</tr></thead>
    <tbody>
{linhas}
    </tbody>
  </table>
  <h2>O que essa conta não considera</h2>
  <ul>
""" + "\n".join(f"    <li>{e(x)}</li>" for x in c["cuidados"]) + f"""
  </ul>
  <h2>Perguntas frequentes</h2>
{faq}
  </div>
</details>
<!-- /conteudo -->
"""


def faq_jsonld(c):
    itens = [{"@type": "Question", "name": q["p"],
              "acceptedAnswer": {"@type": "Answer", "text": q["r"]}} for q in c["faq"]]
    corpo = json.dumps({"@context": "https://schema.org", "@type": "FAQPage",
                        "mainEntity": itens}, ensure_ascii=False)
    return f'<script type="application/ld+json">\n{corpo}\n</script>\n'


def aplica(slug, dados, c):
    txt = dados["html"]
    # 1. FAQPage real no lugar do falso (que repetia a description)
    txt = FAQ_RE.sub("", txt)
    txt = txt.replace('<meta name="google-adsense-account"',
                      faq_jsonld(c) + '<meta name="google-adsense-account"', 1)
    # 2. os links relacionados ficam visíveis, fora de qualquer <details>
    det = DETAILS_RE.search(txt)
    if det:
        rel = REL_RE.search(det.group(0))
        novo = ('<nav class="explicacao">\n  '
                + (rel.group(0) if rel else "") + "\n</nav>") if rel else ""
        txt = txt.replace(det.group(0), novo)
    # 3. a seção de conteúdo entra logo depois do anúncio
    txt = SECAO_RE.sub("", txt)
    secao = render(c)
    if '<div class="ad-slot"></div>' in txt:
        txt = txt.replace('<div class="ad-slot"></div>',
                          '<div class="ad-slot"></div>\n' + secao, 1)
    else:
        txt = txt.replace("</main>", secao + "</main>", 1)
    return txt


def main(slugs, force=False, dry=False):
    todos = slugs or sorted(d.name for d in TOOLS.iterdir() if (d / "index.html").is_file())
    feitos, pulados, erros = 0, 0, 0
    for slug in todos:
        dados = extrai(slug)
        if MARCADOR in dados["html"] and not force:
            pulados += 1
            continue
        try:
            c = gera(slug, dados, force=force)
            novo = aplica(slug, dados, c)
        except Exception as ex:
            print(f"[erro] {slug}: {str(ex)[:160]}")
            erros += 1
            continue
        palavras = len(re.sub(r"<[^>]+>", " ", novo).split())
        print(f"[ok] {slug}: +{len(c['faq'])} FAQ, página com ~{palavras} palavras")
        if not dry:
            dados["path"].write_text(novo, encoding="utf-8")
        feitos += 1
    print(f"\n{feitos} escritas, {pulados} já tinham conteúdo, {erros} erro(s)")
    return 1 if erros else 0


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    sys.exit(main(args, force="--force" in sys.argv, dry="--dry-run" in sys.argv))
