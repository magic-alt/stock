<template>
  <div class="data-page">
    <el-card shadow="never" class="dark-card">
      <template #header>
        <div class="card-header">
          <span>Data Browser</span>
          <div class="header-tags">
            <el-tag size="small" effect="plain">{{ chartData.source || form.source }}</el-tag>
            <el-tag size="small" effect="plain">{{ rows.length }} rows</el-tag>
          </div>
        </div>
      </template>

      <el-form :model="form" inline size="small" class="toolbar">
        <el-form-item label="Dataset">
          <el-select
            v-model="selectedDatasetKey"
            placeholder="Local datasets"
            clearable
            filterable
            class="dataset-select"
            :loading="datasetsLoading"
            @change="selectDataset"
          >
            <el-option
              v-for="dataset in localDatasets"
              :key="datasetKey(dataset)"
              :label="`${dataset.symbol} · ${dataset.freq} · ${dataset.rows} rows`"
              :value="datasetKey(dataset)"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="Symbol">
          <el-input v-model="form.symbol" placeholder="600519.SH" class="symbol-input" />
        </el-form-item>
        <el-form-item label="Days">
          <el-input-number v-model="form.days" :min="10" :max="5000" :step="10" />
        </el-form-item>
        <el-form-item label="Source">
          <el-select v-model="form.source" class="source-select">
            <el-option label="Local DuckDB" value="local" />
            <el-option label="Auto" value="auto" />
            <el-option label="AKShare" value="akshare" />
            <el-option label="Sina Finance" value="sina" />
            <el-option label="Tencent Finance" value="tencent" />
            <el-option label="Eastmoney" value="eastmoney" />
            <el-option label="YFinance" value="yfinance" />
            <el-option label="TuShare" value="tushare" />
          </el-select>
        </el-form-item>
        <el-form-item>
          <el-button type="primary" :loading="loading" @click="loadData">Load</el-button>
          <el-button :loading="updating" @click="updateLocalData">Update Local</el-button>
        </el-form-item>
      </el-form>

      <el-alert v-if="error" :title="error" type="error" show-icon :closable="false" class="mb-4" />
      <el-alert
        v-if="localDatasets.length === 0 && !datasetsLoading"
        title="Local DuckDB is ready. Use Update Local to fetch and persist the current symbol."
        type="info"
        show-icon
        :closable="false"
        class="mb-4"
      />

      <el-descriptions :column="4" border size="small" class="mb-4">
        <el-descriptions-item label="Symbol">{{ chartData.symbol || form.symbol }}</el-descriptions-item>
        <el-descriptions-item label="Source">{{ chartData.source || form.source }}</el-descriptions-item>
        <el-descriptions-item label="Local Sets">{{ localDatasets.length }}</el-descriptions-item>
        <el-descriptions-item label="Store Rows">{{ localStats?.total_rows ?? 0 }}</el-descriptions-item>
      </el-descriptions>

      <div ref="chartEl" class="kline-chart" aria-label="Local market data K-line chart" />

      <el-table :data="rows" stripe size="small" class="data-table">
        <el-table-column prop="date" label="Date" width="120" />
        <el-table-column prop="open" label="Open" />
        <el-table-column prop="high" label="High" />
        <el-table-column prop="low" label="Low" />
        <el-table-column prop="close" label="Close" />
        <el-table-column prop="volume" label="Volume" />
      </el-table>
      <el-empty v-if="!loading && rows.length === 0" description="Load a symbol to inspect recent OHLCV data" />
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import * as echarts from 'echarts'
import type { ECharts, EChartsOption } from 'echarts'
import client, { unwrapApiData } from '@/api/client'

interface ChartData {
  symbol?: string
  source?: string
  dates: string[]
  ohlc: number[][]
  volumes: number[]
}

interface DataRow {
  date: string
  open: string
  high: string
  low: string
  close: string
  volume: string
}

interface LocalDataset {
  symbol: string
  freq: string
  rows: number
  start: string
  end: string
  updated_at: string
}

