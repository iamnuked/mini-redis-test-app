const MAX_LOG_ITEMS = 200;
const MAX_GRAPH_ITEMS = 72;
const ACTIVITY_SIGNAL_MS = 900;
const ANSWER_BALANCE_SLOTS = 9;

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
  HSET: "#63d48d",
  HGET: "#edf3ff",
  HGETALL: "#edf3ff",
  ERROR: "#f0bd66",
};

const OPS_COLORS = {
  redisReads: "#72a7ff",
  mongoReads: "#f4be51",
  mongoWrites: "#63d48d",
};

const STORAGE_COLORS = {
  redis: "#72a7ff",
  db: "#f4be51",
};

const manualForm = document.getElementById("manual-form");
const commandInput = document.getElementById("command");
const fieldInput = document.getElementById("field");
const valueInput = document.getElementById("value");
const scenarioButtons = document.querySelectorAll(".scenario-button");
const resetButton = document.getElementById("reset-button");
const memoryProfileButtons = document.querySelectorAll("[data-memory-profile]");
const ttlProfileButtons = document.querySelectorAll("[data-ttl-profile]");

function createLaneState() {
  return {
    latestResult: null,
    latestRequest: null,
    latestSeenAt: null,
    samples: 0,
    answers: [],
    latencySeries: [],
    opsSeries: [],
    storageCurrent: null,
    activityActive: false,
  };
}

function createReferenceState() {
  return {
    latencySeries: [],
    opsSeries: [],
  };
}

function snapshotVisibleSeries(laneKey) {
  return {
    latencySeries: [
      ...state.references[laneKey].latencySeries,
      ...state.lanes[laneKey].latencySeries,
    ].slice(-MAX_GRAPH_ITEMS),
    opsSeries: [
      ...state.references[laneKey].opsSeries,
      ...state.lanes[laneKey].opsSeries,
    ].slice(-MAX_GRAPH_ITEMS),
  };
}

const activityTimers = {
  redis_db: null,
  db_only: null,
};

