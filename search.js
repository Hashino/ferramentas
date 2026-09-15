// Busca fuzzy da home: filtra e reordena os cards conforme o usuário digita.
// Subsequência sobre data-nome (título + slug + descrição embutida), com
// bônus para letras consecutivas e início de palavra.
(function () {
  var input = document.getElementById("tool-search");
  var lista = document.getElementById("tool-list");
  if (!input || !lista) return;
  var cards = Array.prototype.slice.call(lista.querySelectorAll(".card"));

  function fuzzy(q, text) {
    if (!q) return 0;
    q = q.toLowerCase();
    text = text.toLowerCase();
    var score = 0;
    var last = -2;
    for (var i = 0; i < q.length; i++) {
      var ch = q[i];
      if (ch === " ") continue;
      var idx = text.indexOf(ch, last + 1);
      if (idx === -1) return -1;
      score += idx === last + 1 ? 3 : 1;
      if (idx === 0) score += 2;
      last = idx;
    }
    return score;
  }

  function aplicar() {
    var q = input.value.trim();
    var visiveis = [];
    cards.forEach(function (c) {
      var s = fuzzy(q, c.getAttribute("data-nome") || c.textContent);
      c.style.display = s < 0 ? "none" : "";
      if (s >= 0) visiveis.push([s, c]);
    });
    visiveis.sort(function (a, b) { return b[0] - a[0]; });
    visiveis.forEach(function (p) { lista.appendChild(p[1]); });
  }

  input.addEventListener("input", aplicar);

  // suporta ?q=busca na URL (usado pelo SearchAction do schema.org WebSite,
  // habilita a caixa de busca do Google nos resultados de pesquisa)
  var params = new URLSearchParams(location.search);
  var q0 = params.get("q");
  if (q0) {
    input.value = q0;
    aplicar();
  }
})();
