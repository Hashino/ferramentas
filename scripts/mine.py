#!/usr/bin/env python3
"""Minera sugestões do Google (autocomplete) e alimenta backlog/keywords.csv.

Uso:
  python3 scripts/mine.py [limite]      # coleta novas keywords (default 30)
  python3 scripts/mine.py --check [N]   # baixa SERP (Serper) das N primeiras candidatas sem SERP
"""
import csv
import json
import os
import pathlib
import sys
import time
import urllib.parse
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parent.parent
BACKLOG = ROOT / "backlog"
CSV_PATH = BACKLOG / "keywords.csv"
SERP_PATH = BACKLOG / "serp.json"

# cabeças de busca em PT-BR; o alfabeto serve para expandir cada cabeça
SEEDS = [
    "calculadora de ",
    "gerador de ",
    "como calcular ",
    "quantos dias ",
    "converter ",
    "simulador de ",
    "tabela de ",
    "quanto é ",
]
ALFABETO = "abcdefghijklmnopqrstuvxz"


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


def sugestoes(query: str) -> list[str]:
    url = (
        "https://suggestqueries.google.com/complete/search?client=firefox&hl=pt-BR&gl=br&q="
        + urllib.parse.quote(query)
    )
    data = json.loads(_get(url).decode("utf-8"))
    return [s.strip().lower() for s in data[1] if isinstance(s, str)]


def load_rows() -> dict:
    rows = {}
    if CSV_PATH.exists():
        with open(CSV_PATH, newline="", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                rows[row["keyword"]] = {
                    "status": row["status"],
                    "adicionada_em": row["adicionada_em"],
                }
    return rows


def save_rows(rows: dict) -> None:
    BACKLOG.mkdir(exist_ok=True)
    with open(CSV_PATH, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["keyword", "status", "adicionada_em"])
        w.writeheader()
        for kw in sorted(rows):
            w.writerow({"keyword": kw, **rows[kw]})


def harvest(limite: int) -> None:
    rows = load_rows()
    novos = []
    hoje = time.strftime("%Y-%m-%d")
    for seed in SEEDS:
        for sufixo in [""] + list(ALFABETO):
            q = seed + sufixo
            try:
                for s in sugestoes(q):
                    if not 3 <= len(s) <= 60:
                        continue
                    if s in rows or s in novos:
                        continue
                    rows[s] = {"status": "candidata", "adicionada_em": hoje}
                    novos.append(s)
            except Exception as e:  # rede/limite: registra e segue
                print(f"aviso: {q!r}: {e}", file=sys.stderr)
            time.sleep(0.8)
            if len(novos) >= limite:
                save_rows(rows)
                print(f"{len(novos)} novas keywords salvas em {CSV_PATH.relative_to(ROOT)}")
                return
    save_rows(rows)
    print(f"{len(novos)} novas keywords salvas em {CSV_PATH.relative_to(ROOT)}")


def check(limite: int) -> None:
    api = _ler_dotenv()
    if not api:
        sys.exit("erro: SERPER_API_KEY ausente (.env ou ambiente)")
    rows = load_rows()
    serp = json.loads(SERP_PATH.read_text(encoding="utf-8")) if SERP_PATH.exists() else {}
    pendentes = [
        kw
        for kw, meta in sorted(rows.items())
        if meta["status"] == "candidata" and kw not in serp
    ][:limite]
    if not pendentes:
        print("nenhuma candidata pendente de SERP")
        return
    for kw in pendentes:
        try:
            data = json.loads(
                _post(
                    "https://google.serper.dev/search",
                    {"q": kw, "gl": "br", "hl": "pt-br", "num": 10},
                    {"X-API-KEY": api},
                ).decode("utf-8")
            )
            serp[kw] = [
                f"{item.get('title', '')} :: {item.get('link', '')}"
                for item in data.get("organic", [])
            ]
            print(f"ok: {kw} ({len(serp[kw])} resultados)")
        except Exception as e:  # não aborta o lote
            print(f"erro em {kw!r}: {e}", file=sys.stderr)
        time.sleep(1.2)
    BACKLOG.mkdir(exist_ok=True)
    SERP_PATH.write_text(json.dumps(serp, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"serp.json atualizado ({len(serp)} keywords com dados)")


if __name__ == "__main__":
    args = sys.argv[1:]
    if args and args[0] == "--check":
        check(int(args[1]) if len(args) > 1 else 10)
    else:
        harvest(int(args[0]) if args else 30)
