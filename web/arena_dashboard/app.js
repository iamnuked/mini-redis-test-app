const MAX_LOG_ITEMS = 200;
const MAX_GRAPH_ITEMS = 72;

const LANE_CHART_COLORS = {
  redis_db: {
    stroke: "#b79dff",
    fill: "rgba(155, 124, 255, 0.16)",
  },
  db_only: {
    stroke: "#f4be51",
    fill: "rgba(244, 190, 81, 0.16)",
  },
};

const COMMAND_COLORS = {
  SET: "#63d48d",
  GET: "#edf3ff",
  DEL: "#ff7f78",
  ERROR: "#f0bd66",
};

const OPS_COLORS = {
  redisReads: "#72a7ff",
  mongoReads: "#f4be51",
  mongoWrites: "#63d48d",
};

const manualForm = document.getElementById("manual-form");
const commandInput = document.getElementById("command");
const valueInput = document.getElementById("value");
const scenarioButtons = document.querySelectorAll("[data-scenario-id]");
const resetButton = document.getElementById("reset-button");

function createLaneState() {
  return {
    latestResult: null,
    latestRequest: null,
    latestSeenAt: null,
    samples: 0,
    cacheHits: 0,
    cacheMisses: 0,
    answers: [],
    latencySeries: [],
    opsSeries: [],
  };
}

const state = {
  lanes: {
    redis_db: createLaneState(),
    db_only: createLaneState(),
  },
  seenRequests: new Set(),
  health: null,
  sseConnected: false,
  requestStatus: {
    label: "Idle",
    tone: "idle",
  },
  activeScenario: null,
  lastRequestLabel: "-",
  lastEventLabel: "-",
  lastHealthAt: null,
};

function setRequestStatus(label, tone = "idle") {
  state.requestStatus = { label, tone };
  renderStatusPanel();
}

function toneForStatus(value) {
  switch (value) {
    case "ok":
    case "connected":
      return "ok";
    case "degraded":
    case "busy":
    case "running":
      return "busy";
    case "error":
    case "disconnected":
    case "offline":
      return "error";
    default:
      return "idle";
  }
}

function toneForAnswer(kind) {
  switch (kind) {
    case "ok":
    case "value":
    case "deleted":
      return "ok";
    case "nil":
    case "not_found":
      return "idle";
    case "error":
      return "error";
    default:
      return "idle";
  }
}

function formatMetric(value) {
  if (value == null || Number.isNaN(value)) {
    return "-";
  }
  return `${Number(value).toFixed(3)} ms`;
}

function formatCache(cache) {
  if (!cache) {
    return "-";
  }
  if (cache.hit) {
    return "hit";
  }
  if (cache.miss) {
    return "miss";
  }
  return "n/a";
}

function formatList(values) {
  if (!values || values.length === 0) {
    return "-";
  }
  return values.join(" -> ");
}

function formatTime(date) {
  if (!date) {
    return "-";
  }
  return date.toLocaleTimeString("ko-KR", {
    hour12: false,
    hour: "2-digit",
    minute: "2-digit",
  });
}

function requestLabel(request) {
  if (!request) {
    return "-";
  }
  return `${request.mode.toUpperCase()} / ${request.command} / ${request.key}`;
}

function summarizeRequest(request, result) {
  return `${request.command} ${request.key}`;
}

function latestServiceTime(result) {
  return result?.metrics?.service_time_ms ?? result?.latency_ms ?? null;
}

function latestDbTime(result) {
  return result?.metrics?.db_time_ms ?? null;
}

function latestRedisTime(result) {
  return result?.metrics?.redis_time_ms ?? null;
}

function latestGatewayRtt(result) {
  return result?.metrics?.gateway_round_trip_ms ?? null;
}

function deriveAnswerText(request, result) {
  if (result.answer_text) {
    return result.answer_text;
  }
  if (request.command === "SET") {
    return "OK";
  }
  if (request.command === "GET") {
    return result.value_preview ?? "(nil)";
  }
  if (request.command === "DEL") {
    return result.storage_changes?.some((entry) => entry.includes("deleted"))
      ? "deleted"
      : "not found";
  }
  return "-";
}

