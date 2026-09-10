# Ferramentas — fábrica de micro-ferramentas (SEO + GEO)

Site estático em PT-BR hospedado em https://hashino.github.io/ferramentas/
(GitHub Pages, branch `main`, raiz do repo — sem build step, sem Jekyll: `.nojekyll` presente).
Cada ferramenta é uma página `tools/<slug>/index.html` que mira UMA keyword de cauda longa.
Monetização: Google AdSense, configurado em `site.json` e injetado via `config.js` (gerado por `scripts/build.py`) + `ads.js`.

## Layout

- `backlog/keywords.csv` — fila de keywords (`status`: `candidata` | `feita` | `descartada`)
- `backlog/serp.json` — top-10 do Google por keyword (via Serper), para julgar concorrência
- `scripts/mine.py` — mineração: `python3 scripts/mine.py [limite]` (harvest de autocomplete) e `python3 scripts/mine.py --check [N]` (SERP das candidatas)
- `scripts/build.py` — regenera `index.html` (hub), `sitemap.xml`, `robots.txt`, `llms.txt`, `config.js`, `ads.txt`. SEMPRE rodar antes de commitar.
- `scripts/ping_indexnow.py` — roda no CI a cada push; não rodar manualmente
- `search.js` — busca fuzzy da home (filtra/reordena os cards conforme digitação)
- `chrome.js` — UI compartilhada de TODAS as páginas, injetada em runtime: starfield (3 camadas), topnav ("Ferramentas" + toggle de tema), AdSense (se config.js tiver client) e rodapé (só nas páginas com `<body data-footer>`). Alterar UI do site = editar `chrome.js`/`style.css` UMA vez; propaga para todas as páginas sem rebuild. Página de ferramenta NUNCA contém topnav/stars/footer no HTML.
- `templates/tool/index.html` — molde com tokens `{{...}}`; copiar e preencher. A página da ferramenta contém apenas: head com meta/SEO + `<main>` (H1 + `.app` + `.ad-slot`) + `config.js`, `chrome.js` e o JS da ferramenta.
- Visual: Nord + monoespaçada + cards de vidro + starfield (herdado do learnive/hashino.github.io). Tema CLARO é o default; toggle claro/escuro na barra superior (persiste em localStorage; o tema inicial vem do snippet inline no `<head>` para evitar flash).
- `.env` — `SERPER_API_KEY` (NUNCA comitar; está no .gitignore)

## Comando: "faça as próximas N aplicações"

1. **Abastecer o backlog** se houver menos de ~3×N linhas `candidata`:
   - `python3 scripts/mine.py <N*10>` (harvest; rede)
   - `python3 scripts/mine.py --check <N*3>` (SERP via Serper)
2. **Selecionar N candidatas** lendo `backlog/serp.json`. Critérios, em ordem:
   (a) SERP sem ferramenta dedicada no top-10 (fóruns, Reddit, resultados genéricos = demanda sem oferta);
   (b) tarefa resolvível em 1 página estática de vanilla JS (calcular/gerar/convertar);
   (c) sem overlap com ferramenta já publicada em `tools/`.
3. **Criar cada ferramenta**: copiar `templates/tool/index.html` para `tools/<slug>/index.html` e preencher:
   - slug: kebab-case curto, derivado da keyword
   - `<title>`: keyword primeiro, ≤60 chars · meta description ≤155 chars
   - H1 = título humano; `{{APP_HTML}}` + `{{APP_JS}}` = a ferramenta (funciona offline, sem CDN, sem biblioteca)
   - A página da ferramenta é SÓ a ferramenta: barra superior + H1 + app + rodapé.
   NADA de seção "Como funciona", FAQ visível ou qualquer texto explicativo (decisão do dono).
   - marca a keyword como `feita` em `backlog/keywords.csv`
4. **Build + deploy**: `python3 scripts/build.py` → commit (`tool: <slug>`) → `git push`.
5. **Reportar**: URLs criadas; o workflow `indexnow` no GitHub Actions cuida de avisar Bing/Yandex.

## Regras

- NUNCA editar `tools/<slug>/` já publicado sem pedido explícito do usuário.
- Página de ferramenta = head (meta/SEO) + `<main>` (H1 + `.app` + `.ad-slot`) + scripts `config.js`, `chrome.js` e o JS da ferramenta. SEM footer, SEM texto explicativo, SEM markup de UI comum (chrome.js injeta).
- Home (gerada por build.py): lista de cards com H1 + descrição; sobre/privacidade mantêm texto.
- 1 ferramenta = 1 página = 1 keyword. Zero dependências externas (sem CDN, sem fontes remotas, sem analytics pesado).
- Sempre `scripts/build.py` antes de commit.
- Ferramentas em PT-BR por padrão; versão EN só sob pedido.
- Não inventar dados de volume de busca: o pipeline só mede autocomplete + SERP; volume fica para o Search Console decidir.
- `indexnow.key` e `<key>.txt` são públicos por design. `.env` nunca sai do git.

## AdSense (quando o ID existir)

Usuário informa `ca-pub-XXXX` e slot → preencher `adsense_client`/`adsense_slot` em `site.json`
→ `python3 scripts/build.py` (regenera `config.js` + `ads.txt`) → commit + push.
Todas as páginas (hub e ferramentas) já injetam o anúncio sozinhas via `ads.js`; sem ID configurado nada é carregado.
