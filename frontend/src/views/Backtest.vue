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
              <el-input v-model="form.source" placeholder="auto" />
            </el-form-item>
            <el-form-item label="Benchmark Source">
              <el-input v-model="form.benchmarkSource" placeholder="auto" />
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
              <div class="result-tags">
                <el-tag size="small" effect="plain">{{ formatText(backtestStore.lastResult._engine) }}</el-tag>
                <el-tag v-if="backtestStore.lastRunAt" size="small" type="success" effect="plain">
                  Updated {{ formatRunTime(backtestStore.lastRunAt) }}
                </el-tag>
              </div>
            </div>
          </template>

          <div class="kpi-grid">
            <div v-for="kpi in kpis" :key="kpi.label" class="kpi-box">
              <div class="kpi-label">{{ kpi.label }}</div>
              <div class="kpi-value" :class="kpi.cls">{{ kpi.value }}</div>
            </div>
          </div>

          <div
            v-if="technicalChart || equityCurve.length > 0"
            ref="chartEl"
            class="backtest-chart"
            aria-label="Backtest technical chart"
          />

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
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import * as echarts from 'echarts'
import type { ECharts, EChartsOption } from 'echarts'
import { useBacktestStore } from '@/stores/backtest'
import client, { unwrapApiData } from '@/api/client'
import type {
  BacktestChartPoint,
  BacktestJobPayload,
  BacktestRunPayload,
  BacktestTechnicalChart,
  NullableNumber,
  StrategyInfo,
} from '@/api/types'

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
const chartEl = ref<HTMLDivElement | null>(null)
let backtestChart: ECharts | null = null

const runModeOptions = [
  { label: 'Sync', value: 'sync' },
  { label: 'Job', value: 'job' },
]

