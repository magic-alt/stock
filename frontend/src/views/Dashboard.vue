<template>
  <div class="dashboard">
    <el-row :gutter="16" class="mb-4">
      <el-col :span="6" v-for="stat in statsCards" :key="stat.label">
        <el-card shadow="never" class="stat-card">
          <div class="stat-label">{{ stat.label }}</div>
          <div class="stat-value" :class="stat.color">{{ stat.value }}</div>
        </el-card>
      </el-col>
    </el-row>

    <el-row :gutter="16" class="mb-4">
      <el-col :span="16">
        <el-card shadow="never" class="dark-card">
          <template #header>
            <span>System Status</span>
          </template>
          <el-descriptions :column="2" border size="small">
            <el-descriptions-item label="Gateway">
              <el-tag :type="tradingStore.connected ? 'success' : 'danger'" size="small">
                {{ tradingStore.status.status }}
              </el-tag>
            </el-descriptions-item>
            <el-descriptions-item label="Mode">{{ tradingStore.status.mode }}</el-descriptions-item>
            <el-descriptions-item label="Broker">{{ tradingStore.status.broker }}</el-descriptions-item>
            <el-descriptions-item label="Strategies">{{ strategyCount }}</el-descriptions-item>
          </el-descriptions>
        </el-card>
      </el-col>
      <el-col :span="8">
        <el-card shadow="never" class="dark-card">
          <template #header>
            <span>Quick Actions</span>
          </template>
          <el-space direction="vertical" fill style="width: 100%">
            <el-button type="primary" style="width: 100%" @click="$router.push('/backtest')">
              New Backtest
            </el-button>
            <el-button style="width: 100%" @click="$router.push('/trading')">
              Trading Console
            </el-button>
            <el-button style="width: 100%" @click="$router.push('/strategies')">
              Strategy Library
            </el-button>
          </el-space>
        </el-card>
      </el-col>
    </el-row>

    <el-row :gutter="16">
      <el-col :span="24">
        <el-card shadow="never" class="dark-card">
          <template #header>
            <span>Recent Backtest Results</span>
          </template>
          <el-table :data="backtestStore.history.slice(0, 10)" stripe style="width: 100%" size="small">
            <el-table-column prop="strategy" label="Strategy" width="140" />
            <el-table-column label="Return" width="100">
              <template #default="{ row }">
                <span :class="row.cum_return >= 0 ? 'text-green' : 'text-red'">
                  {{ formatPct(row.cum_return) }}
                </span>
              </template>
            </el-table-column>
            <el-table-column label="Sharpe" width="90">
              <template #default="{ row }">{{ formatNum(row.sharpe) }}</template>
            </el-table-column>
            <el-table-column label="MDD" width="90">
              <template #default="{ row }">
                <span class="text-red">{{ formatPct(row.mdd) }}</span>
              </template>
            </el-table-column>
            <el-table-column label="Trades" width="80" prop="trades" />
            <el-table-column label="Win Rate" width="90">
              <template #default="{ row }">{{ formatPct(row.win_rate) }}</template>
            </el-table-column>
          </el-table>
          <el-empty v-if="backtestStore.history.length === 0" description="No backtest results yet" />
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted } from 'vue'
import { useTradingStore } from '@/stores/trading'
import { useBacktestStore } from '@/stores/backtest'
import client from '@/api/client'
import { ref } from 'vue'

const tradingStore = useTradingStore()
const backtestStore = useBacktestStore()
const strategyCount = ref(0)

onMounted(async () => {
  tradingStore.fetchStatus()
  try {
    const resp = await client.get('/api/v2/strategies')
    strategyCount.value = resp.data.count || 0
  } catch { /* ignore */ }
})

const statsCards = computed(() => [
  { label: 'Gateway', value: tradingStore.connected ? 'Online' : 'Offline', color: tradingStore.connected ? 'text-green' : 'text-red' },
  { label: 'Strategies', value: String(strategyCount.value), color: '' },
  { label: 'Backtests', value: String(backtestStore.history.length), color: '' },
  { label: 'Positions', value: String(tradingStore.positions.length), color: '' },
])

function formatPct(v: number | undefined): string {
  if (v === undefined || v !== v) return 'N/A'
  return (v * 100).toFixed(2) + '%'
}

function formatNum(v: number | undefined): string {
  if (v === undefined || v !== v) return 'N/A'
  return v.toFixed(4)
}
</script>

<style scoped>
.dashboard { max-width: 1400px; }
.mb-4 { margin-bottom: 16px; }
.stat-card {
  background: var(--bg-card);
  border-color: var(--border);
  text-align: center;
}
.stat-label { color: var(--text-secondary); font-size: 12px; text-transform: uppercase; }
.stat-value { font-size: 24px; font-weight: 700; margin-top: 6px; }
.dark-card { background: var(--bg-card); border-color: var(--border); }
.text-green { color: var(--green); }
.text-red { color: var(--red); }
</style>
