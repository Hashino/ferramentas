// Toggle de tema (claro padrão). A escolha fica no localStorage; o tema
// inicial já foi aplicado por um snippet inline no <head> para evitar flash.
(function () {
  var btn = document.getElementById("theme-toggle");
  if (!btn) return;
  function atual() {
    return document.documentElement.getAttribute("data-theme") || "light";
  }
  function pinta() {
    btn.textContent = atual() === "dark" ? "☀" : "☾"; // ☀ : ☾
  }
  btn.addEventListener("click", function () {
    var next = atual() === "dark" ? "light" : "dark";
    document.documentElement.setAttribute("data-theme", next);
    try {
      localStorage.setItem("theme", next);
    } catch (e) {
      /* modo privado: só não persiste */
    }
    pinta();
  });
  pinta();
})();
