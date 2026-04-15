<template>
  <div class="trading-page">
    <el-row :gutter="16" class="mb-4">
      <el-col :span="10">
        <el-card shadow="never" class="dark-card">
          <template #header><span>Gateway Connection</span></template>
          <el-form :model="connectForm" label-position="top" size="small">
            <el-row :gutter="12">
              <el-col :span="12">
                <el-form-item label="Mode">
                  <el-select v-model="connectForm.mode" style="width: 100%">
                    <el-option label="paper" value="paper" />
                    <el-option label="live" value="live" />
                  </el-select>
                </el-form-item>
              </el-col>
              <el-col :span="12">
                <el-form-item label="Broker">
                  <el-select v-model="connectForm.broker" style="width: 100%">
                    <el-option v-for="broker in brokers" :key="broker" :label="broker" :value="broker" />
                  </el-select>
                </el-form-item>
              </el-col>
            </el-row>

            <el-row :gutter="12">
              <el-col :span="12">
                <el-form-item label="Account">
                  <el-input v-model="connectForm.account" placeholder="paper / live account" />
                </el-form-item>
              </el-col>
              <el-col :span="12">
                <el-form-item label="Password">
                  <el-input v-model="connectForm.password" placeholder="Optional" show-password />
                </el-form-item>
              </el-col>
            </el-row>

            <el-row :gutter="12">
              <el-col :span="12">
                <el-form-item label="Host">
                  <el-input v-model="connectForm.host" placeholder="127.0.0.1" />
                </el-form-item>
              </el-col>
              <el-col :span="12">
                <el-form-item label="Port">
                  <el-input-number v-model="connectForm.port" :min="0" :step="1" style="width: 100%" />
                </el-form-item>
              </el-col>
            </el-row>

            <el-row :gutter="12">
              <el-col :span="12">
                <el-form-item label="Terminal Type">
                  <el-input v-model="connectForm.terminal_type" placeholder="QMT" />
                </el-form-item>
              </el-col>
              <el-col :span="12">
                <el-form-item label="Client ID">
                  <el-input-number v-model="connectForm.client_id" :min="1" :step="1" style="width: 100%" />
                </el-form-item>
              </el-col>
            </el-row>

            <el-form-item label="Terminal Path">
              <el-input v-model="connectForm.terminal_path" placeholder="C:\\QMT\\bin" />
            </el-form-item>

            <el-row :gutter="12">
              <el-col :span="12">
                <el-form-item label="Trade Server">
                  <el-input v-model="connectForm.trade_server" placeholder="tcp://host:port" />
                </el-form-item>
              </el-col>
              <el-col :span="12">
                <el-form-item label="Quote Server">
                  <el-input v-model="connectForm.quote_server" placeholder="tcp://host:port" />
                </el-form-item>
              </el-col>
            </el-row>

            <el-row :gutter="12">
              <el-col :span="12">
                <el-form-item label="TD Front">
                  <el-input v-model="connectForm.td_front" placeholder="tcp://host:port" />
                </el-form-item>
              </el-col>
              <el-col :span="12">
                <el-form-item label="MD Front">
                  <el-input v-model="connectForm.md_front" placeholder="tcp://host:port" />
                </el-form-item>
              </el-col>
            </el-row>

            <el-divider />

            <el-row :gutter="12">
              <el-col :span="8">
                <el-form-item label="Initial Cash">
                  <el-input-number v-model="connectForm.initial_cash" :min="1000" :step="10000" style="width: 100%" />
                </el-form-item>
              </el-col>
              <el-col :span="8">
                <el-form-item label="Commission">
                  <el-input-number
                    v-model="connectForm.commission_rate"
                    :min="0"
                    :max="0.1"
                    :step="0.0001"
                    :precision="4"
                    style="width: 100%"
                  />
                </el-form-item>
              </el-col>
              <el-col :span="8">
                <el-form-item label="Slippage">
                  <el-input-number
                    v-model="connectForm.slippage"
                    :min="0"
                    :max="0.1"
                    :step="0.0001"
                    :precision="4"
                    style="width: 100%"
                  />
                </el-form-item>
              </el-col>
            </el-row>

            <el-form-item>
              <el-switch v-model="connectForm.enable_risk_check" active-text="Risk Check" />
            </el-form-item>

            <div class="actions">
              <el-button type="primary" :loading="tradingStore.loading" @click="connectGateway">Connect</el-button>
              <el-button @click="disconnectGateway">Disconnect</el-button>
              <el-button @click="refreshAll">Refresh</el-button>
            </div>
          </el-form>
        </el-card>
      </el-col>

      <el-col :span="14">
        <el-card shadow="never" class="dark-card mb-4">
          <template #header><span>Trading Status</span></template>
          <el-descriptions :column="4" border size="small">
            <el-descriptions-item label="Status">
              <el-tag :type="tradingStore.connected ? 'success' : 'info'">{{ tradingStore.status.status }}</el-tag>
            </el-descriptions-item>
            <el-descriptions-item label="Mode">{{ tradingStore.status.mode }}</el-descriptions-item>
            <el-descriptions-item label="Broker">{{ tradingStore.status.broker }}</el-descriptions-item>
            <el-descriptions-item label="Account">{{ tradingStore.status.account || '-' }}</el-descriptions-item>
          </el-descriptions>
        </el-card>

        <el-card shadow="never" class="dark-card mb-4">
          <template #header><span>Account</span></template>
          <el-descriptions v-if="tradingStore.account" :column="3" border size="small">
            <el-descriptions-item label="Cash">{{ formatNum(tradingStore.account.cash) }}</el-descriptions-item>
            <el-descriptions-item label="Total Value">{{ formatNum(tradingStore.account.total_value) }}</el-descriptions-item>
            <el-descriptions-item label="Available">{{ formatNum(tradingStore.account.available) }}</el-descriptions-item>
            <el-descriptions-item label="Margin">{{ formatNum(tradingStore.account.margin) }}</el-descriptions-item>
            <el-descriptions-item label="Unrealized PnL">{{ formatNum(tradingStore.account.unrealized_pnl) }}</el-descriptions-item>
            <el-descriptions-item label="Realized PnL">{{ formatNum(tradingStore.account.realized_pnl) }}</el-descriptions-item>
          </el-descriptions>
          <el-empty v-else description="Connect a gateway to load account info" />
        </el-card>

        <el-card shadow="never" class="dark-card">
          <template #header><span>Positions</span></template>
          <el-table :data="tradingStore.positions" stripe size="small">
            <el-table-column prop="symbol" label="Symbol" width="120" />
            <el-table-column prop="size" label="Qty" width="90" />
            <el-table-column prop="avg_price" label="Avg Price" width="110">
              <template #default="{ row }">{{ formatNum(row.avg_price) }}</template>
            </el-table-column>
            <el-table-column prop="market_value" label="Market Value" width="120">
              <template #default="{ row }">{{ formatNum(row.market_value) }}</template>
            </el-table-column>
            <el-table-column label="Unrealized PnL">
              <template #default="{ row }">
                <span :class="row.unrealized_pnl >= 0 ? 'text-green' : 'text-red'">
                  {{ formatNum(row.unrealized_pnl) }}
                </span>
              </template>
            </el-table-column>
          </el-table>
          <el-empty v-if="tradingStore.positions.length === 0" description="No positions" />
        </el-card>
      </el-col>
    </el-row>

    <el-row :gutter="16">
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
            <el-form-item label="Order Type">
              <el-select v-model="orderForm.order_type" style="width: 100%">
                <el-option label="limit" value="limit" />
                <el-option label="market" value="market" />
                <el-option label="stop" value="stop" />
              </el-select>
            </el-form-item>
            <el-form-item label="Quantity">
              <el-input-number v-model="orderForm.quantity" :min="1" :step="100" style="width: 100%" />
            </el-form-item>
            <el-form-item label="Price">
              <el-input-number v-model="orderForm.price" :min="0" :step="0.01" :precision="2" style="width: 100%" />
            </el-form-item>
            <el-form-item>
              <el-button type="primary" style="width: 100%" @click="submitOrder" :disabled="!tradingStore.connected">
                Submit Order
              </el-button>
            </el-form-item>
          </el-form>

          <el-divider />

          <div class="section-title">Paper Price Feed</div>
          <el-form :model="priceForm" label-position="top" size="small">
            <el-form-item label="Symbol">
              <el-input v-model="priceForm.symbol" placeholder="600519.SH" />
            </el-form-item>
            <el-form-item label="Price">
              <el-input-number v-model="priceForm.price" :min="0" :step="0.01" :precision="2" style="width: 100%" />
            </el-form-item>
            <el-form-item>
              <el-button
                style="width: 100%"
                @click="pushPrice"
                :disabled="tradingStore.status.mode !== 'paper' || !tradingStore.connected"
              >
                Update Price
              </el-button>
            </el-form-item>
          </el-form>
        </el-card>
      </el-col>

      <el-col :span="16">
        <el-card shadow="never" class="dark-card mb-4">
          <template #header><span>Orders</span></template>
          <el-table :data="tradingStore.orders" stripe size="small">
            <el-table-column prop="order_id" label="Order ID" min-width="170" show-overflow-tooltip />
            <el-table-column prop="symbol" label="Symbol" width="110" />
            <el-table-column prop="side" label="Side" width="80" />
            <el-table-column prop="status" label="Status" width="120" />
            <el-table-column prop="quantity" label="Qty" width="80" />
            <el-table-column prop="filled_quantity" label="Filled" width="90" />
            <el-table-column label="Price" width="100">
              <template #default="{ row }">{{ row.price === null ? 'MKT' : formatNum(row.price) }}</template>
            </el-table-column>
            <el-table-column label="Updated" width="170">
              <template #default="{ row }">{{ formatTime(row.update_time || row.create_time) }}</template>
            </el-table-column>
            <el-table-column label="Actions" width="110">
              <template #default="{ row }">
                <el-button
                  size="small"
                  @click="cancelOrder(row.order_id)"
                  :disabled="!canCancel(row.status)"
                >
                  Cancel
                </el-button>
              </template>
            </el-table-column>
          </el-table>
          <el-empty v-if="tradingStore.orders.length === 0" description="No orders yet" />
        </el-card>

        <el-card shadow="never" class="dark-card">
          <template #header><span>Trades</span></template>
          <el-table :data="tradingStore.trades" stripe size="small">
            <el-table-column prop="trade_id" label="Trade ID" min-width="170" show-overflow-tooltip />
            <el-table-column prop="order_id" label="Order ID" min-width="170" show-overflow-tooltip />
            <el-table-column prop="symbol" label="Symbol" width="110" />
            <el-table-column prop="side" label="Side" width="80" />
            <el-table-column label="Price" width="100">
              <template #default="{ row }">{{ formatNum(row.price) }}</template>
            </el-table-column>
            <el-table-column prop="quantity" label="Qty" width="80" />
            <el-table-column label="Commission" width="110">
              <template #default="{ row }">{{ formatNum(row.commission) }}</template>
            </el-table-column>
            <el-table-column label="Time" width="170">
              <template #default="{ row }">{{ formatTime(row.timestamp) }}</template>
            </el-table-column>
          </el-table>
          <el-empty v-if="tradingStore.trades.length === 0" description="No trades yet" />
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup lang="ts">
import { onMounted, onUnmounted, reactive } from 'vue'
import { ElMessage } from 'element-plus'
import { useTradingStore } from '@/stores/trading'
import type { GatewayConnectPayload } from '@/api/types'

