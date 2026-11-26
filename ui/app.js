"use strict";
/* Turn-taking knobs. Tune here. */
const SILENCE_MS = 900;           // quiet this long = your turn is over
const SPEECH_RMS = 0.02;          // mic level that counts as speech
const MIN_SPEECH_MS = 300;        // shorter blips are ignored
const NO_SPEECH_RESET_MS = 8000;  // recording with no speech is dropped and restarted (saves transcription cost)
const RESUME_DELAY_MS = 400;      // pause after JARVIS stops talking before the mic opens again

function vadStep(V, rms, now) {   // pure: returns "start" | "blip" | "end" | "reset" | null
  if (rms > SPEECH_RMS) { V.voiceAt = now; if (!V.speaking) { V.speaking = true; V.speechStart = now; return "start"; } return null; }
  if (V.speaking && now - V.voiceAt > SILENCE_MS) { V.speaking = false; return V.voiceAt - V.speechStart < MIN_SPEECH_MS ? "blip" : "end"; }
  if (!V.speaking && now - V.t0 > NO_SPEECH_RESET_MS) return "reset";
  return null;
}
(async () => {
  const $ = s => document.querySelector(s), el = (t, p = {}, ...kids) => { const e = Object.assign(document.createElement(t), p); e.append(...kids); return e; };
  const banner = m => { const b = $("#banner"); b.textContent = m; b.hidden = false; };
  let d;
  try { const r = await fetch("/api/graph"); if (!r.ok) throw new Error("HTTP " + r.status); d = await r.json(); }
  catch (e) { banner("Can't reach the JARVIS server (" + e.message + "). Start it with: python agent\\main.py"); return; }
  $("#badge").textContent = d.demo ? "demo" : "real"; $("#badge").classList.toggle("real", !d.demo);
  $("#stats").textContent = d.nodes.length + " notes, " + d.edges.length + " links";
  const miss = Object.keys(d.skipped).filter(k => /^(missing folder|folder is the app)/.test(k));
  if (miss.length) banner(miss.join("; ") + ". Check JARVIS_FOLDERS in .env.");
  else if (!d.nodes.length) banner("Index is empty: no .md, .txt or .pdf under 2 MB in the configured folders.");
  const pal = ["#4cc9f0", "#f5b83d", "#3ddc84", "#ff5fa2", "#a78bfa", "#e8ecf1", "#ff9f43", "#5b8def", "#2dd4bf", "#f87171"];
  const cnt = {}; d.nodes.forEach(n => cnt[n.k] = (cnt[n.k] || 0) + 1);
  const types = Object.keys(cnt).sort((a, b) => cnt[b] - cnt[a]), colors = {}; types.forEach((t, i) => colors[t] = pal[i % pal.length]);
  const hidden = new Set(); let g;
  const dot = c => el("span", { className: "dot", style: "background:" + c + ";box-shadow:0 0 6px " + c });
  const show = async i => {
    const box = $("#insp"); box.replaceChildren(el("p", { className: "dim" }, "Loading..."));
    if (i < 0) return box.replaceChildren(el("p", { className: "dim" }, "Click a node to focus it. Shift-click a second to trace the path."));
    try {
      const n = await (await fetch("/api/note?i=" + i)).json();
      box.replaceChildren(el("span", { className: "chip" }, dot(colors[n.k]), n.k), el("h2", {}, n.t), el("div", { className: "dim" }, n.p + " | " + n.links.length + " links"),
        el("pre", {}, n.text.trim() || "No readable text in this file."),
        ...n.links.slice(0, 40).map(j => el("button", { className: "row lk", onclick: () => g.select(j, true) }, dot(colors[d.nodes[j].k]), d.nodes[j].t)));
    } catch (e) { box.replaceChildren(el("p", {}, "Couldn't load that note: " + e.message)); }
  };
  g = new Graph($("#cv"), d, colors, {
    hover: () => {}, focus: show,
    path: (p, a, b) => { const box = $("#insp"); box.replaceChildren(el("span", { className: "chip" }, "path"), el("h2", {}, p ? (p.length - 1) + " hops" : "No path"),
      el("div", { className: "dim" }, p ? p.map(i => d.nodes[i].t).join("  >  ") : d.nodes[a].t + " and " + d.nodes[b].t + " aren't connected (check the filters).")); }
  });
  const hubs = [...d.nodes.keys()].sort((a, b) => d.nodes[b].d - d.nodes[a].d).slice(0, 8);
  $("#hubs").replaceChildren(...hubs.map(i => el("li", {}, el("button", { className: "row", onclick: () => g.select(i, true) }, dot(colors[d.nodes[i].k]), d.nodes[i].t, el("span", { className: "n" }, d.nodes[i].d)))));
  const rows = {};
  $("#filter").replaceChildren(...types.map(t => rows[t] = el("li", {}, el("button", { className: "row", onclick: () => {
    hidden.has(t) ? hidden.delete(t) : hidden.add(t); rows[t].firstChild.classList.toggle("off", hidden.has(t)); g.setHidden(hidden);
  } }, dot(colors[t]), t, el("span", { className: "n" }, cnt[t])))));
  const ticks = $("#ticks"); for (let a = 0; a < 360; a += 10) { const r = a * Math.PI / 180, l = a % 30 ? 3 : 6; const ln = document.createElementNS("http://www.w3.org/2000/svg", "line");
    ln.setAttribute("x1", 46 * Math.cos(r)); ln.setAttribute("y1", 46 * Math.sin(r)); ln.setAttribute("x2", (46 + l) * Math.cos(r)); ln.setAttribute("y2", (46 + l) * Math.sin(r)); ticks.append(ln); }
  window.setReactor = s => { $("#reactor").dataset.state = s; $("#rstate").textContent = s; };  // used from step 3 on
  const ex = ["Which invoices are still unpaid?", "What did I quote on the last proposal?", "Who haven't I followed up with?", "Plan my day", "Brief me"]; let n = 0;
  const rot = () => $("#ask").placeholder = ex[n++ % ex.length]; rot(); setInterval(rot, 4000);
  const ask = $("#ask"); ask.disabled = false; 
  const badge = r => { const m = $("#model"); m.textContent = r.model ? "model: " + r.model : "model missing"; m.className = r.model ? "ok" : "bad"; m.title = r.error || "";
    if (!r.model && r.error) banner(r.error); else if (r.model) $("#banner").hidden = true;
    if (r.voice) { const v = $("#voice"); V.voiceOk = r.voice.ok; V.voiceErr = r.voice.error; v.textContent = r.voice.ok ? "voice on" : "voice missing"; v.className = r.voice.ok ? "ok" : "bad"; v.title = r.voice.error || "used " + r.voice.chars + " of " + r.voice.cap + " characters this run"; } };
  const render = r => { $("#resp").hidden = false; $("#say").textContent = r.spoken;
    $("#cardbox").replaceChildren(...(r.card ? [el("h3", {}, r.card.title), ...r.card.rows.map(x => el("div", { className: "crow" }, el("b", {}, x.h), el("span", {}, x.b)))] : [])); badge(r); };
  const send = async b => { barge(); state("thinking"); ask.disabled = true; let spoken = "";
    try { const r = await fetch("/api/ask", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(b) }); if (!r.ok) throw new Error("HTTP " + r.status); const j = await r.json(); render(j); spoken = j.spoken; }
    catch (e) { spoken = "Request failed."; render({ spoken, card: { title: "Error", rows: [{ h: "server", b: e.message }] } }); }
    ask.disabled = false; if (!V.on) ask.focus(); await sayOut(spoken); fetch("/api/status").then(r => r.json()).then(badge).catch(() => {}); };
  ask.addEventListener("keydown", e => { const t = ask.value.trim(); if (e.key === "Enter" && t) { ask.value = ""; $("#asked").textContent = t; send({ text: t }); } });
  document.querySelectorAll("[data-tool]").forEach(b => { b.disabled = false; b.onclick = () => { $("#asked").textContent = b.textContent; send({ tool: b.dataset.tool }); }; });
  fetch("/api/status").then(r => r.json()).then(badge).catch(() => {});
  // ---- voice: record in the browser, transcribe and speak on the server ----
  const V = { st: "idle", on: false, muted: false, gen: 0, keep: false, voiceOk: true, voiceErr: "" }, bars = $("#bars").getContext("2d");
  const cap = t => $("#caption").textContent = t, vfail = m => { banner(m); cap(m); };
  function state(s) { V.st = s; setReactor(s); $("#mic").classList.toggle("on", V.on); }
  async function openMic() {
    if (V.stream) return true;
    if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia || !window.MediaRecorder) { vfail("This browser can't record audio. Use a current Chrome, Edge, Firefox or Brave."); return false; }
    try { V.stream = await navigator.mediaDevices.getUserMedia({ audio: { echoCancellation: true, noiseSuppression: true } }); }
    catch (e) { vfail(e.name === "NotAllowedError" ? "Microphone blocked. Click the lock or Shields icon in the address bar, allow the microphone for localhost, then press mic again." : e.name === "NotFoundError" ? "No microphone found. Plug one in or choose one in system sound settings." : "Microphone failed: " + e.name); return false; }
    V.ctx = new AudioContext(); V.an = V.ctx.createAnalyser(); V.an.fftSize = 1024; V.ctx.createMediaStreamSource(V.stream).connect(V.an); V.buf = new Uint8Array(V.an.fftSize); V.freq = new Uint8Array(V.an.frequencyBinCount);
    V.stream.getAudioTracks()[0].onended = () => { V.stream = null; stopListening(); vfail("Microphone disconnected."); };
    return true;
  }
  function newRec() {
    if (V.rec) { V.rec.onstop = null; if (V.rec.state === "recording") V.rec.stop(); }   // never two recorders
    V.chunks = []; const r = V.rec = new MediaRecorder(V.stream); r.ondataavailable = e => e.data.size && V.chunks.push(e.data);
    r.onstop = () => { const k = V.keep; V.keep = false; if (k) turn(new Blob(V.chunks, { type: r.mimeType })); else if (V.on && V.st === "listening") newRec(); };
    r.start(); V.t0 = Date.now(); V.speaking = false;
  }
  const stopRec = () => { if (V.rec && V.rec.state === "recording") V.rec.stop(); };
  async function startListening() {
    if (!V.voiceOk) return vfail(V.voiceErr || "Voice isn't set up.");
    if (!(await openMic())) return;
    await V.ctx.resume(); barge(); V.on = true; state("listening"); cap("listening..."); newRec();
  }
  function stopListening() { V.on = false; V.keep = false; stopRec(); state("idle"); cap("press mic, then talk"); }
  function barge() { V.gen++; if (V.audio) { V.audio.pause(); if (V.stopAudio) V.stopAudio(); } }
  const resume = () => { if (V.on && V.stream) setTimeout(() => { if (V.on && V.st !== "listening") { state("listening"); cap("listening..."); newRec(); } }, RESUME_DELAY_MS); else { state("idle"); cap("press mic, then talk"); } };
  async function turn(blob) {
    try {
      const r = await fetch("/api/listen", { method: "POST", headers: { "Content-Type": blob.type || "audio/webm" }, body: blob }), j = await r.json();
      if (!r.ok) throw new Error(j.error || "HTTP " + r.status);
      if (!j.text) { cap("Didn't catch that."); return resume(); }
      cap("heard: " + j.text); $("#asked").textContent = j.text; await send({ text: j.text });
    } catch (e) { vfail("Transcription failed: " + e.message); stopListening(); }
  }
  async function sayOut(text) {
    const g = ++V.gen;
    if (V.muted || !text || !V.voiceOk) { if (V.st !== "listening") resume(); return; }
    try {
      state("speaking"); cap(text);
      const r = await fetch("/api/speak", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ text }) });
      if (!r.ok) throw new Error((await r.json()).error || "HTTP " + r.status);
      const url = URL.createObjectURL(await r.blob()); if (g !== V.gen) return URL.revokeObjectURL(url);
      V.audio = new Audio(url);
      await new Promise(res => { V.stopAudio = res; V.audio.onended = V.audio.onerror = res; V.audio.play().catch(e => { vfail("The browser blocked audio playback: " + e.message); res(); }); });
      URL.revokeObjectURL(url);
    } catch (e) { vfail("Voice output failed: " + e.message + " Text still works."); }
    V.audio = null; if (g === V.gen && V.st === "speaking") resume();
  }
  // setInterval, not requestAnimationFrame: RAF stops in a background tab and the mic goes silently deaf.
  setInterval(() => {
    if (!V.an) return;
    V.an.getByteTimeDomainData(V.buf); let s = 0; for (const v of V.buf) { const x = (v - 128) / 128; s += x * x; }
    const rms = Math.sqrt(s / V.buf.length), live = V.st === "listening"; V.an.getByteFrequencyData(V.freq);
    bars.clearRect(0, 0, 96, 22); bars.fillStyle = live ? "#38d6c4" : "rgba(56,214,196,.25)";
    for (let i = 0; i < 24; i++) { const h = Math.max(2, V.freq[i * 3 + 2] / 255 * 22); bars.fillRect(i * 4, 22 - h, 3, h); }
    if (!live) return;                                    // deaf while thinking or speaking
    const a = vadStep(V, rms, Date.now());
    if (a === "start") cap("hearing you...");
    else if (a === "blip") cap("listening...");
    else if (a === "end") { V.keep = true; state("thinking"); cap("transcribing..."); stopRec(); }
    else if (a === "reset") stopRec();                    // no speech: drop this recording; onstop starts a fresh one
  }, 50);
  $("#mic").onclick = e => { e.currentTarget.blur(); (V.on && V.st !== "speaking") ? stopListening() : startListening(); };
  $("#mute").onclick = e => { e.currentTarget.blur(); V.muted = !V.muted; e.currentTarget.classList.toggle("on", V.muted); if (V.muted) { barge(); if (V.st === "speaking") resume(); } };
  addEventListener("keydown", e => {
    if (e.key === "Escape") { barge(); stopListening(); }
    else if (e.key === " " && !/^(INPUT|TEXTAREA)$/.test(e.target.tagName)) { e.preventDefault(); if (V.st === "speaking" || V.st === "idle") startListening(); }
  });
})();