function deriveAnswerKind(request, result) {
  if (result.answer_kind) {
    return result.answer_kind;
  }
  if (request.command === "GET") {
    return result.value_preview == null ? "nil" : "value";
  }
  return result.status === "error" ? "error" : "ok";
}

function pushLog(log, entry) {
  log.unshift(entry);
  if (log.length > MAX_LOG_ITEMS) {
    log.length = MAX_LOG_ITEMS;
  }
}

function pushGraphSample(series, entry) {
  series.push(entry);
  if (series.length > MAX_GRAPH_ITEMS) {
    series.shift();
  }
}

function setTonedText(id, label, tone) {
  const element = document.getElementById(id);
  element.textContent = label;
  element.title = label;
  element.dataset.tone = tone;
}

function setMonitorField(rootId, field, value, tone = null) {
  const node = document
    .getElementById(rootId)
    .querySelector(`[data-monitor-field="${field}"]`);
  node.textContent = value;
  node.title = value;
  if (tone) {
    node.dataset.tone = tone;
  } else {
    delete node.dataset.tone;
  }
}

function renderMonitoring(rootId, laneKey) {
  const laneState = state.lanes[laneKey];
  const result = laneState.latestResult;
  const request = laneState.latestRequest;
  const answerKind = result ? deriveAnswerKind(request, result) : "-";

  setMonitorField(rootId, "status", result?.status ?? "-", toneForStatus(result?.status));
  setMonitorField(rootId, "samples", String(laneState.samples));
  setMonitorField(rootId, "request", requestLabel(request));
  setMonitorField(rootId, "cache", result ? formatCache(result.cache) : "-");
  setMonitorField(rootId, "service_time", formatMetric(latestServiceTime(result)));
  setMonitorField(rootId, "db_time", formatMetric(latestDbTime(result)));
  setMonitorField(rootId, "redis_time", formatMetric(latestRedisTime(result)));
  setMonitorField(rootId, "gateway_rtt", formatMetric(latestGatewayRtt(result)));
  setMonitorField(rootId, "mongo_reads", result ? String(result.mongo_reads ?? 0) : "-");
  setMonitorField(rootId, "answer_kind", answerKind, toneForAnswer(answerKind));
  setMonitorField(rootId, "path", result ? formatList(result.path) : "-");
  setMonitorField(rootId, "storage", result ? formatList(result.storage_changes) : "-");
}

function answerDisplayEntry(request, result, timeLabel) {
  if (result.status === "error") {
    return {
      timeLabel,
      command: request.command,
      keyText: "error",
      valueText: "error",
      keyTone: "error",
      valueTone: "error",
    };
  }

  if (request.command === "SET") {
    return {
      timeLabel,
      command: request.command,
      keyText: request.key || "nil",
      valueText: request.value ?? result.value_preview ?? "nil",
      keyTone: request.key ? "set" : "nil",
      valueTone: result.value_preview != null || request.value != null ? "set" : "nil",
    };
  }

  if (request.command === "GET") {
    const hasValue = result.value_preview != null;
    return {
      timeLabel,
      command: request.command,
      keyText: request.key || "nil",
      valueText: hasValue ? result.value_preview : "nil",
      keyTone: request.key ? "get" : "nil",
      valueTone: hasValue ? "get" : "nil",
    };
  }

  const deleted = result.answer_kind === "deleted";
  return {
    timeLabel,
    command: request.command,
    keyText: request.key || "nil",
    valueText: deleted ? "deleted" : "nil",
    keyTone: request.key ? "del" : "nil",
    valueTone: deleted ? "del" : "nil",
  };
}