const tradingStore = useTradingStore()
const brokers = ['paper', 'eastmoney', 'futu', 'xueqiu', 'ib', 'xtquant', 'xtp', 'hundsun']

const connectForm = reactive<GatewayConnectPayload>({
  mode: 'paper',
  broker: 'paper',
  host: '127.0.0.1',
  port: 11111,
  account: 'paper',
  password: '',
  api_key: '',
  secret: '',
  initial_cash: 1_000_000,
  commission_rate: 0.0003,
  slippage: 0.0001,
  enable_risk_check: true,
  terminal_type: 'QMT',
  terminal_path: '',
  trade_server: '',
  quote_server: '',
  client_id: 1,
  td_front: '',
  md_front: '',
})

const orderForm = reactive({
  symbol: '600519.SH',
  side: 'buy',
  quantity: 100,
  price: 1800,
  order_type: 'limit',
})

const priceForm = reactive({
  symbol: '600519.SH',
  price: 1800,
})

onMounted(() => {
  void tradingStore.refreshAll()
  tradingStore.startAutoRefresh(4000)
})

onUnmounted(() => {
  tradingStore.stopAutoRefresh()
})

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

function canCancel(status: string): boolean {
  return status === 'pending' || status === 'submitted' || status === 'partial'
}

async function refreshAll() {
  await tradingStore.refreshAll()
}

