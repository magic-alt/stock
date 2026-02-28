/* ============================================================
   Unified Quant Platform – Live Console (app.js)
   State management, form validation, auto-refresh, notifications.
   ============================================================ */

// ---------------------------------------------------------------------------
// State
// ---------------------------------------------------------------------------
var state = {
  connected: false,
  broker: "-",
  mode: "-",
  refreshTimer: null,
  REFRESH_MS: 5000,
};

// ---------------------------------------------------------------------------
// DOM references
// ---------------------------------------------------------------------------
var statusEl = document.getElementById("gateway-status");
var metaEl = document.getElementById("gateway-meta");
var accountEl = document.getElementById("account");
var positionsEl = document.getElementById("positions");
var jobsEl = document.getElementById("jobs");

// ---------------------------------------------------------------------------
// API helpers
// ---------------------------------------------------------------------------
function apiGet(path) {
  return fetch(path).then(function (res) {
    if (!res.ok) throw new Error("HTTP " + res.status);
    return res.json();
  });
}

function apiPost(path, payload) {
  return fetch(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload || {}),
  }).then(function (res) {
    if (!res.ok) throw new Error("HTTP " + res.status);
    return res.json();
  });
}

// ---------------------------------------------------------------------------
// Notifications
// ---------------------------------------------------------------------------
function notify(msg, level) {
  level = level || "info";
  var bar = document.getElementById("notify-bar");
  if (!bar) {
    bar = document.createElement("div");
    bar.id = "notify-bar";
    bar.style.cssText =
      "position:fixed;top:12px;right:12px;z-index:9999;max-width:400px;" +
      "padding:10px 16px;border-radius:8px;font-size:13px;color:#fff;" +
      "box-shadow:0 4px 12px rgba(0,0,0,.25);transition:opacity .3s;";
    document.body.appendChild(bar);
  }
  var bg = { info: "#3b82f6", success: "#22c55e", error: "#ef4444", warning: "#f59e0b" };
  bar.style.background = bg[level] || bg.info;
  bar.textContent = msg;
  bar.style.opacity = "1";
  clearTimeout(bar._hideTimer);
  bar._hideTimer = setTimeout(function () {
    bar.style.opacity = "0";
  }, 4000);
}

// ---------------------------------------------------------------------------
// Status / data display
// ---------------------------------------------------------------------------
function setStatus(data) {
  var st = (data && data.gateway && data.gateway.status) || (data && data.status) || "disconnected";
  var mode = (data && data.gateway && data.gateway.mode) || "-";
  var broker = (data && data.gateway && data.gateway.broker) || "-";
  state.connected = st === "connected";
  state.mode = mode;
  state.broker = broker;
  statusEl.textContent = st;
  metaEl.textContent = "mode: " + mode + " \u00b7 broker: " + broker;
  statusEl.style.background = state.connected
    ? "rgba(123, 223, 242, 0.2)"
    : "rgba(246, 193, 119, 0.2)";
}

function showJson(target, payload) {
  target.textContent = JSON.stringify(payload || {}, null, 2);
}

// ---------------------------------------------------------------------------
// Data refresh functions
// ---------------------------------------------------------------------------
async function refreshStatus() {
  try {
    var data = await apiGet("/gateway/status");
    setStatus(data);
  } catch (_) {
    setStatus({});
  }
}

async function refreshAccount() {
  try {
    var data = await apiGet("/gateway/account");
    showJson(accountEl, data.account || data);
  } catch (err) {
    showJson(accountEl, { error: String(err) });
  }
}

async function refreshPositions() {
  try {
    var data = await apiGet("/gateway/positions");
    showJson(positionsEl, data.positions || data);
  } catch (err) {
    showJson(positionsEl, { error: String(err) });
  }
}

async function refreshJobs() {
  try {
    var data = await apiGet("/jobs");
    showJson(jobsEl, data.jobs || data);
  } catch (err) {
    showJson(jobsEl, { error: String(err) });
  }
}

async function refreshAll() {
  await Promise.all([refreshStatus(), refreshAccount(), refreshPositions(), refreshJobs()]);
}

function startAutoRefresh() {
  stopAutoRefresh();
  state.refreshTimer = setInterval(refreshAll, state.REFRESH_MS);
}

function stopAutoRefresh() {
  if (state.refreshTimer) {
    clearInterval(state.refreshTimer);
    state.refreshTimer = null;
  }
}

