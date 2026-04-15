<template>
  <div class="monitor-page">
    <el-row :gutter="16" class="mb-4">
      <el-col :span="4" v-for="card in cards" :key="card.label">
        <el-card shadow="never" class="stat-card">
          <div class="stat-label">{{ card.label }}</div>
          <div class="stat-value" :class="card.className">{{ card.value }}</div>
          <div class="stat-subtitle">{{ card.subtitle }}</div>
        </el-card>
      </el-col>
    </el-row>

    <el-row :gutter="16" class="mb-4">
      <el-col :span="12">
        <el-card shadow="never" class="dark-card">
          <template #header>
            <div class="card-header">
              <span>System Metrics</span>
              <el-button size="small" @click="refreshNow" :loading="monitorStore.loading">Refresh</el-button>
            </div>
          </template>

          <div v-if="systemMetrics">
            <div class="metric-row">
              <span>CPU</span>
              <el-progress :percentage="systemMetrics.cpu_percent" :status="progressStatus(systemMetrics.cpu_percent)" />
            </div>
            <div class="metric-row">
              <span>Memory</span>
              <el-progress :percentage="systemMetrics.memory_percent" :status="progressStatus(systemMetrics.memory_percent)" />
            </div>
            <div class="metric-row">
              <span>Disk</span>
              <el-progress :percentage="systemMetrics.disk_usage_percent" :status="progressStatus(systemMetrics.disk_usage_percent)" />
            </div>

            <el-descriptions :column="2" border size="small">
              <el-descriptions-item label="Memory Used">{{ formatNum(systemMetrics.memory_used_mb) }} MB</el-descriptions-item>
              <el-descriptions-item label="Memory Available">{{ formatNum(systemMetrics.memory_available_mb) }} MB</el-descriptions-item>
              <el-descriptions-item label="Disk Free">{{ formatNum(systemMetrics.disk_free_gb) }} GB</el-descriptions-item>
              <el-descriptions-item label="DB Size">{{ formatNum(systemMetrics.database_size_mb) }} MB</el-descriptions-item>
              <el-descriptions-item label="Active Connections">{{ systemMetrics.active_connections }}</el-descriptions-item>
              <el-descriptions-item label="Last Sample">{{ formatTime(summary.timestamp) }}</el-descriptions-item>
            </el-descriptions>
          </div>

          <el-empty v-else description="No monitoring samples yet" />
        </el-card>
      </el-col>

      <el-col :span="12">
        <el-card shadow="never" class="dark-card">
          <template #header><span>Gateway Snapshot</span></template>
          <el-descriptions :column="2" border size="small">
            <el-descriptions-item label="Status">
              <el-tag :type="gatewayTagType" size="small">{{ summary.gateway.status.status }}</el-tag>
            </el-descriptions-item>
            <el-descriptions-item label="Broker">{{ summary.gateway.status.broker }}</el-descriptions-item>
            <el-descriptions-item label="Mode">{{ summary.gateway.status.mode }}</el-descriptions-item>
            <el-descriptions-item label="Account">{{ summary.gateway.status.account || '-' }}</el-descriptions-item>
            <el-descriptions-item label="Positions">{{ summary.gateway.positions.length }}</el-descriptions-item>
            <el-descriptions-item label="Open Orders">{{ openOrderCount }}</el-descriptions-item>
            <el-descriptions-item label="Recent Trades">{{ summary.gateway.trades.length }}</el-descriptions-item>
            <el-descriptions-item label="Connected At">{{ formatTime(summary.gateway.status.connected_at) }}</el-descriptions-item>
          </el-descriptions>

          <el-divider />

          <div class="mini-section">
            <div class="section-title">Latest Trades</div>
            <el-table :data="summary.gateway.trades.slice(0, 5)" size="small" stripe>
              <el-table-column prop="symbol" label="Symbol" width="110" />
              <el-table-column prop="side" label="Side" width="80" />
              <el-table-column prop="price" label="Price" width="100" />
              <el-table-column prop="quantity" label="Qty" width="80" />
              <el-table-column label="Time">
                <template #default="{ row }">{{ formatTime(row.timestamp) }}</template>
              </el-table-column>
            </el-table>
            <el-empty v-if="summary.gateway.trades.length === 0" description="No recent trades" />
          </div>
        </el-card>
      </el-col>
    </el-row>

    <el-row :gutter="16">
      <el-col :span="12">
        <el-card shadow="never" class="dark-card">
          <template #header><span>Alerts</span></template>
          <el-table :data="monitorStore.alerts" size="small" stripe>
            <el-table-column prop="level" label="Level" width="100">
              <template #default="{ row }">
                <el-tag :type="alertTagType(row.level)" size="small">{{ row.level }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="message" label="Message" />
            <el-table-column label="Time" width="170">
              <template #default="{ row }">{{ formatTime(row.timestamp) }}</template>
            </el-table-column>
          </el-table>
          <el-empty v-if="monitorStore.alerts.length === 0" description="No alerts" />
        </el-card>
      </el-col>

      <el-col :span="12">
        <el-card shadow="never" class="dark-card">
          <template #header><span>Recent Jobs</span></template>
          <el-table :data="summary.jobs" size="small" stripe>
            <el-table-column prop="job_id" label="Job ID" min-width="180" show-overflow-tooltip />
            <el-table-column prop="task_type" label="Task" width="110" />
            <el-table-column prop="status" label="Status" width="110" />
            <el-table-column label="Created" width="170">
              <template #default="{ row }">{{ formatTime(row.created_at) }}</template>
            </el-table-column>
          </el-table>
          <el-empty v-if="summary.jobs.length === 0" description="No jobs submitted" />
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, onUnmounted } from 'vue'
import { useMonitorStore } from '@/stores/monitor'
import { ElMessage } from 'element-plus'