const state = {
  lanes: {
    redis_db: createLaneState(),
    db_only: createLaneState(),
  },
  references: {
    redis_db: createReferenceState(),
    db_only: createReferenceState(),
  },
  seenRequests: new Set(),
  health: null,
  sseConnected: false,
  requestStatus: {
    label: "Idle",
    tone: "idle",
  },
  activeScenario: null,
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

function formatMetric(value) {
  if (value == null || Number.isNaN(value)) {
    return "-";
  }
  return `${Number(value).toFixed(3)} ms`;
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

function pushLog(log, entry) {
  log.push(entry);
  if (log.length > MAX_LOG_ITEMS) {
    log.shift();
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
  if (!element) {
    return;
  }
  element.textContent = label;
  element.title = label;
  element.dataset.tone = tone;
}

function setBannerField(field, value) {
  const node = document.querySelector(`[data-banner-field="${field}"]`);
  if (!node) {
    return;
  }
  node.textContent = value;
  node.title = value;
}

function setAnswerBalanceSlot(side, index, active) {
  const node = document.querySelector(`[data-answer-balance-slot="${side}-${index}"]`);
  if (!node) {
    return;
  }
  node.dataset.active = active ? "true" : "false";
}

function renderAnswerBalance() {
  const redisResult = state.lanes.redis_db.latestResult;
  const dbResult = state.lanes.db_only.latestResult;
  const redisTime = latestServiceTime(redisResult);
  const dbTime = latestServiceTime(dbResult);

  let redisSlots = 0;
  let dbSlots = 0;

  if (
    redisResult?.status === "ok" &&
    dbResult?.status === "ok" &&
    Number.isFinite(redisTime) &&
    Number.isFinite(dbTime) &&
    redisTime > 0 &&
    dbTime > 0
  ) {
    const total = redisTime + dbTime;
    redisSlots = Math.max(
      0,
      Math.min(ANSWER_BALANCE_SLOTS, Math.round((ANSWER_BALANCE_SLOTS * dbTime) / total))
    );
    dbSlots = ANSWER_BALANCE_SLOTS - redisSlots;
  }

  for (let index = 0; index < ANSWER_BALANCE_SLOTS; index += 1) {
    setAnswerBalanceSlot(
      "redis",
      index,
      index >= ANSWER_BALANCE_SLOTS - redisSlots
    );
    setAnswerBalanceSlot("db", index, index < dbSlots);
  }
}

function renderBannerMetrics() {
  const redisResult = state.lanes.redis_db.latestResult;
  const dbResult = state.lanes.db_only.latestResult;

  setBannerField("redis_service_time", formatMetric(latestServiceTime(redisResult)));
  setBannerField("redis_gateway_rtt", formatMetric(latestGatewayRtt(redisResult)));
  setBannerField("redis_db_time", formatMetric(latestDbTime(redisResult)));
  setBannerField("redis_redis_time", formatMetric(latestRedisTime(redisResult)));

  setBannerField("db_service_time", formatMetric(latestServiceTime(dbResult)));
  setBannerField("db_gateway_rtt", formatMetric(latestGatewayRtt(dbResult)));
  setBannerField("db_db_time", formatMetric(latestDbTime(dbResult)));
  setBannerField("db_redis_time", formatMetric(latestRedisTime(dbResult)));
  renderAnswerBalance();
}

function answerDisplayEntry(request, result, timeLabel) {
  const keyText = (() => {
    if (!request.key) {
      return "nil";
    }
    if (request.command === "HGETALL") {
      return `${request.key}.*`;
    }
    if ((request.command === "HSET" || request.command === "HGET") && request.field) {
      return `${request.key}.${request.field}`;
    }
    return request.key;
  })();

  const commandTone = (() => {
    if (request.command === "SET" || request.command === "HSET") {
      return "set";
    }
    if (request.command === "DEL") {
      return "del";
    }
    return "get";
  })();

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
      keyText,
      valueText: request.value ?? result.value_preview ?? "nil",
      keyTone: request.key ? "set" : "nil",
      valueTone: result.value_preview != null || request.value != null ? "set" : "nil",
    };
  }

  if (request.command === "HSET") {
    return {
      timeLabel,
      command: request.command,
      keyText,
      valueText: request.value ?? result.value_preview ?? "nil",
      keyTone: request.key ? "set" : "nil",
      valueTone: result.value_preview != null || request.value != null ? "set" : "nil",
    };
  }

  if (request.command === "GET" || request.command === "HGET" || request.command === "HGETALL") {
    const hasValue = result.value_preview != null;
    return {
      timeLabel,
      command: request.command,
      keyText,
      valueText: hasValue ? result.value_preview : "nil",
      keyTone: request.key ? commandTone : "nil",
      valueTone: hasValue ? commandTone : "nil",
    };
  }

  const deleted = result.answer_kind === "deleted";
  return {
    timeLabel,
    command: request.command,
    keyText,
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

function renderAnswerList(listId, countId, entries, sampleCount) {
  const list = document.getElementById(listId);
  const fragment = document.createDocumentFragment();
  entries.forEach((entry) => {
    fragment.appendChild(buildAnswerItem(entry));
  });
  list.replaceChildren(fragment);
  document.getElementById(countId).textContent = String(sampleCount);
  const scrollBody = list.parentElement;
  if (scrollBody) {
    scrollBody.scrollTop = scrollBody.scrollHeight;
  }
}

function countPathToken(path, token) {
  return (path ?? []).reduce((count, item) => count + (item === token ? 1 : 0), 0);
}

function buildLatencySample(request, result, timeLabel) {
  return {
    requestId: request.request_id,
    timeLabel,
    command: request.command,
    value: Number(latestServiceTime(result) ?? 0),
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

function buildStorageSample(laneHealth, timeLabel) {
  const storage = laneHealth?.storage ?? {};
  return {
    timeLabel,
    redisAvailable: Boolean(storage.redis?.available),
    redisBytes: Number(storage.redis?.logical_bytes ?? 0),
    redisMaxBytes: Number(storage.redis?.max_memory_bytes ?? 0),
    dbBytes: Number(storage.mongo?.logical_bytes ?? 0),
    redisCount: Number(storage.redis?.key_count ?? 0),
    dbCount: Number(storage.mongo?.document_count ?? 0),
    evictedKeys: Number(storage.redis?.evicted_keys ?? 0),
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

  return { ctx, width, height };
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
  drawRoundedRect(ctx, 0, 0, width, height, 8);
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

function currentDbStorageCeiling() {
  const values = ["redis_db", "db_only"]
    .map((laneKey) => state.lanes[laneKey].storageCurrent?.dbBytes ?? 0)
    .filter((value) => Number.isFinite(value) && value >= 0);
  if (values.length === 0) {
    return 64;
  }
  return Math.max(64, Math.max(...values) * 1.08);
}

function formatBytes(value) {
  if (!Number.isFinite(value) || value <= 0) {
    return "0B";
  }
  return `${Math.round(value)}B`;
}

function pulseLaneActivity(laneKey) {
  const laneState = state.lanes[laneKey];
  laneState.activityActive = true;
  renderLaneActivitySignals();

  if (activityTimers[laneKey] != null) {
    window.clearTimeout(activityTimers[laneKey]);
  }

  activityTimers[laneKey] = window.setTimeout(() => {
    state.lanes[laneKey].activityActive = false;
    renderLaneActivitySignals();
    activityTimers[laneKey] = null;
  }, ACTIVITY_SIGNAL_MS);
}

function renderLaneActivitySignals() {
  ["redis_db", "db_only"].forEach((laneKey) => {
    const active = state.lanes[laneKey].activityActive;
    document
      .querySelectorAll(`[data-lane-activity="${laneKey}"]`)
      .forEach((element) => {
        element.dataset.active = active ? "true" : "false";
        element.title = active ? "activity detected" : "idle";
      });
  });
}

function storageSnapshotChanged(previousSample, nextSample) {
  if (!previousSample) {
    return false;
  }

  return (
    previousSample.redisBytes !== nextSample.redisBytes ||
    previousSample.redisMaxBytes !== nextSample.redisMaxBytes ||
    previousSample.dbBytes !== nextSample.dbBytes ||
    previousSample.redisCount !== nextSample.redisCount ||
    previousSample.dbCount !== nextSample.dbCount ||
    previousSample.evictedKeys !== nextSample.evictedKeys
  );
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
  const liveSamples = state.lanes[laneKey].latencySeries;
  const referenceSamples = state.references[laneKey].latencySeries;
  const boundaryIndex = referenceSamples.length > 0 ? referenceSamples.length : null;
  const samples = [...referenceSamples, ...liveSamples].slice(-MAX_GRAPH_ITEMS);
  const trimmedBoundaryIndex =
    boundaryIndex == null
      ? null
      : Math.max(0, boundaryIndex - Math.max(0, referenceSamples.length + liveSamples.length - MAX_GRAPH_ITEMS));

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
  drawRoundedRect(ctx, 0, 0, width, height, 8);
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

  if (trimmedBoundaryIndex != null && trimmedBoundaryIndex > 0) {
    const boundarySlot = startSlot + trimmedBoundaryIndex - 0.5;
    const x = slotX(boundarySlot, left, plotWidth);
    ctx.strokeStyle = "rgba(255, 255, 255, 0.78)";
    ctx.lineWidth = 1.2;
    ctx.beginPath();
    ctx.moveTo(x, top);
    ctx.lineTo(x, top + plotHeight);
    ctx.stroke();
  }
}

function renderOpsChart(canvasId, laneKey) {
  const surface = getCanvasSurface(canvasId);
  if (!surface) {
    return;
  }

  const { ctx, width, height } = surface;
  const liveSamples = state.lanes[laneKey].opsSeries;
  const referenceSamples = state.references[laneKey].opsSeries;
  const boundaryIndex = referenceSamples.length > 0 ? referenceSamples.length : null;
  const samples = [...referenceSamples, ...liveSamples].slice(-MAX_GRAPH_ITEMS);
  const trimmedBoundaryIndex =
    boundaryIndex == null
      ? null
      : Math.max(0, boundaryIndex - Math.max(0, referenceSamples.length + liveSamples.length - MAX_GRAPH_ITEMS));

  ctx.fillStyle = "rgba(255, 255, 255, 0.025)";
  drawRoundedRect(ctx, 0, 0, width, height, 8);
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

  const barWidth = Math.max(3, Math.min(8, plotWidth / MAX_GRAPH_ITEMS - 1));
  const startSlot = MAX_GRAPH_ITEMS - samples.length;

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
      drawRoundedRect(ctx, x, y, barWidth, barHeight, 2);
      ctx.fill();
    });
  });

  if (trimmedBoundaryIndex != null && trimmedBoundaryIndex > 0) {
    const boundarySlot = startSlot + trimmedBoundaryIndex - 0.5;
    const x = slotX(boundarySlot, left, plotWidth);
    ctx.strokeStyle = "rgba(255, 255, 255, 0.78)";
    ctx.lineWidth = 1.2;
    ctx.beginPath();
    ctx.moveTo(x, top);
    ctx.lineTo(x, top + plotHeight);
    ctx.stroke();
  }
}

function renderStorageChart(canvasId, laneKey) {
  const surface = getCanvasSurface(canvasId);
  if (!surface) {
    return;
  }

  const { ctx, width, height } = surface;
  const sample = state.lanes[laneKey].storageCurrent;

  ctx.fillStyle = "rgba(255, 255, 255, 0.025)";
  drawRoundedRect(ctx, 0, 0, width, height, 8);
  ctx.fill();

  const rows = [
    {
      key: "redisBytes",
      label: "RD",
      color: STORAGE_COLORS.redis,
      available: laneKey === "redis_db",
    },
    {
      key: "dbBytes",
      label: "DB",
      color: STORAGE_COLORS.db,
      available: true,
    },
  ];

  const left = 30;
  const right = 78;
  const top = 8;
  const bottom = 8;
  const plotWidth = Math.max(1, width - left - right);
  const plotHeight = Math.max(1, height - top - bottom);
  const rowHeight = plotHeight / rows.length;
  const dbCeiling = currentDbStorageCeiling();

  ctx.font = '600 10px "SFMono-Regular", "Menlo", monospace';
  ctx.textAlign = "left";
  ctx.textBaseline = "middle";

  rows.forEach((row, index) => {
    const rowTop = top + index * rowHeight;
    const baseline = rowTop + rowHeight - 4;

    ctx.strokeStyle = "rgba(255, 255, 255, 0.06)";
    ctx.beginPath();
    ctx.moveTo(left, baseline);
    ctx.lineTo(width - right, baseline);
    ctx.stroke();

    ctx.fillStyle = "rgba(173, 194, 226, 0.6)";
    ctx.fillText(row.label, 4, rowTop + rowHeight / 2);

    if (!row.available) {
      ctx.strokeStyle = "rgba(255, 255, 255, 0.12)";
      ctx.setLineDash([4, 3]);
      ctx.beginPath();
      ctx.moveTo(left + 8, rowTop + rowHeight / 2);
      ctx.lineTo(width - right - 8, rowTop + rowHeight / 2);
      ctx.stroke();
      ctx.setLineDash([]);
      ctx.fillStyle = "rgba(173, 194, 226, 0.44)";
      ctx.textAlign = "right";
      ctx.fillText("N/A", width - right - 2, rowTop + rowHeight / 2);
      ctx.textAlign = "left";
    }
  });

  if (!sample) {
    ctx.fillStyle = "rgba(173, 194, 226, 0.55)";
    ctx.textAlign = "center";
    ctx.fillText("Awaiting health", width / 2, height / 2);
    return;
  }

  rows.forEach((row, rowIndex) => {
    if (!row.available) {
      return;
    }

    const rowTop = top + rowIndex * rowHeight;
    const centerY = rowTop + rowHeight / 2;
    const trackY = rowTop + rowHeight * 0.32;
    const trackHeight = Math.max(10, rowHeight * 0.34);
    const value = sample[row.key] ?? 0;
    const ceiling =
      row.key === "redisBytes"
        ? Math.max(sample.redisMaxBytes || 0, value || 0, 64)
        : dbCeiling;
    const ratio = ceiling > 0 ? Math.min(value / ceiling, 1) : 0;
    const fillWidth = Math.max(0, plotWidth * ratio);
    const detail =
      row.key === "redisBytes"
        ? sample.redisMaxBytes > 0
          ? `${formatBytes(value)} / ${formatBytes(sample.redisMaxBytes)}`
          : formatBytes(value)
        : formatBytes(value);

    ctx.fillStyle = "rgba(255, 255, 255, 0.045)";
    drawRoundedRect(ctx, left, trackY, plotWidth, trackHeight, 4);
    ctx.fill();

    if (fillWidth > 0) {
      ctx.fillStyle = row.color;
      drawRoundedRect(ctx, left, trackY, fillWidth, trackHeight, 4);
      ctx.fill();
    }

    ctx.fillStyle = "rgba(173, 194, 226, 0.86)";
    ctx.textAlign = "right";
    ctx.fillText(detail, width - 8, centerY);
    ctx.textAlign = "left";
  });
}

function renderLaneGraphs() {
  renderLatencyChart("redis-latency-chart", "redis_db");
  renderLatencyChart("db-latency-chart", "db_only");
  renderOpsChart("redis-mongo-chart", "redis_db");
  renderOpsChart("db-mongo-chart", "db_only");
  renderStorageChart("redis-storage-chart", "redis_db");
  renderStorageChart("db-storage-chart", "db_only");
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
  renderLaneActivitySignals();
  renderAnswerList(
    "redis-answer-log",
    "redis-answer-count",
    state.lanes.redis_db.answers,
    state.lanes.redis_db.samples
  );
  renderAnswerList(
    "db-answer-log",
    "db-answer-count",
    state.lanes.db_only.answers,
    state.lanes.db_only.samples
  );
  scheduleLaneGraphs();
}

function memoryControlLabel() {
  const memory = state.health?.controls?.memory;
  if (!memory) {
    return "-";
  }
  const selectedProfile = memory.profiles?.find((profile) => profile.key === memory.selected);
  return `${selectedProfile?.label ?? memory.selected} / ${memory.locked ? "locked" : "open"}`;
}

function ttlControlLabel() {
  const ttl = state.health?.controls?.ttl;
  if (!ttl) {
    return "-";
  }
  if (ttl.selected == null) {
    return "off";
  }
  const selectedProfile = ttl.profiles?.find((profile) => profile.key === ttl.selected);
  return selectedProfile?.label ?? (ttl.seconds != null ? `${ttl.seconds}s` : "off");
}

function renderStatusPanel() {
  const health = state.health;
  const scenarioLabel = state.activeScenario ? `running / ${state.activeScenario}` : "Idle";

  const requestPill = document.getElementById("status-request-pill");
  requestPill.textContent = state.requestStatus.label;
  requestPill.dataset.tone = state.requestStatus.tone;

  setTonedText("status-overall", health?.status ?? "offline", toneForStatus(health?.status ?? "offline"));
  setTonedText(
    "status-sse",
    state.sseConnected ? "connected" : "disconnected",
    toneForStatus(state.sseConnected ? "connected" : "disconnected")
  );
  setTonedText(
    "status-gateway",
    health?.gateway?.status ?? "offline",
    toneForStatus(health?.gateway?.status ?? "offline")
  );
  setTonedText(
    "status-lane-a",
    health?.redis_lane?.status ?? "offline",
    toneForStatus(health?.redis_lane?.status ?? "offline")
  );
  setTonedText(
    "status-lane-b",
    health?.db_only_lane?.status ?? "offline",
    toneForStatus(health?.db_only_lane?.status ?? "offline")
  );
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

  document.getElementById("status-scenario").textContent = scenarioLabel;
  document.getElementById("status-scenario").title = scenarioLabel;
  document.getElementById("status-last-health").textContent = formatTime(state.lastHealthAt);
  document.getElementById("status-last-health").title = formatTime(state.lastHealthAt);
  document.getElementById("status-memory").textContent = memoryControlLabel();
  document.getElementById("status-memory").title = memoryControlLabel();
  document.getElementById("status-ttl").textContent = ttlControlLabel();
  document.getElementById("status-ttl").title = ttlControlLabel();
}

function renderControlButtons() {
  const memory = state.health?.controls?.memory;
  const ttl = state.health?.controls?.ttl;
  const memoryLocked = Boolean(memory?.locked);
  const scenarioRunning = Boolean(state.activeScenario);

  memoryProfileButtons.forEach((button) => {
    const selected = memory?.selected === button.dataset.memoryProfile;
    button.dataset.selected = selected ? "true" : "false";
    button.disabled = memoryLocked;
  });

  ttlProfileButtons.forEach((button) => {
    const isOffButton = button.dataset.ttlProfile === "off";
    const selected = isOffButton ? ttl?.selected == null : ttl?.selected === button.dataset.ttlProfile;
    button.dataset.selected = selected ? "true" : "false";
    button.disabled = scenarioRunning;
  });

  scenarioButtons.forEach((button) => {
    button.disabled = scenarioRunning;
  });
}

function renderAll() {
  renderBannerMetrics();
  renderLanePanels();
  renderStatusPanel();
  renderControlButtons();
}

function updateStorageState(health, receivedAt) {
  const timeLabel = formatTime(receivedAt);

  [
    ["redis_db", health?.redis_lane],
    ["db_only", health?.db_only_lane],
  ].forEach(([laneKey, laneHealth]) => {
    const laneState = state.lanes[laneKey];
    const nextSample = buildStorageSample(laneHealth, timeLabel);
    if (storageSnapshotChanged(laneState.storageCurrent, nextSample)) {
      pulseLaneActivity(laneKey);
    }
    laneState.storageCurrent = nextSample;
  });
}

function applyExecution(execution, receivedAt = new Date()) {
  if (state.seenRequests.has(execution.request.request_id)) {
    return;
  }
  state.seenRequests.add(execution.request.request_id);

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
    pulseLaneActivity(laneKey);
  });

  renderAll();
}

function resetLocalState() {
  ["redis_db", "db_only"].forEach((laneKey) => {
    const visibleSeries = snapshotVisibleSeries(laneKey);
    if (visibleSeries.latencySeries.length > 0 || visibleSeries.opsSeries.length > 0) {
      state.references[laneKey] = visibleSeries;
    }
  });
  state.lanes.redis_db = createLaneState();
  state.lanes.db_only = createLaneState();
  state.seenRequests = new Set();
  state.activeScenario = null;
  state.lastEventLabel = "scenario_reset";
  renderAll();
}

function clearCurrentSnapshots() {
  ["redis_db", "db_only"].forEach((laneKey) => {
    const laneState = state.lanes[laneKey];
    laneState.latestResult = null;
    laneState.latestRequest = null;
    laneState.latestSeenAt = null;
    laneState.storageCurrent = null;
    laneState.activityActive = false;
  });
}

async function fetchHealth() {
  try {
    const response = await fetch("/api/health");
    if (!response.ok) {
      throw new Error("Health request failed");
    }
    state.health = await response.json();
    state.activeScenario = state.health?.scenario?.active_label ?? null;
    state.lastHealthAt = new Date();
    updateStorageState(state.health, state.lastHealthAt);
  } catch (_error) {
    state.health = null;
    state.activeScenario = null;
    clearCurrentSnapshots();
    state.lastHealthAt = new Date();
  }
  renderAll();
}

async function runManualCommand(event) {
  event.preventDefault();
  setRequestStatus("Running", "busy");

  const command = commandInput.value;
  const requiresField = command === "HSET" || command === "HGET";
  const requiresValue = command === "SET" || command === "HSET";
  const ttlSeconds = state.health?.controls?.ttl?.seconds ?? null;
  const payload = {
    command,
    key: document.getElementById("key").value,
    field: requiresField ? fieldInput.value : null,
    value: requiresValue ? valueInput.value : null,
    ttl_enabled: ttlSeconds != null,
    ttl_seconds: ttlSeconds,
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

function scenarioLabel(scenarioId, readHotPercent) {
  if (scenarioId === "read") {
    return `read ${readHotPercent}%`;
  }
  return scenarioId;
}

async function runScenario(event) {
  const users = Number(document.getElementById("scenario-users").value);
  const durationSeconds = Number(document.getElementById("scenario-duration").value);
  const ttlSeconds = state.health?.controls?.ttl?.seconds ?? null;
  const ttlEnabled = ttlSeconds != null;
  const scenarioId = event.currentTarget.dataset.scenarioId;
  const readHotPercentRaw = event.currentTarget.dataset.readHotPercent;
  const readHotPercent = readHotPercentRaw ? Number(readHotPercentRaw) : null;
  const label = scenarioLabel(scenarioId, readHotPercent ?? 60);

  state.activeScenario = label;
  state.lastEventLabel = `scenario_requested / ${label}`;
  setRequestStatus(`Scenario ${label}`, "busy");
  renderAll();

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
        read_hot_percent: readHotPercent,
        ttl_enabled: ttlEnabled,
        ttl_seconds: ttlSeconds,
      }),
    });
    const payload = await response.json();
    if (!response.ok) {
      throw new Error(payload.detail ?? "Scenario run failed");
    }
    setRequestStatus(payload.message, "ok");
    fetchHealth();
  } catch (error) {
    state.activeScenario = null;
    setRequestStatus(error.message, "error");
    renderAll();
  }
}