// ---------------------------------------------------------------------------
// Form payload readers (with validation)
// ---------------------------------------------------------------------------
function val(id) {
  var el = document.getElementById(id);
  return el ? el.value.trim() : "";
}

function readConnectPayload() {
  return {
    mode: val("mode"),
    broker: val("broker"),
    host: val("host"),
    port: val("port"),
    account: val("account_id"),
    password: val("password"),
    api_key: val("api_key"),
    secret: val("secret"),
    initial_cash: val("initial_cash"),
    commission_rate: val("commission_rate"),
    slippage: val("slippage"),
    enable_risk_check: document.getElementById("enable_risk_check")
      ? document.getElementById("enable_risk_check").checked
      : true,
    terminal_type: val("terminal_type"),
    terminal_path: val("terminal_path"),
    trade_server: val("trade_server"),
    quote_server: val("quote_server"),
    client_id: val("client_id"),
    td_front: val("td_front"),
    md_front: val("md_front"),
  };
}

function readOrderPayload() {
  var symbol = val("order-symbol");
  var side = val("order-side");
  var qty = val("order-qty");
  var price = val("order-price");
  var orderType = val("order-type");

  if (!symbol) return { _error: "Symbol is required" };
  if (!qty || isNaN(Number(qty)) || Number(qty) <= 0)
    return { _error: "Quantity must be a positive number" };
  if (orderType === "limit" && (!price || isNaN(Number(price)) || Number(price) <= 0))
    return { _error: "Limit orders require a positive price" };

  return { symbol: symbol, side: side, quantity: qty, price: price, order_type: orderType };
}

function readCancelPayload() {
  var orderId = val("cancel-id");
  if (!orderId) return { _error: "Order ID is required" };
  return { order_id: orderId };
}

function readPricePayload() {
  var symbol = val("price-symbol");
  var price = val("price-value");
  if (!symbol) return { _error: "Symbol is required" };
  if (!price || isNaN(Number(price)) || Number(price) <= 0)
    return { _error: "Price must be a positive number" };
  return { symbol: symbol, price: price };
}

// ---------------------------------------------------------------------------
// Event handlers
// ---------------------------------------------------------------------------
document.getElementById("connect-form").addEventListener("submit", async function (event) {
  event.preventDefault();
  try {
    var data = await apiPost("/gateway/connect", readConnectPayload());
    setStatus(data);
    notify("Gateway connected", "success");
    startAutoRefresh();
  } catch (err) {
    notify("Connection failed: " + err.message, "error");
  }
});

document.getElementById("disconnect").addEventListener("click", async function () {
  try {
    var data = await apiPost("/gateway/disconnect", {});
    setStatus(data);
    notify("Gateway disconnected", "warning");
    stopAutoRefresh();
  } catch (err) {
    notify("Disconnect failed: " + err.message, "error");
  }
});

document.getElementById("order-form").addEventListener("submit", async function (event) {
  event.preventDefault();
  var payload = readOrderPayload();
  if (payload._error) {
    notify(payload._error, "error");
    return;
  }
  try {
    await apiPost("/gateway/order", payload);
    notify("Order submitted: " + payload.side + " " + payload.symbol, "success");
    await refreshAccount();
    await refreshPositions();
  } catch (err) {
    notify("Order failed: " + err.message, "error");
  }
});

document.getElementById("cancel-form").addEventListener("submit", async function (event) {
  event.preventDefault();
  var payload = readCancelPayload();
  if (payload._error) {
    notify(payload._error, "error");
    return;
  }
  try {
    await apiPost("/gateway/cancel", payload);
    notify("Cancel sent: " + payload.order_id, "success");
  } catch (err) {
    notify("Cancel failed: " + err.message, "error");
  }
});

var priceForm = document.getElementById("price-form");
if (priceForm) {
  priceForm.addEventListener("submit", async function (event) {
    event.preventDefault();
    var payload = readPricePayload();
    if (payload._error) {
      notify(payload._error, "error");
      return;
    }
    try {
      await apiPost("/gateway/price", payload);
      notify("Price updated: " + payload.symbol + " = " + payload.price, "info");
    } catch (err) {
      notify("Price update failed: " + err.message, "error");
    }
  });
}

// Manual refresh buttons
var refreshAccountBtn = document.getElementById("refresh-account");
if (refreshAccountBtn) refreshAccountBtn.addEventListener("click", refreshAccount);

