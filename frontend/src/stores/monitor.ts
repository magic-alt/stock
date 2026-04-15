import { defineStore } from 'pinia'
import { ref } from 'vue'
import client, { unwrapApiData } from '@/api/client'
import type { AlertInfo, MonitorSummary, SystemMetrics } from '@/api/types'

const EMPTY_SUMMARY: MonitorSummary = {
  status: 'degraded',
  timestamp: '',
  system: null,
  alerts: [],
  gateway: {
    status: {
      status: 'disconnected',
      connected: false,
      mode: '-',
      broker: '-',
      account: '',
      connected_at: null,
      last_error: null,
    },
    account: null,
    positions: [],
    orders: [],
    trades: [],
  },
  job_queue: {
    total_jobs: 0,
    pending_jobs: 0,
    running_jobs: 0,
    success_jobs: 0,
    failed_jobs: 0,
    cancelled_jobs: 0,
    in_flight_futures: 0,
    queue_delay_ms_p50: 0,
    queue_delay_ms_p95: 0,
    queue_delay_ms_p99: 0,
    run_duration_ms_p50: 0,
    run_duration_ms_p95: 0,
    run_duration_ms_p99: 0,
  },
  api: {},
  jobs: [],
}

export const useMonitorStore = defineStore('monitor', () => {
  const loading = ref(false)
  const error = ref<string | null>(null)
  const summary = ref<MonitorSummary>({ ...EMPTY_SUMMARY })
  const history = ref<SystemMetrics[]>([])
  const alerts = ref<AlertInfo[]>([])
  const refreshTimer = ref<ReturnType<typeof setInterval> | null>(null)

  async function refresh(limit = 20) {
    loading.value = true
    error.value = null
    try {
      const [summaryResp, historyResp, alertsResp] = await Promise.all([
        client.get('/api/v2/monitor/summary', { params: { limit } }),
        client.get('/api/v2/monitor/history', { params: { limit } }),
        client.get('/api/v2/monitor/alerts', { params: { limit } }),
      ])

      const summaryData = unwrapApiData<{ monitor: MonitorSummary }>(summaryResp.data)
      const historyData = unwrapApiData<{ history: SystemMetrics[] }>(historyResp.data)
      const alertsData = unwrapApiData<{ alerts: AlertInfo[] }>(alertsResp.data)

      summary.value = summaryData.monitor
      history.value = historyData.history || []
      alerts.value = alertsData.alerts || []
    } catch (err) {
      error.value = (err as Error).message
    } finally {
      loading.value = false
    }
  }

  function startAutoRefresh(intervalMs = 5000) {
    stopAutoRefresh()
    refreshTimer.value = setInterval(() => {
      void refresh()
    }, intervalMs)
  }

  function stopAutoRefresh() {
    if (refreshTimer.value) {
      clearInterval(refreshTimer.value)
      refreshTimer.value = null
    }
  }

  return {
    alerts,
    error,
    history,
    loading,
    refresh,
    startAutoRefresh,
    stopAutoRefresh,
    summary,
  }
})