async function resetArena() {
  setRequestStatus("Resetting", "busy");
  try {
    const response = await fetch("/api/scenarios/reset", { method: "POST" });
    const payload = await response.json();
    if (!response.ok) {
      throw new Error(payload.detail ?? "Reset failed");
    }
    resetLocalState();
    setRequestStatus(payload.message, "ok");
    fetchHealth();
  } catch (error) {
    setRequestStatus(error.message, "error");
  }
}

async function updateMemoryProfile(event) {
  const profileKey = event.currentTarget.dataset.memoryProfile;
  try {
    const response = await fetch("/api/controls/memory-profile", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ profile_key: profileKey }),
    });
    const payload = await response.json();
    if (!response.ok) {
      throw new Error(payload.detail ?? "Memory profile update failed");
    }
    setRequestStatus(`Memory ${profileKey}`, "ok");
    fetchHealth();
  } catch (error) {
    setRequestStatus(error.message, "error");
  }
}

async function updateTtlProfile(event) {
  const clickedProfileKey = event.currentTarget.dataset.ttlProfile;
  const profileKey = clickedProfileKey === "off" ? null : clickedProfileKey;
  try {
    const response = await fetch("/api/controls/ttl-profile", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ profile_key: profileKey }),
    });
    const payload = await response.json();
    if (!response.ok) {
      throw new Error(payload.detail ?? "TTL profile update failed");
    }
    setRequestStatus(profileKey == null ? "TTL off" : `TTL ${profileKey}`, "ok");
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
      renderAll();
      fetchHealth();
    }

    if (envelope.type === "scenario_finished") {
      state.activeScenario = null;
      setRequestStatus(envelope.payload.message, "ok");
      renderAll();
      fetchHealth();
    }

    if (envelope.type === "scenario_reset") {
      resetLocalState();
      setRequestStatus(envelope.payload.message, "ok");
      fetchHealth();
    }
  });

  source.addEventListener("error", () => {
    state.sseConnected = false;
    setRequestStatus("SSE disconnected", "error");
    fetchHealth();
  });
}

