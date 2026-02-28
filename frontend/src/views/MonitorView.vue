<template>
  <div>
    <el-card shadow="never" class="dark-card">
      <template #header><span>System Monitor</span></template>
      <el-descriptions :column="2" border size="small">
        <el-descriptions-item label="Platform">Unified Quant Platform V5.0</el-descriptions-item>
        <el-descriptions-item label="Python">3.12</el-descriptions-item>
        <el-descriptions-item label="Gateway">
          <el-tag :type="tradingStore.connected ? 'success' : 'info'" size="small">
            {{ tradingStore.status.status }}
          </el-tag>
        </el-descriptions-item>
        <el-descriptions-item label="Mode">{{ tradingStore.status.mode }}</el-descriptions-item>
      </el-descriptions>
      <el-divider />
      <el-empty description="Real-time metrics coming in V5.0-C with FastAPI integration" />
    </el-card>
  </div>
</template>
<script setup lang="ts">
import { useTradingStore } from '@/stores/trading'
const tradingStore = useTradingStore()
</script>
<style scoped>
.dark-card { background: var(--bg-card); border-color: var(--border); }
</style>
