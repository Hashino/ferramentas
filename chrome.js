// Chrome compartilhado do site — ÚNICO ponto de UI comum a todas as páginas.
// Injeta em runtime: starfield (3 camadas), barra superior com toggle de tema,
// o anúncio (se config.js tiver adsense_client) e, nas páginas que declaram
// <body data-footer>, o rodapé.
//
// Página de ferramenta NUNCA escreve topnav/stars/footer no HTML: basta carregar
// config.js + chrome.js. Alterar a UI do site = editar este arquivo (ou style.css)
// e as mudanças propagam para todas as páginas sem rebuild nem redeploy.
//
// O tema inicial é aplicado por um snippet inline no <head> de cada página
// (antes do CSS) para não haver flash.

(function () {
  var EM_FERRAMENTA = location.pathname.indexOf("/tools/") !== -1;
  var P = EM_FERRAMENTA ? "../../" : "./"; // prefixo relativo até a raiz do site

  // ── starfield em 3 camadas (herdado do learnive) ──────────────────────────
  ["stars", "stars2", "stars3"].forEach(function (id) {
    var d = document.createElement("div");
    d.id = id;
    document.body.insertBefore(d, document.body.firstChild);
  });

  // ── barra superior: "Ferramentas" à esquerda, toggle de tema à direita ────
  var nav = document.createElement("nav");
  nav.className = "top-nav";
  nav.innerHTML =
    '<div class="nav-container">' +
    '<a class="nav-title" href="' + P + '">Ferramentas</a>' +
    '<button id="theme-toggle" class="theme-toggle" aria-label="Alternar tema"></button>' +
    "</div>";
  document.body.insertBefore(nav, document.body.firstChild);

  // ── rodapé: somente em páginas que pedirem (<body data-footer>) ───────────
  if (document.body.hasAttribute("data-footer")) {
    var f = document.createElement("footer");
    f.innerHTML =
      '<a href="' + P + 'sobre.html">Sobre</a> · ' +
      '<a href="' + P + 'privacidade.html">Privacidade</a> · ' +
      '<a href="https://github.com/Hashino/ferramentas">GitHub</a>';
    document.body.appendChild(f);
  }

  // ── toggle de tema (claro é o default; escolha persistida) ────────────────
  var btn = document.getElementById("theme-toggle");
  function temaAtual() {
    return document.documentElement.getAttribute("data-theme") || "light";
  }
  function pintaToggle() {
    btn.textContent = temaAtual() === "dark" ? "☀" : "☾";
  }
  btn.addEventListener("click", function () {
    var next = temaAtual() === "dark" ? "light" : "dark";
    document.documentElement.setAttribute("data-theme", next);
    try {
      localStorage.setItem("theme", next);
    } catch (e) {
      /* modo privado: só não persiste */
    }
    pintaToggle();
  });
  pintaToggle();

  // ── AdSense: o <script> do client já está estático no <head> de cada página
  // (exigência da verificação do AdSense). Aqui só preenchemos o bloco de anúncio
  // (.ad-slot) quando houver slot ID em site.json — sem slot, quem coloca anúncio
  // é o Auto Ads do painel do AdSense. ─────────────────────────────────────────
  if (window.SITE && window.SITE.adClient && window.SITE.adSlot) {
    var slot = document.querySelector(".ad-slot");
    if (slot) {
      var ins = document.createElement("ins");
      ins.className = "adsbygoogle";
      ins.style.display = "block";
      ins.setAttribute("data-ad-client", window.SITE.adClient);
      ins.setAttribute("data-ad-slot", window.SITE.adSlot);
      ins.setAttribute("data-full-width-responsive", "true");
      slot.appendChild(ins);
      try {
        (window.adsbygoogle = window.adsbygoogle || []).push({});
      } catch (e) {
        /* sem rede / bloqueador: a página continua funcionando */
      }
    }
  }
})();