interface LocalStats {
  total_rows: number
  symbols: number
  frequencies: string[]
  db_path: string
}

const loading = ref(false)
const updating = ref(false)
const datasetsLoading = ref(false)
const error = ref<string | null>(null)
const chartData = ref<ChartData>({ dates: [], ohlc: [], volumes: [] })
const localDatasets = ref<LocalDataset[]>([])
const localStats = ref<LocalStats | null>(null)
const selectedDatasetKey = ref('')
const chartEl = ref<HTMLDivElement | null>(null)
let chart: ECharts | null = null

const form = ref({
  symbol: '600519.SH',
  days: 120,
  source: 'local',
})

const rows = computed<DataRow[]>(() =>
  chartData.value.dates.map((date, index) => {
    const item = chartData.value.ohlc[index] || []
    return {
      date,
      open: formatNumber(item[0]),
      close: formatNumber(item[1]),
      low: formatNumber(item[2]),
      high: formatNumber(item[3]),
      volume: formatNumber(chartData.value.volumes[index], 0),
    }
  }),
)

onMounted(async () => {
  window.addEventListener('resize', resizeChart)
  await loadLocalDatasets()
  if (localDatasets.value.length > 0) {
    const first = localDatasets.value[0]
    selectedDatasetKey.value = datasetKey(first)
    form.value.symbol = first.symbol
    form.value.source = 'local'
    await loadData()
  }
})

onBeforeUnmount(() => {
  window.removeEventListener('resize', resizeChart)
  chart?.dispose()
  chart = null
})

watch(chartData, () => {
  void renderChart()
}, { deep: true })

async function loadLocalDatasets() {
  datasetsLoading.value = true
  try {
    const resp = await client.get('/api/v2/local-data', { params: { freq: 'daily' } })
    const data = unwrapApiData<{ datasets: LocalDataset[]; stats: LocalStats }>(resp.data)
    localDatasets.value = data.datasets || []
    localStats.value = data.stats || null
  } catch (e) {
    error.value = (e as Error).message
  } finally {
    datasetsLoading.value = false
  }
}

async function loadData() {
  if (!form.value.symbol.trim()) {
    error.value = 'Symbol is required'
    return
  }
  loading.value = true
  error.value = null
  try {
    const resp = await client.get('/api/v2/chart-data', {
      params: {
        symbol: form.value.symbol.trim(),
        days: form.value.days,
        source: form.value.source || 'local',
      },
    })
    chartData.value = unwrapApiData<ChartData>(resp.data)
  } catch (e) {
    chartData.value = { dates: [], ohlc: [], volumes: [] }
    error.value = (e as Error).message
  } finally {
    loading.value = false
  }
}

async function updateLocalData() {
  if (!form.value.symbol.trim()) {
    error.value = 'Symbol is required'
    return
  }
  updating.value = true
  error.value = null
  try {
    const remoteSource = form.value.source === 'local' ? 'auto' : form.value.source
    const resp = await client.post('/api/v2/local-data/update', {
      symbol: form.value.symbol.trim(),
      days: form.value.days,
      source: remoteSource || 'auto',
      freq: 'daily',
      replace: true,
    })
    const data = unwrapApiData<{ symbol: string; rows: number }>(resp.data)
    ElMessage.success(`Updated ${data.symbol}: ${data.rows} rows`)
    await loadLocalDatasets()
    form.value.source = 'local'
    form.value.symbol = data.symbol
    selectedDatasetKey.value = `${data.symbol}:daily`
    await loadData()
  } catch (e) {
    error.value = (e as Error).message
  } finally {
    updating.value = false
  }
}

function selectDataset(value: string) {
  const dataset = localDatasets.value.find((item) => datasetKey(item) === value)
  if (!dataset) return
  form.value.symbol = dataset.symbol
  form.value.source = 'local'
  void loadData()
}

function datasetKey(dataset: LocalDataset): string {
  return `${dataset.symbol}:${dataset.freq}`
}

