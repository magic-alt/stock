import { defineStore } from 'pinia'
import { ref } from 'vue'
import client, { unwrapApiData } from '@/api/client'
import type { BacktestJobPayload, BacktestMetrics, BacktestRunPayload, JobInfo } from '@/api/types'

export const useBacktestStore = defineStore('backtest', () => {
  const loading = ref(false)
  const jobLoading = ref(false)
  const lastResult = ref<BacktestMetrics | null>(null)
  const activeJob = ref<JobInfo | null>(null)
  const error = ref<string | null>(null)
  const history = ref<BacktestMetrics[]>([])

  function recordResult(metrics: BacktestMetrics) {
    lastResult.value = metrics
    history.value.unshift(metrics)
  }

  async function runBacktest(params: BacktestRunPayload) {
    loading.value = true
    error.value = null
    try {
      const resp = await client.post('/api/v2/backtest/run', params)
      const data = unwrapApiData<{ metrics: BacktestMetrics }>(resp.data)
      if (data.metrics) {
        recordResult(data.metrics)
      } else {
        error.value = 'Backtest failed'
      }
    } catch (e) {
      error.value = (e as Error).message
    } finally {
      loading.value = false
    }
  }

  async function submitBacktestJob(params: BacktestJobPayload) {
    jobLoading.value = true
    error.value = null
    try {
      const resp = await client.post('/api/v2/backtest/jobs', params)
      const data = unwrapApiData<{ job_id: string }>(resp.data)
      if (!data.job_id) {
        error.value = 'Backtest job submission failed'
        return null
      }
      const job = await fetchBacktestJob(data.job_id)
      return job
    } catch (e) {
      error.value = (e as Error).message
      return null
    } finally {
      jobLoading.value = false
    }
  }

  async function fetchBacktestJob(jobId: string) {
    jobLoading.value = true
    error.value = null
    try {
      const resp = await client.get(`/api/v2/backtest/jobs/${jobId}`)
      const data = unwrapApiData<{ job: JobInfo }>(resp.data)
      activeJob.value = data.job
      const metrics = data.job?.result?.metrics as BacktestMetrics | undefined
      if (metrics) {
        recordResult(metrics)
      }
      return data.job
    } catch (e) {
      error.value = (e as Error).message
      return null
    } finally {
      jobLoading.value = false
    }
  }

  async function cancelBacktestJob(jobId: string) {
    jobLoading.value = true
    error.value = null
    try {
      const resp = await client.post(`/api/v2/backtest/jobs/${jobId}/cancel`)
      const data = unwrapApiData<{ job: JobInfo }>(resp.data)
      activeJob.value = data.job
      return data.job
    } catch (e) {
      error.value = (e as Error).message
      return null
    } finally {
      jobLoading.value = false
    }
  }

  return {
    activeJob,
    cancelBacktestJob,
    error,
    fetchBacktestJob,
    history,
    jobLoading,
    lastResult,
    loading,
    runBacktest,
    submitBacktestJob,
  }
})
