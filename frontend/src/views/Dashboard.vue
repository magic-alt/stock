<template>
  <div class="dashboard">
    <el-row :gutter="16" class="mb-4">
      <el-col :xs="12" :sm="12" :md="6" v-for="stat in statsCards" :key="stat.label">
        <el-card shadow="never" class="stat-card">
          <div class="stat-label">{{ stat.label }}</div>
          <div class="stat-value" :class="stat.color">{{ stat.value }}</div>
        </el-card>
      </el-col>
    </el-row>

    <el-row :gutter="16" class="mb-4">
      <el-col :xs="24" :lg="16">
        <el-card shadow="never" class="dark-card analysis-card">
          <template #header>
            <div class="card-header">
              <span>Beginner Analysis</span>
              <el-tag size="small" effect="plain">{{ analysisResult?.data_quality.source || 'auto' }}</el-tag>
            </div>
          </template>

          <el-form :model="analysisForm" inline size="small" class="analysis-toolbar">
            <el-form-item label="Symbol">
              <el-input v-model="analysisForm.symbol" placeholder="600519.SH" clearable />
            </el-form-item>
            <el-form-item label="Source">
              <el-select v-model="analysisForm.source" class="source-select">
                <el-option label="Auto (AKShare + Sina + Tencent)" value="auto" />
                <el-option label="AKShare" value="akshare" />
                <el-option label="Sina Finance" value="sina" />
                <el-option label="Tencent Finance" value="tencent" />
                <el-option label="Eastmoney" value="eastmoney" />
                <el-option label="YFinance" value="yfinance" />
                <el-option label="TuShare" value="tushare" />
              </el-select>
            </el-form-item>
            <el-form-item label="Days">
              <el-input-number v-model="analysisForm.days" :min="10" :max="500" :step="10" />
            </el-form-item>
            <el-form-item>
              <el-checkbox v-model="analysisForm.use_ai">AI</el-checkbox>
            </el-form-item>
            <el-form-item>
              <el-button type="primary" :loading="analysisLoading" @click="runAnalysis">
                Analyze
              </el-button>
            </el-form-item>
          </el-form>

          <el-alert
            v-if="analysisError"
            :title="analysisError"
            type="error"
            show-icon
            :closable="false"
            class="mb-4"
          />

          <div v-if="analysisResult" class="analysis-result">
            <div class="analysis-summary">
              <div>
                <div class="stat-label">{{ analysisResult.symbol }} · {{ analysisResult.as_of }}</div>
                <div class="analysis-price">
                  {{ formatPrice(analysisResult.price.latest) }}
                  <span :class="priceChangeClass(analysisResult.price.change_pct)">
                    {{ formatPct(analysisResult.price.change_pct) }}
                  </span>
                </div>
              </div>
              <el-progress
                type="dashboard"
                :percentage="analysisResult.signal.score"
                :status="scoreStatus"
                :width="92"
              />
              <el-tag :type="ratingType" size="large">{{ analysisResult.signal.rating.toUpperCase() }}</el-tag>
            </div>

            <el-row :gutter="12" class="mb-4">
              <el-col :xs="24" :md="12">
                <div class="mini-panel">
                  <div class="panel-title">Reasons</div>
                  <ul>
                    <li v-for="item in analysisResult.signal.reasons" :key="item">{{ item }}</li>
                  </ul>
                </div>
              </el-col>
              <el-col :xs="24" :md="12">
                <div class="mini-panel">
                  <div class="panel-title">Risks</div>
                  <ul>
                    <li v-for="item in analysisResult.signal.risks" :key="item">{{ item }}</li>
                  </ul>
                </div>
              </el-col>
            </el-row>

            <el-descriptions :column="4" border size="small" class="mb-4">
              <el-descriptions-item label="Rows">{{ analysisResult.data_quality.rows }}</el-descriptions-item>
              <el-descriptions-item label="20D Low">{{ formatNum(analysisResult.price.range_20d.low) }}</el-descriptions-item>
              <el-descriptions-item label="20D High">{{ formatNum(analysisResult.price.range_20d.high) }}</el-descriptions-item>
              <el-descriptions-item label="Preview Return">
                {{ analysisResult.backtest_preview.enabled ? formatPct(analysisResult.backtest_preview.cum_return) : 'N/A' }}
              </el-descriptions-item>
            </el-descriptions>

            <el-alert
              v-for="warning in visibleAnalysisWarnings"
              :key="warning"
              :title="warning"
              type="warning"
              show-icon
              :closable="false"
              class="mb-2"
            />

            <div class="report-actions">
              <el-button size="small" @click="copyReport">Copy Markdown</el-button>
              <el-button size="small" @click="$router.push('/backtest')">Open Backtest</el-button>
              <el-button size="small" @click="$router.push('/data')">Inspect Data</el-button>
            </div>
          </div>

          <el-empty v-else-if="!analysisLoading" description="Enter a stock code to fetch real market data and run analysis" />
        </el-card>
      </el-col>

      <el-col :xs="24" :lg="8">
        <el-card shadow="never" class="dark-card">
          <template #header>
            <span>Quick Start</span>
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
          <el-space direction="vertical" fill style="width: 100%">
            <el-button type="primary" style="width: 100%" :loading="analysisLoading" @click="runAnalysis">
              Run Real Data Analysis
            </el-button>
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

        <el-card shadow="never" class="dark-card analysis-history-card">
          <template #header>
            <div class="card-header">
              <span>Analysis Records</span>
              <el-tag size="small" effect="plain">{{ analysisHistory.length }}</el-tag>
            </div>
          </template>
          <div v-if="analysisHistory.length > 0" class="analysis-history">
            <button
              v-for="record in analysisHistory"
              :key="record.symbol"
              type="button"
              class="history-item"
              :class="{ active: analysisResult?.symbol === record.symbol }"
              @click="selectAnalysisRecord(record)"
            >
              <div>
                <div class="history-symbol">{{ record.symbol }}</div>
                <div class="history-meta">{{ record.as_of }} · {{ record.source }}</div>
              </div>
              <div class="history-metrics">
                <span>{{ formatPrice(record.latest) }}</span>
                <span :class="priceChangeClass(record.change_pct)">
                  {{ formatPct(record.change_pct) }}
                </span>
                <el-tag :type="record.rating === 'buy' ? 'success' : record.rating === 'sell' ? 'danger' : 'warning'" size="small">
                  {{ record.rating.toUpperCase() }}
                </el-tag>
              </div>
            </button>
          </div>
          <el-empty v-else description="No analysis records yet" />
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
import { computed, onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { useTradingStore } from '@/stores/trading'
import { useBacktestStore } from '@/stores/backtest'
import client, { unwrapApiData } from '@/api/client'
import type { AnalysisResult } from '@/api/types'

const ANALYSIS_HISTORY_KEY = 'stock.dashboard.analysisHistory'
const MAX_ANALYSIS_HISTORY = 12

interface AnalysisHistoryRecord {
  symbol: string
  as_of: string
  source: string
  latest: number
  change_pct: number
  rating: string
  score: number
  saved_at: string
  result: AnalysisResult
}

const tradingStore = useTradingStore()
const backtestStore = useBacktestStore()
const strategyCount = ref(0)
const analysisLoading = ref(false)
const analysisError = ref<string | null>(null)
const analysisResult = ref<AnalysisResult | null>(null)
const analysisHistory = ref<AnalysisHistoryRecord[]>([])
const analysisForm = ref({
  symbol: '600519.SH',
  source: 'auto',
  days: 120,
  use_ai: false,
})

onMounted(async () => {
  loadAnalysisHistory()
  if (analysisHistory.value.length > 0) {
    selectAnalysisRecord(analysisHistory.value[0])
  }
  await tradingStore.ensurePaperGatewayConnected()
  try {
    const resp = await client.get('/api/v2/strategies')
    const data = unwrapApiData<{ count: number }>(resp.data)
    strategyCount.value = data.count || 0
  } catch { /* ignore */ }
  await runAnalysis()
})

const statsCards = computed(() => [
  { label: 'Gateway', value: tradingStore.connected ? 'Online' : 'Offline', color: tradingStore.connected ? 'text-green' : 'text-red' },
  { label: 'Strategies', value: String(strategyCount.value), color: '' },
  { label: 'Analysis', value: analysisResult.value ? analysisResult.value.signal.rating.toUpperCase() : 'Ready', color: analysisColor.value },
  { label: 'Positions', value: String(tradingStore.positions.length), color: '' },
])

const ratingType = computed(() => {
  const rating = analysisResult.value?.signal.rating
  if (rating === 'buy') return 'success'
  if (rating === 'sell') return 'danger'
  return 'warning'
})

const scoreStatus = computed(() => {
  const score = analysisResult.value?.signal.score || 0
  if (score >= 70) return 'success'
  if (score < 45) return 'exception'
  return 'warning'
})

const analysisColor = computed(() => {
  const rating = analysisResult.value?.signal.rating
  if (rating === 'buy') return 'text-green'
  if (rating === 'sell') return 'text-red'
  return 'text-yellow'
})

const visibleAnalysisWarnings = computed(() => {
  const hiddenPatterns = [
    /^primary OHLCV verified on /i,
    /^selected .+ because it has broader or newer OHLCV coverage than .+/i,
  ]
  return (analysisResult.value?.data_quality.warnings || []).filter(
    (warning) => !hiddenPatterns.some((pattern) => pattern.test(warning)),
  )
})

async function runAnalysis() {
  if (!analysisForm.value.symbol.trim()) {
    analysisError.value = 'Symbol is required'
    return
  }
  analysisLoading.value = true
  analysisError.value = null
  try {
    const resp = await client.post('/api/v2/analysis/run', {
      symbol: analysisForm.value.symbol.trim(),
      source: analysisForm.value.source,
      days: analysisForm.value.days,
      strategy: 'macd',
      include_backtest: true,
      use_ai: analysisForm.value.use_ai,
    })
    const data = unwrapApiData<{ analysis: AnalysisResult }>(resp.data)
    analysisResult.value = data.analysis
    saveAnalysisRecord(data.analysis)
  } catch (e) {
    analysisError.value = (e as Error).message
  } finally {
    analysisLoading.value = false
  }
}

async function copyReport() {
  if (!analysisResult.value?.markdown_report) return
  try {
    await navigator.clipboard.writeText(analysisResult.value.markdown_report)
    ElMessage.success('Markdown copied')
  } catch {
    ElMessage.error('Copy failed')
  }
}

function loadAnalysisHistory() {
  try {
    const raw = window.localStorage.getItem(ANALYSIS_HISTORY_KEY)
    if (!raw) return
    const records = JSON.parse(raw) as AnalysisHistoryRecord[]
    analysisHistory.value = records.filter((record) => record?.symbol && record?.result).slice(0, MAX_ANALYSIS_HISTORY)
  } catch {
    analysisHistory.value = []
  }
}

function saveAnalysisRecord(result: AnalysisResult) {
  const record: AnalysisHistoryRecord = {
    symbol: result.symbol,
    as_of: result.as_of,
    source: result.data_quality.source,
    latest: result.price.latest,
    change_pct: result.price.change_pct,
    rating: result.signal.rating,
    score: result.signal.score,
    saved_at: new Date().toISOString(),
    result,
  }
  analysisHistory.value = [
    record,
    ...analysisHistory.value.filter((item) => item.symbol !== result.symbol),
  ].slice(0, MAX_ANALYSIS_HISTORY)
  window.localStorage.setItem(ANALYSIS_HISTORY_KEY, JSON.stringify(analysisHistory.value))
}

function selectAnalysisRecord(record: AnalysisHistoryRecord) {
  analysisResult.value = record.result
  analysisForm.value.symbol = record.symbol
  analysisForm.value.source = record.source
  analysisError.value = null
}

function formatPct(v: number | undefined): string {
  if (v === undefined || v !== v) return 'N/A'
  return (v * 100).toFixed(2) + '%'
}

function formatNum(v: number | undefined): string {
  if (v === undefined || v !== v) return 'N/A'
  return v.toFixed(4)
}

function formatPrice(v: number | undefined): string {
  if (v === undefined || v !== v) return 'N/A'
  return v.toFixed(2)
}

function priceChangeClass(v: number | undefined): string {
  if (v === undefined || v !== v) return ''
  return v >= 0 ? 'text-red' : 'text-green'
}
</script>

<style scoped>
.dashboard { max-width: 1400px; }
.mb-4 { margin-bottom: 16px; }
.mb-2 { margin-bottom: 8px; }
.stat-card {
  background: var(--bg-card);
  border-color: var(--border);
  text-align: center;
  margin-bottom: 12px;
}
.stat-label { color: var(--text-secondary); font-size: 12px; text-transform: uppercase; }
.stat-value { font-size: 24px; font-weight: 700; margin-top: 6px; }
.dark-card { background: var(--bg-card); border-color: var(--border); }
.text-green { color: var(--green); }
.text-red { color: var(--red); }
.text-yellow { color: #f59e0b; }

.analysis-card {
  min-height: 440px;
}

.analysis-history-card {
  margin-top: 16px;
}

.card-header,
.analysis-summary,
.report-actions {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.analysis-toolbar {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
}

.source-select {
  width: 130px;
}

.analysis-result {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.analysis-summary {
  padding: 12px;
  border: 1px solid var(--border);
  background: rgba(15, 23, 42, 0.35);
}

.analysis-price {
  font-size: 28px;
  font-weight: 700;
  margin-top: 4px;
}

.mini-panel {
  min-height: 150px;
  padding: 12px;
  border: 1px solid var(--border);
  background: rgba(15, 23, 42, 0.25);
}

.panel-title {
  font-size: 13px;
  font-weight: 700;
  margin-bottom: 8px;
}

.mini-panel ul {
  padding-left: 18px;
  color: var(--text-secondary);
  line-height: 1.55;
}

.report-actions {
  justify-content: flex-start;
  flex-wrap: wrap;
}

.analysis-history {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.history-item {
  width: 100%;
  min-height: 64px;
  padding: 10px 12px;
  border: 1px solid var(--border);
  background: rgba(15, 23, 42, 0.25);
  color: var(--text-primary);
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  text-align: left;
}

.history-item:hover,
.history-item.active {
  border-color: var(--primary);
  background: rgba(59, 130, 246, 0.12);
}

.history-symbol {
  font-weight: 700;
}

.history-meta {
  margin-top: 4px;
  color: var(--text-secondary);
  font-size: 12px;
}

.history-metrics {
  min-width: 86px;
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: 6px;
  font-size: 12px;
}

@media (max-width: 768px) {
  .analysis-summary {
    align-items: flex-start;
    flex-direction: column;
  }
}
</style>
