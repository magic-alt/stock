<template>
  <div class="backtest-page">
    <div class="backtest-grid">
      <el-card shadow="never" class="dark-card config-panel">
        <template #header>
          <div class="card-header">
            <span>Backtest Configuration</span>
            <el-tag size="small" effect="plain">{{ selectedStrategy?.params ? paramEntries.length : 0 }} params</el-tag>
          </div>
        </template>

        <el-alert v-if="loadError" :title="loadError" type="warning" show-icon :closable="false" class="mb-4" />
        <el-alert v-if="backtestStore.error" :title="backtestStore.error" type="error" show-icon :closable="false" class="mb-4" />

        <el-form :model="form" label-position="top" size="small">
          <el-form-item label="Run Mode">
            <el-segmented v-model="form.runMode" :options="runModeOptions" class="full-width" />
          </el-form-item>

          <el-form-item label="Strategy" required>
            <el-select v-model="form.strategy" placeholder="Select strategy" class="full-width" filterable>
              <el-option v-for="s in strategies" :key="s.name" :label="s.name" :value="s.name" />
            </el-select>
          </el-form-item>

          <el-form-item label="Symbols" required>
            <el-input v-model="form.symbolsStr" placeholder="600519.SH,000001.SZ" />
          </el-form-item>

          <el-form-item label="Date Range" required>
            <el-date-picker
              v-model="form.dateRange"
              type="daterange"
              start-placeholder="Start"
              end-placeholder="End"
              value-format="YYYY-MM-DD"
              class="full-width"
            />
          </el-form-item>

          <div class="form-grid two">
            <el-form-item label="Initial Cash">
              <el-input-number v-model="form.cash" :min="1" :step="10000" class="full-width" />
            </el-form-item>
            <el-form-item label="Engine">
              <el-select v-model="form.engine" class="full-width">
                <el-option label="Backtrader" value="backtrader" />
                <el-option label="Zipline" value="zipline" />
              </el-select>
            </el-form-item>
          </div>

          <div class="form-grid two">
            <el-form-item label="Commission">
              <el-input-number v-model="form.commission" :min="0" :max="0.1" :step="0.0001" :precision="4" class="full-width" />
            </el-form-item>
            <el-form-item label="Slippage">
              <el-input-number v-model="form.slippage" :min="0" :max="0.1" :step="0.0001" :precision="4" class="full-width" />
            </el-form-item>
          </div>

          <div class="form-grid two">
            <el-form-item label="Data Source">
              <el-input v-model="form.source" placeholder="akshare" />
            </el-form-item>
            <el-form-item label="Benchmark Source">
              <el-input v-model="form.benchmarkSource" placeholder="akshare" />
            </el-form-item>
          </div>

          <div class="form-grid two">
            <el-form-item label="Benchmark">
              <el-input v-model="form.benchmark" placeholder="000300.SH" clearable />
            </el-form-item>
            <el-form-item label="Calendar">
              <el-select v-model="form.calendarMode" class="full-width">
                <el-option label="Off" value="off" />
                <el-option label="Fill" value="fill" />
                <el-option label="Drop" value="drop" />
              </el-select>
            </el-form-item>
          </div>

          <div class="form-grid two">
            <el-form-item label="Adjustment">
              <el-select v-model="form.adj" class="full-width" clearable>
                <el-option label="None" value="" />
                <el-option label="qfq" value="qfq" />
                <el-option label="hfq" value="hfq" />
              </el-select>
            </el-form-item>
            <el-form-item label="Generate Report">
              <el-switch v-model="form.plot" :disabled="form.runMode === 'sync'" />
            </el-form-item>
          </div>

          <el-divider v-if="paramEntries.length > 0" content-position="left">Strategy Parameters</el-divider>
          <div v-if="paramEntries.length > 0" class="param-grid">
            <el-form-item v-for="param in paramEntries" :key="param.name" :label="param.name">
              <el-switch v-if="param.kind === 'boolean'" v-model="paramValues[param.name]" />
              <el-input-number
                v-else-if="param.kind === 'number'"
                v-model="paramValues[param.name]"
                :step="param.step"
                class="full-width"
              />
              <el-input v-else v-model="paramValues[param.name]" />
            </el-form-item>
          </div>

          <el-form-item>
            <el-button
              type="primary"
              class="full-width"
              :loading="backtestStore.loading || backtestStore.jobLoading"
              @click="runBacktest"
            >
              {{ form.runMode === 'sync' ? 'Run Backtest' : 'Submit Backtest Job' }}
            </el-button>
          </el-form-item>
        </el-form>
      </el-card>

      <div class="result-panel">
        <el-card shadow="never" class="dark-card" v-if="backtestStore.activeJob">
          <template #header>
            <div class="card-header">
              <span>Job Status</span>
              <el-tag :type="jobTagType(backtestStore.activeJob.status)" size="small">
                {{ backtestStore.activeJob.status }}
              </el-tag>
            </div>
          </template>
          <el-descriptions :column="2" border size="small">
            <el-descriptions-item label="Job ID">{{ backtestStore.activeJob.job_id }}</el-descriptions-item>
            <el-descriptions-item label="Created">{{ formatText(backtestStore.activeJob.created_at) }}</el-descriptions-item>
            <el-descriptions-item label="Started">{{ formatText(backtestStore.activeJob.started_at) }}</el-descriptions-item>
            <el-descriptions-item label="Finished">{{ formatText(backtestStore.activeJob.finished_at) }}</el-descriptions-item>
            <el-descriptions-item label="Report">{{ formatText(backtestStore.activeJob.result?.report_dir) }}</el-descriptions-item>
            <el-descriptions-item label="Snapshot">{{ formatText(backtestStore.activeJob.result?.snapshot_path) }}</el-descriptions-item>
          </el-descriptions>
          <el-alert
            v-if="backtestStore.activeJob.error"
            :title="backtestStore.activeJob.error"
            type="error"
            show-icon
            :closable="false"
            class="mt-4"
          />
          <div class="job-actions">
            <el-button size="small" :loading="backtestStore.jobLoading" @click="refreshActiveJob">Refresh</el-button>
            <el-button
              size="small"
              type="warning"
              :disabled="backtestStore.activeJob.status !== 'pending'"
              :loading="backtestStore.jobLoading"
              @click="cancelActiveJob"
            >
              Cancel
            </el-button>
          </div>
        </el-card>

        <el-card shadow="never" class="dark-card" v-if="backtestStore.lastResult">
          <template #header>
            <div class="card-header">
              <span>Results: {{ backtestStore.lastResult.strategy }}</span>
              <el-tag size="small" effect="plain">{{ formatText(backtestStore.lastResult._engine) }}</el-tag>
            </div>
          </template>

          <div class="kpi-grid">
            <div v-for="kpi in kpis" :key="kpi.label" class="kpi-box">
              <div class="kpi-label">{{ kpi.label }}</div>
              <div class="kpi-value" :class="kpi.cls">{{ kpi.value }}</div>
            </div>
          </div>

          <el-table :data="metricRows" stripe size="small" class="metric-table">
            <el-table-column prop="label" label="Metric" min-width="160" />
            <el-table-column prop="value" label="Value" min-width="160" />
          </el-table>
        </el-card>

        <el-card shadow="never" class="dark-card" v-else>
          <el-empty description="Configure and run a backtest to see results" />
        </el-card>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import { useBacktestStore } from '@/stores/backtest'
