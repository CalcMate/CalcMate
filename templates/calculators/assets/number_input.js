/* number_input.js — 금액 입력 천단위 콤마 실시간 표시(표시만, 계산은 숫자) */
(function (w, d) {
  "use strict";
  function fmt(el) {
    var raw = String(el.value).replace(/[^\d.]/g, "");
    if (raw === "") { el.value = ""; return; }
    var parts = raw.split(".");
    var intp = parts[0].replace(/^0+(?=\d)/, "");
    var f = Number(intp || "0").toLocaleString();
    el.value = (parts.length > 1) ? (f + "." + parts[1]) : f;
  }
  w.smInitNumberInputs = function () {
    d.querySelectorAll(".sm-input[data-comma]").forEach(function (el) {
      el.addEventListener("input", function () { fmt(el); });
    });
  };
  w.smGetNumber = function (el) { return parseFloat(String(el.value).replace(/,/g, "")) || 0; };
})(window, document);