function formatNumber(value: unknown, digits = 2): string {
  const numeric = Number(value)
  if (Number.isNaN(numeric)) return 'N/A'
  return numeric.toFixed(digits)
}

function resizeChart() {
  chart?.resize()
}

async function renderChart() {
  await nextTick()
  if (!chartEl.value || chartData.value.dates.length === 0) {
    chart?.dispose()
    chart = null
    return
  }
  chart ||= echarts.init(chartEl.value)
  chart.setOption(buildChartOption(), true)
  chart.resize()
}

function candleColor(candle: number[] | undefined): string {
  if (!candle || candle.length < 2) return '#64748b'
  return Number(candle[1]) >= Number(candle[0]) ? '#ef4444' : '#16a34a'
}

function buildChartOption(): EChartsOption {
  const dates = chartData.value.dates
  const volumeBars = chartData.value.volumes.map((volume, index) => ({
    value: volume,
    itemStyle: { color: candleColor(chartData.value.ohlc[index]) },
  }))
  return {
    backgroundColor: '#f8fafc',
    animation: false,
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'cross' },
      backgroundColor: 'rgba(255, 255, 255, 0.96)',
      borderColor: '#cbd5e1',
      textStyle: { color: '#0f172a' },
    },
    axisPointer: { link: [{ xAxisIndex: [0, 1] }] },
    grid: [
      { left: 56, right: 56, top: 36, height: '58%' },
      { left: 56, right: 56, top: '74%', height: '16%' },
    ],
    xAxis: [
      {
        type: 'category',
        data: dates,
        boundaryGap: true,
        axisLine: { lineStyle: { color: '#94a3b8' } },
        axisLabel: { show: false },
        splitLine: { show: true, lineStyle: { color: 'rgba(100, 116, 139, 0.18)' } },
        min: 'dataMin',
        max: 'dataMax',
      },
      {
        type: 'category',
        gridIndex: 1,
        data: dates,
        boundaryGap: true,
        axisLine: { lineStyle: { color: '#94a3b8' } },
        axisLabel: { color: '#334155', fontSize: 10 },
        splitLine: { show: true, lineStyle: { color: 'rgba(100, 116, 139, 0.18)' } },
        min: 'dataMin',
        max: 'dataMax',
      },
    ],
    yAxis: [
      {
        scale: true,
        position: 'right',
        axisLabel: { color: '#334155', fontSize: 10 },
        splitLine: { lineStyle: { color: 'rgba(100, 116, 139, 0.22)' } },
      },
      {
        scale: true,
        gridIndex: 1,
        position: 'right',
        axisLabel: { color: '#334155', fontSize: 10 },
        splitLine: { lineStyle: { color: 'rgba(100, 116, 139, 0.22)' } },
      },
    ],
    dataZoom: [
      { type: 'inside', xAxisIndex: [0, 1], start: 0, end: 100 },
      { type: 'slider', xAxisIndex: [0, 1], bottom: 6, height: 18, start: 0, end: 100 },
    ],
    series: [
      {
        name: `${chartData.value.symbol || form.value.symbol} K-line`,
        type: 'candlestick',
        data: chartData.value.ohlc,
        itemStyle: {
          color: '#ef4444',
          color0: '#16a34a',
          borderColor: '#ef4444',
          borderColor0: '#16a34a',
        },
      },
      {
        name: 'Volume',
        type: 'bar',
        xAxisIndex: 1,
        yAxisIndex: 1,
        data: volumeBars,
      },
    ],
  }
}
</script>

<style scoped>
.data-page {
  max-width: 1400px;
}

.dark-card {
  background: var(--bg-card);
  border-color: var(--border);
}

.card-header,
.header-tags {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.toolbar {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
}

.dataset-select {
  width: 260px;
}

.source-select {
  width: 150px;
}

.symbol-input {
  width: 140px;
}

.mb-4 {
  margin-bottom: 16px;
}

.kline-chart {
  width: 100%;
  height: 420px;
  margin-bottom: 16px;
  border: 1px solid var(--border);
  background: #f8fafc;
}

.data-table {
  width: 100%;
}
</style>
