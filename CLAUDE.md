# Ferramentas — fábrica de micro-ferramentas (SEO + GEO)

Site estático em PT-BR hospedado em https://hashino.github.io/ferramentas/
(GitHub Pages, branch `main`, raiz do repo — sem build step, sem Jekyll: `.nojekyll` presente).
Cada ferramenta é uma página `tools/<slug>/index.html` que mira UMA keyword de cauda longa.
Monetização: Google AdSense, configurado em `site.json` e injetado via `config.js` (gerado por `scripts/build.py`) + `ads.js`.

## Layout

- `backlog/keywords.csv` — fila de keywords (`status`: `candidata` | `feita` | `descartada`)
- `backlog/serp.json` — top-10 do Google por keyword (via Serper), para julgar concorrência
- `scripts/mine.py` — mineração multi-fonte, um só portão de qualidade (só entra no backlog o que o Google sugere = demanda real):
  - `mine.py harvest [N]` — cabeças × alfabeto (fonte original)
  - `mine.py matrix [N]` — varre os próximos N domínios de `seeds.json` × cabeças (fonte principal; guarda progresso em `matrix_state.json`)
  - `mine.py check [N]` — SERP das candidatas (também ingere relatedSearches/PAA quando a Serper os retorna)
  - `mine.py deep [N]` — variantes em volta de keywords provadas (`feita`/`boa`) — melhor custo-benefício, rode após cada lote publicado
  - `mine.py reddit [N]` — caça pedidos de ferramenta em threads BR do Reddit
  - `mine.py sitemaps [N]` — títulos de sites concorrentes validados no autocomplete
  - Seeds editáveis em `backlog/seeds.json` (cabeças, domínios, queries de reddit, sitemaps)
- `scripts/lint_fake_calculator.py` — bloqueia ferramenta "preço de mercado" (custo-, consulta-, cirurgia-, consertar-, alugar-, instalar-, trocar-, exame-, aula-, etc.) sem nenhum `<input type="number">`/`type="date"` real: isso é resposta informacional disfarçada de calculadora — exatamente o formato que a AI Overview do Google sintetiza direto na SERP a partir de blogs (mesma faixa de preço, sem precisar de dado pessoal do usuário). Rodar nas N ferramentas da leva ANTES de commitar (`python3 scripts/lint_fake_calculator.py <slug1> <slug2> ...`) — exit 1 se achar alguma; redesenhar com input real (idade, m², quantidade, datas — algo que só o usuário sabe) ou descartar a keyword.
- `scripts/backfill_explicacao.py` — insere `<details class="explicacao">` (texto SEO colapsado, reaproveita a própria `{{DESCRIPTION}}` de cada ferramenta + 3 links "relacionadas" por bucket de prefixo do slug), FAQPage JSON-LD e `data-footer` em qualquer `tools/*/index.html` que ainda não tenha. Idempotente. Rodar depois de criar as ferramentas da leva, ANTES do `build.py`.
- `scripts/build.py` — regenera `index.html` (hub), `sitemap.xml`, `robots.txt`, `llms.txt`, `config.js`, `ads.txt`. SEMPRE rodar antes de commitar.
- `scripts/ping_indexnow.py` — roda no CI a cada push; não rodar manualmente
- `search.js` — busca fuzzy da home (filtra/reordena os cards conforme digitação)
- `chrome.js` — UI compartilhada de TODAS as páginas, injetada em runtime: starfield (3 camadas), topnav ("Ferramentas" + toggle de tema), AdSense (se config.js tiver client) e rodapé (só nas páginas com `<body data-footer>` — TODAS as ferramentas têm isso desde o backfill). Alterar UI do site = editar `chrome.js`/`style.css` UMA vez; propaga para todas as páginas sem rebuild. Página de ferramenta NUNCA contém topnav/stars/footer no HTML (isso é injetado; `data-footer` só liga o interruptor).
- `templates/tool/index.html` — molde com tokens `{{...}}`; copiar e preencher. A página da ferramenta contém apenas: head com meta/SEO + `<main>` (H1 + `.app` + `.ad-slot`) + `config.js`, `chrome.js` e o JS da ferramenta. NÃO copiar `<details>`/FAQPage/`data-footer` manualmente — isso é sempre obra do `backfill_explicacao.py` (ver Layout acima).
- Visual: Nord + monoespaçada + cards de vidro + starfield (herdado do learnive/hashino.github.io). Tema CLARO é o default; toggle claro/escuro na barra superior (persiste em localStorage; o tema inicial vem do snippet inline no `<head>` para evitar flash).
- `.env` — `SERPER_API_KEY` (NUNCA comitar; está no .gitignore)

## Comando: "faça as próximas N aplicações"

1. **Abastecer o backlog** se houver menos de ~3×N linhas `candidata`:
   - `python3 scripts/mine.py matrix 4` (rede; ~2 min por domínio)
   - se já houver ferramentas publicadas: `python3 scripts/mine.py deep 3`
   - `python3 scripts/mine.py check <N*3>` (SERP via Serper; classifica saturação a partir de `serp.json`)
   - opcional, para diversificar: `mine.py reddit 3` e `mine.py sitemaps 10`
