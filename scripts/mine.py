#!/usr/bin/env python3
"""Mineração de keywords para o backlog — várias fontes, um só portão de qualidade.

Fontes (IA só gera hipótese; o portão é sempre dado humano do Google):
  harvest   cabeças de busca × alfabeto no autocomplete
  matrix    varredura sistemática: domínios de seeds.json × cabeças (+ estado)
  check     SERP (Serper) das candidatas + INGESTÃO de relatedSearches/PAA
  deep      expande keywords provadas (feitas/boa) em variantes mais longas
  reddit    threads BR pedindo ferramenta (Serper) → candidatos validados
  sitemaps  títulos de sites de ferramentas concorrentes → candidatos validados

Portão de validação: um candidato só entra no backlog se aparecer numa sugestão
do autocomplete do Google (prova de demanda real digitada por gente).

Uso:
  python3 scripts/mine.py                 # harvest, 30 novas
  python3 scripts/mine.py harvest 50
  python3 scripts/mine.py matrix 5        # varre os próximos 5 domínios
  python3 scripts/mine.py --check 10      # idêntico a: check 10
  python3 scripts/mine.py check 10
  python3 scripts/mine.py deep 3          # variantes em volta de 3 keywords provadas
  python3 scripts/mine.py reddit 5        # caça pedidos de ferramenta em 5 domínios
  python3 scripts/mine.py sitemaps 20     # até 20 candidatos validados por site
"""
import csv
import datetime
import json
import os
import pathlib
import re
import sys
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

ROOT = pathlib.Path(__file__).resolve().parent.parent
BACKLOG = ROOT / "backlog"
CSV_PATH = BACKLOG / "keywords.csv"
SERP_PATH = BACKLOG / "serp.json"
SEEDS_PATH = BACKLOG / "seeds.json"
MATRIX_STATE = BACKLOG / "matrix_state.json"
CAMPOS = ["keyword", "status", "adicionada_em", "origem"]
SLEEP = 0.7  # pausa entre chamadas ao Google; mexa só para baixo com calma
ALFABETO = "abcdefghijklmnopqrstuvxz"

TRIGGER = re.compile(
    r"(calculadora|gerador|conversor|simulador|ferramenta|planilha|tabela|app|site)"
    r"[^a-z0-9]{0,3}(?:pra|para|de|do|da|dos|das)?\s*([a-z0-9à-ú ]{3,40})"
)
URL_FIM = re.compile(r"[^a-z0-9à-ú]+")


def _get(url: str, timeout: int = 10) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (X11; Linux x86_64)"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def _post(url: str, payload: dict, headers: dict, timeout: int = 15) -> bytes:
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json", **headers},
    )
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def _ler_dotenv() -> str:
    env = ROOT / ".env"
    if env.exists():
        for linha in env.read_text(encoding="utf-8").splitlines():
            if linha.startswith("SERPER_API_KEY="):
                return linha.split("=", 1)[1].strip()
    return os.environ.get("SERPER_API_KEY", "")


def _seeds() -> dict:
    return json.loads(SEEDS_PATH.read_text(encoding="utf-8"))


def _hoje() -> str:
    return datetime.date.today().isoformat()


def sugestoes(query: str) -> list[str]:
    url = (
        "https://suggestqueries.google.com/complete/search?client=firefox&hl=pt-BR&gl=br&q="
        + urllib.parse.quote(query)
    )
    data = json.loads(_get(url).decode("utf-8"))
    return [s.strip().lower() for s in data[1] if isinstance(s, str)]


def validado(query: str) -> bool:
    """Portão: o Google sugere algo que contém a query? (demanda comprovada)"""
    try:
        return any(query in s for s in sugestoes(query))
    except Exception:
        return False