const form = ref({
  runMode: 'sync',
  strategy: '',
  symbolsStr: '600519.SH',
  dateRange: ['2024-01-01', '2024-12-31'] as [string, string] | null,
  cash: 1_000_000,
  commission: 0.001,
  slippage: 0.001,
  source: 'auto',
  benchmarkSource: 'auto',
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

const equityCurve = computed(() => normalizeCurve(backtestStore.lastResult?.equity_curve))
const drawdownCurve = computed(() => normalizeCurve(backtestStore.lastResult?.drawdown_curve))
const technicalChart = computed(() => normalizeTechnicalChart(backtestStore.lastResult?.technical_chart))

onMounted(async () => {
  window.addEventListener('resize', resizeChart)
  await loadStrategies()
  applyRouteStrategy()
  await renderBacktestChart()
})

onBeforeUnmount(() => {
  window.removeEventListener('resize', resizeChart)
  backtestChart?.dispose()
  backtestChart = null
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

watch(
  () => backtestStore.lastResult,
  () => {
    void renderBacktestChart()
  },
  { deep: true },
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

function buildParamsPayload(): Record<string, unknown> {
  const paramDefs = selectedStrategy.value?.params || {}
  return Object.fromEntries(
    Object.entries(paramValues.value).filter(([name, value]) => {
      const defaultValue = paramDefs[name]?.default
      const isBlankNullableDefault =
        (defaultValue === null || defaultValue === undefined) &&
        (value === '' || value === null || value === undefined)
      return !isBlankNullableDefault
    }),
  )
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
    source: form.value.source || 'auto',
    benchmark_source: form.value.benchmarkSource || form.value.source || 'auto',
    benchmark: form.value.benchmark || undefined,
    adj: form.value.adj || undefined,
    calendar_mode: form.value.calendarMode || undefined,
    engine: form.value.engine,
    params: buildParamsPayload(),
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
  const metrics = await backtestStore.runBacktest(payload)
  if (!metrics) {
    if (backtestStore.error) ElMessage.error(backtestStore.error)
    return
  }
  const trades = Number(metrics.trades ?? 0)
  if (trades === 0) {
    ElMessage.warning('Backtest completed, but no trades were generated. Check signal rules, cash, and lot size.')
  } else {
    ElMessage.success(`Backtest completed: ${trades} trades`)
  }
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

function formatRunTime(value: string): string {
  return new Date(value).toLocaleTimeString()
}

function normalizeCurve(value: unknown): BacktestChartPoint[] {
  if (!Array.isArray(value)) return []
  return value.flatMap((item) => {
    if (!item || typeof item !== 'object') return []
    const point = item as Partial<BacktestChartPoint>
    const numeric = Number(point.value)
    if (!point.date || Number.isNaN(numeric)) return []
    return [{ date: String(point.date), value: numeric }]
  })
}

function normalizeTechnicalChart(value: unknown): BacktestTechnicalChart | null {
  if (!value || typeof value !== 'object') return null
  const chart = value as BacktestTechnicalChart
  if (!Array.isArray(chart.dates) || !Array.isArray(chart.ohlc) || chart.dates.length === 0) return null
  if (!Array.isArray(chart.volumes)) return null
  return chart
}

function asNullableSeries(values: NullableNumber[] | undefined, length: number): NullableNumber[] {
  return Array.from({ length }, (_, index) => {
    const value = values?.[index]
    return typeof value === 'number' && Number.isFinite(value) ? value : null
  })
}

function candleColor(candle: number[] | undefined): string {
  if (!candle || candle.length < 2) return '#64748b'
  return Number(candle[1]) >= Number(candle[0]) ? '#ef4444' : '#16a34a'
}

function buildLineSeries(
  name: string,
  data: NullableNumber[],
  color: string,
  xAxisIndex = 0,
  yAxisIndex = 0,
  width = 1.4,
  dashed = false,
) {
  return {
    name,
    type: 'line' as const,
    xAxisIndex,
    yAxisIndex,
    data,
    showSymbol: false,
    connectNulls: false,
    lineStyle: { color, width, type: dashed ? ('dashed' as const) : ('solid' as const) },
    emphasis: { focus: 'series' as const },
  }
}

function resizeChart() {
  backtestChart?.resize()
}

async function renderBacktestChart() {
  await nextTick()
  if (!chartEl.value || (!technicalChart.value && equityCurve.value.length === 0)) {
    backtestChart?.dispose()
    backtestChart = null
    return
  }

  backtestChart ||= echarts.init(chartEl.value)
  const option = technicalChart.value
    ? buildTechnicalChartOption(technicalChart.value)
    : buildEquityChartOption()
  backtestChart.setOption(option, true)
  backtestChart.resize()
}

function buildTechnicalChartOption(chart: BacktestTechnicalChart): EChartsOption {
  const dates = chart.dates
  const panelIndexes = [0, 1, 2, 3, 4]
  const textColor = '#334155'
  const gridColor = 'rgba(100, 116, 139, 0.22)'
  const volumeBars = chart.volumes.map((volume, index) => ({
    value: volume,
    itemStyle: { color: candleColor(chart.ohlc[index]) },
  }))
  const buyMarkers = (chart.trades || [])
    .filter((trade) => String(trade.type).toUpperCase() === 'BUY')
    .map((trade) => [trade.date, trade.price])
  const sellMarkers = (chart.trades || [])
    .filter((trade) => String(trade.type).toUpperCase() === 'SELL')
    .map((trade) => [trade.date, trade.price])

  return {
    backgroundColor: '#f8fafc',
    animation: false,
    color: ['#06b6d4', '#2563eb', '#7c3aed', '#0f172a', '#f97316', '#dc2626', '#16a34a'],
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'cross' },
      backgroundColor: 'rgba(255, 255, 255, 0.96)',
      borderColor: '#cbd5e1',
      textStyle: { color: '#0f172a' },
      valueFormatter: (value) => {
        const numeric = Number(value)
        return Number.isNaN(numeric) ? String(value) : numeric.toFixed(2)
      },
    },
    axisPointer: { link: [{ xAxisIndex: panelIndexes }] },
    legend: {
      type: 'scroll',
      left: 10,
      right: 10,
      top: 8,
      textStyle: { color: textColor, fontSize: 11 },
      data: [
        `${chart.symbol} K线`,
        'MA5',
        'MA10',
        'MA20',
        'MA30',
        'Boll Upper',
        'Boll Mid',
        'Boll Lower',
        '买入',
        '卖出',
        'Volume',
        'RSI(14)',
        'MACD',
        'DIF',
        'Signal',
        'K',
        'D',
        'J',
      ],
    },
    grid: [
      { left: 56, right: 72, top: 52, height: '42%' },
      { left: 56, right: 72, top: '52%', height: '10%' },
      { left: 56, right: 72, top: '65%', height: '9%' },
      { left: 56, right: 72, top: '77%', height: '9%' },
      { left: 56, right: 72, top: '89%', height: '8%' },
    ],
    xAxis: panelIndexes.map((gridIndex) => ({
      type: 'category',
      gridIndex,
      data: dates,
      boundaryGap: gridIndex === 0,
      axisLine: { lineStyle: { color: '#94a3b8' } },
      axisTick: { show: gridIndex === 4 },
      axisLabel: { show: gridIndex === 4, color: textColor, fontSize: 10 },
      splitLine: { show: true, lineStyle: { color: gridColor } },
      min: 'dataMin',
      max: 'dataMax',
    })),
    yAxis: [
      {
        scale: true,
        position: 'right',
        axisLabel: { color: textColor, fontSize: 10 },
        splitLine: { lineStyle: { color: gridColor } },
      },
      {
        scale: true,
        gridIndex: 1,
        position: 'right',
        axisLabel: { color: textColor, fontSize: 10 },
        splitLine: { lineStyle: { color: gridColor } },
      },
      {
        gridIndex: 2,
        min: 0,
        max: 100,
        position: 'right',
        axisLabel: { color: textColor, fontSize: 10 },
        splitLine: { lineStyle: { color: gridColor } },
      },
      {
        scale: true,
        gridIndex: 3,
        position: 'right',
        axisLabel: { color: textColor, fontSize: 10 },
        splitLine: { lineStyle: { color: gridColor } },
      },
      {
        gridIndex: 4,
        min: 0,
        max: 120,
        position: 'right',
        axisLabel: { color: textColor, fontSize: 10 },
        splitLine: { lineStyle: { color: gridColor } },
      },
    ],
    dataZoom: [{ type: 'inside', xAxisIndex: panelIndexes, start: 0, end: 100 }],
    series: [
      {
        name: `${chart.symbol} K线`,
        type: 'candlestick',
        data: chart.ohlc,
        itemStyle: {
          color: '#ef4444',
          color0: '#16a34a',
          borderColor: '#dc2626',
          borderColor0: '#15803d',
        },
      },
      buildLineSeries('MA5', asNullableSeries(chart.ma?.ma5, dates.length), '#06b6d4', 0, 0, 1.2),
      buildLineSeries('MA10', asNullableSeries(chart.ma?.ma10, dates.length), '#2563eb', 0, 0, 1.2),
      buildLineSeries('MA20', asNullableSeries(chart.ma?.ma20, dates.length), '#7c3aed', 0, 0, 1.2),
      buildLineSeries('MA30', asNullableSeries(chart.ma?.ma30, dates.length), '#0f172a', 0, 0, 1.2),
      buildLineSeries('Boll Upper', asNullableSeries(chart.boll?.upper, dates.length), '#f97316', 0, 0, 1.1),
      buildLineSeries('Boll Mid', asNullableSeries(chart.boll?.mid, dates.length), '#f97316', 0, 0, 1.0, true),
      buildLineSeries('Boll Lower', asNullableSeries(chart.boll?.lower, dates.length), '#f97316', 0, 0, 1.1),
      {
        name: '买入',
        type: 'scatter',
        data: buyMarkers,
        symbol: 'triangle',
        symbolSize: 13,
        itemStyle: { color: '#ef4444', borderColor: '#991b1b', borderWidth: 1 },
        z: 8,
      },
      {
        name: '卖出',
        type: 'scatter',
        data: sellMarkers,
        symbol: 'triangle',
        symbolRotate: 180,
        symbolSize: 13,
        itemStyle: { color: '#22c55e', borderColor: '#166534', borderWidth: 1 },
        z: 8,
      },
      {
        name: 'Volume',
        type: 'bar',
        xAxisIndex: 1,
        yAxisIndex: 1,
        data: volumeBars,
        barWidth: '58%',
      },
      {
        ...buildLineSeries('RSI(14)', asNullableSeries(chart.rsi, dates.length), '#06b6d4', 2, 2, 1.5),
        markLine: {
          silent: true,
          symbol: 'none',
          label: { show: false },
          lineStyle: { color: '#94a3b8', width: 1, type: 'dashed' },
          data: [{ yAxis: 70 }, { yAxis: 30 }],
        },
      },
      {
        name: 'MACD',
        type: 'bar',
        xAxisIndex: 3,
        yAxisIndex: 3,
        data: asNullableSeries(chart.macd?.hist, dates.length).map((value) => ({
          value,
          itemStyle: { color: (value ?? 0) >= 0 ? '#ef4444' : '#16a34a' },
        })),
        barWidth: '55%',
      },
      buildLineSeries('DIF', asNullableSeries(chart.macd?.dif, dates.length), '#06b6d4', 3, 3, 1.4),
      buildLineSeries('Signal', asNullableSeries(chart.macd?.signal, dates.length), '#2563eb', 3, 3, 1.4, true),
      {
        ...buildLineSeries('K', asNullableSeries(chart.kdj?.k, dates.length), '#06b6d4', 4, 4, 1.3),
        markLine: {
          silent: true,
          symbol: 'none',
          label: { show: false },
          lineStyle: { color: '#94a3b8', width: 1, type: 'dashed' },
          data: [{ yAxis: 80 }, { yAxis: 20 }],
        },
      },
      buildLineSeries('D', asNullableSeries(chart.kdj?.d, dates.length), '#2563eb', 4, 4, 1.3),
      buildLineSeries('J', asNullableSeries(chart.kdj?.j, dates.length), '#f97316', 4, 4, 1.3),
    ],
  }
}

function buildEquityChartOption(): EChartsOption {
  const dates = equityCurve.value.map((point) => point.date)
  const drawdownByDate = new Map(drawdownCurve.value.map((point) => [point.date, point.value]))
  const navValues = equityCurve.value.map((point) => point.value)
  const drawdownValues = dates.map((date) => drawdownByDate.get(date) ?? 0)
  return {
    backgroundColor: 'transparent',
    color: ['#60a5fa', '#ef4444'],
    tooltip: {
      trigger: 'axis',
      valueFormatter: (value) => {
        const numeric = Number(value)
        return Number.isNaN(numeric) ? String(value) : numeric.toFixed(4)
      },
    },
    legend: {
      top: 0,
      textStyle: { color: '#a0aec0' },
      data: ['Equity', 'Drawdown'],
    },
    grid: { top: 36, right: 54, bottom: 48, left: 48 },
    xAxis: {
      type: 'category',
      boundaryGap: false,
      data: dates,
      axisLine: { lineStyle: { color: '#2a2a4a' } },
      axisLabel: { color: '#a0aec0' },
    },
    yAxis: [
      {
        type: 'value',
        name: 'NAV',
        min: 'dataMin',
        axisLabel: { color: '#a0aec0' },
        splitLine: { lineStyle: { color: 'rgba(160, 174, 192, 0.14)' } },
      },
      {
        type: 'value',
        name: 'DD',
        axisLabel: {
          color: '#a0aec0',
          formatter: (value: number) => `${(value * 100).toFixed(0)}%`,
        },
        splitLine: { show: false },
      },
    ],
    dataZoom: [
      { type: 'inside' },
      {
        type: 'slider',
        height: 18,
        bottom: 8,
        borderColor: '#2a2a4a',
        fillerColor: 'rgba(96, 165, 250, 0.18)',
        handleStyle: { color: '#60a5fa' },
        textStyle: { color: '#a0aec0' },
      },
    ],
    series: [
      {
        name: 'Equity',
        type: 'line',
        data: navValues,
        showSymbol: false,
        smooth: true,
        lineStyle: { width: 2 },
        areaStyle: { opacity: 0.08 },
      },
      {
        name: 'Drawdown',
        type: 'line',
        yAxisIndex: 1,
        data: drawdownValues,
        showSymbol: false,
        lineStyle: { width: 1.5 },
        areaStyle: { opacity: 0.12 },
      },
    ],
  }
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
  width: 100%;
  max-width: 1680px;
}

.backtest-grid {
  display: grid;
  grid-template-columns: minmax(300px, 360px) minmax(720px, 1fr);
  gap: 20px;
  align-items: start;
}

.result-panel {
  min-width: 0;
}

.dark-card {
  background: var(--bg-card);
  border-color: var(--border);
  margin-bottom: 16px;
}

.result-tags {
  display: flex;
  gap: 8px;
  align-items: center;
  flex-wrap: wrap;
  justify-content: flex-end;
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

.backtest-chart {
  width: 100%;
  height: 780px;
  min-height: 680px;
  margin-top: 16px;
  border: 1px solid var(--border);
  border-radius: 8px;
  background: #f8fafc;
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

@media (max-width: 1600px) {
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

  .backtest-chart {
    height: 640px;
    min-height: 640px;
  }
}
</style>
