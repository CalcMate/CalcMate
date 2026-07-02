/* faq.js — FAQ 아코디언 토글(디자인/동작 유지) */
(function (w, d) {
  "use strict";
  w.toggleFaq = function (btn) {
    if (btn && btn.parentElement) btn.parentElement.classList.toggle("open");
  };
})(window, document);
