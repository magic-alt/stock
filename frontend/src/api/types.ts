export interface StrategyParam {
  type: string
  default: unknown
}

export interface StrategyInfo {
  name: string
  description: string
  params: Record<string, StrategyParam>
}

export interface BacktestMetrics {
  strategy: string
  cum_return: number
  ann_return: number
  ann_vol: number
  sharpe: number
  mdd: number
  calmar: number
  win_rate: number
  trades: number
  [key: string]: unknown
}

export interface GatewayStatus {
  status: string
  connected: boolean
  mode: string
  broker: string
  account?: string
  connected_at?: string | null
  last_error?: string | null
}

export interface AccountInfo {
  account_id: string
  cash: number
  total_value: number
  available: number
  margin: number
  unrealized_pnl: number
  realized_pnl: number
  [key: string]: unknown
}

export interface PositionInfo {
  symbol: string
  size: number
  avg_price: number
  market_value: number
  unrealized_pnl: number
  realized_pnl: number
  [key: string]: unknown
}

export interface OrderInfo {
  order_id: string
  symbol: string
  side: string
  order_type: string
  price: number | null
  quantity: number
  filled_quantity: number
  avg_fill_price: number
  status: string
  create_time?: string | null
  update_time?: string | null
}

export interface TradeInfo {
  trade_id: string
  order_id: string
  symbol: string
  side: string
  price: number
  quantity: number
  commission: number
  timestamp?: string | null
}

export interface JobInfo {
  job_id: string
  task_type: string
  status: string
  created_at: string
  [key: string]: unknown
}

export interface SystemMetrics {
  timestamp?: string
  cpu_percent: number
  memory_percent: number
  memory_used_mb: number
  memory_available_mb: number
  disk_usage_percent: number
  disk_free_gb: number
  active_connections: number
  database_size_mb: number
}

export interface AlertInfo {
  level: string
  message: string
  timestamp: string
  details: Record<string, unknown>
}

export interface JobQueueMetrics {
  total_jobs: number
  pending_jobs: number
  running_jobs: number
  success_jobs: number
  failed_jobs: number
  cancelled_jobs: number
  in_flight_futures: number
  queue_delay_ms_p50: number
  queue_delay_ms_p95: number
  queue_delay_ms_p99: number
  run_duration_ms_p50: number
  run_duration_ms_p95: number
  run_duration_ms_p99: number
  [key: string]: unknown
}

export interface GatewaySnapshot {
  status: GatewayStatus
  account: AccountInfo | null
  positions: PositionInfo[]
  orders: OrderInfo[]
  trades: TradeInfo[]
}

export interface MonitorSummary {
  status: string
  timestamp: string
  system: SystemMetrics | null
  alerts: AlertInfo[]
  gateway: GatewaySnapshot
  job_queue: JobQueueMetrics
  api: Record<string, unknown>
  jobs: JobInfo[]
}

export interface GatewayConnectPayload {
  mode: string
  broker: string
  host: string
  port: number | null
  account: string
  password: string
  api_key: string
  secret: string
  initial_cash: number
  commission_rate: number
  slippage: number
  enable_risk_check: boolean
  terminal_type: string
  terminal_path: string
  trade_server: string
  quote_server: string
  client_id: number
  td_front: string
  md_front: string
}
