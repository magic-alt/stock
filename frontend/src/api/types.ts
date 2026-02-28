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
  mode: string
  broker: string
}

export interface AccountInfo {
  total_assets: number
  available_cash: number
  frozen_cash: number
  market_value: number
  [key: string]: unknown
}

export interface PositionInfo {
  symbol: string
  quantity: number
  avg_cost: number
  market_value: number
  unrealized_pnl: number
  [key: string]: unknown
}

export interface JobInfo {
  id: string
  strategy: string
  status: string
  created_at: string
  [key: string]: unknown
}

export interface SystemMetrics {
  cpu_percent: number
  memory_percent: number
  disk_percent: number
  uptime_seconds: number
}
