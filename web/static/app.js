/* robo-rl viewer frontend -- no dependencies, no build step.
 *
 * Talks to the server over WebSocket (`/ws`) and falls back to polling
 * `GET /api/state` when an upgrade is blocked by a proxy. Both paths render the
 * identical snapshot, so the fallback can never show different numbers.
 *
 * In Phase 4 this is what gets rebuilt in Angular: snapshot -> component state,
 * WebSocket -> WebSocketSubject, buttons -> command service.
 */
(() => {
  "use strict";

  const POLL_HZ = 5;
  const WS_TIMEOUT_MS = 2500;

  const el = (id) => document.getElementById(id);
  const dom = {
    modeLabel: el("mode-label"),
    modeBadge: el("mode-badge"),
    linkBadge: el("link-badge"),
    uptime: el("uptime-badge"),
    banner: el("honesty-banner"),
    cell: el("cell"),
    cellHint: el("cell-hint"),
    cellCaption: el("cell-caption"),
    grid: el("grid"),
    bins: el("bins"),
    object: el("object"),
    objectDot: el("object-dot"),
    objectLabel: el("object-label"),
    arm: el("arm"),
    gripper: el("gripper"),
    stats: el("stats"),
    runState: el("run-state"),
    rateSuccess: el("rate-success"),
    rateReview: el("rate-review"),
    rateInterventions: el("rate-interventions"),
    spark: el("spark"),
    sparkLine: el("spark-line"),
    sparkThreshold: el("spark-threshold"),
    graph: el("graph"),
    graphNote: el("graph-note"),
    log: el("log"),
    threshold: el("threshold"),
    thresholdValue: el("threshold-value"),
    thresholdNote: el("threshold-note"),
    rate: el("rate"),
    rateValue: el("rate-value"),
    autoPause: el("auto-pause"),
    cmdTopic: el("cmd-topic"),
    cmdFeedback: el("cmd-feedback"),
    footerMode: el("footer-mode"),
    advToggle: el("adv-toggle"),
    advBody: el("adv-body"),
  };

  let socket = null;
  let link = "connecting"; // websocket | polling
  let lastLogSignature = "";
  let dragging = false; // don't fight the user while they drag sliders

  // ---------------------------------------------------------------- transport
  function connect() {
    let settled = false;
    try {
      socket = new WebSocket(`${location.protocol === "https:" ? "wss" : "ws"}://${location.host}/ws`);
    } catch (error) {
      startPolling();
      return;
    }
    const fallback = setTimeout(() => {
      if (!settled) {
        try { socket.close(); } catch (e) { /* ignore */ }
        startPolling();
      }
    }, WS_TIMEOUT_MS);

    socket.onopen = () => {
      settled = true;
      clearTimeout(fallback);
      link = "websocket";
      socket.send(JSON.stringify({ op: "subscribe", topic: "/detected_object" }));
      renderLink();
    };
    socket.onmessage = (event) => {
      try {
        const frame = JSON.parse(event.data);
        if (frame.op === "state") render(frame.msg);
        else if (frame.op === "error") flash(frame.msg, true);
      } catch (error) { /* ignore malformed frame */ }
    };
    socket.onclose = () => {
      clearTimeout(fallback);
      if (!settled) { settled = true; startPolling(); return; }
      if (link === "websocket") { link = "down"; renderLink(); setTimeout(connect, 1500); }
    };
    socket.onerror = () => { /* onclose handles it */ };
  }

  function startPolling() {
    if (link === "polling") return;
    link = "polling";
    renderLink();
    const tick = async () => {
      try {
        const response = await fetch("/api/state", { cache: "no-store" });
        if (response.ok) render(await response.json());
      } catch (error) { /* keep trying */ }
      if (link === "polling") setTimeout(tick, 1000 / POLL_HZ);
    };
    tick();
  }

  function renderLink() {
    dom.linkBadge.textContent = link === "websocket" ? "ws /ws" : link === "polling" ? `poll ${POLL_HZ}Hz` : "reconnecting";
    dom.linkBadge.className = `badge ${link === "down" ? "down" : link === "polling" ? "sim" : "ok"}`;
  }

  function send(command) {
    const message = JSON.stringify({ op: "publish", msg: command });
    if (socket && socket.readyState === WebSocket.OPEN) { socket.send(message); return Promise.resolve(); }
    return fetch("/api/command", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ command }),
    }).then((r) => r.json()).catch(() => ({}));
  }

  function simConfig(body) {
    return fetch("/api/sim_config", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    }).catch(() => ({}));
  }

  function flash(text, bad) {
    dom.cmdFeedback.textContent = text ? ` ${text}` : "";
    dom.cmdFeedback.style.color = bad ? "#e0685f" : "#5ec27b";
    setTimeout(() => { dom.cmdFeedback.textContent = ""; }, 2500);
  }

  // ------------------------------------------------------------------ drawing
  function buildGrid() {
    const ns = "http://www.w3.org/2000/svg";
    for (let x = 40; x < 500; x += 40) {
      const line = document.createElementNS(ns, "line");
      line.setAttribute("x1", x); line.setAttribute("y1", 30);
      line.setAttribute("x2", x); line.setAttribute("y2", 220);
      dom.grid.appendChild(line);
    }
    for (let y = 50; y < 220; y += 40) {
      const line = document.createElementNS(ns, "line");
      line.setAttribute("x1", 20); line.setAttribute("y1", y);
      line.setAttribute("x2", 500); line.setAttribute("y2", y);
      dom.grid.appendChild(line);
    }
  }

  const BIN_LABELS = [
    { key: "item_a", title: "BIN A" },
    { key: "item_b", title: "BIN B" },
    { key: "item_c", title: "BIN C" },
    { key: "review", title: "NEEDS HUMAN" },
  ];
  const binNodes = {};

  function buildBins() {
    const ns = "http://www.w3.org/2000/svg";
    BIN_LABELS.forEach((bin, index) => {
      const x = 40 + index * 112;
      const rect = document.createElementNS(ns, "rect");
      rect.setAttribute("x", x); rect.setAttribute("y", 245);
      rect.setAttribute("width", 96); rect.setAttribute("height", 86);
      rect.setAttribute("rx", 8); rect.setAttribute("class", "bin-rect");
      const title = document.createElementNS(ns, "text");
      title.setAttribute("x", x + 8); title.setAttribute("y", 264);
      title.setAttribute("class", "bin-title");
      title.textContent = bin.title;
      const count = document.createElementNS(ns, "text");
      count.setAttribute("x", x + 8); count.setAttribute("y", 300);
      count.setAttribute("class", "bin-count");
      count.textContent = "0";
      const tail = document.createElementNS(ns, "text");
      tail.setAttribute("x", x + 8); tail.setAttribute("y", 320);
      tail.setAttribute("class", "bin-label");
      tail.textContent = bin.key === "review" ? "below threshold" : bin.key;
      dom.bins.append(rect, title, count, tail);
      binNodes[bin.key] = { rect, count };
    });
  }

  const cellToSvg = (x, y) => ({
    cx: 260 + (x / 0.25) * 150,
    cy: 130 - (y / 0.25) * 70,
  });

  function renderCell(snapshot) {
    const current = snapshot.current;
    const objects = (snapshot.objects || []).filter((o) => o.phase === "approach" || o.phase === "carry");
    const shown = current || objects[objects.length - 1] || null;

    if (!shown) {
      dom.object.classList.add("hidden");
      dom.arm.setAttribute("x2", 260); dom.arm.setAttribute("y2", 40);
      dom.gripper.setAttribute("transform", "");
      dom.cellCaption.textContent = snapshot.running ? "waiting for the next object…" : "stopped";
      return;
    }

    const { cx, cy } = cellToSvg(shown.x, shown.y);
    dom.object.classList.remove("hidden");
    dom.objectDot.setAttribute("cx", cx); dom.objectDot.setAttribute("cy", cy);
    const confidence = shown.confidence;
    dom.objectDot.setAttribute("class", confidence >= 0.8 ? "high" : confidence >= 0.65 ? "mid" : "low");
    dom.objectLabel.setAttribute("x", cx); dom.objectLabel.setAttribute("y", cy);
    dom.objectLabel.textContent = `#${shown.id}`;

    const reaching = shown.phase === "approach" || shown.phase === "carry";
    const tip = reaching ? { x: cx, y: cy - 18 } : { x: 260, y: 40 };
    dom.arm.setAttribute("x2", tip.x); dom.arm.setAttribute("y2", tip.y);
    dom.gripper.setAttribute("transform", `translate(${tip.x - 260}, ${tip.y - 40})`);

    const bits = [`#${shown.id} ${shown.label}`, `conf ${confidence.toFixed(2)}`, shown.phase];
    if (shown.destination) bits.push(shown.success === false ? "grasp failed" : `-> ${shown.destination}`);
    dom.cellCaption.textContent = bits.join("  ·  ");
  }

  const STAT_DEFS = [
    { key: "published", label: "detections", cls: "" },
    { key: "attempted", label: "picks tried", cls: "good" },
    { key: "skipped", label: "skipped", cls: "warn" },
    { key: "placed", label: "placed", cls: "good" },
    { key: "dropped", label: "dropped", cls: "bad" },
    { key: "needs_review", label: "needs human", cls: "warn" },
  ];

  function renderStats(snapshot) {
    const counters = snapshot.counters;
    dom.stats.innerHTML = STAT_DEFS.map((def) =>
      `<div class="stat ${def.cls}"><span>${counters[def.key] ?? 0}</span><small>${def.label}</small></div>`
    ).join("");
    dom.runState.textContent = snapshot.running ? "running" : `paused: ${snapshot.pause_reason || "stopped"}`;
    dom.runState.style.color = snapshot.running ? "#5ec27b" : "#e0a458";
    dom.rateSuccess.textContent = snapshot.rates.success === null ? "—" : `${Math.round(snapshot.rates.success * 100)}%`;
    dom.rateReview.textContent = snapshot.rates.review === null ? "—" : `${Math.round(snapshot.rates.review * 100)}%`;
    dom.rateInterventions.textContent = counters.support_requests;
  }

  function renderSpark(snapshot) {
    const history = snapshot.confidence_history || [];
    const threshold = snapshot.config.min_confidence;
    const y = (value) => 66 - value * 62;
    dom.sparkThreshold.setAttribute("y1", y(threshold));
    dom.sparkThreshold.setAttribute("y2", y(threshold));
    if (!history.length) { dom.sparkLine.setAttribute("points", ""); return; }
    const step = 300 / Math.max(history.length - 1, 1);
    dom.sparkLine.setAttribute("points", history.map((value, index) => `${(index * step).toFixed(1)},${y(value).toFixed(1)}`).join(" "));
  }

  function renderGraph(snapshot) {
    const graph = snapshot.graph || { nodes: [], topics: [] };
    dom.graphNote.textContent = graph.is_real ? "live rclpy introspection" : "modelled (no ROS 2 running)";
    dom.graph.innerHTML = [
      ...graph.nodes.map((node) => `<div class="graph-row node"><span>${node.name}</span><span>${node.role}</span></div>`),
      ...graph.topics.map((topic) => `<div class="graph-row topic"><span>${topic.name}</span><span>${topic.type} · ${topic.published} msg</span></div>`),
    ].join("");
  }

  function renderLog(snapshot) {
    const lines = snapshot.log || [];
    const signature = `${lines.length}:${lines.length ? lines[lines.length - 1].text : ""}`;
    if (signature === lastLogSignature) return;
    lastLogSignature = signature;
    if (!lines.length) { dom.log.innerHTML = '<div class="empty">no events yet</div>'; return; }
    const atBottom = dom.log.scrollTop + dom.log.clientHeight >= dom.log.scrollHeight - 24;
    dom.log.innerHTML = lines.map((line) => {
      const stamp = formatStamp(line.t);
      return `<div><span class="t">${stamp}</span><span class="${line.level}">${escapeHtml(line.text)}</span></div>`;
    }).join("");
    if (atBottom) dom.log.scrollTop = dom.log.scrollHeight;
  }

  const formatStamp = (seconds) => {
    const total = Math.max(0, Math.floor(seconds));
    const mm = String(Math.floor(total / 60)).padStart(2, "0");
    const ss = String(total % 60).padStart(2, "0");
    return `${mm}:${ss}`;
  };

  const escapeHtml = (text) => String(text).replace(/[&<>"']/g, (char) =>
    ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[char]));

  function renderMode(snapshot) {
    dom.modeLabel.textContent = snapshot.mode_label;
    dom.modeBadge.textContent = snapshot.mode === "ros2" ? "ROS 2 / DDS LIVE" : "SIMULATION";
    dom.modeBadge.className = `badge ${snapshot.mode === "ros2" ? "real" : "sim"}`;
    dom.uptime.textContent = `t=${snapshot.uptime_s.toFixed(1)}s · tick ${snapshot.tick}`;
    dom.footerMode.textContent = `mode=${snapshot.mode} · ros available here: ${snapshot.ros_available ? "yes" : "no"}`;

    if (snapshot.mode === "ros2") {
      dom.banner.className = "banner live";
      dom.banner.innerHTML = "<strong>Live ROS 2.</strong><span>State below comes from real DDS traffic on this machine. Commands are published to <code>" +
        escapeHtml(snapshot.config.command_topic) + "</code> for the real picker node.</span>";
    } else {
      dom.banner.className = "banner";
      dom.banner.innerHTML = "<strong>Simulation mode.</strong><span>ROS 2 is not running. These decisions come from the same <code>pipeline.py</code> the ROS 2 nodes call, but nothing here proves DDS. Run <code>tools/verify.sh --ros2</code> where ROS 2 is installed.</span>";
    }

    dom.cmdTopic.textContent = snapshot.config.command_topic;
    dom.cellHint.textContent = snapshot.mode === "ros2"
      ? "live detections from the ROS 2 topic"
      : "object position from the detection message";
  }

  function render(snapshot) {
    renderMode(snapshot);
    renderCell(snapshot);
    renderStats(snapshot);
    renderSpark(snapshot);
    renderGraph(snapshot);
    renderLog(snapshot);

    if (!dragging) {
      dom.threshold.value = snapshot.config.min_confidence;
      dom.thresholdValue.textContent = snapshot.config.min_confidence.toFixed(2);
      dom.rate.value = snapshot.config.rate_hz;
      dom.rateValue.textContent = snapshot.config.rate_hz.toFixed(2);
      dom.autoPause.checked = snapshot.config.auto_pause_on_review;
    }
    dom.thresholdNote.textContent =
      `Lower threshold = more picks attempted (and more failed grasps). Higher = fewer attempts, more items need a human. Currently ${snapshot.counters.needs_review} item(s) flagged for review.`;

    // bin highlights
    const bins = snapshot.bins || {};
    BIN_LABELS.forEach((bin) => {
      const node = binNodes[bin.key];
      if (!node) return;
      node.count.textContent = bins[bin.key] ?? 0;
      const active = snapshot.current && snapshot.current.phase === "settle" && snapshot.current.destination === bin.key;
      node.rect.setAttribute("class", active ? "bin-rect flash" : "bin-rect");
    });
  }

  // ------------------------------------------------------------------ wiring
  function wire() {
    buildGrid();
    buildBins();

    el("btn-start").addEventListener("click", () => send({ action: "start" }));
    el("btn-stop").addEventListener("click", () => send({ action: "stop" }));
    el("btn-support").addEventListener("click", () => send({ action: "call_support" }));
    el("btn-resolve").addEventListener("click", () => fetch("/api/resolve_review", { method: "POST" }));
    el("btn-reset").addEventListener("click", () => simConfig({ reset: true }));

    dom.threshold.addEventListener("input", () => {
      dragging = true;
      dom.thresholdValue.textContent = Number(dom.threshold.value).toFixed(2);
    });
    dom.threshold.addEventListener("change", () => {
      dragging = false;
      send({ action: "set_min_confidence", value: Number(dom.threshold.value) });
    });

    dom.rate.addEventListener("input", () => { dom.rateValue.textContent = Number(dom.rate.value).toFixed(2); });
    dom.rate.addEventListener("change", () => simConfig({ rate_hz: Number(dom.rate.value) }));
    dom.autoPause.addEventListener("change", () => simConfig({ auto_pause_on_review: dom.autoPause.checked }));

    dom.advToggle.addEventListener("click", () => {
      const hidden = dom.advBody.style.display === "none";
      dom.advBody.style.display = hidden ? "" : "none";
      dom.advToggle.textContent = hidden ? "hide" : "show";
      dom.advToggle.setAttribute("aria-expanded", String(hidden));
    });
  }

  wire();
  renderLink();
  connect();
})();