var refreshPositionsBtn = document.getElementById("refresh-positions");
if (refreshPositionsBtn) refreshPositionsBtn.addEventListener("click", refreshPositions);

var refreshJobsBtn = document.getElementById("refresh-jobs");
if (refreshJobsBtn) refreshJobsBtn.addEventListener("click", refreshJobs);

// ---------------------------------------------------------------------------
// WebSocket real-time updates (optional – server must support ws)
// ---------------------------------------------------------------------------
function connectWebSocket() {
  var protocol = location.protocol === "https:" ? "wss:" : "ws:";
  var wsUrl = protocol + "//" + location.host + "/ws";
  var ws;
  try {
    ws = new WebSocket(wsUrl);
  } catch (_) {
    return;
  }

  ws.onopen = function () {
    notify("WebSocket connected", "info");
  };

  ws.onmessage = function (event) {
    try {
      var msg = JSON.parse(event.data);
      if (msg.type === "status") setStatus(msg.data);
      else if (msg.type === "account") showJson(accountEl, msg.data);
      else if (msg.type === "positions") showJson(positionsEl, msg.data);
      else if (msg.type === "order") notify("Order update: " + (msg.data && msg.data.status || ""), "info");
      else if (msg.type === "trade") notify("Trade: " + JSON.stringify(msg.data), "success");
    } catch (_) {
      /* ignore parse errors */
    }
  };

  ws.onclose = function () {
    setTimeout(connectWebSocket, 5000);
  };

  ws.onerror = function () {
    ws.close();
  };
}

// ---------------------------------------------------------------------------
// K-line Chart (ECharts)
// ---------------------------------------------------------------------------
var _klineChart = null;

function renderKlineChart(data) {
  var container = document.getElementById("kline-chart");
  if (!container || typeof echarts === "undefined") return;
  if (_klineChart) _klineChart.dispose();
  _klineChart = echarts.init(container, "dark");

  var dates = data.dates || [];
  var ohlc = data.ohlc || [];
  var volumes = data.volumes || [];

  var option = {
    tooltip: { trigger: "axis", axisPointer: { type: "cross" } },
    legend: { data: ["K-line", "Volume"], top: 0 },
    grid: [
      { left: "8%", right: "4%", top: "12%", height: "55%" },
      { left: "8%", right: "4%", top: "72%", height: "18%" },
    ],
    xAxis: [
      { type: "category", data: dates, gridIndex: 0, boundaryGap: true },
      { type: "category", data: dates, gridIndex: 1, boundaryGap: true },
    ],
    yAxis: [
      { scale: true, gridIndex: 0 },
      { scale: true, gridIndex: 1, splitNumber: 2 },
    ],
    dataZoom: [
      { type: "inside", xAxisIndex: [0, 1], start: 60, end: 100 },
      { type: "slider", xAxisIndex: [0, 1], start: 60, end: 100, top: "94%" },
    ],
    series: [
      {
        name: "K-line",
        type: "candlestick",
        data: ohlc,
        xAxisIndex: 0,
        yAxisIndex: 0,
        itemStyle: {
          color: "#ef4444",
          color0: "#22c55e",
          borderColor: "#ef4444",
          borderColor0: "#22c55e",
        },
      },
      {
        name: "Volume",
        type: "bar",
        data: volumes,
        xAxisIndex: 1,
        yAxisIndex: 1,
        itemStyle: { color: "rgba(59,130,246,0.5)" },
      },
    ],
  };
  _klineChart.setOption(option);
}

async function loadChart() {
  var symbol = val("chart-symbol");
  var days = val("chart-days") || "120";
  if (!symbol) { notify("Symbol is required", "error"); return; }
  try {
    var data = await apiGet(
      "/api/v1/chart-data?symbol=" + encodeURIComponent(symbol) + "&days=" + days
    );
    var chartData = (data && data.data) || data;
    if (!chartData || !chartData.dates || chartData.dates.length === 0) {
      notify("No chart data available", "warning");
      return;
    }
    renderKlineChart(chartData);
    notify("Chart loaded: " + symbol, "success");
  } catch (err) {
    notify("Chart load failed: " + err.message, "error");
  }
}

var chartForm = document.getElementById("chart-form");
if (chartForm) {
  chartForm.addEventListener("submit", function (event) {
    event.preventDefault();
    loadChart();
  });
}

// ---------------------------------------------------------------------------
// Boot
// ---------------------------------------------------------------------------
refreshAll();
startAutoRefresh();
connectWebSocket();
