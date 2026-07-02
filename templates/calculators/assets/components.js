/* components.js — SalaryMate 공통 컴포넌트 (모든 계산기 공통, 변경 최소)
   설계: calculate()는 입력 수집→computeResult()(계산기별) 호출→renderResult()(공통 UI).
   계산기가 늘어나도 calculate()/renderResult()는 수정하지 않는다. */
(function (w, d) {
  "use strict";
  var CFG = w.SM_CONFIG || {};

  function num(v) { return (typeof v === "number") ? v : (parseFloat(String(v).replace(/,/g, "")) || 0); }
  function comma(n) { return (Math.round(n)).toLocaleString(); }

  // 입력 수집: number → 숫자(콤마제거), date → 문자열
  function collectInputs() {
    var inputs = {};
    (CFG.inputs || []).forEach(function (f) {
      var el = d.getElementById("in_" + f.name);
      if (!el) { inputs[f.name] = (f.type === "date") ? "" : 0; return; }
      inputs[f.name] = (f.type === "date") ? el.value : num(el.value);
    });
    return inputs;
  }

  // 카운트업 애니메이션 (디자인 유지)
  function countUp(el, target) {
    if (!el) return;
    var dur = 600, start = performance.now();
    (function step(now) {
      var p = Math.min((now - start) / dur, 1);
      var ease = 1 - Math.pow(1 - p, 3);
      el.textContent = comma(ease * target);
      if (p < 1) requestAnimationFrame(step);
    })(performance.now());
  }

  // 결과 UI 렌더 (계산 로직 없음 — 표시만)
  function renderResult(inputs, outputs) {
    outputs = outputs || {};
    var primary = CFG.primaryOutput;
    var pv = num(outputs[primary]);

    var card = d.getElementById("result-card");
    if (card) { card.classList.remove("show"); void card.offsetWidth; card.classList.add("show"); }
    countUp(d.getElementById("out_" + primary), pv);

    var sub = d.getElementById("result-formula");
    if (sub) sub.textContent = outputs._formula || "";

    var actions = d.getElementById("result-actions");
    if (actions) actions.classList.add("show");

    // 계산 상세: 입력값 + 출력값 + (계산기별 _detail) 자동 나열
    var rows = [];
    (CFG.inputs || []).forEach(function (f) {
      var v = inputs[f.name];
      var disp = (f.type === "date") ? (v || "-") : (comma(num(v)) + (f.unit || ""));
      rows.push([f.label || f.name, disp]);
    });
    (outputs._detail || []).forEach(function (r) { rows.push([r.label, r.value]); });
    (CFG.outputs || []).forEach(function (o) {
      rows.push([o.label || o.key, comma(num(outputs[o.key])) + (o.unit || "")]);
    });
    if (CFG.show_detail !== false) {
      var host = d.getElementById("detail-rows");
      if (host) {
        host.innerHTML = rows.map(function (r) {
          return '<div class="sm-detail-row"><span class="sm-detail-label">' + esc(r[0]) +
            '</span><span class="sm-detail-value">' + esc(r[1]) + "</span></div>";
        }).join("");
        var dc = d.getElementById("detail-card"); if (dc) dc.style.display = "block";
      }
    }
  }

  function esc(s) { return String(s == null ? "" : s).replace(/[&<>"]/g, function (c) {
    return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]; }); }

  // 공통 계산 진입점 — 계산기별 computeResult(inputs)만 교체하면 재사용
  function calculate() {
    var inputs = collectInputs();
    var outputs;
    try {
      outputs = (typeof w.computeResult === "function") ? w.computeResult(inputs) : null;
    } catch (e) { console.error(e); outputs = null; }
    if (!outputs || !isFinite(num(outputs[CFG.primaryOutput]))) {
      alert("입력값을 확인해주세요.");
      return;
    }
    renderResult(inputs, outputs);
  }

  // 초기화: show_* 플래그 반영 + 기능 모듈 init
  function init() {
    // 광고/CPA: 설정 시에만 노출(기본 숨김) — SM_CONFIG(대시보드/ SITE_MODE) 값으로만 제어
    if (CFG.show_adsense) toggleAll(".sm-adsense", true);
    if (CFG.show_cpa) toggleAll(".sm-cpa", true);
    // 결과 액션 버튼: 플래그로 개별 노출
    hideActionIf("result_save", CFG.show_result_save === false);
    hideActionIf("share", CFG.show_share === false);
    hideActionIf("pwa", CFG.show_pwa === false);
    // 섹션 노출 제어(FAQ/안내문/관련계산기) — 기본 노출, 설정 false면 숨김
    if (CFG.show_faq === false) hideEl("#faq-card");
    if (CFG.show_notice === false) hideEl(".sm-notice");
    if (CFG.show_related === false) hideEl("#related-card");
    if (w.smInitNumberInputs) w.smInitNumberInputs();
    if (w.smInitPwa) w.smInitPwa();
  }
  function hideEl(sel) { var el = d.querySelector(sel); if (el) el.style.display = "none"; }
  function toggleAll(sel, on) { d.querySelectorAll(sel).forEach(function (el) { el.style.display = on ? "block" : "none"; }); }
  function hideActionIf(action, hide) {
    if (!hide) return;
    var b = d.querySelector('.sm-action-btn[data-action="' + action + '"]');
    if (b) b.style.display = "none";
  }

  w.calculate = calculate;
  w.smRenderResult = renderResult;
  if (d.readyState === "loading") d.addEventListener("DOMContentLoaded", init);
  else init();
})(window, document);
