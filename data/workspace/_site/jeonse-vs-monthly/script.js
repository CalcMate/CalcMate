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
    // E-1: faq_open 이벤트 (열릴 때만)
    if (isOpen && w.smTrack) {
      w.smTrack("faq_open", { q: (btn.textContent || "").trim().replace(/[+−]/g, "").trim() });
    }
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

/* components.js — SalaryMate 공통 컴포넌트 (Phase C: notices / step accordion)
   계산 로직 없음. calculate()→computeResult()(계산기별)→renderResult()(공통 UI).
   계산기가 늘어나도 calculate()/renderResult()는 수정하지 않는다. */
(function (w, d) {
  "use strict";
  var CFG = w.SM_CONFIG || {};

  function num(v) { return (typeof v === "number") ? v : (parseFloat(String(v).replace(/,/g, "")) || 0); }
  function comma(n) { return (Math.round(n)).toLocaleString(); }

  function esc(s) {
    return String(s == null ? "" : s).replace(/[&<>"]/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c];
    });
  }

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

  // Phase C: notices 렌더 (계산 결과의 안내 메시지 목록)
  function renderNotices(notices) {
    var host = d.getElementById("notices-container");
    if (!host) return;
    if (!notices || !notices.length) {
      host.classList.remove("show");
      return;
    }
    host.innerHTML = notices.map(function (n) {
      return '<div class="sm-notice-item">'
        + '<span class="sm-notice-item-icon" aria-hidden="true">ℹ️</span>'
        + '<span>' + esc(n) + '</span>'
        + '</div>';
    }).join("");
    host.classList.add("show");
  }

  // Phase C: 계산 과정 step accordion 렌더
  // 항목이 2개 이상일 때 아코디언, 그 미만은 기존 detail-row 형태
  function renderSteps(detail, formula) {
    var host = d.getElementById("steps-list");
    var card = d.getElementById("steps-card");
    if (!host || !card) return;
    if (!detail || !detail.length) { card.style.display = "none"; return; }

    if (detail.length >= 3) {
      // 아코디언 형태 (연말정산 11단계 등)
      var idx = 0;
      host.innerHTML = detail.map(function (r) {
        var bid = "step-btn-" + (idx);
        var aid = "step-ans-" + (idx);
        idx++;
        var labelText = esc(r.label || "");
        var valueText = esc(r.value || "");
        var formulaHtml = formula
          ? '<div class="sm-steps-formula">' + esc(formula) + '</div>'
          : "";
        return '<div class="sm-steps-item">'
          + '<button class="sm-steps-q" id="' + bid + '" '
          + 'aria-expanded="false" aria-controls="' + aid + '" type="button" '
          + 'onclick="smToggleStep(this)">'
          + '<span class="sm-steps-label">' + labelText + '</span>'
          + '<span class="sm-steps-value">' + valueText + '</span>'
          + '<span class="sm-steps-icon" aria-hidden="true">+</span>'
          + '</button>'
          + '<div class="sm-steps-a" id="' + aid + '" hidden>'
          + '<strong>' + labelText + '</strong>: ' + valueText
          + formulaHtml
          + '</div>'
          + '</div>';
      }).join("");
      card.style.display = "block";
    } else {
      // 단순 목록 형태 (항목 수 적은 계산기)
      host.innerHTML = detail.map(function (r) {
        return '<div class="sm-detail-row">'
          + '<span class="sm-detail-label">' + esc(r.label) + '</span>'
          + '<span class="sm-detail-value">' + esc(r.value) + '</span>'
          + '</div>';
      }).join("");
      card.style.display = "block";
    }
  }

  // Phase C: step accordion 토글 (공통)
  w.smToggleStep = function (btn) {
    var item = btn && btn.parentElement;
    if (!item) return;
    var isOpen = item.classList.toggle("open");
    btn.setAttribute("aria-expanded", isOpen ? "true" : "false");
    var ans = item.querySelector(".sm-steps-a");
    if (ans) ans.hidden = !isOpen;
  };

  // 결과 UI 렌더 (계산 로직 없음 — 표시만)
  function renderResult(inputs, outputs) {
    outputs = outputs || {};
    var primary = CFG.primaryOutput;
    var pv = num(outputs[primary]);

    var card = d.getElementById("result-card");
    if (card) { card.classList.remove("show"); void card.offsetWidth; card.classList.add("show"); }
    // 결과 카드 내 모든 출력 요소(primary + 추가 출력)를 countUp으로 업데이트
    (CFG.outputs || []).forEach(function(o) {
      var el = d.getElementById("out_" + o.key);
      if (el) countUp(el, num(outputs[o.key]));
    });

    var sub = d.getElementById("result-formula");
    if (sub) sub.textContent = outputs._formula || "";

    var actions = d.getElementById("result-actions");
    if (actions) actions.classList.add("show");

    // Phase C: notices 표시
    renderNotices(outputs.notices);

    // Phase C: 계산 과정 step accordion
    renderSteps(outputs._detail || [], outputs._formula || "");

    // Phase D-1: article_content placeholder 치환
    updateArticlePlaceholders(inputs, outputs);
    // Phase D-3: 조건 기반 CTA 업데이트
    renderDynamicCta(inputs, outputs);
    // Phase D-4: 동적 FAQ 삽입
    renderDynamicFaq(inputs, outputs);

    // E-1: result_view 이벤트
    if (w.smTrack) {
      w.smTrack("result_view", { primary_key: primary, primary_value: pv });
    }

    // 기존 계산 상세 (detail-card) — steps-card와 중복 방지: steps-card 있으면 detail-card 숨김
    if (!d.getElementById("steps-card")) {
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
  }

  // Phase D-1: article_content 내 <span data-ph> 를 계산 결과로 치환
  function updateArticlePlaceholders(inputs, outputs) {
    d.querySelectorAll("[data-ph]").forEach(function (el) {
      var key = el.getAttribute("data-ph");
      var fmt = el.getAttribute("data-fmt") || "text";
      // inputs 우선, 없으면 outputs 에서 읽기
      var raw = (outputs && outputs[key] != null) ? outputs[key]
              : (inputs  && inputs[key]  != null) ? inputs[key]
              : null;
      if (raw == null || raw === "" || raw === 0 && key !== "family_count") return;
      var display;
      if (fmt === "currency") {
        display = Math.round(num(raw)).toLocaleString() + "원";
      } else if (fmt === "currency_signed") {
        var n = Math.round(num(raw));
        display = (n >= 0 ? "+" : "") + n.toLocaleString() + "원";
      } else if (fmt === "number") {
        display = num(raw).toLocaleString();
      } else {
        display = String(raw);
      }
      el.textContent = display;
    });
  }

  // Phase D-3: SM_CTA_RULES 조건 평가 → #sm-result-cta 동적 업데이트
  function renderDynamicCta(inputs, outputs) {
    var host = d.getElementById("sm-result-cta");
    var rules = w.SM_CTA_RULES;
    if (!host || !rules) return;
    var matched = null;
    var ruleList = rules.rules || [];
    for (var i = 0; i < ruleList.length; i++) {
      try {
        var ok = (new Function("inputs", "outputs", "return !!(" + ruleList[i].condition + ");"))(inputs, outputs);
        if (ok) { matched = ruleList[i]; break; }
      } catch (e) { /* 조건 평가 실패 시 다음 룰 */ }
    }
    var rule = matched || rules.default;
    if (!rule) return;
    var linksHtml = (rule.links || []).map(function (l) {
      return '<a class="sm-result-cta-link" href="' + esc(l.href) + '">' + esc(l.label) + '</a>';
    }).join("");
    host.innerHTML =
      '<p class="sm-result-cta-text">' + esc(rule.text || "") + '</p>' +
      '<div class="sm-result-cta-links">' + linksHtml + '</div>';
    // Analytics 훅 (Phase E에서 실제 연동)
    if (rule.analytics && w.smTrack) { w.smTrack(rule.analytics, {inputs: inputs, outputs: outputs}); }
  }

  // Phase D-4: SM_DYNAMIC_FAQ 조건 평가 → #sm-dynamic-faq 에 우선순위 순으로 삽입
  function renderDynamicFaq(inputs, outputs) {
    var host = d.getElementById("sm-dynamic-faq");
    var items = w.SM_DYNAMIC_FAQ;
    if (!host || !items || !items.length) return;
    // 우선순위(1→4) 정렬 후 조건 평가
    var sorted = items.slice().sort(function (a, b) { return (a.priority || 4) - (b.priority || 4); });
    var matched = [];
    sorted.forEach(function (item) {
      try {
        var ok = (new Function("inputs", "outputs", "return !!(" + item.condition + ");"))(inputs, outputs);
        if (ok) matched.push(item);
      } catch (e) { /* skip */ }
    });
    if (!matched.length) return;
    var idx = 9000; // dynamic FAQ id prefix (정적 FAQ와 겹치지 않게)
    host.innerHTML = matched.map(function (item) {
      var bid = "faq-dyn-btn-" + idx;
      var aid = "faq-dyn-ans-" + (idx++);
      return '<div class="sm-faq-item sm-faq-dynamic">' +
        '<button class="sm-faq-q" id="' + bid + '" type="button" ' +
        'aria-expanded="false" aria-controls="' + aid + '" onclick="toggleFaq(this)">' +
        esc(item.q || "") +
        '<span class="sm-faq-icon" aria-hidden="true">+</span></button>' +
        '<div class="sm-faq-a" id="' + aid + '" hidden>' + esc(item.a || "") + '</div>' +
        '</div>';
    }).join("");
  }

  // E-1: calculate 호출 횟수 (retry 감지)
  var _calcCount = 0;

  // 공통 계산 진입점 — 계산기별 computeResult(inputs)만 교체하면 재사용
  function calculate() {
    _calcCount++;
    // E-1: calculator_submit (첫 번째) / retry_calculation (2번째~)
    if (w.smTrack) {
      w.smTrack(_calcCount > 1 ? "retry_calculation" : "calculator_submit", {});
    }
    var inputs = collectInputs();
    var outputs;
    try {
      outputs = (typeof w.computeResult === "function") ? w.computeResult(inputs) : null;
    } catch (e) { console.error(e); outputs = null; }
    if (!outputs || !isFinite(num(outputs[CFG.primaryOutput]))) {
      var errEl = d.getElementById("calc-error");
      if (!errEl) {
        errEl = d.createElement("p");
        errEl.id = "calc-error";
        errEl.style.cssText = "color:#DC2626;font-size:14px;margin-top:8px;font-weight:600;";
        var btn = d.querySelector(".sm-btn");
        if (btn && btn.parentNode) btn.parentNode.insertBefore(errEl, btn.nextSibling);
      }
      errEl.textContent = "입력값을 확인해주세요.";
      return;
    }
    var errEl2 = d.getElementById("calc-error");
    if (errEl2) errEl2.textContent = "";
    renderResult(inputs, outputs);
  }

  // 초기화: show_* 플래그 반영 + 기능 모듈 init
  function init() {
    if (CFG.show_adsense) toggleAll(".sm-adsense", true);
    if (CFG.show_cpa) toggleAll(".sm-cpa", true);
    hideActionIf("result_save", CFG.show_result_save === false);
    hideActionIf("share", CFG.show_share === false);
    hideActionIf("pwa", CFG.show_pwa === false);
    if (CFG.show_faq === false) hideEl("#faq-card");
    if (CFG.show_notice === false) hideEl(".sm-notice");
    if (CFG.show_related === false) hideEl("#related-card");
    if (CFG.show_article === false) hideEl(".sm-article");
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


window.computeResult = function(inputs){
  var jeonse_deposit = inputs["jeonse_deposit"] || 0;
  var wolse_deposit = inputs["wolse_deposit"] || 0;
  var wolse_amount = inputs["wolse_amount"] || 0;
  var rate = inputs["rate"] || 0;
  var out = {};
  out.notices = [];
  if (rate <= 0) { return null; }
  out["jeonse_opp_cost"] = ((jeonse_deposit - wolse_deposit) * rate / 100 / 12);
  out["wolse_to_jeonse_equiv"] = (wolse_deposit + wolse_amount * 1200 / rate);
  out["monthly_savings"] = (wolse_amount - (jeonse_deposit - wolse_deposit) * rate / 100 / 12);
  out._formula = "";
  return out;
};
