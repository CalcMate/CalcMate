/* analytics.js — smTrack() GA4 이벤트 훅 · A/B 테스트 (Phase E-1, E-2)
   _JS_ORDER의 첫 번째 — 다른 모듈에서 smTrack()을 호출하기 전에 로드됨 */
(function (w, d) {
  "use strict";
  var CFG = w.SM_CONFIG || {};

  // ── E-1: GA4 gtag 전송 ───────────────────────────────────────────
  function _ga4(name, params) {
    if (typeof w.gtag === "function") {
      w.gtag("event", name, params || {});
    }
  }

  // smTrack: 모든 이벤트의 단일 진입점
  w.smTrack = function (event_name, params) {
    var p = Object.assign({}, {
      calc_name: CFG.name || "",
      calc_slug: CFG.slug || ""
    }, params || {});
    _ga4(event_name, p);
    if (w.SM_TRACK_DEBUG || (w.location && w.location.hostname === "localhost")) {
      console.log("[smTrack]", event_name, p);
    }
  };

  // ── E-2: A/B 테스트 — CTA 변형 (A=대조군 / B=실험군) ────────────
  var SM_AB_VARIANT = "A";
  try {
    var _sk = "sm_cta_v_" + (CFG.slug || "all");
    var _stored = sessionStorage.getItem(_sk);
    if (!_stored) {
      _stored = Math.random() < 0.5 ? "A" : "B";
      sessionStorage.setItem(_sk, _stored);
    }
    SM_AB_VARIANT = _stored;
  } catch (e) { /* sessionStorage 불가 시 기본값 "A" */ }
  w.SM_AB_VARIANT = SM_AB_VARIANT;

  // ── E-1: calculator_view + 위임 이벤트 리스너 ────────────────────
  function _initAnalytics() {
    w.smTrack("calculator_view", { page_path: w.location.pathname });

    // E-2: cta_variant data-ph 스팬 업데이트 + AB impression
    d.querySelectorAll('[data-ph="cta_variant"]').forEach(function (el) {
      el.textContent = SM_AB_VARIANT;
    });
    w.smTrack("ab_impression", { variant: SM_AB_VARIANT });

    // cta_click — 결과 카드 내 CTA 링크
    d.addEventListener("click", function (e) {
      var t = e.target;
      var el = t.closest ? t.closest(".sm-result-cta-link") : null;
      if (el) {
        w.smTrack("cta_click", {
          href: el.getAttribute("href") || "",
          label: (el.textContent || "").trim(),
          variant: SM_AB_VARIANT
        });
      }
    }, true);

    // related_calculator_click — 관련 계산기 링크
    d.addEventListener("click", function (e) {
      var t = e.target;
      var el = t.closest ? t.closest(".sm-related-item") : null;
      if (el) {
        var nm = el.querySelector(".sm-related-name");
        w.smTrack("related_calculator_click", {
          href: el.getAttribute("href") || "",
          label: nm ? (nm.textContent || "").trim() : ""
        });
      }
    }, true);

    // share_click — 카카오 공유 버튼
    d.addEventListener("click", function (e) {
      var t = e.target;
      var el = t.closest ? t.closest('.sm-action-btn[data-action="share"]') : null;
      if (el) w.smTrack("share_click", { method: "kakao" });
    }, true);

    // copy_result — 결과 저장 버튼
    d.addEventListener("click", function (e) {
      var t = e.target;
      var el = t.closest ? t.closest('.sm-action-btn[data-action="result_save"]') : null;
      if (el) w.smTrack("copy_result", {});
    }, true);
  }

  if (d.readyState === "loading") {
    d.addEventListener("DOMContentLoaded", _initAnalytics);
  } else {
    _initAnalytics();
  }
})(window, document);
