#!/usr/bin/env python3
"""Lint anti-AI-Overview: flags ferramentas cuja PERGUNTA em si é informacional
("quanto custa/vale/sai/é/cobra X", "preço de X", "valor de X") — mesmo que a
calculadora por trás seja boa e tenha input real.

Por quê (lição do cleanup de 212 ferramentas em set/2026): a AI Overview do
Google responde pela INTENÇÃO da busca, não pela qualidade da página. Uma
calculadora ótima de "quanto custa construir uma piscina" com m² real como
input ainda perde o clique, porque a intenção "me dá uma estimativa" já foi
satisfeita ali mesmo na SERP — o usuário nunca chega a testar o input. Ter
número/data real no formulário protege quando a pergunta pede um resultado
que só existe DEPOIS do cálculo (bhaskara, boost de jogo, arcano pessoal) —
não protege quando a pergunta em si já É a resposta que o Google sintetiza.

Critério (qualquer um dos dois já reprova, input real não isenta):
  (a) slug começa com prefixo de bucket conhecido como preço de serviço/produto
      (custo-, consulta-, cirurgia-, consertar-, alugar-, instalar-, trocar-,
      exame-, aula-, curso-, tratamento- etc.)
  (b) title/description contém "quanto custa/é/sai/vale/cobra", "preço de",
      "valor de" ou "custo de"

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

def parece_preco_de_mercado(slug: str, html: str) -> bool:
    if slug.split("-")[0] in PREFIXOS_RISCO:
        return True
    return bool(PADRAO_PRECO_MERCADO.search(html[:2000]))  # title/description ficam no início


def eh_fake_calculator(slug: str, html: str) -> bool:
    # input real não isenta mais: a pergunta em si já é o que a AI Overview responde.
    return parece_preco_de_mercado(slug, html)


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
