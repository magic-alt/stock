<template>
  <div class="strategies-page">
    <el-card shadow="never" class="dark-card">
      <template #header>
        <div style="display: flex; justify-content: space-between; align-items: center;">
          <span>Strategy Library</span>
          <el-input v-model="search" placeholder="Search strategies..." style="width: 240px" size="small" clearable />
        </div>
      </template>
      <el-table :data="filtered" stripe size="small" style="width: 100%">
        <el-table-column prop="name" label="Name" width="180" sortable />
        <el-table-column prop="description" label="Description" />
        <el-table-column label="Parameters" width="120">
          <template #default="{ row }">
            {{ Object.keys(row.params || {}).length }} params
          </template>
        </el-table-column>
        <el-table-column label="Actions" width="200">
          <template #default="{ row }">
            <el-button size="small" @click="showDetail(row)">Detail</el-button>
            <el-button size="small" type="primary" @click="runQuick(row)">Backtest</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <el-dialog v-model="detailVisible" :title="selectedStrategy?.name || ''" width="600px">
      <el-descriptions :column="1" border v-if="selectedStrategy">
        <el-descriptions-item label="Name">{{ selectedStrategy.name }}</el-descriptions-item>
        <el-descriptions-item label="Description">{{ selectedStrategy.description || 'N/A' }}</el-descriptions-item>
      </el-descriptions>
      <h4 style="margin: 16px 0 8px;">Parameters</h4>
      <el-table :data="paramList" size="small" v-if="selectedStrategy">
        <el-table-column prop="name" label="Name" width="140" />
        <el-table-column prop="type" label="Type" width="100" />
        <el-table-column prop="default" label="Default" />
      </el-table>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import client, { unwrapApiData } from '@/api/client'
import type { StrategyInfo } from '@/api/types'

const router = useRouter()
const strategies = ref<StrategyInfo[]>([])
const search = ref('')
const detailVisible = ref(false)
const selectedStrategy = ref<StrategyInfo | null>(null)

onMounted(async () => {
  try {
    const resp = await client.get('/api/v2/strategies')
    const data = unwrapApiData<{ strategies: StrategyInfo[] }>(resp.data)
    strategies.value = data.strategies || []
  } catch { /* ignore */ }
})

const filtered = computed(() => {
  if (!search.value) return strategies.value
  const q = search.value.toLowerCase()
  return strategies.value.filter(s => s.name.toLowerCase().includes(q))
})

const paramList = computed(() => {
  if (!selectedStrategy.value) return []
  return Object.entries(selectedStrategy.value.params || {}).map(([name, p]) => ({
    name,
    type: p.type,
    default: String(p.default ?? ''),
  }))
})

function showDetail(s: StrategyInfo) {
  selectedStrategy.value = s
  detailVisible.value = true
}

function runQuick(s: StrategyInfo) {
  router.push({ path: '/backtest', query: { strategy: s.name } })
}
</script>

<style scoped>
.dark-card { background: var(--bg-card); border-color: var(--border); }
</style>
