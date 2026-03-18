const ACTIVE_RUN_STATUSES = new Set([
  "queued",
  "bootstrapping",
  "warming_up",
  "running_baseline",
  "running_cache",
  "running_reference",
  "aggregating",
]);

const LANE_DEFINITIONS = [
  {
    key: "db_only",
    label: "DB 전용",
    description: "앱 -> DB -> 응답",
  },
  {
    key: "cache_aside",
    label: "Redis + DB",
    description: "적중, 미스, 폴백, 쓰기 반영",
  },
  {
    key: "redis_only_reference",
    label: "Redis 기준선",
    description: "선택형 Redis 전용 기준선",
  },
];

const state = {
  apiBase: "/api",
  apiBaseSource: "meta",
  apiBasePreferred: "/api",
  apiBasePreferredSource: "meta",
  apiBaseCandidates: [],
  apiBaseResolved: false,
  bundleBase: "/",
  health: null,
  runs: [],
  currentRunId: null,
  currentRun: null,
  presentation: null,
  events: [],
  requests: [],
  bucketSeries: [],
  selectedRequestId: null,
  runRequestToken: 0,
  pollingTimer: null,
  pollingInFlight: false,
  playback: {
    active: false,
    cursor: 0,
    speed: 2,
    timer: null,
  },
};

const elements = {};

window.addEventListener("DOMContentLoaded", () => {
  cacheElements();
  hydrateRuntimeContext();
  bindEvents();
  renderAll();
  initializeDashboard().catch((error) => {
    setScenarioNote(error.message);
  });
});

async function initializeDashboard() {
  await ensureReachableApiBase({ force: true });
  await Promise.all([refreshHealth(), refreshRuns()]);
  const activeRun = state.runs.find((run) => ACTIVE_RUN_STATUSES.has(run.status)) || null;
  if (activeRun) {
    await selectRun(activeRun.run_id);
    return;
  }

  // 진행 중인 run이 없으면 첫 화면에서 바로 benchmark를 시작합니다.
  await maybeAutoStartRunFromUi();
}

