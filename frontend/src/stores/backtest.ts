import { defineStore } from 'pinia'
import { ref } from 'vue'
import client, { unwrapApiData } from '@/api/client'
import type { BacktestMetrics } from '@/api/types'

export const useBacktestStore = defineStore('backtest', () => {
  const loading = ref(false)
  const lastResult = ref<BacktestMetrics | null>(null)
  const error = ref<string | null>(null)
  const history = ref<BacktestMetrics[]>([])

  async function runBacktest(params: {
    strategy: string
    symbols: string[]
    start: string
    end: string
    cash?: number
    commission?: number
    slippage?: number
    params?: Record<string, unknown>
  }) {
    loading.value = true
    error.value = null
    try {
      const resp = await client.post('/api/v2/strategies/run', params)
      const data = unwrapApiData<{ metrics: BacktestMetrics }>(resp.data)
      if (data.metrics) {
        lastResult.value = data.metrics
        history.value.unshift(data.metrics)
      } else {
        error.value = 'Backtest failed'
      }
    } catch (e) {
      error.value = (e as Error).message
    } finally {
      loading.value = false
    }
  }

  return { loading, lastResult, error, history, runBacktest }
})
