// Injeta o anúncio do AdSense em qualquer página que tenha .ad-slot,
// se e somente se site.json tiver adsense_client configurado (scripts/build.py → config.js).
(function () {
  if (!window.SITE || !window.SITE.adClient) return;
  var s = document.createElement("script");
  s.async = true;
  s.src =
    "https://pagead2.googlesyndication.com/pagead/js/adsbygoogle.js?client=" +
    window.SITE.adClient;
  s.crossOrigin = "anonymous";
  document.head.appendChild(s);
  window.addEventListener("DOMContentLoaded", function () {
    var slot = document.querySelector(".ad-slot");
    if (!slot) return;
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
      /* sem rede / bloqueador: página continua funcionando */
    }
  });
})();
