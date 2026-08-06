/* result_save.js — 결과 카드만 PNG 저장(html2canvas 지연 로드, 클릭 시에만) */
(function (w, d) {
  "use strict";
  var LIB = "https://cdnjs.cloudflare.com/ajax/libs/html2canvas/1.4.1/html2canvas.min.js";
  function load() {
    return new Promise(function (res, rej) {
      if (w.html2canvas) return res(w.html2canvas);
      var s = d.createElement("script"); s.src = LIB;
      s.onload = function () { res(w.html2canvas); }; s.onerror = rej;
      d.head.appendChild(s);
    });
  }
  function ts(sep) {
    var n = new Date(), p = function (x) { return (x < 10 ? "0" : "") + x; };
    // 파일명용: YYYYMMDD_HHMM (초 제외)
    var fname = "" + n.getFullYear() + p(n.getMonth() + 1) + p(n.getDate()) + "_" + p(n.getHours()) + p(n.getMinutes());
    var human = n.getFullYear() + "-" + p(n.getMonth() + 1) + "-" + p(n.getDate()) + " " + p(n.getHours()) + ":" + p(n.getMinutes());
    return sep ? human : fname;
  }
  w.saveResultPng = function () {
    var card = d.getElementById("result-card");
    if (!card || !card.classList.contains("show")) { alert("먼저 계산을 실행해주세요."); return; }
    var cfg = w.SM_CONFIG || {};
    // 캡처용 임시 정보(계산기명 · 계산일시 · CalcMate) — 본문/광고 미포함
    var tag = d.createElement("div");
    tag.style.cssText = "margin-top:12px;font-size:12px;opacity:.85;line-height:1.6";
    tag.innerHTML = (cfg.name || "계산 결과") + "<br>" + ts(true) + " · CalcMate";
    card.appendChild(tag);
    load().then(function (h2c) {
      return h2c(card, { backgroundColor: null, scale: 2 });
    }).then(function (canvas) {
      if (tag.parentNode) card.removeChild(tag);
      var a = d.createElement("a");
      a.href = canvas.toDataURL("image/png");
      a.download = (cfg.name || "calculator").replace(/\s+/g, "") + "_" + ts(false) + ".png";
      a.click();
    }).catch(function (e) {
      if (tag.parentNode) card.removeChild(tag);
      console.error(e); alert("이미지 저장에 실패했습니다.");
    });
  };
})(window, document);
