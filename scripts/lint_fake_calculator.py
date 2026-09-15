#!/usr/bin/env python3
"""Lint anti-AI-Overview: flags ferramentas que são, na prática, uma pergunta
informacional ("quanto custa X") disfarçada de calculadora — dropdown fixo
multiplicando uma constante, sem nenhum número/data que o usuário digite.

Por quê: esse é exatamente o formato que a AI Overview do Google sintetiza
direto na SERP a partir de blogs (mesma pergunta, mesma resposta de faixa de
preço, zero necessidade de dado pessoal do usuário) — cliques cortados antes
de chegar no site. Calculadora com input numérico/data real (idade, m²,
quantidade, datas) é defensável: a resposta depende de dado que só o usuário
tem, então a IA não consegue pré-sintetizar um valor único.

Critério: bucket de slug conhecido como "preço de serviço/produto de mercado"
(custo-, consulta-, cirurgia-, consertar-, alugar-, instalar-, trocar-,
exame-, aula-, curso-, tratamento- etc.) SEM nenhum <input type="number"> ou
type="date"> real na página.

Uso:
  python3 scripts/lint_fake_calculator.py                 # varre tools/ inteiro, relatório
  python3 scripts/lint_fake_calculator.py <slug> [<slug>...]  # só as informadas; exit 1 se achar
"""
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
TOOLS_DIR = ROOT / "tools"

PREFIXOS_RISCO = {
    "custo", "consulta", "cirurgia", "consertar", "alugar", "instalar",
    "trocar", "troca", "exame", "aula", "curso", "tratamento", "desentupir",
    "higienizacao", "instalacao", "limpar", "limpeza", "pintar", "vacina",
    "acupuntura", "adestramento", "animacao", "banho", "blindar", "castracao",
    "drenagem", "harmonizacao", "micropigmentacao", "extrair", "implante",
    "protese", "clareamento", "reforma", "reformar", "construir", "dedetizacao",
}

PADRAO_PRECO_MERCADO = re.compile(
    r"quanto (custa|é|sai|vale|cobra)|pre[cç]o (de|do|da)|"
    r"valor (de|do|da)|custo (de|do|da)",
    re.I,
)

INPUT_REAL = re.compile(r'<input[^>]*type="(number|date)"')


def parece_preco_de_mercado(slug: str, html: str) -> bool:
    if slug.split("-")[0] in PREFIXOS_RISCO:
        return True
    return bool(PADRAO_PRECO_MERCADO.search(html[:2000]))  # title/description ficam no início


def eh_fake_calculator(slug: str, html: str) -> bool:
    return parece_preco_de_mercado(slug, html) and not INPUT_REAL.search(html)


def varrer(slugs: list[str] | None) -> list[str]:
    alvos = (
        [TOOLS_DIR / s for s in slugs]
        if slugs
        else sorted(TOOLS_DIR.iterdir())
    )
    achados = []
    for d in alvos:
        f = d / "index.html"
        if not f.is_file():
            print(f"aviso: {d} sem index.html", file=sys.stderr)
            continue
        html = f.read_text(encoding="utf-8")
        if eh_fake_calculator(d.name, html):
            achados.append(d.name)
    return achados


if __name__ == "__main__":
    slugs = sys.argv[1:] or None
    achados = varrer(slugs)
    if slugs:
        if achados:
            print("FALHOU — parecem preço de mercado sem input real (risco de AI Overview):")
            for s in achados:
                print(f"  {s}")
            sys.exit(1)
        print(f"ok: {len(slugs)} ferramenta(s) sem risco óbvio de AI Overview")
    else:
        total = len(list(TOOLS_DIR.iterdir()))
        print(f"{len(achados)}/{total} ferramentas publicadas parecem 'preço de mercado' sem input real:")
        for s in achados:
            print(f"  {s}")