def load_rows() -> dict:
    rows = {}
    if CSV_PATH.exists():
        with open(CSV_PATH, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                rows[row["keyword"]] = {
                    "status": row["status"],
                    "adicionada_em": row.get("adicionada_em", ""),
                    "origem": row.get("origem", "") or "",
                }
    return rows


def save_rows(rows: dict) -> None:
    BACKLOG.mkdir(exist_ok=True)
    with open(CSV_PATH, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=CAMPOS)
        w.writeheader()
        for kw in sorted(rows):
            w.writerow({"keyword": kw, **rows[kw]})


def add(rows: dict, novos: dict, kw: str, origem: str) -> bool:
    """Tenta inserir com o portão já passado (kw já validada)."""
    if not 3 <= len(kw) <= 70:
        return False
    if kw in rows or kw in novos:
        return False
    rows[kw] = {"status": "candidata", "adicionada_em": _hoje(), "origem": origem}
    novos[kw] = True
    return True


def limpar(linha: str) -> str:
    return re.sub(r"\s+", " ", linha.strip().lower())


# ── harvest: cabeças × alfabeto ──────────────────────────────────────────────
def harvest(limite: int) -> None:
    seeds = _seeds()
    rows = load_rows()
    novos = {}
    instrumento = seeds["cabecas"]["instrumento"]
    todas = instrumento + seeds["cabecas"]["pergunta"] + seeds["cabecas"]["acao"]
    for cabeca in todas:
        variacoes = [cabeca + c for c in [""] + list(ALFABETO)] if cabeca in instrumento else [cabeca]
        for q in variacoes:
            try:
                for s in sugestoes(q):
                    if not 3 <= len(s) <= 70:
                        continue
                    if s in rows or s in novos:
                        continue
                    rows[s] = {"status": "candidata", "adicionada_em": _hoje(), "origem": "harvest"}
                    novos[s] = True
            except Exception as e:  # rede/limite: registra e segue
                print(f"aviso: {q!r}: {e}", file=sys.stderr)
            time.sleep(SLEEP)
            if len(novos) >= limite:
                break
        if len(novos) >= limite:
            break
    save_rows(rows)
    print(f"harvest: {len(novos)} novas keywords salvas em {CSV_PATH.relative_to(ROOT)}")


# ── deep: expande keywords já provadas (feitas/boas) em variantes mais longas ─
def deep(limite: int) -> None:
    """Sugestões do Google que CONTÊM uma keyword provada já nascem validadas:
    são demanda real em volta de um tema que comprovadamente nos encontra."""
    rows = load_rows()
    alvos = [
        kw
        for kw, meta in sorted(rows.items())
        if meta["status"] in {"feita", "boa"}
    ][:limite]
    if not alvos:
        print("deep: nenhuma keyword feita/boa para expandir")
        return
    novos = {}
    for kw in alvos:
        antes = len(novos)
        for sufixo in [" "] + [c + " " for c in ALFABETO]:
            try:
                for s in sugestoes(kw + sufixo):
                    if (
                        3 <= len(s) <= 70
                        and kw in s
                        and s != kw
                        and s not in rows
                        and s not in novos
                    ):
                        rows[s] = {"status": "candidata", "adicionada_em": _hoje(), "origem": f"deep:{kw}"}
                        novos[s] = True
            except Exception as e:
                print(f"aviso: {kw + sufixo!r}: {e}", file=sys.stderr)
            time.sleep(SLEEP)
        print(f"deep: '{kw}' → {len(novos) - antes} variantes")
    save_rows(rows)
    print(f"deep: {len(novos)} novas keywords em volta de {len(alvos)} provadas")


# ── matrix: domínio × cabeças, com estado de progresso ───────────────────────
def matrix(n_dominios: int) -> None:
    seeds = _seeds()
    state = json.loads(MATRIX_STATE.read_text(encoding="utf-8")) if MATRIX_STATE.exists() else {"varridos": []}
    restantes = [d for d in seeds["dominios"] if d not in state["varridos"]]
    if not restantes:
        print("matrix: todos os domínios já varridos — adicione domínios em seeds.json")
        return
    rows = load_rows()
    novos = {}
    varridos_agora = 0
    for dominio in restantes:
        if varridos_agora >= n_dominios:
            break
        for cabeca in seeds["cabecas"]["instrumento"] + seeds["cabecas"]["pergunta"]:
            for q in [cabeca + dominio, cabeca + dominio + " "]:
                try:
                    for s in sugestoes(q):
                        if 3 <= len(s) <= 70 and s not in rows and s not in novos:
                            rows[s] = {"status": "candidata", "adicionada_em": _hoje(), "origem": f"matrix:{dominio}"}
                            novos[s] = True
                except Exception as e:
                    print(f"aviso: {q!r}: {e}", file=sys.stderr)
                time.sleep(SLEEP)
        state["varridos"].append(dominio)
        varridos_agora += 1
        print(f"matrix: domínio '{dominio}' varrido ({len(novos)} novas até agora)")
        MATRIX_STATE.write_text(json.dumps(state, ensure_ascii=False, indent=1), encoding="utf-8")
    save_rows(rows)
    print(f"matrix: {varridos_agora} domínios, {len(novos)} novas keywords "
          f"({len([d for d in seeds['dominios'] if d not in state['varridos']])} domínios restantes)")


# ── check: SERP + ingestão de relatedSearches/PAA ────────────────────────────
def check(limite: int, filtro: str = "") -> None:
    """`filtro` casa com a keyword OU com a origem (ex.: "matrix:imc").

    Sem filtro a fila sai em ordem alfabética e, com 3.000 candidatas, isso
    significa gastar crédito para sempre dentro de "calculadora de ..." —
    justamente a família mais saturada. Descoberto em 18/09/2026: dois `check`
    seguidos não saíram do bloco financeiro enquanto domínios recém-minerados
    (imc, calorias, água por dia) seguiam sem SERP.
    """
    api = _ler_dotenv()
    if not api:
        sys.exit("erro: SERPER_API_KEY ausente (.env ou ambiente)")
    rows = load_rows()
    serp = json.loads(SERP_PATH.read_text(encoding="utf-8")) if SERP_PATH.exists() else {}

    # Corte por família ANTES de gastar crédito: se um nicho já foi checado
    # várias vezes e não rendeu nenhuma ferramenta, as variações restantes não
    # vão render também. Sem isso a conta queimou ~1100 créditos, boa parte em
    # famílias inteiras condenadas de uma vez pela triagem (7 variações de
    # "calculadora de bitcoin", 11 de "gerador de ...").
    from triagem import familia, familias_condenadas  # import tardio: puxa ai.py
    mortas = familias_condenadas()

    # duas passadas: primeiro condena o backlog TODO (não custa nada e limpa o
    # CSV de uma vez), só depois escolhe as `limite` que vão gastar crédito.
    # Fazer numa passada só, cortando até bater o limite, deixaria o resto das
    # famílias mortas vivo no CSV e adiaria a economia para runs futuros.
    cortadas = 0
    for kw, meta in rows.items():
        if meta["status"] == "candidata" and kw not in serp and familia(kw) in mortas:
            meta["status"] = "descartada"
            cortadas += 1

    # vários filtros separados por vírgula: a fila alfabética dentro de UM
    # filtro também engana ("--filtro matrix:tinta" gastou 12 créditos só em
    # "calculadora de tinta <marca>", a cabeça mais saturada da família).
    fs = [x.strip().lower() for x in filtro.split(",") if x.strip()]
    def casa(kw, meta):
        alvo = kw.lower() + " || " + meta.get("origem", "").lower()
        return not fs or any(f in alvo for f in fs)
    pendentes = [
        kw for kw, meta in sorted(rows.items())
        if meta["status"] == "candidata" and kw not in serp and casa(kw, meta)
    ][:limite]

    if cortadas:
        save_rows(rows)
        print(f"corte por família: {cortadas} candidatas descartadas sem gastar SERP "
              f"({len(mortas)} famílias condenadas: {', '.join(sorted(mortas)[:6])})")
    if not pendentes:
        print("check: nenhuma candidata pendente de SERP")
        return
    novos = {}
    for kw in pendentes:
        try:
            data = json.loads(
                _post(
                    "https://google.serper.dev/search",
                    {"q": kw, "gl": "br", "hl": "pt-br", "num": 10},
                    {"X-API-KEY": api},
                ).decode("utf-8")
            )
            # o snippet vem de graça na mesma chamada e costuma listar os
            # CAMPOS do formulário ("Data inicial; Valor a ser corrigido; %
            # do CDI") — é o sinal mais forte de que o resultado é ferramenta
            # interativa e não artigo. Formato antigo (string "titulo :: link")
            # continua sendo lido; ver lint_serp.normalizar.
            serp[kw] = [
                {
                    "title": item.get("title", ""),
                    "link": item.get("link", ""),
                    "snippet": item.get("snippet", ""),
                }
                for item in data.get("organic", [])
            ]
            print(f"ok: {kw} ({len(serp[kw])} resultados)")
            # ingestão: related searches e PAA são demanda real do próprio Google
            for item in data.get("relatedSearches", [])[:8]:
                rel = limpar(item.get("query", "") if isinstance(item, dict) else str(item))
                if rel and add(rows, novos, rel, f"related:{kw}"):
                    pass
            for item in data.get("peopleAlsoAsk", [])[:4]:
                paa = limpar(item.get("question", ""))
                if paa and add(rows, novos, paa, f"paa:{kw}"):
                    pass
        except Exception as e:  # não aborta o lote
            print(f"erro em {kw!r}: {e}", file=sys.stderr)
        time.sleep(1.2)
    save_rows(rows)
    BACKLOG.mkdir(exist_ok=True)
    SERP_PATH.write_text(json.dumps(serp, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"check: {len(serp)} keywords com SERP; {len(novos)} novas via related/PAA")


# ── reddit: threads pedindo ferramenta → validar no autocomplete ─────────────
def reddit(n_dominios: int) -> None:
    api = _ler_dotenv()
    if not api:
        sys.exit("erro: SERPER_API_KEY ausente (.env ou ambiente)")
    seeds = _seeds()
    rows = load_rows()
    novos = {}
    feitos = 0
    for dominio in seeds["dominios"]:
        if feitos >= n_dominios:
            break
        achados_antes = len(novos)
        for modelo in seeds["reddit_queries"]:
            q = modelo.format(dominio=dominio)
            try:
                data = json.loads(
                    _post(
                        "https://google.serper.dev/search",
                        {"q": q, "gl": "br", "hl": "pt-br", "num": 10},
                        {"X-API-KEY": api},
                    ).decode("utf-8")
                )
                titulos = [limpar(i.get("title", "")) for i in data.get("organic", [])]
            except Exception as e:
                print(f"aviso: {q!r}: {e}", file=sys.stderr)
                continue
            for titulo in titulos:
                for m in TRIGGER.finditer(titulo):
                    gatilho, topico = m.group(1), m.group(2).strip(" ?!.,")
                    if not topico or len(topico.split()) > 6:
                        continue
                    candidato = limpar(f"{gatilho} {topico}")
                    if 3 <= len(candidato) <= 70 and candidato not in rows and candidato not in novos:
                        time.sleep(SLEEP)
                        if validado(candidato):
                            rows[candidato] = {"status": "candidata", "adicionada_em": _hoje(), "origem": f"reddit:{dominio}"}
                            novos[candidato] = True
            time.sleep(1.2)
        feitos += 1
        print(f"reddit: '{dominio}' → {len(novos) - achados_antes} candidatos validados")
    save_rows(rows)
    print(f"reddit: {len(novos)} novas keywords (validadas no autocomplete)")


# ── sitemaps: títulos de concorrentes → validar no autocomplete ──────────────
def _locais_de_sitemap(url: str, teto: int = 3) -> list[str]:
    """Retorna <loc>s; se for sitemap index, desce até teto filhos."""
    try:
        xml = _get(url, timeout=15).decode("utf-8", "replace")
    except Exception as e:
        print(f"aviso: sitemap {url}: {e}", file=sys.stderr)
        return []
    raiz = ET.fromstring(xml)
    def tag(e):
        return e.tag.split("}")[-1]
    if tag(raiz) == "sitemapindex":
        filhos = [e.text.strip() for e in raiz.iter() if tag(e) == "loc"][:teto]
        locais = []
        for filho in filhos:
            locais.extend(_locais_de_sitemap(filho, teto=0))
            time.sleep(SLEEP)
        return locais
    return [e.text.strip() for e in raiz.iter() if tag(e) == "loc"]


def _url_para_frase(loc: str) -> str:
    fim = urllib.parse.urlparse(loc).path.rstrip("/").rsplit("/", 1)[-1]
    fim = re.sub(r"\.(html?|php|aspx?)$", "", fim)
    partes = [p for p in URL_FIM.split(fim) if p and not p.isdigit() and p not in {"index", "page", "blog", "categoria"}]
    return limpar(" ".join(partes))


def sitemaps(n_por_site: int) -> None:
    seeds = _seeds()
    rows = load_rows()
    novos = {}
    for url in seeds["sitemaps"]:
        dominio = urllib.parse.urlparse(url).netloc
        antes = len(novos)
        for loc in _locais_de_sitemap(url):
            if len(novos) - antes >= n_por_site:
                break
            frase = _url_para_frase(loc)
            if not 8 <= len(frase) <= 70 or frase in rows or frase in novos:
                continue
            time.sleep(SLEEP)
            if validado(frase):
                rows[frase] = {"status": "candidata", "adicionada_em": _hoje(), "origem": f"sitemap:{dominio}"}
                novos[frase] = True
        print(f"sitemaps: {dominio} → {len(novos) - antes} validados")
    save_rows(rows)
    print(f"sitemaps: {len(novos)} novas keywords (validadas no autocomplete)")


if __name__ == "__main__":
    args = sys.argv[1:]
    modo = args[0] if args and not args[0].isdigit() else "harvest"
    n = int(args[1]) if len(args) > 1 else (int(args[0]) if args and args[0].isdigit() else 30)
    if modo in {"--check", "check"}:
        filtro = args[args.index("--filtro") + 1] if "--filtro" in args else ""
        check(n, filtro)
    elif modo == "matrix":
        matrix(n)
    elif modo == "deep":
        deep(n)
    elif modo == "reddit":
        reddit(n)
    elif modo == "sitemaps":
        sitemaps(n)
    else:
        harvest(n)
