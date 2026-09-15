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
- `scripts/proxima.py` — **o comando do passo 1**: decide qual ferramenta construir agora. Minera se o backlog estiver seco, busca SERP, roda a triagem e imprime `KEYWORD:`/`SLUG:`/`MOTIVO:`. Existe para que ninguém escolha keyword "no olho" — foi assim que 264 páginas viraram lixo.
- `scripts/triagem.py` — o julgamento que regex não faz, via IA grátis: lê a SERP e responde (1) o buscador quer mesmo uma ferramenta, ou quer salário de mercado/cotação/vaga? (2) cada resultado do top-3 é ferramenta interativa ou só artigo explicando? (3) um AI Overview responderia a busca inteira sem dado do usuário? Só aprova quando as três dão certo. Cache em `backlog/triagem.json`, versionado por `VERSAO` (suba ao mudar critério e os vereditos velhos são refeitos).
- `scripts/lint_serp.py` — detector de ferramenta na SERP por título/URL, sem API e sem IA. Generoso de propósito (confunde artigo com ferramenta); serve de sinal cru para a `triagem.py` e de auditoria offline (`--tools` audita o que já está publicado).
- `scripts/ai.py` — cliente de LLM grátis (endpoint OpenAI-compatible). A chave é lida em runtime do `.env` do learnive e **nunca** entra neste repo. Trata as pegadinhas do free tier: 429 é por pool do modelo (troca de modelo em vez de esperar), Cloudflare da Groq exige User-Agent de browser, e `response_format: json_object` exige a palavra "json" na mensagem.
- `scripts/lint_fake_calculator.py` — rede de segurança automática, só por prefixo de slug (bucket de categorias JÁ CONHECIDAS como "preço de serviço/produto": custo-, consulta-, cirurgia-, consertar-, alugar-, instalar-, trocar-, exame-, aula-, etc.). NÃO tenta mais detectar a frase "preço/valor de X" no texto via regex — foi abandonado porque a mesma frase aparece tanto numa pergunta informacional real quanto describing um input legítimo de calculadora ("valor da hora", "preço do kg do gás"), e regex não distingue intenção. A distinção real é feita pelo AGENTE no passo 2(d) abaixo, ANTES de construir a ferramenta — este script só pega reincidências óbvias de categoria. Rodar nas N ferramentas da leva antes de commitar (`python3 scripts/lint_fake_calculator.py <slug1> <slug2> ...`) — exit 1 se achar alguma.
- `scripts/backfill_explicacao.py` — insere `<details class="explicacao">` (texto SEO colapsado, reaproveita a própria `{{DESCRIPTION}}` de cada ferramenta + 3 links "relacionadas" por bucket de prefixo do slug), FAQPage JSON-LD e `data-footer` em qualquer `tools/*/index.html` que ainda não tenha. Idempotente. Rodar depois de criar as ferramentas da leva, ANTES do `build.py`.
- `scripts/build.py` — regenera `index.html` (hub), `sitemap.xml`, `robots.txt`, `llms.txt`, `config.js`, `ads.txt`. SEMPRE rodar antes de commitar.
- `scripts/ping_indexnow.py` — roda no CI a cada push; não rodar manualmente
- `search.js` — busca fuzzy da home (filtra/reordena os cards conforme digitação)
- `chrome.js` — UI compartilhada de TODAS as páginas, injetada em runtime: starfield (3 camadas), topnav ("Ferramentas" + toggle de tema), AdSense (se config.js tiver client) e rodapé (só nas páginas com `<body data-footer>` — TODAS as ferramentas têm isso desde o backfill). Alterar UI do site = editar `chrome.js`/`style.css` UMA vez; propaga para todas as páginas sem rebuild. Página de ferramenta NUNCA contém topnav/stars/footer no HTML (isso é injetado; `data-footer` só liga o interruptor).
- `templates/tool/index.html` — molde com tokens `{{...}}`; copiar e preencher. A página da ferramenta contém apenas: head com meta/SEO + `<main>` (H1 + `.app` + `.ad-slot`) + `config.js`, `chrome.js` e o JS da ferramenta. NÃO copiar `<details>`/FAQPage/`data-footer` manualmente — isso é sempre obra do `backfill_explicacao.py` (ver Layout acima).
- Visual: Nord + monoespaçada + cards de vidro + starfield (herdado do learnive/hashino.github.io). Tema CLARO é o default; toggle claro/escuro na barra superior (persiste em localStorage; o tema inicial vem do snippet inline no `<head>` para evitar flash).
- `.env` — `SERPER_API_KEY` (NUNCA comitar; está no .gitignore)

## Comando: "construa as próximas N ferramentas"

Repita o ciclo abaixo N vezes. **Uma ferramenta por ciclo, um commit por ciclo.**
Não escolha keyword por conta própria e não pule o passo 1 — escolher "no olho"
é o que fez o site acumular 264 páginas inúteis, todas deletadas depois.

### Ciclo

**1. Pedir a keyword.** Rode:

```
python3 scripts/proxima.py
```

Ele minera, busca a SERP e julga sozinho (leva alguns minutos na primeira vez).
Imprime exatamente isto:

```
KEYWORD: <a busca do usuário no Google>
SLUG: <nome-da-pasta>
MOTIVO: <por que vale construir>
```

Se imprimir `NENHUMA: ...`, siga a instrução da própria mensagem e pare o ciclo.
Use o SLUG que ele deu, sem alterar.

**2. Criar `tools/<SLUG>/index.html`.** Leia `templates/tool/index.html` e
substitua os tokens `{{...}}`. Não invente estrutura: o template já tem tudo.

| token | o que colocar |
|---|---|
| `{{SLUG}}` | o SLUG do passo 1 |
| `{{TOOL_NAME}}` | nome curto da ferramenta |
| `{{TITLE}}` | título SEO, a keyword no começo, até 60 caracteres |
| `{{DESCRIPTION}}` | meta description, até 155 caracteres, sem aspas duplas |
| `{{H1}}` | título visível, em linguagem humana |
| `{{APP_HTML}}` | os campos do formulário e a área de resultado |
| `{{APP_JS}}` | o JavaScript que calcula |

Regras do código (todas obrigatórias):

- JavaScript puro. Sem biblioteca, sem CDN, sem `fetch`. Funciona offline.
- **Não** escreva `<html>`, `<head>`, `<body>`, `<style>`, barra de navegação,
  rodapé, `<details>` nem texto explicativo. O template já cuida do head, e
  `chrome.js` injeta o resto em runtime. Escrever isso à mão quebra a
  consistência das páginas.
- Cada entrada é `<label for="x">Texto</label>` + `<input id="x" type="number">`.
  O resultado vai em `<div id="resultado" class="resultado"></div>`.
- Pelo menos um input numérico cujo valor **só o usuário sabe**. Se a ferramenta
  funciona sem o usuário digitar nada, ela é uma tabela de médias disfarçada —
  refaça.
- Recalcule a cada tecla (`addEventListener("input", ...)`), sem exigir botão.
  Campo vazio ou inválido mostra vazio, nunca `NaN`.
- PT-BR, números com `toLocaleString("pt-BR")`.

**3. Marcar a keyword** como `feita` em `backlog/keywords.csv` (troque
`candidata` por `feita` na linha dessa keyword).

**4. Publicar.** Nesta ordem, sem pular nenhum:

```
python3 scripts/lint_fake_calculator.py <SLUG>
python3 scripts/backfill_explicacao.py
python3 scripts/build.py
git add -A && git commit -m "tool: <SLUG>" && git push
```

Se o lint falhar, conserte a ferramenta e rode de novo — não commite.
`backfill_explicacao.py` é quem insere explicação/FAQ/rodapé; por isso o passo 2
proíbe escrever isso à mão.

**5. Conferir** que `tools/<SLUG>/index.html` não tem mais nenhum `{{` sobrando,
e voltar ao passo 1 para a próxima ferramenta.

## Regras

- NUNCA editar `tools/<slug>/` já publicado sem pedido explícito do usuário — EXCETO rodar `backfill_explicacao.py`, que é seguro (idempotente, só adiciona o que falta) e faz parte da pipeline padrão.
- Página de ferramenta = head (meta/SEO) + `<main>` (H1 + `.app` + `.ad-slot`) + scripts `config.js`, `chrome.js` e o JS da ferramenta, criada assim pelo template. `backfill_explicacao.py` acrescenta depois: `<details class="explicacao">` (texto SEO + 3 links relacionados, colapsado por padrão — invisível até o clique), FAQPage JSON-LD e `data-footer` (liga o footer com Sobre/Privacidade/GitHub). Nenhum desses três é escrito à mão nem varia o design visível da ferramenta.
- Home (gerada por build.py): lista de cards com H1 + descrição; sobre/privacidade mantêm texto.
- 1 ferramenta = 1 página = 1 keyword. Zero dependências externas (sem CDN, sem fontes remotas, sem analytics pesado).
- Sempre `scripts/build.py` antes de commit.
- Ferramentas em PT-BR por padrão; versão EN só sob pedido.
- Não inventar dados de volume de busca: o pipeline só mede autocomplete + SERP; volume fica para o Search Console decidir.
- Regra anti-AI-Overview: nenhuma ferramenta nova pode responder uma pergunta do tipo "quanto custa/vale/sai/é/cobra X" — isso é a mesma resposta que o Google já sintetiza direto na busca, e input numérico real NÃO isenta (a AI Overview responde pela intenção, não pela qualidade da calculadora). Só entram keywords cujo resultado só existe depois de um cálculo com dado específico do usuário. Esse julgamento é feito pelo AGENTE na seleção (passo 2d), não por regex — `scripts/lint_fake_calculator.py` é só uma rede de segurança por categoria de slug conhecida, não a fonte da verdade.
- `indexnow.key` e `<key>.txt` são públicos por design. `.env` nunca sai do git.

## AdSense (quando o ID existir)

Usuário informa `ca-pub-XXXX` e slot → preencher `adsense_client`/`adsense_slot` em `site.json`
→ `python3 scripts/build.py` (regenera `config.js` + `ads.txt`) → commit + push.
Todas as páginas (hub e ferramentas) já injetam o anúncio sozinhas via `ads.js`; sem ID configurado nada é carregado.
