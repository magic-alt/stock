import { defineStore } from 'pinia'
import { ref } from 'vue'
import client from '@/api/client'
import type { GatewayStatus, AccountInfo, PositionInfo } from '@/api/types'

export const useTradingStore = defineStore('trading', () => {
  const connected = ref(false)
  const status = ref<GatewayStatus>({ status: 'disconnected', mode: '-', broker: '-' })
  const account = ref<AccountInfo | null>(null)
  const positions = ref<PositionInfo[]>([])
  const refreshTimer = ref<ReturnType<typeof setInterval> | null>(null)

  async function fetchStatus() {
    try {
      const resp = await client.get('/gateway/status')
      const data = resp.data
      status.value = data.gateway || data
      connected.value = (status.value.status === 'connected')
    } catch {
      connected.value = false
    }
  }

  async function fetchAccount() {
    try {
      const resp = await client.get('/gateway/account')
      account.value = resp.data.account || resp.data
    } catch { /* ignore */ }
  }

  async function fetchPositions() {
    try {
      const resp = await client.get('/gateway/positions')
      positions.value = resp.data.positions || []
    } catch { /* ignore */ }
  }

  async function refreshAll() {
    await Promise.all([fetchStatus(), fetchAccount(), fetchPositions()])
  }

  function startAutoRefresh(intervalMs = 5000) {
    stopAutoRefresh()
    refreshTimer.value = setInterval(refreshAll, intervalMs)
  }

  function stopAutoRefresh() {
    if (refreshTimer.value) {
      clearInterval(refreshTimer.value)
      refreshTimer.value = null
    }
  }

  return {
    connected, status, account, positions,
    fetchStatus, fetchAccount, fetchPositions, refreshAll,
    startAutoRefresh, stopAutoRefresh,
  }
})
