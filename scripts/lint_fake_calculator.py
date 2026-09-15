#!/usr/bin/env python3
"""Sanity check anti-AI-Overview: flags ferramentas cujo SLUG cai em uma
categoria conhecida de "preço de serviço/produto" — mesmo que a calculadora
por trás seja boa e tenha input real.

Por quê (lição do cleanup de 212 ferramentas em set/2026): a AI Overview do
Google responde pela INTENÇÃO da busca, não pela qualidade da página. Ter
número/data real no formulário protege quando a pergunta pede um resultado
que só existe DEPOIS do cálculo (bhaskara, boost de jogo, arcano pessoal) —
não protege quando a pergunta em si já É a resposta que o Google sintetiza
("quanto custa X", "preço de X").

Isto é só uma rede de segurança para categorias JÁ CONHECIDAS (bucket de
prefixo de slug) — NÃO tenta mais detectar a frase "preço/valor de X" no
texto da página via regex. Foi abandonado: a mesma frase aparece tanto numa
pergunta informacional real ("preço de mercado de X") quanto describing um
INPUT que o usuário fornece numa calculadora legítima ("valor da hora",
"preço do kg do gás") — são semanticamente diferentes mas textualmente
idênticas, e regex não distingue intenção. Essa distinção agora é feita pelo
agente NA SELEÇÃO da keyword (passo 2d do CLAUDE.md), antes de a ferramenta
ser construída — é ali que "esta pergunta seria totalmente respondida por um
resumo de IA em 2 frases, sem precisar de nenhum dado pessoal do usuário?"
precisa ser julgado caso a caso. Este script continua útil só para pegar
automaticamente slugs que reincidem numa categoria já comprovadamente ruim.

Uso:
  python3 scripts/lint_fake_calculator.py                 # varre tools/ inteiro, relatório
  python3 scripts/lint_fake_calculator.py <slug> [<slug>...]  # só as informadas; exit 1 se achar
"""
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
TOOLS_DIR = ROOT / "tools"

PREFIXOS_RISCO = {
    "custo", "consulta", "cirurgia", "consertar", "alugar", "instalar",
    "trocar", "troca", "exame", "aula", "curso", "tratamento", "desentupir",
    "higienizacao", "instalacao", "limpar", "limpeza", "pintar", "vacina",
    "acupuntura", "adestramento", "animacao", "blindar", "castracao",
    "drenagem", "harmonizacao", "micropigmentacao", "extrair", "implante",
    "protese", "clareamento", "reforma", "reformar", "construir", "dedetizacao",
}


def parece_preco_de_mercado(slug: str, html: str) -> bool:
    return slug.split("-")[0] in PREFIXOS_RISCO


def eh_fake_calculator(slug: str, html: str) -> bool:
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