function syncManualValueState() {
  const command = commandInput.value;
  const requiresField = command === "HSET" || command === "HGET";
  const requiresValue = command === "SET" || command === "HSET";

  fieldInput.disabled = !requiresField;
  fieldInput.required = requiresField;
  fieldInput.placeholder = requiresField ? "name" : "";
  if (!requiresField) {
    fieldInput.value = "";
  }

  valueInput.disabled = !requiresValue;
  valueInput.required = requiresValue;
  if (command === "SET") {
    valueInput.placeholder = '{"name":"kim"}';
  } else if (command === "HSET") {
    valueInput.placeholder = "kim";
  } else {
    valueInput.placeholder = "";
  }
  if (!requiresValue) {
    valueInput.value = "";
  }
}

manualForm.addEventListener("submit", runManualCommand);
commandInput.addEventListener("change", syncManualValueState);
resetButton.addEventListener("click", resetArena);
memoryProfileButtons.forEach((button) => button.addEventListener("click", updateMemoryProfile));
ttlProfileButtons.forEach((button) => button.addEventListener("click", updateTtlProfile));
scenarioButtons.forEach((button) => button.addEventListener("click", runScenario));

syncManualValueState();
renderAll();
connectEvents();
fetchHealth();
window.addEventListener("resize", scheduleLaneGraphs);
window.setInterval(fetchHealth, 1500);
