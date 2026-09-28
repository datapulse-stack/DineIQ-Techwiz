/* =========================================================================
   fx.js — the "feel premium" layer, shared by every page.
   custom cursor, ember/steam particles for the scene, and button ripples.
   pure vanilla, no deps. safe to load on any page (everything is guarded).
   ========================================================================= */
(function () {
  const reduce = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  const coarse = window.matchMedia && window.matchMedia("(pointer: coarse)").matches;

  /* ---- custom cursor: a dot pinned to the pointer + a ring that eases in -- */
  if (!coarse) {
    const ring = document.createElement("div"); ring.className = "cursor-ring";
    const dot = document.createElement("div"); dot.className = "cursor-dot";
    document.body.appendChild(ring); document.body.appendChild(dot);
    let mx = innerWidth / 2, my = innerHeight / 2, rx = mx, ry = my;
    addEventListener("mousemove", e => {
      mx = e.clientX; my = e.clientY;
      dot.style.transform = `translate(${mx}px,${my}px) translate(-50%,-50%)`;
    });
    (function loop() {
      // ease the ring toward the pointer for a smooth trailing feel
      rx += (mx - rx) * 0.18; ry += (my - ry) * 0.18;
      ring.style.transform = `translate(${rx}px,${ry}px) translate(-50%,-50%)`;
      requestAnimationFrame(loop);
    })();
    // grow the ring over anything clickable
    const hot = "a,button,.btn,input,select,.nav a,.card,.tag-toggle button,th,.rec";
    addEventListener("mouseover", e => { if (e.target.closest(hot)) ring.classList.add("hot"); });
    addEventListener("mouseout", e => { if (e.target.closest(hot)) ring.classList.remove("hot"); });
    addEventListener("mousedown", () => ring.classList.add("click"));
    addEventListener("mouseup", () => ring.classList.remove("click"));
    addEventListener("mouseleave", () => { ring.style.opacity = 0; dot.style.opacity = 0; });
    addEventListener("mouseenter", () => { ring.style.opacity = 1; dot.style.opacity = 1; });
  }

  /* ---- ripple on buttons ------------------------------------------------- */
  document.addEventListener("click", e => {
    const b = e.target.closest(".btn");
    if (!b) return;
    const r = document.createElement("span");
    r.className = "ripple";
    const rect = b.getBoundingClientRect();
    const size = Math.max(rect.width, rect.height);
    r.style.width = r.style.height = size + "px";
    r.style.left = (e.clientX - rect.left - size / 2) + "px";
    r.style.top = (e.clientY - rect.top - size / 2) + "px";
    b.appendChild(r);
    setTimeout(() => r.remove(), 600);
  });

  /* ---- ambience particles: warm bokeh drifting up + soft kitchen steam ---- */
  if (!reduce) {
    // candle-light bokeh orbs, random size/speed/position so it never loops obviously
    const bokeh = document.getElementById("bokeh");
    if (bokeh) {
      for (let i = 0; i < 26; i++) {
        const b = document.createElement("i");
        const s = 6 + Math.random() * 26;             // small sparks to fat blurry orbs
        b.style.width = b.style.height = s + "px";
        b.style.left = Math.random() * 100 + "%";
        b.style.animationDuration = (14 + Math.random() * 16) + "s";
        b.style.animationDelay = (-Math.random() * 26) + "s"; // stagger so they're mid-flight on load
        bokeh.appendChild(b);
      }
    }
    // a few steam wisps rising off the "kitchen" side
    const steam = document.getElementById("steam");
    if (steam) {
      for (let i = 0; i < 6; i++) {
        const p = document.createElement("i");
        p.style.left = (i * 30 + Math.random() * 12) + "%";
        p.style.animationDelay = (-Math.random() * 4) + "s";
        steam.appendChild(p);
      }
    }
  }
})();