function buildAnswerItem(entry) {
  const item = document.createElement("li");
  item.className = "answer-item";
  item.title = `${entry.timeLabel} ${entry.command} ${entry.keyText} ${entry.valueText}`;

  const time = document.createElement("span");
  time.className = "answer-cell answer-time";
  time.textContent = entry.timeLabel;
  item.appendChild(time);

  const command = document.createElement("span");
  command.className = "answer-cell answer-command";
  command.textContent = entry.command;
  item.appendChild(command);

  const key = document.createElement("span");
  key.className = "answer-cell answer-key";
  key.textContent = entry.keyText;
  key.dataset.tone = entry.keyTone;
  item.appendChild(key);

  const value = document.createElement("span");
  value.className = "answer-cell answer-value";
  value.textContent = entry.valueText;
  value.dataset.tone = entry.valueTone;
  item.appendChild(value);

  return item;
}

function renderAnswerList(listId, countId, entries) {
  const list = document.getElementById(listId);
  const fragment = document.createDocumentFragment();

  entries.forEach((entry) => {
    fragment.appendChild(buildAnswerItem(entry));
  });

  list.replaceChildren(fragment);
  document.getElementById(countId).textContent = String(entries.length);
}

function countPathToken(path, token) {
  return (path ?? []).reduce((count, item) => count + (item === token ? 1 : 0), 0);
}

function latencyDisplayValue(result) {
  return Number(latestServiceTime(result) ?? 0);
}

function buildLatencySample(request, result, timeLabel) {
  return {
    requestId: request.request_id,
    timeLabel,
    command: request.command,
    value: latencyDisplayValue(result),
    status: result.status,
  };
}

function buildOpsSample(request, result, timeLabel) {
  const path = result.path ?? [];
  return {
    requestId: request.request_id,
    timeLabel,
    command: request.command,
    status: result.status,
    redisReads: countPathToken(path, "redis_read"),
    mongoReads: countPathToken(path, "mongo_read"),
    mongoWrites: countPathToken(path, "mongo_write") + countPathToken(path, "mongo_delete"),
  };
}

function getCanvasSurface(canvasId) {
  const canvas = document.getElementById(canvasId);
  if (!canvas) {
    return null;
  }

  const rect = canvas.getBoundingClientRect();
  const width = Math.max(1, Math.round(rect.width));
  const height = Math.max(1, Math.round(rect.height));
  const dpr = window.devicePixelRatio || 1;

  if (canvas.width !== width * dpr || canvas.height !== height * dpr) {
    canvas.width = width * dpr;
    canvas.height = height * dpr;
  }

  const ctx = canvas.getContext("2d");
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  ctx.clearRect(0, 0, width, height);

  return { canvas, ctx, width, height };
}

function drawRoundedRect(ctx, x, y, width, height, radius) {
  const r = Math.min(radius, width / 2, height / 2);
  ctx.beginPath();
  ctx.moveTo(x + r, y);
  ctx.arcTo(x + width, y, x + width, y + height, r);
  ctx.arcTo(x + width, y + height, x, y + height, r);
  ctx.arcTo(x, y + height, x, y, r);
  ctx.arcTo(x, y, x + width, y, r);
  ctx.closePath();
}

function drawEmptyChart(surface, message) {
  const { ctx, width, height } = surface;
  ctx.fillStyle = "rgba(255, 255, 255, 0.04)";
  drawRoundedRect(ctx, 0, 0, width, height, 10);
  ctx.fill();
  ctx.fillStyle = "rgba(173, 194, 226, 0.55)";
  ctx.font = '600 11px "SFMono-Regular", "Menlo", monospace';
  ctx.textAlign = "center";
  ctx.textBaseline = "middle";
  ctx.fillText(message, width / 2, height / 2);
}

function percentile(values, ratio) {
  if (values.length === 0) {
    return 0;
  }
  const sorted = [...values].sort((a, b) => a - b);
  const index = Math.min(
    sorted.length - 1,
    Math.max(0, Math.floor((sorted.length - 1) * ratio))
  );
  return sorted[index];
}

