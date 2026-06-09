import { defineStore } from 'pinia'
import { ref } from 'vue'
import client, { unwrapApiData } from '@/api/client'
import type {
  AccountInfo,
  GatewayConnectPayload,
  GatewaySnapshot,
  GatewayStatus,
  OrderInfo,
  PositionInfo,
  TradeInfo,
} from '@/api/types'

const DEFAULT_STATUS: GatewayStatus = {
  status: 'disconnected',
  connected: false,
  mode: '-',
  broker: '-',
  account: '',
  connected_at: null,
  last_error: null,
}

const DEFAULT_PAPER_CONNECT_PAYLOAD: GatewayConnectPayload = {
  mode: 'paper',
  broker: 'paper',
  host: '127.0.0.1',
  port: 11111,
  account: 'paper',
  password: '',
  api_key: '',
  secret: '',
  initial_cash: 1_000_000,
  commission_rate: 0.0003,
  slippage: 0.0001,
  enable_risk_check: true,
  terminal_type: 'QMT',
  terminal_path: '',
  trade_server: '',
  quote_server: '',
  client_id: 1,
  td_front: '',
  md_front: '',
  sdk_path: '',
  sdk_log_path: '',
  gateway_provider: 'self',
  qmt_provider: 'self',
  vnpy_gateway: '',
  vnpy_setting: {},
  broker_options: {},
}

function normalizeStatus(value: unknown): GatewayStatus {
  if (!value || typeof value !== 'object') {
    return { ...DEFAULT_STATUS }
  }
  const raw = value as Partial<GatewayStatus>
  return {
    ...DEFAULT_STATUS,
    ...raw,
    connected: Boolean(raw.connected),
  }
}

function normalizePositions(value: unknown): PositionInfo[] {
  if (Array.isArray(value)) {
    return value as PositionInfo[]
  }
  if (value && typeof value === 'object') {
    return Object.values(value as Record<string, PositionInfo>)
  }
  return []
}

function normalizeOrders(value: unknown): OrderInfo[] {
  return Array.isArray(value) ? (value as OrderInfo[]) : []
}

function normalizeTrades(value: unknown): TradeInfo[] {
  return Array.isArray(value) ? (value as TradeInfo[]) : []
}

export const useTradingStore = defineStore('trading', () => {
  const connected = ref(false)
  const loading = ref(false)
  const error = ref<string | null>(null)
  const status = ref<GatewayStatus>({ ...DEFAULT_STATUS })
  const account = ref<AccountInfo | null>(null)
  const positions = ref<PositionInfo[]>([])
  const orders = ref<OrderInfo[]>([])
  const trades = ref<TradeInfo[]>([])
  const refreshTimer = ref<ReturnType<typeof setInterval> | null>(null)
  let gatewayInitPromise: Promise<boolean> | null = null

  function applySnapshot(snapshot: Partial<GatewaySnapshot> | null | undefined) {
    const statusValue = snapshot?.status ? normalizeStatus(snapshot.status) : { ...DEFAULT_STATUS }
    status.value = statusValue
    connected.value = statusValue.connected
    account.value = (snapshot?.account as AccountInfo | null | undefined) ?? null
    positions.value = normalizePositions(snapshot?.positions)
    orders.value = normalizeOrders(snapshot?.orders)
    trades.value = normalizeTrades(snapshot?.trades)
  }

  async function fetchStatus() {
    try {
      const resp = await client.get('/api/v2/gateway/status')
      const data = unwrapApiData<{ gateway: GatewayStatus }>(resp.data)
      const nextStatus = normalizeStatus(data.gateway)
      status.value = nextStatus
      connected.value = nextStatus.connected
    } catch (err) {
      connected.value = false
      status.value = { ...DEFAULT_STATUS, last_error: (err as Error).message }
    }
  }

  async function refreshAll(limit = 50) {
    loading.value = true
    error.value = null
    try {
      const resp = await client.get('/api/v2/gateway/snapshot', { params: { limit } })
      const data = unwrapApiData<{ gateway: GatewaySnapshot }>(resp.data)
      applySnapshot(data.gateway)
    } catch (err) {
      error.value = (err as Error).message
      applySnapshot(null)
    } finally {
      loading.value = false
    }
  }

  async function connectGateway(payload: GatewayConnectPayload) {
    loading.value = true
    error.value = null
    try {
      const resp = await client.post('/api/v2/gateway/connect', payload)
      const data = unwrapApiData<{ gateway: GatewayStatus }>(resp.data)
      status.value = normalizeStatus(data.gateway)
      connected.value = status.value.connected
      await refreshAll()
    } catch (err) {
      error.value = (err as Error).message
      throw err
    } finally {
      loading.value = false
    }
  }

  async function ensurePaperGatewayConnected() {
    if (connected.value) {
      return true
    }
    if (gatewayInitPromise) {
      return gatewayInitPromise
    }
    gatewayInitPromise = (async () => {
      await fetchStatus()
      if (connected.value) {
        await refreshAll()
        return true
      }
      try {
        await connectGateway({ ...DEFAULT_PAPER_CONNECT_PAYLOAD })
        return connected.value
      } catch (err) {
        error.value = (err as Error).message
        return false
      }
    })().finally(() => {
      gatewayInitPromise = null
    })
    return gatewayInitPromise
  }

  async function disconnectGateway() {
    try {
      const resp = await client.post('/api/v2/gateway/disconnect', {})
      const data = unwrapApiData<{ gateway: GatewayStatus }>(resp.data)
      status.value = normalizeStatus(data.gateway)
      connected.value = status.value.connected
      account.value = null
      positions.value = []
      orders.value = []
      trades.value = []
    } catch (err) {
      error.value = (err as Error).message
      throw err
    }
  }

  async function submitOrder(payload: Record<string, unknown>) {
    const resp = await client.post('/api/v2/gateway/order', payload)
    const data = unwrapApiData<{ order_id: string }>(resp.data)
    await refreshAll()
    return data.order_id
  }

  async function cancelOrder(orderId: string) {
    const resp = await client.post('/api/v2/gateway/cancel', { order_id: orderId })
    const data = unwrapApiData<{ cancelled: boolean }>(resp.data)
    await refreshAll()
    return data.cancelled
  }

  async function updatePrice(symbol: string, price: number) {
    await client.post('/api/v2/gateway/price', { symbol, price })
    await refreshAll()
  }

  function startAutoRefresh(intervalMs = 5000) {
    stopAutoRefresh()
    refreshTimer.value = setInterval(() => {
      void refreshAll()
    }, intervalMs)
  }

  function stopAutoRefresh() {
    if (refreshTimer.value) {
      clearInterval(refreshTimer.value)
      refreshTimer.value = null
    }
  }

  return {
    account,
    cancelOrder,
    connectGateway,
    connected,
    disconnectGateway,
    error,
    ensurePaperGatewayConnected,
    fetchStatus,
    loading,
    orders,
    positions,
    refreshAll,
    startAutoRefresh,
    status,
    stopAutoRefresh,
    submitOrder,
    trades,
    updatePrice,
  }
})