async function connectGateway() {
  try {
    await tradingStore.connectGateway({ ...connectForm })
    ElMessage.success('Gateway connected')
  } catch (err) {
    ElMessage.error(`Connect failed: ${(err as Error).message}`)
  }
}

async function disconnectGateway() {
  try {
    await tradingStore.disconnectGateway()
    ElMessage.success('Gateway disconnected')
  } catch (err) {
    ElMessage.error(`Disconnect failed: ${(err as Error).message}`)
  }
}

async function submitOrder() {
  if (!orderForm.symbol.trim()) {
    ElMessage.error('Symbol is required')
    return
  }
  if (orderForm.quantity <= 0) {
    ElMessage.error('Quantity must be positive')
    return
  }
  if (orderForm.order_type !== 'market' && orderForm.price <= 0) {
    ElMessage.error('Price must be positive for non-market orders')
    return
  }
  try {
    const orderId = await tradingStore.submitOrder({
      symbol: orderForm.symbol.trim(),
      side: orderForm.side,
      quantity: orderForm.quantity,
      price: orderForm.order_type === 'market' ? null : orderForm.price,
      order_type: orderForm.order_type,
    })
    ElMessage.success(`Order submitted: ${orderId}`)
  } catch (err) {
    ElMessage.error(`Order failed: ${(err as Error).message}`)
  }
}

async function cancelOrder(orderId: string) {
  try {
    const cancelled = await tradingStore.cancelOrder(orderId)
    if (cancelled) {
      ElMessage.success(`Order cancelled: ${orderId}`)
      return
    }
    ElMessage.warning(`Cancel rejected: ${orderId}`)
  } catch (err) {
    ElMessage.error(`Cancel failed: ${(err as Error).message}`)
  }
}

async function pushPrice() {
  if (!priceForm.symbol.trim() || priceForm.price <= 0) {
    ElMessage.error('Paper price update requires symbol and positive price')
    return
  }
  try {
    await tradingStore.updatePrice(priceForm.symbol.trim(), priceForm.price)
    ElMessage.success('Paper price updated')
  } catch (err) {
    ElMessage.error(`Price update failed: ${(err as Error).message}`)
  }
}
</script>

<style scoped>
.trading-page { max-width: 1440px; }
.mb-4 { margin-bottom: 16px; }
.dark-card { background: var(--bg-card); border-color: var(--border); }
.actions { display: flex; gap: 8px; }
.section-title { margin-bottom: 12px; font-weight: 600; color: var(--text-secondary); }
.text-green { color: var(--green); }
.text-red { color: var(--red); }
</style>
