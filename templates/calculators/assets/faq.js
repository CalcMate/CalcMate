/* faq.js — FAQ 아코디언 토글 + ARIA (Phase C) */
(function (w, d) {
  "use strict";

  w.toggleFaq = function (btn) {
    var item = btn && btn.parentElement;
    if (!item) return;
    var isOpen = item.classList.toggle("open");
    btn.setAttribute("aria-expanded", isOpen ? "true" : "false");
    var ans = item.querySelector(".sm-faq-a");
    if (ans) ans.hidden = !isOpen;
  };

  function initFaqAria() {
    var idx = 0;
    d.querySelectorAll(".sm-faq-item").forEach(function (item) {
      var btn = item.querySelector(".sm-faq-q");
      var ans = item.querySelector(".sm-faq-a");
      if (!btn || !ans) return;
      var id = "faq-a-" + (idx++);
      ans.id = id;
      ans.hidden = true;
      btn.setAttribute("aria-expanded", "false");
      btn.setAttribute("aria-controls", id);
      btn.setAttribute("type", "button");
    });
  }

  if (d.readyState === "loading") d.addEventListener("DOMContentLoaded", initFaqAria);
  else initFaqAria();
})(window, document);