import client, { unwrapApiData } from '@/api/client'
import type { BacktestJobPayload, BacktestRunPayload, StrategyInfo } from '@/api/types'

type ParamKind = 'boolean' | 'number' | 'text'

interface ParamEntry {
  name: string
  kind: ParamKind
  step: number
}

const route = useRoute()
const backtestStore = useBacktestStore()
const strategies = ref<StrategyInfo[]>([])
const loadError = ref<string | null>(null)
const paramValues = ref<Record<string, unknown>>({})

const runModeOptions = [
  { label: 'Sync', value: 'sync' },
  { label: 'Job', value: 'job' },
]

const form = ref({
  runMode: 'sync',
  strategy: '',
  symbolsStr: '600519.SH',
  dateRange: ['2024-01-01', '2024-12-31'] as [string, string] | null,
  cash: 100000,
  commission: 0.001,
  slippage: 0.001,
  source: 'akshare',
  benchmarkSource: 'akshare',
  benchmark: '',
  adj: '',
  calendarMode: 'off',
  engine: 'backtrader',
  plot: false,
})

const selectedStrategy = computed(() => strategies.value.find((item) => item.name === form.value.strategy) || null)

const paramEntries = computed<ParamEntry[]>(() => {
  const params = selectedStrategy.value?.params || {}
  return Object.entries(params).map(([name, param]) => ({
    name,
    kind: inferParamKind(param.type, param.default),
    step: inferStep(param.default),
  }))
})

