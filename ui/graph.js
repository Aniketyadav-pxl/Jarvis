"use strict";
/* Canvas force graph. Repulsion uses a spatial grid with a distance cutoff (near-linear). */
class Graph {
  constructor(cv, d, colors, cb) {
    this.cv = cv; this.c = cv.getContext("2d"); this.cb = cb;
    let s = 12345; const rnd = () => (s = (s * 1664525 + 1013904223) % 4294967296) / 4294967296 - 0.5;
    this.nodes = d.nodes.map((n, i) => ({ i, t: n.t, k: n.k, d: n.d, col: colors[n.k], r: 3 + Math.sqrt(n.d) * 1.9, x: rnd() * 500, y: rnd() * 500, vx: 0, vy: 0, pin: false }));
    this.edges = d.edges; this.adj = this.nodes.map(() => []);
    for (const [a, b] of this.edges) { this.adj[a].push(b); this.adj[b].push(a); }
    this.order = [...this.nodes].sort((a, b) => b.d - a.d);
    this.hidden = new Set(); this.k = 1; this.tx = 0; this.ty = 0; this.hover = -1; this.focus = -1;
    this.path = null; this.pulse = null; this.alpha = 1; this.t = 0;
    this.resize(); addEventListener("resize", () => this.resize()); this.bind();
    const t0 = performance.now();
    for (let i = 0; i < 300 && performance.now() - t0 < 700; i++) this.step();
    this.fit();
    setInterval(() => { if (this.edges.length) this.pulse = { e: this.edges[Math.floor(Math.random() * this.edges.length)], t0: performance.now() }; }, 2600);
    const loop = () => { this.step(); this.draw(); requestAnimationFrame(loop); }; loop();
  }
  resize() { const r = this.cv.getBoundingClientRect(); this.dpr = devicePixelRatio || 1; this.w = r.width; this.h = r.height; this.cv.width = r.width * this.dpr; this.cv.height = r.height * this.dpr; }
  step() {
    const N = this.nodes, R = 64, g = new Map(); this.t += 0.016;
    this.alpha = Math.max(0.05, this.alpha * 0.993); const a = this.alpha;
    for (const n of N) { const key = (Math.floor(n.x / R) + 4096) * 8192 + Math.floor(n.y / R) + 4096; let b = g.get(key); if (!b) g.set(key, b = []); b.push(n); }
    for (const n of N) {
      const cx = Math.floor(n.x / R) + 4096, cy = Math.floor(n.y / R) + 4096;
      for (let ox = -1; ox <= 1; ox++) for (let oy = -1; oy <= 1; oy++) {
        const b = g.get((cx + ox) * 8192 + cy + oy); if (!b) continue;
        for (const m of b) {
          if (m.i <= n.i) continue;
          let dx = n.x - m.x, dy = n.y - m.y, d2 = dx * dx + dy * dy; if (d2 >= R * R) continue;
          if (d2 < 0.01) { dx = 0.1; d2 = 0.01; }
          const d = Math.sqrt(d2), f = (1 - d / R) * 16 * a / d;
          n.vx += dx * f; n.vy += dy * f; m.vx -= dx * f; m.vy -= dy * f;
        }
      }
    }
    for (const [i, j] of this.edges) {
      const p = N[i], q = N[j], dx = q.x - p.x, dy = q.y - p.y, d = Math.hypot(dx, dy) || 1, f = (d - 48) * 0.02 * a / d;
      p.vx += dx * f; p.vy += dy * f; q.vx -= dx * f; q.vy -= dy * f;
    }
    for (const n of N) {
      if (n.pin) continue;
      n.vx += -n.x * 0.003 * a + Math.sin(this.t + n.i) * 0.03; n.vy += -n.y * 0.003 * a + Math.cos(this.t * 0.9 + n.i) * 0.03;
      n.vx = Math.max(-8, Math.min(8, n.vx * 0.78)); n.vy = Math.max(-8, Math.min(8, n.vy * 0.78)); n.x += n.vx; n.y += n.vy;
    }
  }
  fit() {
    const v = this.nodes.filter(n => !this.hidden.has(n.k)); if (!v.length) return;
    let x0 = 1e9, x1 = -1e9, y0 = 1e9, y1 = -1e9;
    for (const n of v) { x0 = Math.min(x0, n.x); x1 = Math.max(x1, n.x); y0 = Math.min(y0, n.y); y1 = Math.max(y1, n.y); }
    this.k = Math.max(0.1, Math.min(2.5, Math.min((this.w - 700) / (x1 - x0 + 80), (this.h - 160) / (y1 - y0 + 80))));
    this.tx = this.w / 2 - ((x0 + x1) / 2) * this.k; this.ty = this.h / 2 - ((y0 + y1) / 2) * this.k;
  }
  pick(mx, my) {
    let best = -1, bd = 1e9;
    for (const n of this.nodes) {
      if (this.hidden.has(n.k)) continue;
      const d = Math.hypot(n.x * this.k + this.tx - mx, n.y * this.k + this.ty - my);
      if (d < Math.max(n.r * Math.pow(this.k, 0.6) + 3, 8) && d < bd) { bd = d; best = n.i; }
    }
    return best;
  }
  trace(a, b) {
    const prev = new Map([[a, -1]]), q = [a];
    while (q.length) { const u = q.shift(); if (u === b) break; for (const v of this.adj[u]) if (!prev.has(v) && !this.hidden.has(this.nodes[v].k)) { prev.set(v, u); q.push(v); } }
    if (!prev.has(b)) return null;
    const p = []; for (let u = b; u !== -1; u = prev.get(u)) p.push(u); return p.reverse();
  }
  select(i, center) {
    this.focus = i; this.path = null;
    if (center && i >= 0) { const n = this.nodes[i]; this.tx = this.w / 2 - n.x * this.k; this.ty = this.h / 2 - n.y * this.k; }
    this.cb.focus(i);
  }
  setHidden(set) { this.hidden = set; }
  bind() {
    const cv = this.cv; let mode = null, sx = 0, sy = 0, moved = 0, drag = -1;
    const pos = e => { const r = cv.getBoundingClientRect(); return [e.clientX - r.left, e.clientY - r.top]; };
    cv.addEventListener("pointerdown", e => {
      const [x, y] = pos(e); sx = x; sy = y; moved = 0; drag = this.pick(x, y); mode = drag >= 0 ? "node" : "pan"; cv.setPointerCapture(e.pointerId); cv.style.cursor = "grabbing";
    });
    cv.addEventListener("pointermove", e => {
      const [x, y] = pos(e);
      if (mode) {
        moved += Math.abs(x - sx) + Math.abs(y - sy);
        if (mode === "node") { const n = this.nodes[drag]; n.x = (x - this.tx) / this.k; n.y = (y - this.ty) / this.k; n.pin = true; n.vx = n.vy = 0; this.alpha = Math.max(this.alpha, 0.3); }
        else { this.tx += x - sx; this.ty += y - sy; }
        sx = x; sy = y;
      } else { const h = this.pick(x, y); if (h !== this.hover) { this.hover = h; cv.style.cursor = h >= 0 ? "pointer" : "grab"; this.cb.hover(h); } }
    });
    cv.addEventListener("pointerup", e => {
      cv.style.cursor = "grab";
      if (mode === "node") this.nodes[drag].pin = false;
      if (moved < 4 && drag >= 0) {
        if (e.shiftKey && this.focus >= 0 && drag !== this.focus) { this.path = this.trace(this.focus, drag); this.cb.path(this.path, this.focus, drag); }
        else this.select(drag, false);
      }
      mode = null;
    });
    cv.addEventListener("wheel", e => {
      e.preventDefault(); const [x, y] = pos(e), f = e.deltaY < 0 ? 1.12 : 1 / 1.12, k = Math.max(0.1, Math.min(6, this.k * f));
      this.tx = x - (x - this.tx) * (k / this.k); this.ty = y - (y - this.ty) * (k / this.k); this.k = k;
    }, { passive: false });
  }
  draw() {
    const c = this.c, N = this.nodes, k = this.k, tx = this.tx, ty = this.ty;
    c.setTransform(this.dpr, 0, 0, this.dpr, 0, 0); c.clearRect(0, 0, this.w, this.h);
    const act = this.hover >= 0 ? this.hover : this.focus, nb = act >= 0 ? new Set([act, ...this.adj[act]]) : null;
    const pset = new Set(this.path || []), pe = new Set();
    if (this.path) for (let i = 0; i < this.path.length - 1; i++) { const a = this.path[i], b = this.path[i + 1]; pe.add(Math.min(a, b) * 1e7 + Math.max(a, b)); }
    const hid = n => this.hidden.has(n.k);
    for (const [i, j] of this.edges) {
      const p = N[i], q = N[j]; if (hid(p) || hid(q)) continue;
      let al = 0.13, col = "120,205,215", lw = 1;
      if (pe.has(Math.min(i, j) * 1e7 + Math.max(i, j))) { al = 0.95; col = "56,214,196"; lw = 2.4; }
      else if (nb) { if (i === act || j === act) { al = 0.7; col = "56,214,196"; } else al = 0.03; }
      c.lineWidth = lw; c.strokeStyle = `rgba(${col},${al})`; c.beginPath(); c.moveTo(p.x * k + tx, p.y * k + ty); c.lineTo(q.x * k + tx, q.y * k + ty); c.stroke();
    }
    if (this.pulse) {
      const u = (performance.now() - this.pulse.t0) / 900;
      if (u >= 1) this.pulse = null; else {
        const p = N[this.pulse.e[0]], q = N[this.pulse.e[1]]; c.fillStyle = "rgba(56,214,196,.95)"; c.shadowColor = "#38d6c4"; c.shadowBlur = 12;
        c.beginPath(); c.arc((p.x + (q.x - p.x) * u) * k + tx, (p.y + (q.y - p.y) * u) * k + ty, 2.2, 0, 7); c.fill(); c.shadowBlur = 0;
      }
    }
    for (let z = N.length - 1; z >= 0; z--) {
      const n = this.order[z]; if (hid(n)) continue;
      const lit = !nb || nb.has(n.i) || pset.has(n.i), rr = n.r * Math.pow(k, 0.6) + (n.i === act ? 3 : 0);
      c.globalAlpha = lit ? 1 : 0.1; c.fillStyle = n.col;
      if (lit && (n.i === act || z < 40)) { c.shadowColor = n.col; c.shadowBlur = n.i === act ? 22 : 12; }
      c.beginPath(); c.arc(n.x * k + tx, n.y * k + ty, rr, 0, 7); c.fill(); c.shadowBlur = 0;
    }
    c.globalAlpha = 1; c.font = "11px 'Cascadia Mono',Consolas,monospace"; c.textBaseline = "middle"; c.lineJoin = "round"; c.lineWidth = 3;
    const placed = []; let count = 0;
    const cand = []; if (act >= 0) cand.push(N[act]); for (const i of pset) cand.push(N[i]); for (const n of this.order) if (!nb || nb.has(n.i)) cand.push(n);
    for (const n of cand) {
      if (count > 140 || hid(n) || (n.d < 2 && k < 1.4 && n.i !== act && !pset.has(n.i))) continue;
      const sx = n.x * k + tx, sy = n.y * k + ty; if (sx < -50 || sy < -20 || sx > this.w + 50 || sy > this.h + 20) continue;
      const rr = n.r * Math.pow(k, 0.6), w = c.measureText(n.t).width + 6, bx = sx + rr + 3, by = sy - 8;
      if (placed.some(b => bx < b[0] + b[2] && bx + w > b[0] && by < b[1] + b[3] && by + 16 > b[1])) continue;
      placed.push([bx, by, w, 16]); count++;
      c.strokeStyle = "rgba(4,6,10,.9)"; c.strokeText(n.t, bx + 3, sy); c.fillStyle = "rgba(220,230,238,.92)"; c.fillText(n.t, bx + 3, sy);
    }
  }
}