async function maybeAutoStartRunFromUi() {
  // cacheElements() 이후에만 호출됩니다.
  const formData = new FormData(elements.runForm);
  const payload = {
    scenario: String(formData.get("scenario") || "detail_page"),
    iteration_count: Number(formData.get("iteration_count") || 10),
    concurrency: Number(formData.get("concurrency") || 1),
    ttl_seconds: Number(formData.get("ttl_seconds") || 30),
    hit_rate_buckets: parseBucketInput(String(formData.get("hit_rate_buckets") || "")),
    include_reference: formData.get("include_reference") === "on",
  };

  if (payload.hit_rate_buckets.length === 0) {
    setScenarioNote("");
    renderAll();
    return;
  }

  let response;
  try {
    setScenarioNote("자동 실행을 시작합니다.");
    stopReplay({ preserveFrame: false });
    response = await apiFetch("/api/benchmark-runs", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
  } catch (error) {
    const message = error?.message || String(error);
    const isActiveRunConflict = message.includes("another benchmark run is already active");

    // 이미 누군가 run을 시작한 상태면 최신 run을 선택하고 자동 시작은 중단합니다.
    try {
      await refreshRuns();
      if (state.runs.length > 0) {
        await selectRun(state.runs[0].run_id);
      } else {
        renderAll();
      }
    } finally {
      setScenarioNote(isActiveRunConflict ? "" : message);
    }
    return;
  }

  try {
    if (response?.run_id) {
      await selectRun(response.run_id);
    } else {
      await refreshRuns();
      if (state.runs.length > 0) {
        await selectRun(state.runs[0].run_id);
      } else {
        renderAll();
      }
    }
  } finally {
    setScenarioNote("");
  }
}

function cacheElements() {
  elements.healthStatus = document.getElementById("health-status");
  elements.healthMeta = document.getElementById("health-meta");
  elements.runStatus = document.getElementById("run-status");
  elements.runMeta = document.getElementById("run-meta");
  elements.heroSpotlightTitle = document.getElementById("hero-spotlight-title");
  elements.heroSpotlightDetail = document.getElementById("hero-spotlight-detail");
  elements.heroDbAvg = document.getElementById("hero-db-avg");
  elements.heroCacheAvg = document.getElementById("hero-cache-avg");
  elements.heroLiveStatus = document.getElementById("hero-live-status");
  elements.apiBaseValue = document.getElementById("api-base-value");
  elements.apiBaseMeta = document.getElementById("api-base-meta");
  elements.runForm = document.getElementById("run-form");
  elements.replayButton = document.getElementById("replay-button");
  elements.refreshAllButton = document.getElementById("refresh-all-button");
  elements.playbackStatus = document.getElementById("playback-status");
  elements.playbackSpeed = document.getElementById("playback-speed");
  elements.scenarioNote = document.getElementById("scenario-note");
  elements.summaryHeadline = document.getElementById("summary-headline");
  elements.summaryDetail = document.getElementById("summary-detail");
  elements.metaScenario = document.getElementById("meta-scenario");
  elements.metaConfig = document.getElementById("meta-config");
  elements.metaReplaySource = document.getElementById("meta-replay-source");
  elements.flowMeta = document.getElementById("flow-meta");
  elements.laneSummaryGrid = document.getElementById("lane-summary-grid");
  elements.flowTimeline = document.getElementById("flow-timeline");
  elements.flowBoard = document.getElementById("flow-board");
  elements.latencyChart = document.getElementById("latency-chart");
  elements.bucketChart = document.getElementById("bucket-chart");
  elements.runsList = document.getElementById("runs-list");
  elements.logsList = document.getElementById("logs-list");
  elements.requestDetail = document.getElementById("request-detail");
  elements.kpiNodes = Array.from(document.querySelectorAll("[data-kpi]"));
}

function hydrateRuntimeContext() {
  const runtime = resolveRuntimeContext();
  state.apiBase = runtime.apiBase;
  state.apiBaseSource = runtime.apiBaseSource;
  state.apiBasePreferred = runtime.apiBase;
  state.apiBasePreferredSource = runtime.apiBaseSource;
  state.apiBaseCandidates = runtime.apiBaseCandidates;
  state.apiBaseResolved = false;
  state.bundleBase = runtime.bundleBase;

  // Connection 상태는 오른쪽 mini-card에서 이미 안내합니다.
  // 초기 로딩 시에는 시나리오 노트가 화면 상단을 과하게 밀지 않도록 숨깁니다.
}

function bindEvents() {
  elements.runForm.addEventListener("submit", handleRunSubmit);
  elements.replayButton.addEventListener("click", toggleReplay);
  elements.refreshAllButton.addEventListener("click", handleRefreshAll);
  elements.playbackSpeed.addEventListener("change", (event) => {
    state.playback.speed = Number(event.target.value || "2");
    renderPlaybackStatus();
    if (state.playback.active) {
      startReplay();
    }
  });
  bindTabs();
}

function bindTabs() {
  document.querySelectorAll(".tab-btn[data-target]").forEach((btn) => {
    btn.addEventListener("click", () => {
      const targetId = btn.dataset.target;
      document.querySelectorAll(".tab-btn").forEach((b) => {
        b.classList.remove("tab-btn--active", "active");
      });
      document.querySelectorAll(".tab-pane").forEach((pane) => {
        pane.classList.remove("tab-pane--active");
      });
      btn.classList.add("tab-btn--active");
      const pane = document.getElementById(targetId);
      if (pane) pane.classList.add("tab-pane--active");
    });
  });
}

function activateTab(targetId) {
  document.querySelectorAll(".tab-btn").forEach((b) => {
    b.classList.remove("tab-btn--active", "active");
  });
  document.querySelectorAll(".tab-pane").forEach((pane) => {
    pane.classList.remove("tab-pane--active");
  });
  const btn = document.querySelector(`.tab-btn[data-target="${targetId}"]`);
  const pane = document.getElementById(targetId);
  if (btn) btn.classList.add("tab-btn--active");
  if (pane) pane.classList.add("tab-pane--active");
}

async function handleRefreshAll() {
  try {
    await ensureReachableApiBase({ force: true });
    setScenarioNote("상태, run 기록, 선택된 보드를 새로고침하는 중입니다.");
    await Promise.all([refreshHealth(), refreshRuns()]);
    if (state.currentRunId) {
      await refreshSelectedRun();
    } else {
      renderAll();
    }
  } catch (error) {
    setScenarioNote(error.message);
  }
}

async function handleRunSubmit(event) {
  event.preventDefault();
  const formData = new FormData(elements.runForm);
  const payload = {
    scenario: String(formData.get("scenario") || "detail_page"),
    iteration_count: Number(formData.get("iteration_count") || 10),
    concurrency: Number(formData.get("concurrency") || 1),
    ttl_seconds: Number(formData.get("ttl_seconds") || 30),
    hit_rate_buckets: parseBucketInput(String(formData.get("hit_rate_buckets") || "")),
    include_reference: formData.get("include_reference") === "on",
  };

  if (payload.hit_rate_buckets.length === 0) {
    setScenarioNote("적중률 버킷에는 0에서 100 사이의 정수를 최소 하나 이상 넣어야 합니다.");
    return;
  }

  try {
    setScenarioNote("새 벤치마크 run을 시작합니다.");
    stopReplay({ preserveFrame: false });
    const response = await apiFetch("/api/benchmark-runs", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    await refreshRuns();
    await selectRun(response.run_id);
    setScenarioNote(`${response.run_id} run이 대기열에 들어갔습니다. 완료될 때까지 보드를 주기적으로 갱신합니다.`);
  } catch (error) {
    setScenarioNote(error.message);
  }
}

async function refreshHealth() {
  try {
    state.health = await apiFetch("/api/health");
  } catch (error) {
    state.health = {
      status: "down",
      error: error.message,
      host: "127.0.0.1",
      port: 6379,
    };
  }
  renderHealth();
}

async function refreshRuns() {
  const payload = await apiFetch("/api/benchmark-runs");
  state.runs = Array.isArray(payload.runs) ? payload.runs : [];
  renderRuns();
}

async function selectRun(runId) {
  state.currentRunId = runId;
  stopReplay({ preserveFrame: false });
  await refreshSelectedRun();
}

async function refreshSelectedRun() {
  if (!state.currentRunId) {
    return;
  }

  const runId = state.currentRunId;
  const requestToken = ++state.runRequestToken;
  let runPayload;
  let requestsPayload;
  let presentationPayload;
  try {
    [runPayload, requestsPayload, presentationPayload] = await Promise.all([
      apiFetch(`/api/benchmark-runs/${runId}`),
      apiFetch(`/api/benchmark-runs/${runId}/requests`),
      apiFetch(`/api/benchmark-runs/${runId}/presentation`),
    ]);
  } catch (error) {
    if (requestToken !== state.runRequestToken || runId !== state.currentRunId) {
      return;
    }
    throw error;
  }

  if (requestToken !== state.runRequestToken || runId !== state.currentRunId) {
    return;
  }

  state.currentRun = runPayload;
  state.presentation = presentationPayload;
  state.requests = normalizeRequests(Array.isArray(requestsPayload.requests) ? requestsPayload.requests : []);
  state.events = state.requests.flatMap((request) => request.events);
  state.bucketSeries = buildBucketSeries(state.requests);

  if (!state.selectedRequestId || !state.requests.some((request) => request.id === state.selectedRequestId)) {
    state.selectedRequestId = state.requests.at(-1)?.id || null;
  }

  syncPolling();
  renderAll();
}

function syncPolling() {
  if (state.pollingTimer) {
    window.clearInterval(state.pollingTimer);
    state.pollingTimer = null;
  }

  if (!state.currentRun || !ACTIVE_RUN_STATUSES.has(state.currentRun.status)) {
    state.pollingInFlight = false;
    return;
  }

  state.pollingTimer = window.setInterval(async () => {
    if (state.pollingInFlight) {
      return;
    }
    state.pollingInFlight = true;
    try {
      await refreshSelectedRun();
    } catch (error) {
      setScenarioNote(error.message);
    } finally {
      state.pollingInFlight = false;
    }
  }, 1800);
}

function toggleReplay() {
  if (state.playback.active) {
    stopReplay();
    renderAll();
    return;
  }

  if (state.requests.length === 0) {
    setScenarioNote("재생을 하려면 먼저 요청 이벤트가 필요합니다. 먼저 벤치마크 실행을 시작하세요.");
    return;
  }

  startReplay();
}

function startReplay() {
  stopReplay({ preserveFrame: false });
  state.playback.active = true;
  state.playback.cursor = 0;
  renderPlaybackStatus();
  renderFlowBoard();

  const stepDuration = Math.max(120, Math.round(520 / state.playback.speed));
  state.playback.timer = window.setInterval(() => {
    if (state.playback.cursor >= state.requests.length - 1) {
      stopReplay();
      renderAll();
      return;
    }

    state.playback.cursor += 1;
    renderPlaybackStatus();
    renderFlowBoard();
  }, stepDuration);
}

function stopReplay(options = {}) {
  const preserveFrame = options.preserveFrame !== false;
  if (state.playback.timer) {
    window.clearInterval(state.playback.timer);
    state.playback.timer = null;
  }
  state.playback.active = false;
  if (!preserveFrame) {
    state.playback.cursor = 0;
  }
  renderPlaybackStatus();
}

function renderAll() {
  renderConnectionCard();
  renderHealth();
  renderRunMeta();
  renderHeroSpotlight();
  renderSummary();
  renderKpis();
  renderLaneSummary();
  renderFlowTimeline();
  renderFlowBoard();
  renderLatencyChart();
  renderBucketChart();
  renderRuns();
  renderLogs();
  renderRequestDetail();
  renderPlaybackStatus();
}

function renderConnectionCard() {
  const sourceLabel = {
    query: "쿼리 오버라이드",
    local_storage: "저장된 오버라이드",
    meta: "문서 기본값",
    fallback: "자동 보조 연결",
  }[state.apiBaseSource] || state.apiBaseSource;
  const fallbackMeta = describeApiFallbackMeta();

  elements.apiBaseValue.textContent = state.apiBase;
  elements.apiBaseMeta.textContent = isSameOriginApi()
    ? `${sourceLabel} · 번들 ${state.bundleBase} -> 같은 origin 요청${fallbackMeta}`
    : `${sourceLabel} · 교차 origin 요청은 CORS 또는 프록시 필요${fallbackMeta}`;
}

function renderHealth() {
  if (!state.health) {
    elements.healthStatus.textContent = "확인 중";
    elements.healthMeta.textContent = `${resolveApiUrl("/api/health")} 응답 대기 중`;
    return;
  }

  const isHealthy = state.health.status === "ok";
  elements.healthStatus.textContent = isHealthy ? "정상" : "연결 불가";
  elements.healthMeta.textContent = isHealthy
    ? `${state.health.host}:${state.health.port} 가 응답 중입니다`
    : state.health.error || `${state.health.host}:${state.health.port} 연결이 내려가 있습니다`;
}

function renderRunMeta() {
  if (!state.currentRun) {
    elements.runStatus.textContent = "대기";
    elements.runMeta.textContent = "벤치마크 실행을 시작하세요.";
    return;
  }

  elements.runStatus.textContent = humanizeStatus(state.currentRun.status);
  const updatedAt = state.currentRun.updated_at ? formatDateTime(state.currentRun.updated_at) : "알 수 없음";
  elements.runMeta.textContent = `${state.currentRun.run_id} · 마지막 갱신 ${updatedAt}`;
}

function renderHeroSpotlight() {
  if (!state.currentRun) {
    elements.heroSpotlightTitle.textContent = "벤치마크 결론을 준비하는 중입니다.";
    elements.heroSpotlightDetail.textContent =
      "벤치마크 실행을 시작하면 지금 조건에서 어떤 경로가 우세한지 이 영역에서 먼저 요약합니다.";
    elements.heroDbAvg.textContent = "--";
    elements.heroCacheAvg.textContent = "--";
    elements.heroLiveStatus.textContent = "대기";
    return;
  }

  const summary = state.presentation?.kpis || state.currentRun.summary || null;
  elements.heroLiveStatus.textContent = humanizeStatus(state.currentRun.status);

  if (!summary) {
    elements.heroSpotlightTitle.textContent = `${humanizeStatus(state.currentRun.status)} 상태입니다.`;
    elements.heroSpotlightDetail.textContent =
      "요청과 로그가 먼저 쌓이고, 집계가 끝나면 지금 조건에서 어느 경로가 우세한지 자동으로 요약합니다.";
    elements.heroDbAvg.textContent = "--";
    elements.heroCacheAvg.textContent = "--";
    return;
  }

  const dbAvgText = formatMs(summary.db_avg_ms);
  const cacheAvgText = formatMs(summary.redis_avg_ms);
  const hitAvgText = summary.redis_hit_avg_ms == null ? null : formatMs(summary.redis_hit_avg_ms);
  const missAvgText = summary.redis_miss_avg_ms == null ? null : formatMs(summary.redis_miss_avg_ms);
  const speedup = Number(summary.speedup_ratio || 0);
  const hitRate = formatPercent(summary.cache_hit_rate);
  const breakEvenText = summary.break_even_hit_rate == null ? "아직 도달 전" : `${summary.break_even_hit_rate}%`;

  elements.heroDbAvg.textContent = dbAvgText;
  elements.heroCacheAvg.textContent = hitAvgText || cacheAvgText;

  if (speedup > 1.05) {
    elements.heroSpotlightTitle.textContent = `${hitRate} 적중률에서 캐시 경로가 우세합니다.`;
    elements.heroSpotlightDetail.textContent =
      `DB Only ${dbAvgText}, Redis 적중 ${hitAvgText || "--"}, Redis 미스 ${missAvgText || "--"}로 측정됐습니다. ` +
      `성능 역전 기준 적중률은 ${breakEvenText}라서 발표에선 hit와 miss를 따로 보여주는 게 제일 잘 먹힙니다.`;
    return;
  }

  if (speedup < 0.95) {
    elements.heroSpotlightTitle.textContent = "지금 조건에선 DB 기준선이 더 빠릅니다.";
    elements.heroSpotlightDetail.textContent =
      `DB Only ${dbAvgText}, Redis 적중 ${hitAvgText || "--"}, Redis 미스 ${missAvgText || "--"}입니다. ` +
      "이 경우는 캐시 자체보다 미스 비용과 연결 비용이 더 크게 보인다는 점을 설명하기 좋습니다.";
    return;
  }

  elements.heroSpotlightTitle.textContent = "두 경로가 거의 비슷한 수준입니다.";
  elements.heroSpotlightDetail.textContent =
    `DB Only ${dbAvgText}, Redis 적중 ${hitAvgText || "--"}, Redis 미스 ${missAvgText || "--"}입니다. ` +
    `성능 역전 기준 적중률 ${breakEvenText} 기준으로 경계 조건을 설명하기 좋은 run입니다.`;
}

function renderSummary() {
  if (!state.currentRun) {
    elements.summaryHeadline.textContent = "벤치마크 실행을 시작하면 보드가 채워집니다.";
    elements.summaryDetail.textContent =
      "데이터가 들어오면 현재 경로 분포, 성능 역전 기준 적중률, 캐시 경로가 실제로 이득을 주는지 여기서 바로 설명합니다.";
    elements.metaScenario.textContent = humanizeScenario("detail_page");
    elements.metaConfig.textContent = "10회 / 동시성 1 / ttl 30초";
    elements.metaReplaySource.textContent = "events[] 순서";
    return;
  }

  const config = state.presentation?.config || state.currentRun.config;
  const summary = state.presentation?.kpis || state.currentRun.summary;
  const laneSummary = state.presentation?.lane_summary || [];
  elements.metaScenario.textContent = humanizeScenario(config.scenario);
  elements.metaConfig.textContent =
    `${config.iteration_count}회 / 동시성 ${config.concurrency} / ttl ${config.ttl_seconds}초`;
  elements.metaReplaySource.textContent = state.playback.active ? "클라이언트 재생" : "실시간 또는 마지막 조회";

  if (!summary) {
    if (state.currentRun.status === "failed") {
      elements.summaryHeadline.textContent = "이 run은 summary가 만들어지기 전에 실패했습니다.";
      elements.summaryDetail.textContent =
        state.currentRun.error_message || "실패한 단계는 라이프사이클 로그에서 확인하세요.";
      return;
    }

    elements.summaryHeadline.textContent = `${humanizeStatus(state.currentRun.status)} 진행 중`;
    elements.summaryDetail.textContent =
      "runner가 아직 샘플을 수집하고 있습니다. 최종 KPI가 고정되기 전에 로그와 요청 이벤트가 먼저 채워집니다.";
    return;
  }

  const speedup = formatRatio(summary.speedup_ratio);
  const hitRate = formatPercent(summary.cache_hit_rate);
  const breakEven = summary.break_even_hit_rate == null ? "아직 도달 전" : `${summary.break_even_hit_rate}% 버킷`;
  const cacheLane = laneSummary.find((item) => item.mode === "cache_aside");
  const cacheVolume = cacheLane ? `캐시 경로 요청 ${cacheLane.request_count}건` : "캐시 경로 요청 수 계산 중";
  const hitAvg = summary.redis_hit_avg_ms == null ? "--" : formatMs(summary.redis_hit_avg_ms);
  const missAvg = summary.redis_miss_avg_ms == null ? "--" : formatMs(summary.redis_miss_avg_ms);
  elements.summaryHeadline.textContent = `${hitRate} 적중률에서 ${speedup} 속도 향상`;
  elements.summaryDetail.textContent =
    `성능 역전 기준 적중률은 ${breakEven}입니다. Redis 적중 평균 ${hitAvg}, Redis 미스 평균 ${missAvg}, ` +
    `${cacheVolume}, 오류 ${summary.error_count}건 기준으로 presentation 읽기 모델이 KPI와 첫 비교 그래프를 채웁니다.`;
}

function renderKpis() {
  const summary = state.presentation?.kpis || state.currentRun?.summary || null;
  for (const node of elements.kpiNodes) {
    const key = node.dataset.kpi;
    node.textContent = formatKpiValue(key, summary ? summary[key] : null);
  }
}

function renderLaneSummary() {
  const laneSummary = state.presentation?.lane_summary || buildFallbackLaneSummary();
  if (laneSummary.length === 0) {
    elements.laneSummaryGrid.innerHTML = "";
    return;
  }

  elements.laneSummaryGrid.innerHTML = laneSummary
    .map((lane) => `
      <article class="lane-summary-card">
        <span class="lane-summary-label">${escapeHtml(localizeSeriesLabel(lane.label))}</span>
        <strong>${escapeHtml(String(lane.request_count))}건</strong>
        <span>${escapeHtml(lane.avg_duration_ms == null ? "평균 계산 중" : formatMs(lane.avg_duration_ms))}</span>
        <span>${escapeHtml(`적중 ${lane.hit_count} · 미스 ${lane.miss_count} · 폴백 ${lane.fallback_count}`)}</span>
      </article>
    `)
    .join("");
}

function renderRuns() {
  if (state.runs.length === 0) {
    elements.runsList.innerHTML = emptyStateMarkup(
      "아직 run이 없습니다",
      "벤치마크를 실행하면 최근 run 목록이 여기에 표시됩니다.",
    );
    return;
  }

  elements.runsList.innerHTML = state.runs
    .map((run) => {
      const isActive = run.run_id === state.currentRunId;
      const statusClass = `status-${run.status}`;
      return `
        <button class="run-row ${isActive ? "active" : ""}" type="button" data-run-id="${escapeHtml(run.run_id)}">
          <strong>${escapeHtml(run.run_id)}</strong>
          <span>${escapeHtml(humanizeScenario(run.scenario))} · 마지막 갱신 ${escapeHtml(formatDateTime(run.updated_at))}</span>
          <span class="run-status-pill ${statusClass}">${escapeHtml(humanizeStatus(run.status))}</span>
        </button>
      `;
    })
    .join("");

  for (const button of elements.runsList.querySelectorAll("[data-run-id]")) {
    button.addEventListener("click", async () => {
      try {
        await selectRun(button.dataset.runId);
      } catch (error) {
        setScenarioNote(error.message);
      }
    });
  }
}

function renderLogs() {
  const logs = state.currentRun?.logs || [];
  if (logs.length === 0) {
    elements.logsList.innerHTML = emptyStateMarkup(
      "라이프사이클 로그가 아직 없습니다",
      "run이 시작되면 워밍업, 기준선, 캐시, 집계 로그가 여기에 표시됩니다.",
    );
    return;
  }

  const rows = logs
    .slice()
    .reverse()
    .map((log) => {
      const meta = summarizeMetadata(log.metadata);
      const errorClass = log.level === "ERROR" ? "error-row" : "";
      return `
        <article class="log-row ${errorClass}">
          <strong>${escapeHtml(`[${formatEpoch(log.timestamp)}] ${log.stage}`)}</strong>
          <span>${escapeHtml(log.message)}</span>
          ${meta ? `<span>${escapeHtml(meta)}</span>` : ""}
        </article>
      `;
    })
    .join("");
  elements.logsList.innerHTML = rows;
}

function renderFlowBoard() {
  const visibleRequests = getVisibleRequests();
  if (visibleRequests.length === 0) {
    elements.flowMeta.textContent = `이벤트 ${state.events.length}개`;
    elements.flowBoard.className = "flow-board empty-board";
    elements.flowBoard.innerHTML = emptyStateMarkup(
      "요청 이벤트가 아직 없습니다",
      "벤치마크를 실행하거나 이전 run을 선택하면 레인이 활성화됩니다.",
    );
    return;
  }

  const hasReferenceLane = visibleRequests.some((request) => request.mode === "redis_only_reference");
  const laneDefs = hasReferenceLane
    ? LANE_DEFINITIONS
    : LANE_DEFINITIONS.filter((lane) => lane.key !== "redis_only_reference");

  const playbackMeta = state.playback.active
    ? ` · 재생 ${Math.min(state.playback.cursor + 1, state.requests.length)}/${state.requests.length}`
    : "";
  const selectedRequest = state.requests.find((request) => request.id === state.selectedRequestId) || null;
  const selectionMeta = selectedRequest ? ` · 선택 #${selectedRequest.sequence}` : "";
  elements.flowMeta.textContent = `이벤트 ${state.events.length}개 · 표시 요청 ${visibleRequests.length}건${playbackMeta}${selectionMeta}`;
  elements.flowBoard.className = "flow-board";
  elements.flowBoard.innerHTML = laneDefs
    .map((lane) => renderLaneMarkup(
      lane,
      visibleRequests.filter((request) => request.mode === lane.key),
      getLaneSummaryItem(lane.key),
    ))
    .join("");

  for (const token of elements.flowBoard.querySelectorAll("[data-request-id]")) {
    token.addEventListener("click", () => {
      state.selectedRequestId = token.dataset.requestId;
      renderFlowBoard();
      renderRequestDetail();
      activateTab("tab-detail");
    });
  }
}

function renderFlowTimeline() {
  const visibleRequests = getVisibleRequests();
  if (visibleRequests.length === 0) {
    elements.flowTimeline.innerHTML = emptyChartMarkup(
      "시간축 흐름 데이터가 아직 없습니다",
      "요청이 수집되면 단계 전환을 시간축 위에서 선형 그래프로 보여줍니다.",
    );
    return;
  }

  const selectedRequest = state.requests.find((request) => request.id === state.selectedRequestId)
    || visibleRequests.at(-1)
    || null;
  const primaryRequest = selectedRequest || visibleRequests.at(-1) || null;
  const comparisonRequests = primaryRequest
    ? [...visibleRequests.filter((request) => request.id !== primaryRequest.id).slice(-4), primaryRequest]
    : visibleRequests.slice(-5);
  const stageRows = buildTimelineStageRows(comparisonRequests);
  const maxTime = Math.max(...comparisonRequests.map((request) => request.totalDurationMs || 0), 1);
  const width = 860;
  const rowGap = 70;
  const height = 92 + rowGap * (stageRows.length - 1) + 52;
  const padding = { top: 24, right: 30, bottom: 34, left: 118 };
  const innerWidth = width - padding.left - padding.right;

  const rowGuides = stageRows.map((row, index) => {
    const y = padding.top + index * rowGap;
    return `
      <line class="timeline-row-guide" x1="${padding.left}" y1="${y}" x2="${width - padding.right}" y2="${y}"></line>
      <text class="timeline-row-label" x="${padding.left - 18}" y="${y + 5}" text-anchor="end">${escapeHtml(row.label)}</text>
    `;
  }).join("");

  const axisTicks = [0, 0.25, 0.5, 0.75, 1].map((ratio) => {
    const x = padding.left + innerWidth * ratio;
    const value = maxTime * ratio;
    return `
      <line class="timeline-axis-tick" x1="${x}" y1="${height - padding.bottom}" x2="${x}" y2="${padding.top - 6}"></line>
      <text class="timeline-axis-label" x="${x}" y="${height - 10}" text-anchor="middle">${formatMs(value)}</text>
    `;
  }).join("");

  const seriesMarkup = comparisonRequests.map((request) => renderTimelineSeriesMarkup(
    request,
    stageRows,
    maxTime,
    width,
    height,
    padding,
    primaryRequest != null && request.id === primaryRequest.id,
  )).join("");

  elements.flowTimeline.innerHTML = `
    <div class="flow-timeline-legend">
      <span class="flow-timeline-focus">기준 요청: #${primaryRequest ? primaryRequest.sequence : "-"} ${escapeHtml(primaryRequest?.id || "")}</span>
      <span>최근 요청 ${comparisonRequests.length}건 겹쳐보기</span>
    </div>
    <svg class="timeline-svg" viewBox="0 0 ${width} ${height}" role="img" aria-label="시간축 데이터 흐름 그래프">
      <rect class="timeline-backdrop" x="0" y="0" width="${width}" height="${height}" rx="24"></rect>
      ${rowGuides}
      ${axisTicks}
      <line class="timeline-axis" x1="${padding.left}" y1="${height - padding.bottom}" x2="${width - padding.right}" y2="${height - padding.bottom}"></line>
      ${seriesMarkup}
    </svg>
  `;
}

function renderLatencyChart() {
  const latencySeries = state.presentation?.chart_series?.latency_comparison || buildFallbackLatencySeries();
  if (latencySeries.length === 0) {
    elements.latencyChart.innerHTML = emptyChartMarkup(
      "요약 데이터를 기다리는 중입니다",
      "run 집계가 끝나면 presentation 읽기 모델이 지연시간 비교를 제공합니다.",
    );
    return;
  }

  const series = latencySeries.map((item) => ({
    label: item.label,
    value: item.value,
    className: latencySeriesTone(item.label),
  }));

  const width = 360;
  const height = 240;
  const padding = { top: 18, right: 18, bottom: 44, left: 48 };
  const maxValue = Math.max(...series.map((item) => item.value), 1);
  const innerHeight = height - padding.top - padding.bottom;
  const innerWidth = width - padding.left - padding.right;
  const barWidth = innerWidth / series.length - 26;

  const gridLines = [0.25, 0.5, 0.75, 1].map((ratio) => {
    const y = padding.top + innerHeight - innerHeight * ratio;
    const value = maxValue * ratio;
    return `
      <line class="chart-grid-line" x1="${padding.left}" y1="${y}" x2="${width - padding.right}" y2="${y}"></line>
      <text class="chart-caption" x="${padding.left - 10}" y="${y + 4}" text-anchor="end">${formatMs(value)}</text>
    `;
  }).join("");

  const bars = series.map((item, index) => {
    const barHeight = innerHeight * (item.value / maxValue);
    const x = padding.left + index * (barWidth + 26) + 18;
    const y = padding.top + innerHeight - barHeight;
    return `
      <rect class="${item.className}" x="${x}" y="${y}" width="${barWidth}" height="${barHeight}" rx="18"></rect>
      <text class="chart-value" x="${x + barWidth / 2}" y="${y - 8}" text-anchor="middle">${formatMs(item.value)}</text>
      <text class="chart-caption" x="${x + barWidth / 2}" y="${height - 14}" text-anchor="middle">${escapeHtml(localizeSeriesLabel(item.label))}</text>
    `;
  }).join("");

  elements.latencyChart.innerHTML = `
    <svg class="chart-svg" viewBox="0 0 ${width} ${height}" role="img" aria-label="지연시간 비교 차트">
      ${gridLines}
      <line class="chart-axis" x1="${padding.left}" y1="${padding.top}" x2="${padding.left}" y2="${height - padding.bottom}"></line>
      <line class="chart-axis" x1="${padding.left}" y1="${height - padding.bottom}" x2="${width - padding.right}" y2="${height - padding.bottom}"></line>
      ${bars}
    </svg>
  `;
}

function renderBucketChart() {
  const pathSeries = state.presentation?.chart_series?.path_ratio || buildFallbackPathSeries();
  const stageTotals = state.presentation?.chart_series?.timeline_stage_totals || buildFallbackStageTotals();
  if (pathSeries.length === 0) {
    elements.bucketChart.innerHTML = emptyChartMarkup(
      "경로 분포가 아직 없습니다",
      "요청 타임라인이 준비되면 presentation 읽기 모델이 요청 분포를 제공합니다.",
    );
    return;
  }

  const maxValue = Math.max(...pathSeries.map((item) => item.value), 1);
  elements.bucketChart.innerHTML = `
    <div class="mix-chart" role="img" aria-label="요청 경로 분포 차트">
      <div class="mix-chart-list">
        ${pathSeries.map((item) => {
          const widthPercent = (item.value / maxValue) * 100;
          return `
            <article class="mix-row">
              <div class="mix-copy">
                <strong>${escapeHtml(localizeSeriesLabel(item.label))}</strong>
                <span>${escapeHtml(String(item.value))}건</span>
              </div>
              <div class="mix-track">
                <div class="mix-fill ${pathSeriesTone(item.label)}" style="width: ${widthPercent}%"></div>
              </div>
            </article>
          `;
        }).join("")}
      </div>
      <div class="stage-chip-grid">
        ${stageTotals.map((item) => `
          <article class="stage-chip">
            <span>${escapeHtml(localizeStageLabel(item.label))}</span>
            <strong>${escapeHtml(formatMs(item.value))}</strong>
          </article>
        `).join("")}
      </div>
    </div>
  `;
}

function renderRequestDetail() {
  const request = state.requests.find((item) => item.id === state.selectedRequestId) || null;
  if (!request) {
    elements.requestDetail.innerHTML = emptyStateMarkup(
      "선택된 요청이 없습니다",
      "레인 보드의 토큰을 누르면 경로, 소요 시간, 캐시 상태를 볼 수 있습니다.",
      true,
    );
    return;
  }

  const steps = buildRequestFlowSteps(request);
  const narrative = buildRequestNarrative(request);
  const routeMarkup = renderFlowRouteMarkup(steps, request, { detailed: true });
  const meterMarkup = renderFlowMeterMarkup(request, steps, { detailed: true });
  const stageCards = request.stageDurations
    .map((stage) => `
      <article class="detail-stage">
        <strong>${escapeHtml(localizeStageLabel(stage.stage))}</strong>
        <span>${escapeHtml(formatMs(stage.durationMs))} · 이벤트 ${stage.eventCount}개</span>
      </article>
    `)
    .join("");
  const eventRows = renderEventTimelineMarkup(request);

  elements.requestDetail.innerHTML = `
    <div class="detail-grid">
      <div class="detail-hero">
        <div>
          <h3>${escapeHtml(request.id)}</h3>
          <p class="mini-card-meta">${escapeHtml(humanizeMode(request.mode))} · ${escapeHtml(formatMs(request.totalDurationMs))}</p>
        </div>
        <span class="detail-tag detail-tag-${escapeHtml(requestTokenTone(request))}">${escapeHtml(request.cacheStatusLabel)}</span>
      </div>

      <div class="detail-path">${escapeHtml(request.pathSummary)}</div>

      <section class="detail-story-shell">
        <span class="detail-story-kicker">요청 스토리</span>
        <strong class="detail-story-headline">${escapeHtml(narrative.headline)}</strong>
        <p class="detail-story-copy">${escapeHtml(narrative.description)}</p>
        <div class="detail-story-cue">
          <span>발표 포인트</span>
          <strong>${escapeHtml(narrative.presenterCue)}</strong>
        </div>
      </section>

      <section class="detail-flow-shell">
        <div class="detail-section-head">
          <strong>요청 단계 흐름</strong>
          <span>총 ${escapeHtml(formatMs(request.totalDurationMs))}</span>
        </div>
        <div class="detail-flow-route">${routeMarkup}</div>
        ${meterMarkup}
      </section>

      <div class="detail-stats">
        <article class="detail-stat">
          <strong>요청 순서</strong>
          <span>#${request.sequence}</span>
        </article>
        <article class="detail-stat">
          <strong>버킷</strong>
          <span>${request.bucket == null ? "없음" : `${request.bucket}%`}</span>
        </article>
        <article class="detail-stat">
          <strong>오류</strong>
          <span>${request.hasError ? "있음" : "없음"}</span>
        </article>
        <article class="detail-stat">
          <strong>이벤트 수</strong>
          <span>${request.events.length}개 캡처됨</span>
        </article>
      </div>

      <div class="detail-stages">${stageCards}</div>

      <section class="detail-events-shell">
        <div class="detail-section-head">
          <strong>이벤트 타임라인</strong>
          <span>요청 상대 시간 기준</span>
        </div>
        <div class="detail-event-list">${eventRows}</div>
      </section>
    </div>
  `;
}

function buildRequestNarrative(request) {
  const total = formatMs(request.totalDurationMs);
  if (request.mode === "db_only") {
    return {
      headline: `${total} 동안 DB 기준선으로 끝난 요청입니다.`,
      description: "애플리케이션이 캐시를 거치지 않고 DB로 바로 내려간 기준 경로입니다. 지금 run에서 캐시 경로와 비교할 때 설명의 기준점으로 쓰기 좋습니다.",
      presenterCue: "기준선은 단순하지만, hit가 높아지면 이 경로를 캐시가 얼마나 앞서는지 바로 대비해 보여주면 됩니다.",
    };
  }

  if (request.mode === "redis_only_reference") {
    return {
      headline: `${total} 동안 Redis 기준선만 타고 끝났습니다.`,
      description: "이 요청은 DB fallback 없이 Redis만 조회한 참고 경로입니다. 실제 서비스 주 경로라기보다 캐시 접근의 상한선에 가까운 값입니다.",
      presenterCue: "이 레인은 실서비스 기본축이 아니라, Redis 접근 자체의 이론적 상한선이라고 짚어주면 덜 헷갈립니다.",
    };
  }

  if (request.cacheStatus === "hit") {
    return {
      headline: `${total} 동안 Redis hit로 빠르게 응답했습니다.`,
      description: "Redis 조회 단계에서 필요한 데이터가 바로 나와서 DB lookup과 writeback을 건너뛴 요청입니다. 청중이 캐시 이득을 직감적으로 보기 가장 쉬운 케이스입니다.",
      presenterCue: "이 요청은 DB를 안 건드렸다는 점을 짚으면, 캐시가 왜 평균 지연을 깎는지 바로 먹힙니다.",
    };
  }

  if (request.cacheStatus === "miss" || request.cacheStatus === "miss_writeback_failed") {
    return {
      headline: `${total} 동안 Redis miss 뒤에 DB fallback이 이어졌습니다.`,
      description: "캐시 조회는 실패했고, 실제 데이터는 DB에서 가져온 다음 writeback까지 수행한 요청입니다. 캐시 비용이 늘어나는 이유를 설명하기 좋은 대표 케이스입니다.",
      presenterCue: "miss는 느리지만, 이후 같은 키가 hit로 바뀌면 평균이 어떻게 뒤집히는지 이어서 보여주면 설득력이 확 올라갑니다.",
    };
  }

  if (request.cacheStatus === "fallback") {
    return {
      headline: `${total} 동안 캐시 대신 안전한 fallback으로 마무리했습니다.`,
      description: "Redis 경로에서 문제가 생기거나 기대한 응답을 받지 못해, DB fallback으로 응답을 마친 요청입니다. 기능 유지와 성능 사이의 트레이드오프를 보여줍니다.",
      presenterCue: "캐시가 불안정해도 서비스는 안 죽는다는 점을 여기서 보여주면 운영 관점 설명이 쉬워집니다.",
    };
  }

  if (request.hasError || request.cacheStatus === "error") {
    return {
      headline: `${total} 동안 오류가 포함된 요청이었습니다.`,
      description: "실행 자체는 기록됐지만, 요청 과정에 오류 이벤트가 포함된 케이스입니다. 로그와 이벤트 타임라인을 함께 보면서 실패 지점을 설명해야 합니다.",
      presenterCue: "성능 자랑만 하지 말고, 오류가 끼는 순간 어떤 단계에서 깨지는지도 같이 보여주면 더 믿음이 갑니다.",
    };
  }

  return {
    headline: `${total} 동안 경로가 집계된 요청입니다.`,
    description: "요청 단계와 소요 시간이 정상적으로 기록된 케이스입니다. 상세 패널 아래 단계 카드와 이벤트 타임라인에서 실제 흐름을 이어서 확인할 수 있습니다.",
    presenterCue: "이 영역은 숫자보다 흐름 설명용입니다. 단계 카드와 타임라인으로 바로 연결해서 읽어주면 됩니다.",
  };
}

function renderPlaybackStatus() {
  if (state.playback.active) {
    const visibleCount = Math.min(state.playback.cursor + 1, state.requests.length);
    elements.playbackStatus.textContent = `재생 ${visibleCount}/${state.requests.length} · 속도 ${state.playback.speed}x`;
    elements.replayButton.textContent = "재생 중지";
    return;
  }

  elements.playbackStatus.textContent = "실시간 모드";
  elements.replayButton.textContent = "흐름 재생";
}

function buildRequestModels(events) {
  const requestMap = new Map();
  events.forEach((event, order) => {
    if (!requestMap.has(event.request_id)) {
      requestMap.set(event.request_id, {
        id: event.request_id,
        mode: event.mode,
        firstOrder: order,
        events: [],
      });
    }
    const request = requestMap.get(event.request_id);
    request.events.push({ ...event, _order: order });
  });

  return Array.from(requestMap.values())
    .sort((left, right) => left.firstOrder - right.firstOrder)
    .map((request, index) => finalizeRequestModel(request, index + 1));
}

function finalizeRequestModel(request, sequence) {
  const events = request.events.slice().sort((left, right) => left._order - right._order);
  const responseEvent = events.find((event) => event.event_type === "response_sent") || null;
  const totalDurationMs = Number(responseEvent?.metadata?.total_duration_ms || events.at(-1)?.timestamp || 0);
  const bucket = firstNumericMetadata(events, "bucket");
  const cacheStatus = String(responseEvent?.metadata?.cache_status || deriveCacheStatus(events, request.mode));
  const cacheStatusLabel = humanizeCacheStatus(cacheStatus, request.mode);
  const stageDurations = aggregateStageDurations(events);
  return {
    id: request.id,
    mode: request.mode,
    sequence,
    events,
    totalDurationMs,
    bucket,
    cacheStatus,
    cacheStatusLabel,
    pathSummary: derivePathSummary(request.mode, cacheStatus),
    stageDurations,
    hasError: events.some((event) => event.event_type === "error"),
  };
}

function buildBucketSeries(requests) {
  const bucketMap = new Map();
  for (const request of requests) {
    if (request.mode !== "cache_aside" || request.bucket == null) {
      continue;
    }
    if (!bucketMap.has(request.bucket)) {
      bucketMap.set(request.bucket, []);
    }
    bucketMap.get(request.bucket).push(request.totalDurationMs);
  }

  return Array.from(bucketMap.entries())
    .sort((left, right) => left[0] - right[0])
    .map(([bucket, values]) => ({
      bucket,
      avgMs: average(values),
      count: values.length,
    }));
}

function aggregateStageDurations(events) {
  const stageMap = new Map();
  for (const event of events) {
    const previous = stageMap.get(event.stage) || { stage: event.stage, durationMs: 0, eventCount: 0 };
    previous.durationMs += Number(event.duration_ms || 0);
    previous.eventCount += 1;
    stageMap.set(event.stage, previous);
  }
  return Array.from(stageMap.values()).map((item) => ({
    ...item,
    durationMs: Number(item.durationMs.toFixed(2)),
  }));
}

function renderLaneMarkup(lane, laneRequests, laneSummary) {
  const laneDisplayRequests = laneRequests.slice(-6);
  const hiddenCount = Math.max(0, state.requests.filter((request) => request.mode === lane.key).length - laneDisplayRequests.length);
  const headMeta = laneSummary
    ? `${laneSummary.request_count}건 · ${laneSummary.avg_duration_ms == null ? "평균 계산 중" : formatMs(laneSummary.avg_duration_ms)}`
    : laneDisplayRequests.length > 0
      ? `${laneDisplayRequests.length}건 표시 중${hiddenCount > 0 ? ` · ${hiddenCount}건 숨김` : ""}`
      : "표시 중인 요청이 없습니다";
  const laneBreakdown = laneSummary
    ? `적중 ${laneSummary.hit_count} · 미스 ${laneSummary.miss_count} · 폴백 ${laneSummary.fallback_count} · 오류 ${laneSummary.error_count}`
    : hiddenCount > 0
      ? `${laneDisplayRequests.length}건 표시 중 · ${hiddenCount}건 숨김`
      : "재생 모드에서는 현재 레인 순서를 보여줍니다";
  const topology = buildLaneTopology(lane.key);
  const requestCards = laneDisplayRequests.length > 0
    ? laneDisplayRequests.map((request) => renderLaneRequestCard(request)).join("")
    : `
      <div class="lane-empty-card">
        <strong>이 레인에는 아직 표시 중인 요청이 없습니다</strong>
        <span>run이 진행되거나 재생 커서가 이동하면 실제 경로 카드가 쌓입니다.</span>
      </div>
    `;

  return `
    <section class="lane">
      <aside class="lane-head">
        <strong>${escapeHtml(lane.label)}</strong>
        <span>${escapeHtml(lane.description)}</span>
        <span>${escapeHtml(headMeta)}</span>
        <span>${escapeHtml(laneBreakdown)}</span>
      </aside>
      <div class="lane-track lane-track-rich">
        <div class="lane-topology">
          ${topology.map((node, index) => `
            <div class="lane-topology-node">
              <span>${escapeHtml(node)}</span>
              ${index < topology.length - 1 ? '<i class="lane-topology-arrow" aria-hidden="true"></i>' : ""}
            </div>
          `).join("")}
        </div>
        <div class="lane-request-stack">
          ${requestCards}
        </div>
      </div>
    </section>
  `;
}

function renderLaneRequestCard(request) {
  const steps = buildRequestFlowSteps(request);
  const routeMarkup = renderFlowRouteMarkup(steps, request);
  const meterMarkup = renderFlowMeterMarkup(request, steps);
  const selectedClass = request.id === state.selectedRequestId ? "selected" : "";
  const playbackCurrent = isPlaybackCurrentRequest(request) ? "playback-current" : "";
  const statusTone = `tone-${requestTokenTone(request)}`;
  const bucketMeta = request.bucket == null ? "버킷 없음" : `버킷 ${request.bucket}%`;

  return `
    <button
      class="flow-request-card ${selectedClass} ${playbackCurrent}"
      type="button"
      data-request-id="${escapeHtml(request.id)}"
      title="${escapeHtml(`${request.id} · ${request.pathSummary}`)}"
    >
      <div class="flow-request-top">
        <strong>#${request.sequence} ${escapeHtml(request.id)}</strong>
        <span>${escapeHtml(formatMs(request.totalDurationMs))}</span>
      </div>
      <div class="flow-request-badges">
        <span class="flow-request-pill ${statusTone}">${escapeHtml(request.cacheStatusLabel)}</span>
        <span class="flow-request-meta-chip">${escapeHtml(bucketMeta)}</span>
        <span class="flow-request-meta-chip">${escapeHtml(`이벤트 ${request.events.length}개`)}</span>
      </div>
      ${routeMarkup}
      ${meterMarkup}
      <div class="flow-request-foot">
        <span>${escapeHtml(request.pathSummary)}</span>
        <span>${request.hasError ? "오류 포함" : "정상 완료"}</span>
      </div>
    </button>
  `;
}

function buildLaneTopology(mode) {
  return {
    db_only: ["앱", "DB", "응답"],
    cache_aside: ["앱", "Redis", "DB", "쓰기 반영", "응답"],
    redis_only_reference: ["앱", "Redis", "응답"],
  }[mode] || ["앱", "응답"];
}

function buildRequestFlowSteps(request) {
  const stageDurations = new Map(request.stageDurations.map((stage) => [stage.stage, stage]));
  const stageOrder = [];
  const seenStages = new Set();

  for (const event of request.events) {
    if (!isVisualFlowStage(event.stage) || seenStages.has(event.stage)) {
      continue;
    }
    seenStages.add(event.stage);
    stageOrder.push(event.stage);
  }

  if (stageOrder.length === 0) {
    for (const stage of fallbackStageOrderForRequest(request)) {
      if (!seenStages.has(stage)) {
        seenStages.add(stage);
        stageOrder.push(stage);
      }
    }
  }

  return stageOrder.map((stage) => {
    const details = stageDurations.get(stage) || { durationMs: 0, eventCount: 0 };
    return {
      key: stage,
      label: localizeFlowNodeLabel(stage),
      accent: describeFlowStepAccent(stage, request),
      toneClass: flowToneClassForStage(stage, request),
      durationMs: Number(details.durationMs || 0),
      eventCount: Number(details.eventCount || 0),
    };
  });
}

function buildTimelineStageRows(requests) {
  const preferredOrder = ["request", "redis_lookup", "db_lookup", "writeback", "response"];
  const activeStages = preferredOrder.filter((stage) => requests.some((request) => request.events.some((event) => event.stage === stage)));
  const rows = activeStages.length > 0 ? activeStages : preferredOrder;
  return rows.map((stage, index) => ({
    key: stage,
    index,
    label: localizeStageLabel(stage),
  }));
}

function isVisualFlowStage(stage) {
  return ["request", "redis_lookup", "db_lookup", "writeback", "response"].includes(stage);
}

function fallbackStageOrderForRequest(request) {
  if (request.mode === "db_only") {
    return ["request", "db_lookup", "response"];
  }
  if (request.mode === "redis_only_reference") {
    return ["request", "redis_lookup", "response"];
  }
  if (request.cacheStatus === "hit") {
    return ["request", "redis_lookup", "response"];
  }
  if (request.cacheStatus === "fallback" || request.cacheStatus === "error") {
    return ["request", "redis_lookup", "db_lookup", "response"];
  }
  if (request.cacheStatus === "miss" || request.cacheStatus === "miss_writeback_failed") {
    return ["request", "redis_lookup", "db_lookup", "writeback", "response"];
  }
  return ["request", "redis_lookup", "response"];
}

function localizeFlowNodeLabel(stage) {
  return {
    request: "앱",
    redis_lookup: "Redis",
    db_lookup: "DB",
    writeback: "쓰기 반영",
    response: "응답",
  }[stage] || localizeStageLabel(stage);
}

function describeFlowStepAccent(stage, request) {
  if (stage === "request") {
    return "시작";
  }
  if (stage === "redis_lookup") {
    if (request.mode === "redis_only_reference") {
      return "기준선 조회";
    }
    return {
      hit: "적중",
      reference_hit: "적중",
      miss: "미스",
      miss_writeback_failed: "미스",
      fallback: "폴백",
      error: "오류",
      unknown: "조회",
    }[request.cacheStatus] || "조회";
  }
  if (stage === "db_lookup") {
    return request.mode === "db_only" ? "기준 경로" : "폴백/미스";
  }
  if (stage === "writeback") {
    return request.cacheStatus === "miss_writeback_failed" ? "반영 실패" : "캐시 반영";
  }
  if (stage === "response") {
    return request.hasError ? "오류 응답" : "완료";
  }
  return "";
}

function flowToneClassForStage(stage, request) {
  if (stage === "request") {
    return "flow-tone-app";
  }
  if (stage === "db_lookup") {
    return "flow-tone-db";
  }
  if (stage === "writeback") {
    return request.cacheStatus === "miss_writeback_failed" ? "flow-tone-error" : "flow-tone-writeback";
  }
  if (stage === "response") {
    return request.hasError ? "flow-tone-error" : "flow-tone-response";
  }

  if (request.mode === "redis_only_reference" || request.cacheStatus === "reference_hit") {
    return "flow-tone-reference";
  }
  if (request.cacheStatus === "hit") {
    return "flow-tone-hit";
  }
  if (request.cacheStatus === "miss" || request.cacheStatus === "miss_writeback_failed") {
    return "flow-tone-miss";
  }
  if (request.cacheStatus === "fallback") {
    return "flow-tone-fallback";
  }
  return "flow-tone-error";
}

function renderFlowRouteMarkup(steps, request, options = {}) {
  const detailed = options.detailed === true;
  return `
    <div class="flow-route ${detailed ? "detail-route" : ""}">
      ${steps.map((step, index) => `
        <div class="flow-step">
          <span class="flow-step-node ${step.toneClass}">${escapeHtml(step.label)}</span>
          <span class="flow-step-caption">${escapeHtml(renderFlowStepCaption(step, request))}</span>
        </div>
        ${index < steps.length - 1 ? '<i class="flow-step-arrow" aria-hidden="true"></i>' : ""}
      `).join("")}
    </div>
  `;
}

function renderFlowStepCaption(step, request) {
  if (step.durationMs > 0) {
    return `${step.accent} · ${formatMs(step.durationMs)}`;
  }
  if (step.key === "request") {
    return "진입";
  }
  if (step.key === "response") {
    return request.hasError ? "응답 종료" : "응답";
  }
  return step.accent;
}

function renderFlowMeterMarkup(request, steps, options = {}) {
  const detailed = options.detailed === true;
  const measurableSteps = steps.filter((step) => step.durationMs > 0);
  if (measurableSteps.length === 0) {
    return `
      <div class="flow-meter-shell ${detailed ? "detail-flow-meter-shell" : ""}">
        <div class="flow-meter-empty">측정된 단계 소요시간이 아직 없습니다.</div>
      </div>
    `;
  }

  const totalDuration = Math.max(request.totalDurationMs, measurableSteps.reduce((sum, step) => sum + step.durationMs, 0), 0.01);
  return `
    <div class="flow-meter-shell ${detailed ? "detail-flow-meter-shell" : ""}">
      <div class="flow-meter">
        ${measurableSteps.map((step) => `
          <span
            class="flow-meter-segment ${step.toneClass}"
            style="flex: ${Math.max(step.durationMs, 0.2)}"
            title="${escapeHtml(`${step.label} · ${formatMs(step.durationMs)}`)}"
          ></span>
        `).join("")}
      </div>
      <div class="flow-meter-labels">
        ${measurableSteps.map((step) => `
          <span>${escapeHtml(`${step.label} ${formatPercent((step.durationMs / totalDuration) * 100)}`)}</span>
        `).join("")}
      </div>
    </div>
  `;
}

function renderTimelineSeriesMarkup(request, stageRows, maxTime, width, height, padding, isPrimary) {
  const windows = buildStageWindows(request, stageRows);
  if (windows.length === 0) {
    return "";
  }

  const toneClass = `timeline-${requestTokenTone(request)}`;
  const classStr = `${toneClass} ${isPrimary ? "primary" : "secondary"}`;

  // 각 단계의 픽셀 좌표를 먼저 계산합니다 (최소 폭 6px 보장).
  const MIN_SEGMENT_PX = 6;
  const segments = windows.map((win) => {
    const y      = timelineYForStage(win.stage, stageRows, padding);
    const startX = timelineXForTime(win.startMs, maxTime, width, padding);
    const rawEndX = timelineXForTime(win.endMs, maxTime, width, padding);
    const endX   = Math.max(rawEndX, startX + MIN_SEGMENT_PX);
    return { y, startX, endX };
  });

  // 단계 사이 전환을 cubic Bezier S-커브로 연결합니다.
  // 직각 꺾임(L x oldY → L x newY) 대신:
  //   C midX oldY, midX newY, newX newY
  // 이렇게 하면 두 Y레벨 사이가 자연스러운 S자 곡선으로 이어집니다.
  const points = [];
  segments.forEach((seg, index) => {
    if (index === 0) {
      points.push(`M ${seg.startX} ${seg.y}`);
    } else {
      const prev = segments[index - 1];
      const midX = (prev.endX + seg.startX) / 2;
      // S-커브: 이전 단계 끝에서 현재 단계 시작까지
      points.push(`C ${midX} ${prev.y}, ${midX} ${seg.y}, ${seg.startX} ${seg.y}`);
    }
    // 단계 내 수평 선분
    points.push(`L ${seg.endX} ${seg.y}`);
  });

  // 각 단계 끝에 원형 마커 배치
  const markers = segments.map((seg) => `
    <circle
      class="timeline-marker ${classStr}"
      cx="${seg.endX}" cy="${seg.y}"
      r="${isPrimary ? 5 : 3.2}"
    ></circle>
  `).join("");

  const lastSeg = segments.at(-1);
  const labelX  = Math.min(width - padding.right - 6, lastSeg.endX + 10);
  const labelY  = lastSeg.y - (isPrimary ? 12 : 8);

  return `
    <path class="timeline-path ${classStr}" d="${points.join(" ")}"></path>
    ${markers}
    <text
      class="timeline-request-label ${isPrimary ? "primary" : "secondary"}"
      x="${labelX}" y="${labelY}"
    >#${request.sequence}</text>
  `;
}

function buildStageWindows(request, stageRows) {
  const eventsByStage = new Map();
  for (const event of request.events) {
    if (!eventsByStage.has(event.stage)) {
      eventsByStage.set(event.stage, []);
    }
    eventsByStage.get(event.stage).push(event);
  }

  const orderedStages = buildRequestFlowSteps(request).map((step) => step.key);
  const windows = [];
  let cursor = 0;

  orderedStages.forEach((stage) => {
    if (!stageRows.some((row) => row.key === stage)) {
      return;
    }
    const stageEvents = (eventsByStage.get(stage) || []).slice().sort((left, right) => Number(left.timestamp || 0) - Number(right.timestamp || 0));
    const duration = Number(request.stageDurations.find((item) => item.stage === stage)?.durationMs || 0);
    const rawStartMs = stageEvents[0] ? Number(stageEvents[0].timestamp || 0) : cursor;
    const startMs = Math.max(cursor, rawStartMs);
    let endMs = stageEvents.at(-1) ? Number(stageEvents.at(-1).timestamp || 0) : startMs + duration;
    if (endMs < startMs) {
      endMs = startMs;
    }
    if (endMs === startMs && duration > 0) {
      endMs = startMs + duration;
    }
    cursor = Math.max(cursor, endMs);
    windows.push({
      stage,
      startMs,
      endMs,
    });
  });

  return windows;
}

function timelineXForTime(value, maxTime, width, padding) {
  const innerWidth = width - padding.left - padding.right;
  return padding.left + (Math.max(0, Number(value || 0)) / Math.max(maxTime, 0.01)) * innerWidth;
}

function timelineYForStage(stage, stageRows, padding) {
  const rowGap = 70;
  const rowIndex = stageRows.find((row) => row.key === stage)?.index || 0;
  return padding.top + rowIndex * rowGap;
}

function renderEventTimelineMarkup(request) {
  const orderedEvents = request.events.slice().sort((left, right) => Number(left.timestamp || 0) - Number(right.timestamp || 0));
  if (orderedEvents.length === 0) {
    return emptyStateMarkup("이벤트가 없습니다", "이 요청에는 아직 표시할 이벤트가 없습니다.", true);
  }

  return orderedEvents.map((event, index) => `
    <article class="detail-event-row">
      <div class="detail-event-rail">
        <span class="detail-event-dot ${flowToneClassForEvent(event, request)}"></span>
        ${index < orderedEvents.length - 1 ? '<span class="detail-event-line"></span>' : ""}
      </div>
      <div class="detail-event-copy">
        <strong>${escapeHtml(localizeEventTypeLabel(event.event_type))}</strong>
        <span>${escapeHtml(`${localizeStageLabel(event.stage)} · ${formatRelativeMs(event.timestamp)}`)}</span>
        <span>${escapeHtml(renderEventTimelineMeta(event))}</span>
      </div>
    </article>
  `).join("");
}

function flowToneClassForEvent(event, request) {
  if (event.event_type === "error") {
    return "flow-tone-error";
  }
  if (event.stage === "db_lookup") {
    return "flow-tone-db";
  }
  if (event.stage === "writeback") {
    return request.cacheStatus === "miss_writeback_failed" ? "flow-tone-error" : "flow-tone-writeback";
  }
  if (event.stage === "response") {
    return request.hasError ? "flow-tone-error" : "flow-tone-response";
  }
  return flowToneClassForStage(event.stage, request);
}

function renderEventTimelineMeta(event) {
  const parts = [];
  if (typeof event.duration_ms === "number" && event.duration_ms > 0) {
    parts.push(formatMs(event.duration_ms));
  }
  const metadata = summarizeMetadata(event.metadata);
  if (metadata) {
    parts.push(metadata);
  }
  return parts.length > 0 ? parts.join(" · ") : "메타데이터 없음";
}

function localizeEventTypeLabel(eventType) {
  return {
    request_started: "요청 시작",
    cache_lookup_started: "캐시 조회 시작",
    cache_lookup_completed: "캐시 조회 완료",
    cache_hit: "캐시 적중",
    cache_miss: "캐시 미스",
    db_query_started: "DB 조회 시작",
    db_query_completed: "DB 조회 완료",
    cache_set: "캐시 반영",
    fallback_used: "폴백 사용",
    response_sent: "응답 전송",
    error: "오류 기록",
  }[eventType] || eventType;
}

function formatRelativeMs(value) {
  return `+${Number(value || 0).toFixed(2)} ms`;
}

function isPlaybackCurrentRequest(request) {
  if (!state.playback.active) {
    return false;
  }
  return state.requests[state.playback.cursor]?.id === request.id;
}

function getVisibleRequests() {
  if (state.playback.active) {
    return state.requests.slice(0, state.playback.cursor + 1);
  }
  return state.requests.slice(-18);
}

function getLaneSummaryItem(mode) {
  const laneSummary = state.presentation?.lane_summary || buildFallbackLaneSummary();
  return laneSummary.find((item) => item.mode === mode) || null;
}

function deriveCacheStatus(events, mode) {
  if (mode === "db_only") {
    return "db_only";
  }
  if (mode === "redis_only_reference") {
    return "reference_hit";
  }
  if (events.some((event) => event.event_type === "error")) {
    return "error";
  }
  if (events.some((event) => event.event_type === "fallback_used")) {
    return "fallback";
  }
  if (events.some((event) => event.event_type === "cache_hit")) {
    return "hit";
  }
  if (events.some((event) => event.event_type === "cache_miss")) {
    return "miss";
  }
  return "unknown";
}

function derivePathSummary(mode, cacheStatus) {
  if (mode === "db_only") {
    return "DB 전용: 앱 -> DB -> 응답";
  }
  if (mode === "redis_only_reference") {
    return "Redis 기준선: 앱 -> Redis -> 응답";
  }
  if (cacheStatus === "hit") {
    return "Redis + DB 적중: 앱 -> Redis -> 응답";
  }
  if (cacheStatus === "fallback") {
    return "Redis + DB 폴백: 앱 -> Redis(오류) -> DB -> 응답";
  }
  if (cacheStatus === "miss" || cacheStatus === "miss_writeback_failed") {
    return "Redis + DB 미스: 앱 -> Redis -> DB -> Redis -> 응답";
  }
  if (cacheStatus === "error") {
    return "Redis + DB 오류: 앱 -> Redis(오류) -> DB -> 응답";
  }
  return "캐시 경로: 앱 -> Redis -> 응답";
}

function humanizeCacheStatus(cacheStatus, mode) {
  if (mode === "db_only") {
    return "DB 전용";
  }
  if (mode === "redis_only_reference") {
    return "기준선 적중";
  }
  const lookup = {
    hit: "Redis 적중",
    miss: "Redis 미스",
    miss_writeback_failed: "Redis 미스 후 쓰기 반영 실패",
    fallback: "폴백 사용",
    error: "오류 경로",
    unknown: "알 수 없는 캐시 상태",
  };
  return lookup[cacheStatus] || cacheStatus;
}

function humanizeMode(mode) {
  return {
    db_only: "DB 전용",
    cache_aside: "Redis + DB",
    redis_only_reference: "Redis 기준선",
  }[mode] || mode;
}

function humanizeScenario(scenario) {
  return {
    detail_page: "상세 페이지",
  }[scenario] || scenario;
}

function localizeSeriesLabel(label) {
  return {
    "DB Only": "DB 전용",
    "DB Only Avg": "DB 전용 평균",
    "Redis Hit Avg": "Redis 적중 평균",
    "Redis Miss Avg": "Redis 미스 평균",
    "Redis + DB": "Redis + DB",
    "Redis + DB Avg": "Redis + DB 평균",
    "Redis Only Reference": "Redis 기준선",
    "Redis Only Avg": "Redis 전용 평균",
    "Redis Reference": "Redis 기준선",
    "Redis reference": "Redis 기준선",
    "Redis Hit": "Redis 적중",
    "Redis Miss": "Redis 미스",
    Fallback: "폴백",
    Error: "오류",
  }[label] || label;
}

function localizeStageLabel(stage) {
  return {
    request: "요청",
    redis_lookup: "Redis 조회",
    db_lookup: "DB 조회",
    writeback: "쓰기 반영",
    response: "응답",
    bootstrap: "초기 준비",
    warmup: "워밍업",
    baseline_run: "기준선 실행",
    cache_run: "캐시 실행",
    reference_run: "기준선 Redis 실행",
    aggregation: "집계",
    failed: "실패",
  }[stage] || stage;
}

function localizePathSummary(pathSummary, mode, cacheStatus, hasError = false) {
  const raw = String(pathSummary || "").trim();
  const lookup = {
    "App -> DB -> Response": "앱 -> DB -> 응답",
    "App -> Redis -> Response": "앱 -> Redis -> 응답",
    "App -> Redis -> DB -> Redis -> Response": "앱 -> Redis -> DB -> Redis -> 응답",
    "App -> Redis -> DB -> Response": "앱 -> Redis -> DB -> 응답",
    "App -> Redis(error) -> DB -> Response": "앱 -> Redis(오류) -> DB -> 응답",
  };

  if (raw && lookup[raw]) {
    const prefix = raw === "App -> DB -> Response"
      ? "DB 전용"
      : mode === "redis_only_reference"
        ? "Redis 기준선"
        : cacheStatus === "hit"
          ? "Redis + DB 적중"
          : cacheStatus === "fallback"
            ? "Redis + DB 폴백"
            : cacheStatus === "miss" || cacheStatus === "miss_writeback_failed"
              ? "Redis + DB 미스"
              : hasError
                ? "Redis + DB 오류"
                : "캐시 경로";
    return `${prefix}: ${lookup[raw]}`;
  }

  if (raw) {
    return raw
      .replaceAll("App", "앱")
      .replaceAll("Response", "응답")
      .replaceAll("Redis(error)", "Redis(오류)");
  }

  return derivePathSummary(mode, hasError ? "error" : cacheStatus);
}

function requestTokenTone(request) {
  if (request.mode === "db_only") {
    return "db_only";
  }
  if (request.mode === "redis_only_reference") {
    return "reference_hit";
  }
  if (request.hasError) {
    return "error";
  }
  if (request.cacheStatus === "fallback") {
    return "fallback";
  }
  if (request.cacheStatus === "miss") {
    return "miss";
  }
  return "hit";
}

function latencySeriesTone(label) {
  if (label.includes("DB Only") || label.includes("DB 전용")) {
    return "chart-bar-db";
  }
  if (label.includes("Redis Hit") || label.includes("Redis 적중")) {
    return "chart-bar-hit";
  }
  if (label.includes("Redis Miss") || label.includes("Redis 미스")) {
    return "chart-bar-miss";
  }
  if (label.includes("Redis Only") || label.includes("Redis 전용") || label.includes("Redis 기준선")) {
    return "chart-bar-reference";
  }
  return "chart-bar-cache";
}

function pathSeriesTone(label) {
  if (label === "DB Only" || label === "DB 전용") {
    return "mix-fill-db";
  }
  if (label === "Redis Hit" || label === "Redis 적중") {
    return "mix-fill-hit";
  }
  if (label === "Redis Miss" || label === "Redis 미스") {
    return "mix-fill-miss";
  }
  if (label === "Redis Reference" || label === "Redis 기준선") {
    return "mix-fill-reference";
  }
  if (label === "Fallback" || label === "폴백") {
    return "mix-fill-fallback";
  }
  return "mix-fill-error";
}

function formatKpiValue(key, value) {
  if (value == null) {
    return "--";
  }
  if (key.endsWith("_avg_ms") || key.startsWith("p95_")) {
    return formatMs(value);
  }
  if (key === "speedup_ratio") {
    return formatRatio(value);
  }
  if (key === "break_even_hit_rate" || key === "cache_hit_rate") {
    return formatPercent(value);
  }
  return String(value);
}

function formatMs(value) {
  return `${Number(value).toFixed(2)} ms`;
}

function formatRatio(value) {
  return `${Number(value).toFixed(2)}x`;
}

function formatPercent(value) {
  return `${Number(value).toFixed(2).replace(/\.00$/, "")}%`;
}

function formatDateTime(isoValue) {
  const parsed = new Date(isoValue);
  return Number.isNaN(parsed.getTime()) ? isoValue : parsed.toLocaleString();
}

function formatEpoch(seconds) {
  return new Date(Number(seconds) * 1000).toLocaleTimeString();
}

function humanizeStatus(status) {
  return {
    queued: "대기열 등록",
    bootstrapping: "초기 준비",
    warming_up: "워밍업",
    running_baseline: "기준선 실행",
    running_cache: "캐시 실행",
    running_reference: "기준선 Redis 실행",
    aggregating: "집계 중",
    completed: "완료",
    failed: "실패",
  }[status] || String(status).replaceAll("_", " ");
}

function summarizeMetadata(metadata) {
  if (!metadata || typeof metadata !== "object" || Array.isArray(metadata)) {
    return "";
  }
  const entries = Object.entries(metadata).slice(0, 3);
  return entries.map(([key, value]) => `${key}=${value}`).join(" · ");
}

function parseBucketInput(rawValue) {
  return Array.from(new Set(rawValue
    .split(",")
    .map((value) => Number(value.trim()))
    .filter((value) => Number.isInteger(value) && value >= 0 && value <= 100)))
    .sort((left, right) => left - right);
}

function firstNumericMetadata(events, key) {
  for (const event of events) {
    const value = event.metadata?.[key];
    if (typeof value === "number") {
      return value;
    }
  }
  return null;
}

function normalizeRequests(requests) {
  return requests.map((request, index) => {
    const events = Array.isArray(request.events) ? request.events : [];
    const bucket = firstNumericMetadata(events, "bucket");
    const hasError = Boolean(request.has_error);
    const stageDurations = Object.entries(request.stage_durations || {}).map(([stage, duration]) => ({
      stage,
      durationMs: Number(duration),
      eventCount: events.filter((event) => event.stage === stage).length,
    }));
    return {
      id: request.request_id,
      mode: request.mode,
      sequence: index + 1,
      events,
      totalDurationMs: Number(request.total_duration_ms || 0),
      startedAtMs: Number(request.started_at_ms || 0),
      finishedAtMs: Number(request.finished_at_ms || 0),
      bucket,
      cacheStatus: request.cache_status,
      cacheStatusLabel: humanizeCacheStatus(request.cache_status, request.mode),
      pathSummary: localizePathSummary(request.path_summary, request.mode, request.cache_status, hasError),
      stageDurations,
      hasError,
      eventCount: Number(request.event_count || events.length),
    };
  });
}

function buildFallbackLatencySeries() {
  const summary = state.currentRun?.summary;
  if (!summary) {
    return [];
  }
  const items = [
    { label: "DB Only Avg", value: Number(summary.db_avg_ms || 0) },
  ];
  if (summary.redis_hit_avg_ms != null) {
    items.push({ label: "Redis Hit Avg", value: Number(summary.redis_hit_avg_ms) });
  }
  if (summary.redis_miss_avg_ms != null) {
    items.push({ label: "Redis Miss Avg", value: Number(summary.redis_miss_avg_ms) });
  }
  if (items.length === 1) {
    items.push({ label: "Redis + DB Avg", value: Number(summary.redis_avg_ms || 0) });
  }
  if (summary.reference_avg_ms != null) {
    items.push({ label: "Redis Only Avg", value: Number(summary.reference_avg_ms) });
  }
  return items;
}

function buildFallbackPathSeries() {
  return [
    { label: "DB Only", value: state.requests.filter((request) => request.mode === "db_only").length },
    { label: "Redis Hit", value: state.requests.filter((request) => request.cacheStatus === "hit").length },
    { label: "Redis Miss", value: state.requests.filter((request) => request.cacheStatus === "miss" || request.cacheStatus === "miss_writeback_failed").length },
    { label: "Redis Reference", value: state.requests.filter((request) => request.mode === "redis_only_reference").length },
    { label: "Fallback", value: state.requests.filter((request) => request.cacheStatus === "fallback").length },
    { label: "Error", value: state.requests.filter((request) => request.hasError).length },
  ];
}

function buildFallbackStageTotals() {
  const totals = new Map();
  for (const request of state.requests) {
    for (const stage of request.stageDurations) {
      totals.set(stage.stage, Number(((totals.get(stage.stage) || 0) + stage.durationMs).toFixed(2)));
    }
  }
  return Array.from(totals.entries()).map(([label, value]) => ({ label, value }));
}

function buildFallbackLaneSummary() {
  return ["db_only", "cache_aside", "redis_only_reference"]
    .map((mode) => {
      const laneRequests = state.requests.filter((request) => request.mode === mode);
      if (laneRequests.length === 0 && mode === "redis_only_reference") {
        return null;
      }
      const label = {
        db_only: "DB 전용",
        cache_aside: "Redis + DB",
        redis_only_reference: "Redis 기준선",
      }[mode] || mode;
      return {
        mode,
        label,
        request_count: laneRequests.length,
        avg_duration_ms: laneRequests.length ? average(laneRequests.map((request) => request.totalDurationMs)) : null,
        hit_count: laneRequests.filter((request) => request.cacheStatus === "hit" || request.cacheStatus === "reference_hit").length,
        miss_count: laneRequests.filter((request) => request.cacheStatus === "miss" || request.cacheStatus === "miss_writeback_failed").length,
        fallback_count: laneRequests.filter((request) => request.cacheStatus === "fallback").length,
        error_count: laneRequests.filter((request) => request.hasError).length,
      };
    })
    .filter(Boolean);
}

function average(values) {
  if (values.length === 0) {
    return 0;
  }
  const total = values.reduce((sum, value) => sum + value, 0);
  return Number((total / values.length).toFixed(2));
}

function emptyStateMarkup(title, description, compact = false) {
  return `
    <div class="empty-state ${compact ? "compact" : ""}">
      <div>
        <h3>${escapeHtml(title)}</h3>
        <p>${escapeHtml(description)}</p>
      </div>
    </div>
  `;
}

function emptyChartMarkup(title, description) {
  return `
    <div class="chart-empty">
      <div>
        <h3>${escapeHtml(title)}</h3>
        <p>${escapeHtml(description)}</p>
      </div>
    </div>
  `;
}

function setScenarioNote(message) {
  if (!message) {
    elements.scenarioNote.hidden = true;
    elements.scenarioNote.textContent = "";
    return;
  }

  elements.scenarioNote.hidden = false;
  elements.scenarioNote.textContent = message;
}

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

async function apiFetch(path, options = {}) {
  const requestUrl = resolveApiUrl(path);
  let response;
  try {
    response = await window.fetch(requestUrl, options);
  } catch (error) {
    throw new Error(buildNetworkErrorMessage(requestUrl));
  }
  const isJson = response.headers.get("Content-Type")?.includes("application/json");
  const payload = isJson ? await response.json() : null;

  if (!response.ok) {
    throw new Error(payload?.error || `요청이 실패했습니다: ${response.status}`);
  }

  return payload;
}

function resolveRuntimeContext() {
  const query = new URLSearchParams(window.location.search);
  const queryApiBase = query.get("apiBase");
  if (queryApiBase && queryApiBase.trim()) {
    const normalized = normalizeApiBase(queryApiBase);
    try {
      window.localStorage.setItem("mini-redis-benchmark.api-base", normalized);
    } catch {
      // localStorage can fail in locked-down browser modes; the override still works for this page load.
    }
    return {
      apiBase: normalized,
      apiBaseSource: "query",
      apiBaseCandidates: buildApiBaseCandidates(normalized),
      bundleBase: resolveBundleBase(),
    };
  }

  let storedApiBase = "";
  try {
    storedApiBase = window.localStorage.getItem("mini-redis-benchmark.api-base") || "";
  } catch {
    storedApiBase = "";
  }
  if (storedApiBase) {
    return {
      apiBase: normalizeApiBase(storedApiBase),
      apiBaseSource: "local_storage",
      apiBaseCandidates: buildApiBaseCandidates(storedApiBase),
      bundleBase: resolveBundleBase(),
    };
  }

  const metaApiBase = document
    .querySelector('meta[name="benchmark-api-base"]')
    ?.getAttribute("content");

  return {
    apiBase: normalizeApiBase(metaApiBase || "/api"),
    apiBaseSource: "meta",
    apiBaseCandidates: buildApiBaseCandidates(metaApiBase || "/api"),
    bundleBase: resolveBundleBase(),
  };
}

async function ensureReachableApiBase(options = {}) {
  const force = options.force === true;
  if (!force && state.apiBaseResolved) {
    return;
  }

  state.apiBaseResolved = true;
  const candidates = state.apiBaseCandidates.length > 0 ? state.apiBaseCandidates : [state.apiBase];
  const preferredBase = state.apiBasePreferred;
  const previousBase = state.apiBase;

  for (const candidate of candidates) {
    // Probe the list endpoint because it is lightweight and does not depend on mini-redis health.
    const isReachable = await probeApiBase(candidate);
    if (!isReachable) {
      continue;
    }

    state.apiBase = candidate;
    if (candidate === preferredBase) {
      state.apiBaseSource = state.apiBasePreferredSource;
      if (force && previousBase !== preferredBase) {
        setScenarioNote(`보조 연결에서 기본 API 기준 경로 ${preferredBase}로 복귀했습니다.`);
      }
    } else {
      state.apiBaseSource = "fallback";
      setScenarioNote(`기본 API 기준 경로 ${preferredBase}에 응답이 없어 ${candidate}로 보조 연결했습니다.`);
    }
    renderConnectionCard();
    return;
  }

  if (candidates.length > 1) {
    setScenarioNote(`기본 API와 보조 포트 후보 ${describeApiFallbackChain()} 어디에도 연결하지 못했습니다.`);
  }
  renderConnectionCard();
}

function resolveBundleBase() {
  return new URL("./", window.location.href).pathname;
}

function normalizeApiBase(value) {
  const trimmed = String(value || "").trim();
  if (!trimmed) {
    return "/api";
  }
  if (/^https?:\/\//i.test(trimmed)) {
    return trimmed.replace(/\/+$/, "");
  }
  if (trimmed.startsWith("/")) {
    return trimmed.replace(/\/+$/, "") || "/";
  }
  return `/${trimmed.replace(/^\/+/, "").replace(/\/+$/, "")}`;
}

function resolveApiUrl(path) {
  return resolveApiUrlForBase(state.apiBase, path);
}

function resolveApiUrlForBase(apiBase, path) {
  const baseUrl = new URL(ensureTrailingSlash(apiBase), window.location.href);
  const normalizedPath = String(path || "").replace(/^\/+/, "");
  const withoutApiPrefix = normalizedPath.startsWith("api/") ? normalizedPath.slice(4) : normalizedPath;
  return new URL(withoutApiPrefix, baseUrl).toString();
}

function ensureTrailingSlash(value) {
  return value.endsWith("/") ? value : `${value}/`;
}

function isSameOriginApi() {
  return new URL(ensureTrailingSlash(state.apiBase), window.location.href).origin === window.location.origin;
}

async function probeApiBase(apiBase) {
  const probeUrl = resolveApiUrlForBase(apiBase, "/api/benchmark-runs");
  try {
    const listResponse = await window.fetch(probeUrl, { method: "GET" });
    if (!listResponse.ok) {
      return false;
    }
    if (!listResponse.headers.get("Content-Type")?.includes("application/json")) {
      return false;
    }

    const candidateOrigin = new URL(ensureTrailingSlash(apiBase), window.location.href).origin;
    if (candidateOrigin === window.location.origin) {
      return true;
    }

    const optionsResponse = await window.fetch(probeUrl, { method: "OPTIONS" });
    return optionsResponse.ok;
  } catch {
    return false;
  }
}

function buildApiBaseCandidates(primaryApiBase) {
  const primary = normalizeApiBase(primaryApiBase);
  const candidates = [primary];
  const baseUrl = new URL(ensureTrailingSlash(primary), window.location.href);
  const protocol = window.location.protocol === "https:" ? "https:" : "http:";
  const localHosts = collectLocalHostnames(baseUrl.hostname || window.location.hostname);

  if (localHosts.length === 0) {
    return dedupeStrings(candidates);
  }

  for (const host of localHosts) {
    for (const port of ["8000", "8001", "8002"]) {
      candidates.push(`${protocol}//${host}:${port}/api`);
    }
  }

  return dedupeStrings(candidates);
}

function collectLocalHostnames(hostname) {
  const normalized = String(hostname || "").trim().toLowerCase();
  const hosts = [];
  if (isLocalHostname(normalized)) {
    hosts.push(normalized);
  }
  if (normalized === "localhost") {
    hosts.push("127.0.0.1");
  }
  if (normalized === "127.0.0.1") {
    hosts.push("localhost");
  }
  return dedupeStrings(hosts);
}

function isLocalHostname(hostname) {
  const normalized = String(hostname || "").trim().toLowerCase();
  return normalized === "localhost" || normalized === "127.0.0.1" || normalized === "0.0.0.0";
}

function dedupeStrings(values) {
  return Array.from(new Set(values.filter(Boolean)));
}

function describeApiFallbackChain() {
  const ports = new Set(
    state.apiBaseCandidates
      .map((candidate) => {
        try {
          const parsed = new URL(ensureTrailingSlash(candidate), window.location.href);
          return isLocalHostname(parsed.hostname) ? parsed.port : "";
        } catch {
          return "";
        }
      })
      .filter(Boolean),
  );
  const orderedPorts = ["8000", "8001", "8002"].filter((port) => ports.has(port));
  return orderedPorts.length > 0 ? orderedPorts.join(" -> ") : "없음";
}

function describeApiFallbackNote() {
  const chain = describeApiFallbackChain();
  return chain === "없음" ? "" : ` 실패 시 ${chain} 순서로 보조 연결을 시도합니다.`;
}

function describeApiFallbackMeta() {
  const chain = describeApiFallbackChain();
  return chain === "없음" ? "" : ` · 보조 포트 ${chain}`;
}

function buildNetworkErrorMessage(requestUrl) {
  const targetUrl = new URL(requestUrl);
  if (targetUrl.origin !== window.location.origin) {
    return (
      `${targetUrl.origin}에 연결할 수 없습니다. ` +
      "교차 origin 미리보기는 CORS 또는 리버스 프록시가 있어야 API가 응답합니다."
    );
  }
  return (
    `${targetUrl.pathname}에 연결할 수 없습니다. ` +
    "이 origin에서 벤치마크 컨트롤러가 /api를 서빙하고 있는지 확인하세요."
  );
}
