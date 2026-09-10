# ferramentas

Fábrica de micro-ferramentas web (calculadoras, geradores, conversores) em PT-BR,
publicadas no GitHub Pages e monetizadas com AdSense.

- Site: https://hashino.github.io/ferramentas/
- Pipeline e comando de produção: veja [CLAUDE.md](CLAUDE.md)
- Mineração de keywords: `python3 scripts/mine.py` (harvest) e `python3 scripts/mine.py --check` (SERP via Serper)
- Build do hub/sitemap/etc: `python3 scripts/build.py`

Chaves ficam em `.env` (fora do git). A chave do IndexNow é pública por design.