function sharedLatencyCeiling() {
  const combined = [
    ...state.lanes.redis_db.latencySeries,
    ...state.lanes.db_only.latencySeries,
  ]
    .map((sample) => sample.value)
    .filter((value) => Number.isFinite(value) && value >= 0);

  if (combined.length === 0) {
    return 4;
  }

  const p95 = percentile(combined, 0.95);
  const max = Math.max(...combined);
  return Math.max(4, Math.min(40, Math.max(p95 * 1.25, max * 1.05)));
}

function commandTone(command, status) {
  if (status === "error") {
    return COMMAND_COLORS.ERROR;
  }
  return COMMAND_COLORS[command] ?? COMMAND_COLORS.GET;
}

function slotX(index, left, plotWidth) {
  if (MAX_GRAPH_ITEMS <= 1) {
    return left + plotWidth;
  }
  return left + (index / (MAX_GRAPH_ITEMS - 1)) * plotWidth;
}

function renderLatencyChart(canvasId, laneKey) {
  const surface = getCanvasSurface(canvasId);
  if (!surface) {
    return;
  }

  const { ctx, width, height } = surface;
  const samples = state.lanes[laneKey].latencySeries;

  if (samples.length === 0) {
    drawEmptyChart(surface, "Awaiting samples");
    return;
  }

  const colors = LANE_CHART_COLORS[laneKey];
  const left = 10;
  const right = 8;
  const top = 10;
  const bottom = 14;
  const plotWidth = Math.max(1, width - left - right);
  const plotHeight = Math.max(1, height - top - bottom);
  const ceiling = sharedLatencyCeiling();

  ctx.fillStyle = "rgba(255, 255, 255, 0.025)";
  drawRoundedRect(ctx, 0, 0, width, height, 10);
  ctx.fill();

  ctx.strokeStyle = "rgba(255, 255, 255, 0.06)";
  ctx.lineWidth = 1;
  for (let step = 0; step < 4; step += 1) {
    const y = top + (plotHeight / 3) * step;
    ctx.beginPath();
    ctx.moveTo(left, y);
    ctx.lineTo(width - right, y);
    ctx.stroke();
  }

  const startSlot = MAX_GRAPH_ITEMS - samples.length;
  const points = samples.map((sample, index) => {
    const slotIndex = startSlot + index;
    const x = slotX(slotIndex, left, plotWidth);
    const ratio = Math.min(sample.value / ceiling, 1);
    const y = top + plotHeight - ratio * plotHeight;
    return { x, y, sample };
  });

  ctx.beginPath();
  ctx.moveTo(points[0].x, top + plotHeight);
  points.forEach((point) => ctx.lineTo(point.x, point.y));
  ctx.lineTo(points[points.length - 1].x, top + plotHeight);
  ctx.closePath();
  ctx.fillStyle = colors.fill;
  ctx.fill();

  ctx.beginPath();
  ctx.moveTo(points[0].x, points[0].y);
  points.forEach((point) => ctx.lineTo(point.x, point.y));
  ctx.strokeStyle = colors.stroke;
  ctx.lineWidth = 1.8;
  ctx.lineJoin = "round";
  ctx.lineCap = "round";
  ctx.stroke();

  points.forEach((point, index) => {
    ctx.beginPath();
    ctx.fillStyle = commandTone(point.sample.command, point.sample.status);
    ctx.arc(point.x, point.y, index === points.length - 1 ? 3.1 : 2.2, 0, Math.PI * 2);
    ctx.fill();
  });
}

