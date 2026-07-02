/* pwa.js — 홈 화면 추가(beforeinstallprompt). 설치 가능 환경에서만 버튼 노출 */
(function (w, d) {
  "use strict";
  var deferred = null;
  w.addEventListener("beforeinstallprompt", function (e) {
    e.preventDefault(); deferred = e;
    var b = d.getElementById("pwa-btn"); if (b) b.style.display = "flex";
  });
  w.smInitPwa = function () {
    var b = d.getElementById("pwa-btn");
    if (b && !deferred) b.style.display = "none";  // 설치 불가 환경: 프롬프트 전까지 숨김
  };
  w.pwaInstall = function () {
    if (deferred) { deferred.prompt(); deferred.userChoice.then(function () { deferred = null; }); }
    else { alert("브라우저 주소창의 설치 아이콘을 눌러 홈 화면에 추가할 수 있습니다."); }
  };
})(window, document);
