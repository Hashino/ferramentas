#!/usr/bin/env python3
"""Diz qual ferramenta construir agora. Um comando, uma resposta.

    python3 scripts/proxima.py

Faz sozinho tudo que exige julgamento e rede: abastece o backlog se estiver
seco, busca a SERP das candidatas, e roda a triagem por IA (é ferramenta
interativa ou só artigo? um AI Overview já responderia isso?). Imprime a
keyword aprovada e o slug a usar.

Existe para que quem constrói a ferramenta não precise decidir nada: a
escolha é a parte que dá errado quando feita "no olho" — foi assim que o
site acumulou 52 páginas em SERP já dominada por calculadoras de grandes
portais, todas removidas em set/2026.

Saída (stdout), pronta para ser lida por um agente:
    KEYWORD: quantos sacos de cimento por metro quadrado
    SLUG: sacos-cimento-metro-quadrado
    MOTIVO: nenhuma ferramenta interativa no top-3; exige dado do usuário
Ou, se não houver nada aprovado agora:
    NENHUMA: <explicação>
"""
import json
import pathlib
import re
import subprocess
import sys
import unicodedata

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import triagem  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parent.parent
TOOLS_DIR = ROOT / "tools"
CSV = ROOT / "backlog" / "keywords.csv"
SERP_PATH = ROOT / "backlog" / "serp.json"
CACHE = ROOT / "backlog" / "triagem.json"

PARAR = {"de", "da", "do", "das", "dos", "para", "por", "em", "um", "uma", "o", "a",
         "e", "com", "quanto", "quantos", "quantas", "calculadora", "calcular",
         "tem", "que", "no", "na", "meu", "minha", "online", "gratis"}


def slugificar(kw: str) -> str:
    s = unicodedata.normalize("NFD", kw.lower())
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    s = re.sub(r"[^a-z0-9]+", "-", s).strip("-")
    partes = [p for p in s.split("-") if p and p not in PARAR]
    return "-".join((partes or s.split("-"))[:4])


def _rodar(*args: str) -> None:
    subprocess.run([sys.executable, *args], cwd=ROOT, check=False)


def _linhas() -> list[list[str]]:
    return [l.split(",") for l in CSV.read_text(encoding="utf-8").splitlines()[1:] if l.strip()]


def main() -> None:
    serp = json.loads(SERP_PATH.read_text(encoding="utf-8")) if SERP_PATH.exists() else {}
    cache = json.loads(CACHE.read_text(encoding="utf-8")) if CACHE.exists() else {}
    existentes = {d.name for d in TOOLS_DIR.iterdir() if d.is_dir()}

    pendentes = [c[0] for c in _linhas() if len(c) > 1 and c[1] == "candidata"]
    sem_serp = [k for k in pendentes if k not in serp]

    # backlog seco ou sem SERP? abastece antes de decidir.
    if len(pendentes) < 20:
        print("backlog baixo, minerando...", file=sys.stderr)
        _rodar("scripts/mine.py", "matrix", "3")
        pendentes = [c[0] for c in _linhas() if len(c) > 1 and c[1] == "candidata"]
        sem_serp = [k for k in pendentes if k not in serp]
    if sem_serp:
        print(f"buscando SERP de {min(len(sem_serp), 20)} candidatas...", file=sys.stderr)
        _rodar("scripts/mine.py", "check", "20")
        serp = json.loads(SERP_PATH.read_text(encoding="utf-8"))

    testadas = 0
    for kw in [c[0] for c in _linhas() if len(c) > 1 and c[1] == "candidata"]:
        if kw not in serp:
            continue
        slug = slugificar(kw)
        if slug in existentes:
            continue
        testadas += 1
        r = triagem.triar(kw, serp[kw], cache)
        CACHE.write_text(json.dumps(cache, ensure_ascii=False, indent=1), encoding="utf-8")
        if r["veredito"] == "CONSTRUIR":
            print(f"KEYWORD: {kw}")
            print(f"SLUG: {slug}")
            print(f"MOTIVO: {r['motivo']}")
            return

    print(f"NENHUMA: {testadas} candidatas testadas, nenhuma aprovada. "
          "Rode `python3 scripts/mine.py matrix 5` e `python3 scripts/mine.py check 30` "
          "para trazer keywords novas, depois tente de novo.")


if __name__ == "__main__":
    main()