function renderOpsChart(canvasId, laneKey) {
  const surface = getCanvasSurface(canvasId);
  if (!surface) {
    return;
  }

  const { ctx, width, height } = surface;
  const samples = state.lanes[laneKey].opsSeries;

  ctx.fillStyle = "rgba(255, 255, 255, 0.025)";
  drawRoundedRect(ctx, 0, 0, width, height, 10);
  ctx.fill();

  const rows = [
    { key: "redisReads", label: "RR", color: OPS_COLORS.redisReads },
    { key: "mongoReads", label: "MR", color: OPS_COLORS.mongoReads },
    { key: "mongoWrites", label: "MW", color: OPS_COLORS.mongoWrites },
  ];

  const left = 30;
  const right = 8;
  const top = 10;
  const bottom = 10;
  const plotWidth = Math.max(1, width - left - right);
  const plotHeight = Math.max(1, height - top - bottom);
  const rowHeight = plotHeight / rows.length;

  ctx.font = '600 10px "SFMono-Regular", "Menlo", monospace';
  ctx.textAlign = "left";
  ctx.textBaseline = "middle";

  rows.forEach((row, index) => {
    const rowTop = top + index * rowHeight;
    const centerY = rowTop + rowHeight / 2;

    ctx.strokeStyle = "rgba(255, 255, 255, 0.06)";
    ctx.beginPath();
    ctx.moveTo(left, centerY);
    ctx.lineTo(width - right, centerY);
    ctx.stroke();

    ctx.fillStyle = "rgba(173, 194, 226, 0.6)";
    ctx.fillText(row.label, 4, centerY);
  });

  if (samples.length === 0) {
    ctx.fillStyle = "rgba(173, 194, 226, 0.55)";
    ctx.textAlign = "center";
    ctx.fillText("Awaiting samples", width / 2, height / 2);
    return;
  }

  const startSlot = MAX_GRAPH_ITEMS - samples.length;
  const barWidth = Math.max(3, Math.min(8, plotWidth / MAX_GRAPH_ITEMS - 1));

  samples.forEach((sample, sampleIndex) => {
    const slotIndex = startSlot + sampleIndex;
    const x = slotX(slotIndex, left, plotWidth) - barWidth / 2;

    rows.forEach((row, rowIndex) => {
      const count = sample[row.key] ?? 0;
      if (count <= 0) {
        return;
      }

      const rowTop = top + rowIndex * rowHeight;
      const barHeight = Math.min(14, rowHeight * 0.56 + Math.min(count - 1, 2) * 2);
      const y = rowTop + (rowHeight - barHeight) / 2;

      ctx.fillStyle = row.color;
      drawRoundedRect(ctx, x, y, barWidth, barHeight, 3);
      ctx.fill();
    });
  });
}

function renderLaneGraphs() {
  document.getElementById("redis-latency-count").textContent = String(
    state.lanes.redis_db.latencySeries.length
  );
  document.getElementById("db-latency-count").textContent = String(
    state.lanes.db_only.latencySeries.length
  );
  document.getElementById("redis-mongo-count").textContent = String(
    state.lanes.redis_db.opsSeries.length
  );
  document.getElementById("db-mongo-count").textContent = String(
    state.lanes.db_only.opsSeries.length
  );

  renderLatencyChart("redis-latency-chart", "redis_db");
  renderLatencyChart("db-latency-chart", "db_only");
  renderOpsChart("redis-mongo-chart", "redis_db");
  renderOpsChart("db-mongo-chart", "db_only");
}

let graphRenderFrame = null;

function scheduleLaneGraphs() {
  if (graphRenderFrame != null) {
    return;
  }
  graphRenderFrame = window.requestAnimationFrame(() => {
    graphRenderFrame = null;
    renderLaneGraphs();
  });
}

function renderLanePanels() {
  renderAnswerList("redis-answer-log", "redis-answer-count", state.lanes.redis_db.answers);
  renderAnswerList("db-answer-log", "db-answer-count", state.lanes.db_only.answers);
  scheduleLaneGraphs();
}

