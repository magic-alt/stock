<template>
  <div class="backtest-page">
    <el-row :gutter="16">
      <el-col :span="8">
        <el-card shadow="never" class="dark-card">
          <template #header><span>Backtest Configuration</span></template>
          <el-form :model="form" label-position="top" size="small">
            <el-form-item label="Strategy">
              <el-select v-model="form.strategy" placeholder="Select strategy" style="width: 100%" filterable>
                <el-option v-for="s in strategies" :key="s.name" :label="s.name" :value="s.name" />
              </el-select>
            </el-form-item>
            <el-form-item label="Symbols (comma separated)">
              <el-input v-model="form.symbolsStr" placeholder="600519.SH,000001.SZ" />
            </el-form-item>
            <el-form-item label="Date Range">
              <el-date-picker v-model="form.dateRange" type="daterange" start-placeholder="Start"
                end-placeholder="End" value-format="YYYY-MM-DD" style="width: 100%" />
            </el-form-item>
            <el-form-item label="Initial Cash">
              <el-input-number v-model="form.cash" :min="10000" :step="10000" style="width: 100%" />
            </el-form-item>
            <el-form-item label="Commission">
              <el-input-number v-model="form.commission" :min="0" :max="0.01" :step="0.0001"
                :precision="4" style="width: 100%" />
            </el-form-item>
            <el-form-item>
              <el-button type="primary" @click="runBacktest" :loading="backtestStore.loading" style="width: 100%">
                Run Backtest
              </el-button>
            </el-form-item>
          </el-form>
        </el-card>
      </el-col>

      <el-col :span="16">
        <el-card shadow="never" class="dark-card" v-if="backtestStore.lastResult">
          <template #header><span>Results: {{ backtestStore.lastResult.strategy }}</span></template>
          <el-row :gutter="12" class="mb-4">
            <el-col :span="6" v-for="kpi in kpis" :key="kpi.label">
              <div class="kpi-box">
                <div class="kpi-label">{{ kpi.label }}</div>
                <div class="kpi-value" :class="kpi.cls">{{ kpi.value }}</div>
              </div>
            </el-col>
          </el-row>
        </el-card>
        <el-card shadow="never" class="dark-card" v-else>
          <el-empty description="Configure and run a backtest to see results" />
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useBacktestStore } from '@/stores/backtest'
import client, { unwrapApiData } from '@/api/client'
import type { StrategyInfo } from '@/api/types'

const backtestStore = useBacktestStore()
const strategies = ref<StrategyInfo[]>([])

const form = ref({
  strategy: '',
  symbolsStr: '600519.SH',
  dateRange: ['2024-01-01', '2024-12-31'] as [string, string],
  cash: 100000,
  commission: 0.001,
})

onMounted(async () => {
  try {
    const resp = await client.get('/api/v2/strategies')
    const data = unwrapApiData<{ strategies: StrategyInfo[] }>(resp.data)
    strategies.value = data.strategies || []
  } catch { /* ignore */ }
})

const kpis = computed(() => {
  const r = backtestStore.lastResult
  if (!r) return []
  return [
    { label: 'Return', value: fmtPct(r.cum_return), cls: (r.cum_return ?? 0) >= 0 ? 'text-green' : 'text-red' },
    { label: 'Sharpe', value: fmtNum(r.sharpe), cls: (r.sharpe ?? 0) >= 1 ? 'text-green' : '' },
    { label: 'MDD', value: fmtPct(r.mdd), cls: 'text-red' },
    { label: 'Trades', value: String(r.trades ?? 0), cls: '' },
  ]
})

function fmtPct(v: unknown): string {
  const n = Number(v)
  if (isNaN(n)) return 'N/A'
  return (n * 100).toFixed(2) + '%'
}

function fmtNum(v: unknown): string {
  const n = Number(v)
  if (isNaN(n)) return 'N/A'
  return n.toFixed(4)
}

async function runBacktest() {
  const symbols = form.value.symbolsStr.split(',').map(s => s.trim()).filter(Boolean)
  await backtestStore.runBacktest({
    strategy: form.value.strategy,
    symbols,
    start: form.value.dateRange[0],
    end: form.value.dateRange[1],
    cash: form.value.cash,
    commission: form.value.commission,
  })
}
</script>

<style scoped>
.mb-4 { margin-bottom: 16px; }
.dark-card { background: var(--bg-card); border-color: var(--border); margin-bottom: 16px; }
.kpi-box { background: var(--bg-secondary); border: 1px solid var(--border); border-radius: 8px; padding: 12px; text-align: center; }
.kpi-label { font-size: 11px; color: var(--text-secondary); text-transform: uppercase; }
.kpi-value { font-size: 20px; font-weight: 700; margin-top: 4px; }
.text-green { color: var(--green); }
.text-red { color: var(--red); }
</style>
