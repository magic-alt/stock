<template>
  <div class="data-page">
    <el-card shadow="never" class="dark-card">
      <template #header>
        <div class="card-header">
          <span>Data Browser</span>
          <el-tag size="small" effect="plain">{{ rows.length }} rows</el-tag>
        </div>
      </template>

      <el-form :model="form" inline size="small" class="toolbar">
        <el-form-item label="Symbol">
          <el-input v-model="form.symbol" placeholder="600519.SH" />
        </el-form-item>
        <el-form-item label="Days">
          <el-input-number v-model="form.days" :min="10" :max="500" :step="10" />
        </el-form-item>
        <el-form-item label="Source">
          <el-input v-model="form.source" placeholder="akshare" />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" :loading="loading" @click="loadData">Load</el-button>
        </el-form-item>
      </el-form>

      <el-alert v-if="error" :title="error" type="error" show-icon :closable="false" class="mb-4" />

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
import { computed, onMounted, ref } from 'vue'
import client, { unwrapApiData } from '@/api/client'

interface ChartData {
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

const loading = ref(false)
const error = ref<string | null>(null)
const chartData = ref<ChartData>({ dates: [], ohlc: [], volumes: [] })
const form = ref({
  symbol: '600519.SH',
  days: 120,
  source: 'akshare',
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

onMounted(() => {
  void loadData()
})

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
        source: form.value.source.trim() || 'akshare',
      },
    })
    chartData.value = unwrapApiData<ChartData>(resp.data)
  } catch (e) {
    error.value = (e as Error).message
  } finally {
    loading.value = false
  }
}

function formatNumber(value: unknown, digits = 2): string {
  const numeric = Number(value)
  if (Number.isNaN(numeric)) return 'N/A'
  return numeric.toFixed(digits)
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

.card-header {
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

.mb-4 {
  margin-bottom: 16px;
}

.data-table {
  width: 100%;
}
</style>
