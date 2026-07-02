/* related.js — 관련 계산기(서버 렌더). 향후 slug 기반 동적 생성 훅(UI 동일) */
(function (w, d) {
  "use strict";
  // app_generator가 관련 계산기 앵커를 서버 렌더링함. 필요 시 동적 재구성 지원.
  w.smBuildRelated = function (items) {
    var host = d.querySelector(".sm-related-grid");
    if (!host || !items) return;
    host.innerHTML = items.map(function (it) {
      return '<a class="sm-related-item" href="' + (it.href || "#") + '">' +
        '<span class="sm-related-emoji">' + (it.emoji || "🧮") + '</span>' +
        '<span class="sm-related-name">' + (it.name || "") + "</span></a>";
    }).join("");
  };
})(window, document);