const kpis = computed(() => {
  const r = backtestStore.lastResult
  if (!r) return []
  return [
    { label: 'Return', value: fmtPct(r.cum_return), cls: (r.cum_return ?? 0) >= 0 ? 'text-green' : 'text-red' },
    { label: 'Annual Return', value: fmtPct(r.ann_return), cls: (r.ann_return ?? 0) >= 0 ? 'text-green' : 'text-red' },
    { label: 'Sharpe', value: fmtNum(r.sharpe), cls: (r.sharpe ?? 0) >= 1 ? 'text-green' : '' },
    { label: 'Max Drawdown', value: fmtPct(r.mdd), cls: 'text-red' },
    { label: 'Calmar', value: fmtNum(r.calmar), cls: '' },
    { label: 'Trades', value: String(r.trades ?? 0), cls: '' },
  ]
})

const metricRows = computed(() => {
  const r = backtestStore.lastResult
  if (!r) return []
  const keys = [
    'cum_return',
    'ann_return',
    'ann_vol',
    'sharpe',
    'mdd',
    'calmar',
    'win_rate',
    'trades',
    'profit_factor',
    'avg_hold_bars',
    'bench_return',
    'bench_mdd',
    'excess_return',
    '_engine',
  ]
  return keys
    .filter((key) => r[key] !== undefined)
    .map((key) => ({ label: key, value: formatMetricValue(key, r[key]) }))
})

onMounted(async () => {
  await loadStrategies()
  applyRouteStrategy()
})

watch(() => route.query.strategy, applyRouteStrategy)

watch(
  () => form.value.strategy,
  () => {
    applyStrategyDefaults()
  },
)

watch(
  () => form.value.runMode,
  (mode) => {
    if (mode === 'sync') {
      form.value.plot = false
    }
  },
)

async function loadStrategies() {
  try {
    const resp = await client.get('/api/v2/strategies')
    const data = unwrapApiData<{ strategies: StrategyInfo[] }>(resp.data)
    strategies.value = data.strategies || []
    if (!form.value.strategy && strategies.value.length > 0) {
      form.value.strategy = strategies.value[0].name
    }
    loadError.value = null
  } catch (e) {
    loadError.value = (e as Error).message
  }
}

function applyRouteStrategy() {
  const strategy = route.query.strategy
  if (typeof strategy === 'string' && strategy) {
    form.value.strategy = strategy
  }
}

function applyStrategyDefaults() {
  const params = selectedStrategy.value?.params || {}
  paramValues.value = Object.fromEntries(
    Object.entries(params).map(([name, param]) => [name, normalizeParamValue(param.default)]),
  )
}

function inferParamKind(type: string, value: unknown): ParamKind {
  const normalized = type.toLowerCase()
  if (normalized.includes('bool') || typeof value === 'boolean') return 'boolean'
  if (normalized.includes('int') || normalized.includes('float') || typeof value === 'number') return 'number'
  return 'text'
}

function inferStep(value: unknown): number {
  return typeof value === 'number' && Number.isInteger(value) ? 1 : 0.1
}

function normalizeParamValue(value: unknown): unknown {
  if (typeof value === 'boolean' || typeof value === 'number') return value
  if (value === null || value === undefined) return ''
  return String(value)
}

function parseSymbols(): string[] {
  return form.value.symbolsStr.split(',').map((item) => item.trim()).filter(Boolean)
}

