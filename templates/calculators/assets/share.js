/* share.js — 카카오 공유(SDK 연동 구조 + 미설정 시 안전 폴백, 오류 없음) */
(function (w, d) {
  "use strict";
  w.kakaoShare = function () {
    var cfg = w.SM_CONFIG || {};
    var valEl = d.getElementById("out_" + cfg.primaryOutput);
    var val = valEl ? valEl.textContent : "";
    var text = (cfg.name || "계산 결과") + " 결과: " + val + (cfg.resultUnit || "");
    try {
      if (cfg.kakao_js_key && w.Kakao && w.Kakao.Share &&
          w.Kakao.isInitialized && w.Kakao.isInitialized()) {
        w.Kakao.Share.sendDefault({
          objectType: "text", text: text,
          link: { mobileWebUrl: location.href, webUrl: location.href }
        });
        return;
      }
    } catch (e) { console.error(e); }
    // SDK 미설정/미초기화 → 안전 폴백
    try {
      if (navigator.share) { navigator.share({ title: cfg.name || "계산 결과", text: text, url: location.href }); return; }
      if (navigator.clipboard) {
        navigator.clipboard.writeText(text + "\n" + location.href)
          .then(function () { alert("결과가 클립보드에 복사됐습니다."); });
        return;
      }
    } catch (e) { console.error(e); }
    alert(text);
  };
})(window, document);