const monitorStore = useMonitorStore()

onMounted(() => {
  void monitorStore.refresh()
  monitorStore.startAutoRefresh(5000)
})

onUnmounted(() => {
  monitorStore.stopAutoRefresh()
})

const summary = computed(() => monitorStore.summary)
const systemMetrics = computed(() => summary.value.system)
const openOrderCount = computed(() => summary.value.gateway.orders.filter((order) => order.status !== 'filled').length)
const gatewayTagType = computed(() => {
  if (summary.value.gateway.status.connected) return 'success'
  if (summary.value.gateway.status.status === 'error') return 'danger'
  return 'info'
})

const cards = computed(() => [
  {
    label: 'Monitor',
    value: summary.value.status,
    subtitle: `Updated ${formatTime(summary.value.timestamp)}`,
    className: summary.value.status === 'healthy' ? 'text-green' : 'text-yellow',
  },
  {
    label: 'CPU',
    value: systemMetrics.value ? `${formatNum(systemMetrics.value.cpu_percent)}%` : '--',
    subtitle: 'Current process host usage',
    className: heatClass(systemMetrics.value?.cpu_percent ?? 0),
  },
  {
    label: 'Memory',
    value: systemMetrics.value ? `${formatNum(systemMetrics.value.memory_percent)}%` : '--',
    subtitle: 'Host memory pressure',
    className: heatClass(systemMetrics.value?.memory_percent ?? 0),
  },
  {
    label: 'Queue',
    value: String(summary.value.job_queue.pending_jobs ?? 0),
    subtitle: 'Pending jobs',
    className: '',
  },
  {
    label: 'Gateway',
    value: summary.value.gateway.status.connected ? 'Online' : 'Offline',
    subtitle: `${summary.value.gateway.status.mode} / ${summary.value.gateway.status.broker}`,
    className: summary.value.gateway.status.connected ? 'text-green' : 'text-red',
  },
  {
    label: 'Alerts',
    value: String(monitorStore.alerts.length),
    subtitle: 'Recent threshold hits',
    className: monitorStore.alerts.length > 0 ? 'text-yellow' : '',
  },
])

function formatNum(value: number | null | undefined): string {
  if (value === null || value === undefined || Number.isNaN(value)) return '--'
  return value.toFixed(2)
}

function formatTime(value: string | null | undefined): string {
  if (!value) return '--'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value
  return date.toLocaleString('zh-CN', { hour12: false })
}

function heatClass(value: number): string {
  if (value >= 85) return 'text-red'
  if (value >= 70) return 'text-yellow'
  return 'text-green'
}

function progressStatus(value: number): 'success' | 'warning' | 'exception' {
  if (value >= 85) return 'exception'
  if (value >= 70) return 'warning'
  return 'success'
}

function alertTagType(level: string): 'success' | 'warning' | 'danger' | 'info' {
  if (level === 'CRITICAL' || level === 'ERROR') return 'danger'
  if (level === 'WARNING') return 'warning'
  if (level === 'INFO') return 'success'
  return 'info'
}

async function refreshNow() {
  try {
    await monitorStore.refresh()
  } catch (err) {
    ElMessage.error((err as Error).message)
  }
}
</script>

<style scoped>
.monitor-page { max-width: 1440px; }
.mb-4 { margin-bottom: 16px; }
.dark-card,
.stat-card { background: var(--bg-card); border-color: var(--border); }
.stat-card { min-height: 120px; }
.stat-label { color: var(--text-secondary); font-size: 12px; text-transform: uppercase; }
.stat-value { font-size: 26px; font-weight: 700; margin-top: 10px; }
.stat-subtitle { margin-top: 8px; color: var(--text-secondary); font-size: 12px; }
.card-header { display: flex; align-items: center; justify-content: space-between; }
.metric-row { margin-bottom: 12px; }
.metric-row span { display: inline-block; min-width: 64px; color: var(--text-secondary); }
.mini-section { margin-top: 8px; }
.section-title { margin-bottom: 10px; font-weight: 600; color: var(--text-secondary); }
.text-green { color: var(--green); }
.text-red { color: var(--red); }
.text-yellow { color: #f59e0b; }
</style>
