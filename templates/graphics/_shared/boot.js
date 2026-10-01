/* Applies the brand kit from window.CUE to CSS variables and @font-face, and gives templates helpers.
   Deterministic: no clocks, no Math.random (use MG.rand). */
(function () {
  var C = window.CUE || {}, B = C.brand || {};
  var r = document.documentElement.style;
  r.setProperty("--primary", B.primary || "#0f7a5a"); r.setProperty("--dark", B.dark || "#14201c");
  r.setProperty("--light", B.light || "#f7f5ee"); r.setProperty("--accent", B.accent || B.primary || "#f0c419");
  r.setProperty("--ink", B.ink || "#111"); r.setProperty("--on-primary", B.on_primary || "#fff");
  r.setProperty("--font-head", '"' + (B.font_head_family || "Barlow Condensed") + '"'); r.setProperty("--font-body", '"' + (B.font_body_family || "Inter") + '"');
  var css = "";
  (B.fonts || []).forEach(function (f) { css += '@font-face{font-family:"' + f.family + '";src:url("' + f.file + '");font-weight:' + (f.weight || "100 900") + ';font-display:block}'; });
  css += '@font-face{font-family:"Inter";src:url("assets/fonts/Inter-SemiBold.ttf");font-weight:600;font-display:block}';
  css += '@font-face{font-family:"Barlow Condensed";src:url("assets/fonts/BarlowCondensed-ExtraBold.ttf");font-weight:800;font-display:block}';
  var s = document.createElement("style"); s.textContent = css; document.head.appendChild(s);
  window.T = function (k, d) { return C[k] == null ? d : C[k]; };
  window.place = function (el, def) { var p = C.pos || def || {}; el.style.left = (p.x || 0) + "px"; el.style.top = (p.y || 0) + "px"; if (p.w) el.style.width = p.w + "px"; };
})();