2. **Selecionar N candidatas** lendo `backlog/serp.json`. Critérios, em ordem:
   (a) SERP sem ferramenta dedicada no top-10 (fóruns, Reddit, resultados genéricos = demanda sem oferta);
   (b) tarefa resolvível em 1 página estática de vanilla JS (calcular/gerar/convertar);
   (c) sem overlap com ferramenta já publicada em `tools/`;
   (d) **não é pergunta informacional disfarçada** — se a keyword é do tipo "quanto custa/vale/sai X"
   e a resposta seria só uma faixa de preço médio (sem depender de nenhum dado que só o usuário tem),
   a AI Overview do Google já responde isso direto na SERP a partir de blogs, e a ferramenta nasce
   morta em clique. Só aceitar keyword desse tipo se der pra desenhar um cálculo com input numérico/data
   REAL e específico do usuário (m² da obra, idade, quantidade, datas, medidas) — não um dropdown de
   2-3 categorias multiplicando uma constante. Na dúvida, rode `scripts/lint_fake_calculator.py` depois
   de criar (passo 4) — ele pega esse padrão automaticamente.
   Publicar só o que passar. Se menos que N passarem, publicar as que passarem e reportar o motivo —
   NUNCA forçar página em SERP saturada. Keywords checadas e cortadas: marcar `descartada` no CSV
   (poupa re-checagem de Serper nas próximas levas).
3. **Criar cada ferramenta**: copiar `templates/tool/index.html` para `tools/<slug>/index.html` e preencher:
   - slug: kebab-case curto, derivado da keyword
   - `<title>`: keyword primeiro, ≤60 chars · meta description ≤155 chars
   - H1 = título humano; `{{APP_HTML}}` + `{{APP_JS}}` = a ferramenta (funciona offline, sem CDN, sem biblioteca)
   - A página da ferramenta é visualmente SÓ a ferramenta: barra superior + H1 + app.
   NÃO escreva `<details>`, FAQ visível, footer ou texto explicativo no arquivo — isso é
   sempre o passo 4 abaixo, nunca manual (mantém as 295+ ferramentas consistentes).
   - marca a keyword como `feita` em `backlog/keywords.csv`
4. **Lint + backfill de SEO/GEO + build + deploy**:
   `python3 scripts/lint_fake_calculator.py <slugs da leva>` (se falhar, redesenhar com input real ou descartar a keyword — voltar ao passo 3)
   → `python3 scripts/backfill_explicacao.py` (insere explicação colapsada + FAQPage + footer nas ferramentas novas)
   → `python3 scripts/build.py` (regenera hub/sitemap/robots/llms.txt/ads.txt)
   → commit (`tool: <slug>`) → `git push`.
5. **Reportar**: URLs criadas; o workflow `indexnow` no GitHub Actions cuida de avisar Bing/Yandex.

## Regras

- NUNCA editar `tools/<slug>/` já publicado sem pedido explícito do usuário — EXCETO rodar `backfill_explicacao.py`, que é seguro (idempotente, só adiciona o que falta) e faz parte da pipeline padrão.
- Página de ferramenta = head (meta/SEO) + `<main>` (H1 + `.app` + `.ad-slot`) + scripts `config.js`, `chrome.js` e o JS da ferramenta, criada assim pelo template. `backfill_explicacao.py` acrescenta depois: `<details class="explicacao">` (texto SEO + 3 links relacionados, colapsado por padrão — invisível até o clique), FAQPage JSON-LD e `data-footer` (liga o footer com Sobre/Privacidade/GitHub). Nenhum desses três é escrito à mão nem varia o design visível da ferramenta.
- Home (gerada por build.py): lista de cards com H1 + descrição; sobre/privacidade mantêm texto.
- 1 ferramenta = 1 página = 1 keyword. Zero dependências externas (sem CDN, sem fontes remotas, sem analytics pesado).
- Sempre `scripts/build.py` antes de commit.
- Ferramentas em PT-BR por padrão; versão EN só sob pedido.
- Não inventar dados de volume de busca: o pipeline só mede autocomplete + SERP; volume fica para o Search Console decidir.
- Regra anti-AI-Overview: nenhuma ferramenta nova pode ser um dropdown de categorias multiplicando uma constante para responder "quanto custa X" — isso é a mesma resposta que o Google já sintetiza na própria busca. Toda ferramenta precisa de pelo menos 1 dado numérico/data real e específico do usuário que mude o resultado de forma não-trivial. Ver `scripts/lint_fake_calculator.py`.
- `indexnow.key` e `<key>.txt` são públicos por design. `.env` nunca sai do git.

## AdSense (quando o ID existir)

Usuário informa `ca-pub-XXXX` e slot → preencher `adsense_client`/`adsense_slot` em `site.json`
→ `python3 scripts/build.py` (regenera `config.js` + `ads.txt`) → commit + push.
Todas as páginas (hub e ferramentas) já injetam o anúncio sozinhas via `ads.js`; sem ID configurado nada é carregado.
