<template>
  <div class="trading-page">
    <el-row :gutter="16">
      <el-col :span="16">
        <el-card shadow="never" class="dark-card">
          <template #header><span>Trading Console</span></template>
          <el-descriptions :column="3" border size="small" class="mb-4">
            <el-descriptions-item label="Status">
              <el-tag :type="tradingStore.connected ? 'success' : 'danger'">
                {{ tradingStore.status.status }}
              </el-tag>
            </el-descriptions-item>
            <el-descriptions-item label="Mode">{{ tradingStore.status.mode }}</el-descriptions-item>
            <el-descriptions-item label="Broker">{{ tradingStore.status.broker }}</el-descriptions-item>
          </el-descriptions>

          <div v-if="tradingStore.account" class="mb-4">
            <h4 style="margin-bottom: 8px; color: var(--accent);">Account</h4>
            <el-descriptions :column="2" border size="small">
              <el-descriptions-item
                v-for="(v, k) in tradingStore.account" :key="k"
                :label="String(k)">
                {{ typeof v === 'number' ? v.toFixed(2) : v }}
              </el-descriptions-item>
            </el-descriptions>
          </div>

          <h4 style="margin-bottom: 8px; color: var(--accent);">Positions</h4>
          <el-table :data="tradingStore.positions" stripe size="small" style="width: 100%">
            <el-table-column prop="symbol" label="Symbol" width="120" />
            <el-table-column prop="quantity" label="Qty" width="80" />
            <el-table-column prop="avg_cost" label="Avg Cost" width="100" />
            <el-table-column prop="market_value" label="MktVal" width="100" />
            <el-table-column label="P&L">
              <template #default="{ row }">
                <span :class="(row.unrealized_pnl || 0) >= 0 ? 'text-green' : 'text-red'">
                  {{ (row.unrealized_pnl || 0).toFixed(2) }}
                </span>
              </template>
            </el-table-column>
          </el-table>
          <el-empty v-if="tradingStore.positions.length === 0" description="No positions" />
        </el-card>
      </el-col>
      <el-col :span="8">
        <el-card shadow="never" class="dark-card">
          <template #header><span>Place Order</span></template>
          <el-form :model="orderForm" label-position="top" size="small">
            <el-form-item label="Symbol">
              <el-input v-model="orderForm.symbol" placeholder="600519.SH" />
            </el-form-item>
            <el-form-item label="Side">
              <el-radio-group v-model="orderForm.side">
                <el-radio-button value="buy">Buy</el-radio-button>
                <el-radio-button value="sell">Sell</el-radio-button>
              </el-radio-group>
            </el-form-item>
            <el-form-item label="Quantity">
              <el-input-number v-model="orderForm.quantity" :min="100" :step="100" style="width: 100%" />
            </el-form-item>
            <el-form-item label="Price">
              <el-input-number v-model="orderForm.price" :min="0" :step="0.01" :precision="2" style="width: 100%" />
            </el-form-item>
            <el-form-item>
              <el-button type="primary" @click="submitOrder" style="width: 100%">Submit Order</el-button>
            </el-form-item>
          </el-form>
        </el-card>
        <el-card shadow="never" class="dark-card" style="margin-top: 16px;">
          <template #header><span>Actions</span></template>
          <el-space direction="vertical" fill style="width: 100%">
            <el-button @click="tradingStore.refreshAll" style="width: 100%">Refresh All</el-button>
          </el-space>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue'
import { useTradingStore } from '@/stores/trading'
import { ElMessage } from 'element-plus'
import client from '@/api/client'

const tradingStore = useTradingStore()

const orderForm = ref({
  symbol: '',
  side: 'buy',
  quantity: 100,
  price: 0,
})

onMounted(() => {
  tradingStore.refreshAll()
  tradingStore.startAutoRefresh()
})

onUnmounted(() => {
  tradingStore.stopAutoRefresh()
})

async function submitOrder() {
  try {
    await client.post('/gateway/order', {
      symbol: orderForm.value.symbol,
      side: orderForm.value.side,
      quantity: orderForm.value.quantity,
      price: orderForm.value.price,
      order_type: 'limit',
    })
    ElMessage.success('Order submitted')
    tradingStore.refreshAll()
  } catch (e) {
    ElMessage.error('Order failed: ' + (e as Error).message)
  }
}
</script>

<style scoped>
.mb-4 { margin-bottom: 16px; }
.dark-card { background: var(--bg-card); border-color: var(--border); }
.text-green { color: var(--green); }
.text-red { color: var(--red); }
</style>
