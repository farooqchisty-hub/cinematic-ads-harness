/* Shared deterministic motion helpers for the overlay package.
   Everything here writes into the caller's single paused GSAP timeline, so every
   frame is a pure function of timeline time (seek-safe, no clocks, no Math.random). */
(function () {
  var F = 1 / 30;

  // index-seeded hash in [0,1)
  function rand(i) {
    var x = Math.sin(i * 127.1 + 311.7) * 43758.5453;
    return x - Math.floor(x);
  }

  // Impact shake: decaying, frame-stepped offsets on a dedicated wrapper
  // (never on an element that has its own x/y tweens).
  function shake(tl, target, t, opts) {
    opts = opts || {};
    var amp = opts.amp == null ? 22 : opts.amp;
    var frames = opts.frames || 9;
    var rot = opts.rot || 0;
    var seed = opts.seed || 1;
    var kf = [];
    for (var i = 0; i < frames; i++) {
      var d = 1 - i / frames;
      var a = amp * d * d;
      // alternate sign so the first frames read as a hard kick, not a drift
      var sx = i % 2 === 0 ? 1 : -1;
      kf.push({
        x: sx * (0.45 + 0.55 * rand(seed * 31 + i * 3 + 1)) * a,
        y: (rand(seed * 17 + i * 3 + 2) - 0.5) * 2 * a * 0.8,
        rotation: (rand(seed * 13 + i * 3 + 3) - 0.5) * 2 * rot * d,
        duration: F,
        ease: "none",
      });
    }
    kf.push({ x: 0, y: 0, rotation: 0, duration: F, ease: "none" });
    tl.to(target, { keyframes: kf }, t);
  }

  // High-frequency low-amplitude idle vibration (engine rumble), finite.
  function rumble(tl, target, t, dur, amp, seed) {
    var n = Math.max(1, Math.floor(dur / F));
    var kf = [];
    for (var i = 0; i < n; i++) {
      kf.push({
        x: (rand((seed || 3) * 7 + i * 2) - 0.5) * 2 * amp,
        y: (rand((seed || 3) * 11 + i * 2 + 1) - 0.5) * 2 * amp,
        duration: F,
        ease: "none",
      });
    }
    kf.push({ x: 0, y: 0, duration: F, ease: "none" });
    tl.to(target, { keyframes: kf }, t);
  }

  // Number count driven by a proxy; text written in onUpdate (seek-safe).
  function count(tl, el, from, to, t, dur, fmt, ease) {
    var o = { v: from };
    el.textContent = fmt(from);
    tl.fromTo(
      o,
      { v: from },
      {
        v: to,
        duration: dur,
        ease: ease || "power2.out",
        immediateRender: false,
        onUpdate: function () { el.textContent = fmt(o.v); },
      },
      t
    );
  }

  // Discrete text states at explicit times. One proxy spans the whole comp so any
  // seek (forward or back) resolves the state as a pure function of time.
  // states: [[t, "text"], ...] sorted by t; the first applies from 0.
  function steps(tl, el, states, total) {
    var o = { t: 0 };
    el.textContent = states[0][1];
    function render() {
      var s = states[0][1];
      for (var i = 0; i < states.length; i++) if (o.t >= states[i][0] - 1e-6) s = states[i][1];
      if (el.textContent !== s) el.textContent = s;
    }
    tl.fromTo(o, { t: 0 }, { t: total, duration: total, ease: "none", onUpdate: render }, 0);
  }

  // Scramble-decode a string into place over dur, deterministic glyph substitution.
  function decode(tl, el, finalStr, t, dur, charset, seed, fromStr) {
    charset = charset || "0123456789";
    var o = { p: 0 };
    var n = finalStr.length;
    function render() {
      if (o.p <= 0 && fromStr != null) { el.textContent = fromStr; return; }
      var out = "";
      var fr = Math.floor(o.p * 30 * dur);
      for (var i = 0; i < n; i++) {
        var ch = finalStr[i];
        var lock = (i + 1) / n;
        if (o.p >= lock || ch === " " || ch === "." || ch === "+" || ch === ":") out += ch;
        else out += charset[Math.floor(rand((seed || 5) * 101 + i * 13 + fr) * charset.length)];
      }
      el.textContent = out;
    }
    tl.fromTo(o, { p: 0 }, { p: 1, duration: dur, ease: "none", immediateRender: false, onUpdate: render }, t);
  }

  window.MG = { F: F, rand: rand, shake: shake, rumble: rumble, count: count, steps: steps, decode: decode };
})();