function renderStatusPanel() {
  const health = state.health;
  const scenarioLabel = state.activeScenario ? `running / ${state.activeScenario}` : "Idle";

  const requestPill = document.getElementById("status-request-pill");
  requestPill.textContent = state.requestStatus.label;
  requestPill.dataset.tone = state.requestStatus.tone;

  setTonedText("status-overall", health?.status ?? "offline", toneForStatus(health?.status ?? "offline"));
  setTonedText("status-sse", state.sseConnected ? "connected" : "disconnected", toneForStatus(state.sseConnected ? "connected" : "disconnected"));
  setTonedText("status-gateway", health?.gateway?.status ?? "offline", toneForStatus(health?.gateway?.status ?? "offline"));
  setTonedText("status-lane-a", health?.redis_lane?.status ?? "offline", toneForStatus(health?.redis_lane?.status ?? "offline"));
  setTonedText("status-lane-b", health?.db_only_lane?.status ?? "offline", toneForStatus(health?.db_only_lane?.status ?? "offline"));
  setTonedText(
    "status-redis",
    health?.redis_lane?.redis?.status ?? "offline",
    toneForStatus(health?.redis_lane?.redis?.status ?? "offline")
  );
  setTonedText(
    "status-mongo-a",
    health?.redis_lane?.mongo?.status ?? "offline",
    toneForStatus(health?.redis_lane?.mongo?.status ?? "offline")
  );
  setTonedText(
    "status-mongo-b",
    health?.db_only_lane?.mongo?.status ?? "offline",
    toneForStatus(health?.db_only_lane?.mongo?.status ?? "offline")
  );

  document.getElementById("status-tracked-keys").textContent = String(
    health?.gateway?.tracked_keys ?? 0
  );
  document.getElementById("status-retained-events").textContent = String(
    health?.gateway?.retained_events ?? 0
  );
  document.getElementById("status-scenario").textContent = scenarioLabel;
  document.getElementById("status-scenario").title = scenarioLabel;
  document.getElementById("status-last-health").textContent = formatTime(state.lastHealthAt);
  document.getElementById("status-last-health").title = formatTime(state.lastHealthAt);
  document.getElementById("status-last-request").textContent = state.lastRequestLabel;
  document.getElementById("status-last-request").title = state.lastRequestLabel;
  document.getElementById("status-last-event").textContent = state.lastEventLabel;
  document.getElementById("status-last-event").title = state.lastEventLabel;
}

function renderAll() {
  renderMonitoring("monitor-redis", "redis_db");
  renderMonitoring("monitor-db", "db_only");
  renderLanePanels();
  renderStatusPanel();
}

function applyExecution(execution, receivedAt = new Date()) {
  if (state.seenRequests.has(execution.request.request_id)) {
    return;
  }
  state.seenRequests.add(execution.request.request_id);
  state.lastRequestLabel = requestLabel(execution.request);

  [
    ["redis_db", execution.redis_db],
    ["db_only", execution.db_only],
  ].forEach(([laneKey, result]) => {
    const laneState = state.lanes[laneKey];
    const timeLabel = formatTime(receivedAt);

    laneState.latestResult = result;
    laneState.latestRequest = execution.request;
    laneState.latestSeenAt = receivedAt;
    laneState.samples += 1;

    if (result.cache?.hit) {
      laneState.cacheHits += 1;
    }
    if (result.cache?.miss) {
      laneState.cacheMisses += 1;
    }

    pushLog(laneState.answers, {
      requestId: execution.request.request_id,
      ...answerDisplayEntry(execution.request, result, timeLabel),
    });

    pushGraphSample(
      laneState.latencySeries,
      buildLatencySample(execution.request, result, timeLabel)
    );
    pushGraphSample(
      laneState.opsSeries,
      buildOpsSample(execution.request, result, timeLabel)
    );
  });

  renderAll();
}

function resetLocalState() {
  state.lanes.redis_db = createLaneState();
  state.lanes.db_only = createLaneState();
  state.seenRequests = new Set();
  state.lastRequestLabel = "-";
  state.lastEventLabel = "scenario_reset";
  state.activeScenario = null;
  renderAll();
}

async function fetchHealth() {
  try {
    const response = await fetch("/api/health");
    if (!response.ok) {
      throw new Error("Health request failed");
    }
    state.health = await response.json();
    state.lastHealthAt = new Date();
  } catch (error) {
    state.health = null;
    state.lastHealthAt = new Date();
  }
  renderStatusPanel();
}

