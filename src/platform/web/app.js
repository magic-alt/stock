const statusEl = document.getElementById("gateway-status");
const metaEl = document.getElementById("gateway-meta");
const accountEl = document.getElementById("account");
const positionsEl = document.getElementById("positions");
const jobsEl = document.getElementById("jobs");

function apiGet(path) {
  return fetch(path).then((res) => res.json());
}

function apiPost(path, payload) {
  return fetch(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload || {}),
  }).then((res) => res.json());
}

function setStatus(data) {
  const status = data?.gateway?.status || data?.status || "disconnected";
  const mode = data?.gateway?.mode || "-";
  const broker = data?.gateway?.broker || "-";
  statusEl.textContent = status;
  metaEl.textContent = `mode: ${mode} · broker: ${broker}`;
  statusEl.style.background = status === "connected" ? "rgba(123, 223, 242, 0.2)" : "rgba(246, 193, 119, 0.2)";
}

function showJson(target, payload) {
  target.textContent = JSON.stringify(payload || {}, null, 2);
}

async function refreshStatus() {
  const data = await apiGet("/gateway/status").catch(() => ({}));
  setStatus(data);
}

async function refreshAccount() {
  const data = await apiGet("/gateway/account").catch((err) => ({ error: String(err) }));
  showJson(accountEl, data.account || data);
}

async function refreshPositions() {
  const data = await apiGet("/gateway/positions").catch((err) => ({ error: String(err) }));
  showJson(positionsEl, data.positions || data);
}

async function refreshJobs() {
  const data = await apiGet("/jobs").catch((err) => ({ error: String(err) }));
  showJson(jobsEl, data.jobs || data);
}

function readConnectPayload() {
  return {
    mode: document.getElementById("mode").value,
    broker: document.getElementById("broker").value,
    host: document.getElementById("host").value,
    port: document.getElementById("port").value,
    account: document.getElementById("account_id").value,
    password: document.getElementById("password").value,
    api_key: document.getElementById("api_key").value,
    secret: document.getElementById("secret").value,
    initial_cash: document.getElementById("initial_cash").value,
    commission_rate: document.getElementById("commission_rate").value,
    slippage: document.getElementById("slippage").value,
    enable_risk_check: document.getElementById("enable_risk_check").checked,
    terminal_type: document.getElementById("terminal_type").value,
    terminal_path: document.getElementById("terminal_path").value,
    trade_server: document.getElementById("trade_server").value,
    quote_server: document.getElementById("quote_server").value,
    client_id: document.getElementById("client_id").value,
    td_front: document.getElementById("td_front").value,
    md_front: document.getElementById("md_front").value,
  };
}

function readOrderPayload() {
  return {
    symbol: document.getElementById("order-symbol").value,
    side: document.getElementById("order-side").value,
    quantity: document.getElementById("order-qty").value,
    price: document.getElementById("order-price").value,
    order_type: document.getElementById("order-type").value,
  };
}

function readCancelPayload() {
  return {
    order_id: document.getElementById("cancel-id").value,
  };
}

function readPricePayload() {
  return {
    symbol: document.getElementById("price-symbol").value,
    price: document.getElementById("price-value").value,
  };
}

const connectForm = document.getElementById("connect-form");
connectForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const data = await apiPost("/gateway/connect", readConnectPayload());
  setStatus(data);
});

const disconnectBtn = document.getElementById("disconnect");
disconnectBtn.addEventListener("click", async () => {
  const data = await apiPost("/gateway/disconnect", {});
  setStatus(data);
});

const orderForm = document.getElementById("order-form");
orderForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  await apiPost("/gateway/order", readOrderPayload());
  await refreshAccount();
  await refreshPositions();
});

const cancelForm = document.getElementById("cancel-form");
cancelForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  await apiPost("/gateway/cancel", readCancelPayload());
});

const priceForm = document.getElementById("price-form");
priceForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  await apiPost("/gateway/price", readPricePayload());
});

const refreshAccountBtn = document.getElementById("refresh-account");
refreshAccountBtn.addEventListener("click", refreshAccount);

const refreshPositionsBtn = document.getElementById("refresh-positions");
refreshPositionsBtn.addEventListener("click", refreshPositions);

const refreshJobsBtn = document.getElementById("refresh-jobs");
refreshJobsBtn.addEventListener("click", refreshJobs);

refreshStatus();
refreshAccount();
refreshPositions();
refreshJobs();
