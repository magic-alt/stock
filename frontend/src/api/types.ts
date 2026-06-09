export interface StrategyParam {
  type: string
  default: unknown
}

export interface StrategyInfo {
  name: string
  description: string
  params: Record<string, StrategyParam>
}

export interface BacktestChartPoint {
  date: string
  value: number
}

export type NullableNumber = number | null

export interface BacktestTradeMarker {
  date: string
  type: 'BUY' | 'SELL' | string
  price: number
  size?: number | null
  symbol?: string
}

export interface BacktestTechnicalChart {
  symbol: string
  dates: string[]
  ohlc: number[][]
  volumes: number[]
  ma: {
    ma5: NullableNumber[]
    ma10: NullableNumber[]
    ma20: NullableNumber[]
    ma30: NullableNumber[]
  }
  boll: {
    upper: NullableNumber[]
    mid: NullableNumber[]
    lower: NullableNumber[]
  }
  rsi: NullableNumber[]
  macd: {
    dif: NullableNumber[]
    signal: NullableNumber[]
    hist: NullableNumber[]
  }
  kdj: {
    k: NullableNumber[]
    d: NullableNumber[]
    j: NullableNumber[]
  }
  trades: BacktestTradeMarker[]
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
  equity_curve?: BacktestChartPoint[]
  drawdown_curve?: BacktestChartPoint[]
  technical_chart?: BacktestTechnicalChart | null
  [key: string]: unknown
}

export interface BacktestRunPayload {
  strategy: string
  symbols: string[]
  start: string
  end: string
  cash?: number
  commission?: number
  slippage?: number
  params?: Record<string, unknown>
  source?: string
  benchmark_source?: string
  benchmark?: string
  adj?: string
  calendar_mode?: string
  engine?: string
}

export interface AnalysisPriceSummary {
  latest: number
  previous_close: number
  change: number
  change_pct: number
  range_20d: {
    low: number
    high: number
  }
}

export interface AnalysisSignal {
  score: number
  rating: 'buy' | 'watch' | 'sell'
  reasons: string[]
  risks: string[]
  disclaimer: string
}

export interface AnalysisBacktestPreview {
  enabled: boolean
  strategy?: string
  cum_return?: number
  sharpe?: number
  mdd?: number
  trades?: number
  reason?: string
  note?: string
}

export interface AnalysisAiSummary {
  enabled: boolean
  status: string
  text: string
  model?: string
  error?: string
}

export interface AnalysisResult {
  symbol: string
  as_of: string
  data_quality: {
    source: string
    rows: number
    warnings: string[]
    [key: string]: unknown
  }
  price: AnalysisPriceSummary
  indicators: Record<string, unknown>
  signal: AnalysisSignal
  chart_data: {
    dates: string[]
    ohlc: number[][]
    volumes: number[]
  }
  backtest_preview: AnalysisBacktestPreview
  ai_summary: AnalysisAiSummary
  markdown_report: string
}

export interface AnalysisRunPayload {
  symbol: string
  days?: number
  source?: string
  strategy?: string
  include_backtest?: boolean
  use_ai?: boolean
}

export interface BacktestJobPayload extends BacktestRunPayload {
  plot?: boolean
  report_dir?: string
  out_dir?: string
  cache_dir?: string
  register_data_lake?: boolean
  data_lake_dir?: string
}

export interface GatewayStatus {
  status: string
  connected: boolean
  mode: string
  broker: string
  gateway_provider?: string
  qmt_provider?: string
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

export type OrderStatus =
  | 'created'
  | 'submitted'
  | 'accepted'
  | 'partial_filled'
  | 'filled'
  | 'cancelled'
  | 'rejected'
  | 'expired'
  | 'pending'
  | 'partial'

export interface OrderInfo {
  order_id: string
  symbol: string
  side: string
  order_type: string
  price: number | null
  quantity: number
  filled_quantity: number
  avg_fill_price: number
  status: OrderStatus
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
  started_at?: string | null
  finished_at?: string | null
  cancelled_at?: string | null
  cancel_requested?: boolean
  result?: Record<string, unknown> | null
  error?: string | null
  payload?: Record<string, unknown>
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
  sdk_path: string
  sdk_log_path: string
  gateway_provider: string
  qmt_provider: string
  vnpy_gateway: string
  vnpy_setting: Record<string, unknown>
  broker_options: Record<string, unknown>
}