async function runManualCommand(event) {
  event.preventDefault();
  setRequestStatus("Running", "busy");

  const command = commandInput.value;
  const payload = {
    command,
    key: document.getElementById("key").value,
    value: command === "SET" ? valueInput.value : null,
    ttl_enabled: document.getElementById("manual-ttl-enabled").checked,
  };

  try {
    const response = await fetch("/api/manual-command", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify(payload),
    });

    if (!response.ok) {
      const errorPayload = await response.json();
      throw new Error(errorPayload.detail ?? "Manual command failed");
    }

    const execution = await response.json();
    applyExecution(execution);
    state.lastEventLabel = "manual_command_completed";
    setRequestStatus("Completed", "ok");
    fetchHealth();
  } catch (error) {
    setRequestStatus(error.message, "error");
  }
}

async function runScenario(event) {
  const scenarioId = event.currentTarget.dataset.scenarioId;
  const users = Number(document.getElementById("scenario-users").value);
  const durationSeconds = Number(document.getElementById("scenario-duration").value);

  state.activeScenario = scenarioId;
  state.lastEventLabel = `scenario_requested / ${scenarioId}`;
  setRequestStatus(`Scenario ${scenarioId}`, "busy");
  renderStatusPanel();

  try {
    const response = await fetch("/api/scenarios/run", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        scenario_id: scenarioId,
        users,
        duration_seconds: durationSeconds,
        ttl_enabled: document.getElementById("scenario-ttl-enabled").checked,
      }),
    });
    const payload = await response.json();
    setRequestStatus(payload.message, "ok");
    fetchHealth();
  } catch (error) {
    state.activeScenario = null;
    setRequestStatus(error.message, "error");
    renderStatusPanel();
  }
}

async function resetArena() {
  setRequestStatus("Resetting", "busy");
  try {
    const response = await fetch("/api/scenarios/reset", { method: "POST" });
    const payload = await response.json();
    resetLocalState();
    setRequestStatus(payload.message, "ok");
    fetchHealth();
  } catch (error) {
    setRequestStatus(error.message, "error");
  }
}

function extractScenarioId(message) {
  if (!message || !message.includes(":")) {
    return null;
  }
  return message.split(":").slice(1).join(":").trim() || null;
}

function connectEvents() {
  const source = new EventSource("/api/events");

  source.addEventListener("open", () => {
    state.sseConnected = true;
    renderStatusPanel();
  });

  source.addEventListener("arena", (event) => {
    const envelope = JSON.parse(event.data);
    state.lastEventLabel = envelope.type;

    if (
      envelope.type === "manual_command_completed" ||
      envelope.type === "scenario_execution_completed"
    ) {
      applyExecution(envelope.payload);
    }

    if (envelope.type === "scenario_accepted") {
      state.activeScenario = extractScenarioId(envelope.payload.message) ?? state.activeScenario;
      setRequestStatus(envelope.payload.message, "ok");
      renderStatusPanel();
      fetchHealth();
    }

    if (envelope.type === "scenario_finished") {
      state.activeScenario = null;
      setRequestStatus(envelope.payload.message, "ok");
      renderStatusPanel();
      fetchHealth();
    }

    if (envelope.type === "scenario_reset") {
      resetLocalState();
      setRequestStatus(envelope.payload.message, "ok");
    }
  });

  source.addEventListener("error", () => {
    state.sseConnected = false;
    setRequestStatus("SSE disconnected", "error");
  });
}

function syncManualValueState() {
  const isSet = commandInput.value === "SET";
  valueInput.disabled = !isSet;
  valueInput.placeholder = isSet ? '{"name":"kim"}' : "SET only";
}

manualForm.addEventListener("submit", runManualCommand);
commandInput.addEventListener("change", syncManualValueState);
scenarioButtons.forEach((button) => button.addEventListener("click", runScenario));
resetButton.addEventListener("click", resetArena);

syncManualValueState();
renderAll();
connectEvents();
fetchHealth();
window.addEventListener("resize", scheduleLaneGraphs);
window.setInterval(fetchHealth, 4000);