function buildPayload(): BacktestRunPayload | null {
  const symbols = parseSymbols()
  if (!form.value.strategy) {
    ElMessage.warning('Select a strategy first')
    return null
  }
  if (symbols.length === 0) {
    ElMessage.warning('Enter at least one symbol')
    return null
  }
  if (!form.value.dateRange || form.value.dateRange.length !== 2) {
    ElMessage.warning('Select a date range')
    return null
  }

  return {
    strategy: form.value.strategy,
    symbols,
    start: form.value.dateRange[0],
    end: form.value.dateRange[1],
    cash: form.value.cash,
    commission: form.value.commission,
    slippage: form.value.slippage,
    source: form.value.source || 'akshare',
    benchmark_source: form.value.benchmarkSource || form.value.source || 'akshare',
    benchmark: form.value.benchmark || undefined,
    adj: form.value.adj || undefined,
    calendar_mode: form.value.calendarMode || undefined,
    engine: form.value.engine,
    params: { ...paramValues.value },
  }
}

async function runBacktest() {
  const payload = buildPayload()
  if (!payload) return
  if (form.value.runMode === 'job') {
    const jobPayload: BacktestJobPayload = { ...payload, plot: form.value.plot }
    const job = await backtestStore.submitBacktestJob(jobPayload)
    if (job) ElMessage.success(`Submitted job ${job.job_id}`)
    return
  }
  await backtestStore.runBacktest(payload)
}

async function refreshActiveJob() {
  if (!backtestStore.activeJob) return
  await backtestStore.fetchBacktestJob(backtestStore.activeJob.job_id)
}

async function cancelActiveJob() {
  if (!backtestStore.activeJob) return
  await backtestStore.cancelBacktestJob(backtestStore.activeJob.job_id)
}

function fmtPct(v: unknown): string {
  const n = Number(v)
  if (Number.isNaN(n)) return 'N/A'
  return `${(n * 100).toFixed(2)}%`
}

function fmtNum(v: unknown): string {
  const n = Number(v)
  if (Number.isNaN(n)) return 'N/A'
  return n.toFixed(4)
}

function formatMetricValue(key: string, value: unknown): string {
  if (key.includes('return') || key.includes('mdd') || key === 'ann_vol' || key === 'win_rate') {
    return fmtPct(value)
  }
  if (typeof value === 'number') return fmtNum(value)
  return formatText(value)
}

function formatText(value: unknown): string {
  if (value === null || value === undefined || value === '') return 'N/A'
  return String(value)
}

function jobTagType(status: string): 'success' | 'warning' | 'danger' | 'info' {
  if (status === 'success') return 'success'
  if (status === 'failed') return 'danger'
  if (status === 'running') return 'warning'
  return 'info'
}
</script>

<style scoped>
.backtest-page {
  max-width: 1480px;
}

.backtest-grid {
  display: grid;
  grid-template-columns: minmax(360px, 440px) minmax(0, 1fr);
  gap: 16px;
  align-items: start;
}

.dark-card {
  background: var(--bg-card);
  border-color: var(--border);
  margin-bottom: 16px;
}

.card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.full-width {
  width: 100%;
}

.mb-4 {
  margin-bottom: 16px;
}

.mt-4 {
  margin-top: 16px;
}

.form-grid {
  display: grid;
  gap: 12px;
}

.form-grid.two {
  grid-template-columns: repeat(2, minmax(0, 1fr));
}

.param-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  column-gap: 12px;
}

.kpi-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 12px;
}

.kpi-box {
  background: var(--bg-secondary);
  border: 1px solid var(--border);
  border-radius: 8px;
  padding: 12px;
  min-height: 72px;
}

.kpi-label {
  font-size: 11px;
  color: var(--text-secondary);
  text-transform: uppercase;
}

.kpi-value {
  font-size: 20px;
  font-weight: 700;
  margin-top: 6px;
}

.metric-table {
  margin-top: 16px;
}

.job-actions {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
  margin-top: 16px;
}

.text-green {
  color: var(--green);
}

.text-red {
  color: var(--red);
}

@media (max-width: 1100px) {
  .backtest-grid {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 680px) {
  .form-grid.two,
  .param-grid,
  .kpi-grid {
    grid-template-columns: 1fr;
  }
}
</style>
