<template>
  <div class="settings-page">
    <el-card shadow="never" class="dark-card">
      <template #header>
        <div class="settings-header">
          <span>Settings</span>
          <div class="header-actions">
            <el-tag v-if="configPath" size="small" effect="plain">
              Local .env ({{ configSource || 'env' }}): {{ configPath }}
            </el-tag>
            <el-button size="small" :loading="loading" @click="loadSettings">Reload</el-button>
            <el-button size="small" @click="resetLocalChanges">Reset</el-button>
            <el-button size="small" type="primary" :loading="saving" @click="saveSettings">Save to .env</el-button>
          </div>
        </div>
      </template>

      <el-alert
        v-if="error"
        :title="error"
        type="error"
        show-icon
        :closable="false"
        class="section-gap"
      />
      <el-alert
        v-if="warnings.length > 0"
        :title="warnings.join('; ')"
        type="warning"
        show-icon
        :closable="false"
        class="section-gap"
      />
      <el-alert
        v-if="envError"
        :title="envError"
        type="warning"
        show-icon
        :closable="false"
        class="section-gap"
      />

      <section class="settings-section">
        <div class="section-title">API Access</div>
        <el-form label-position="top" size="small" class="settings-grid">
          <el-form-item label="API Token">
            <el-input v-model="authStore.token" placeholder="Enter API token" show-password />
          </el-form-item>
          <el-form-item class="button-row">
            <el-button type="primary" @click="saveToken">Save Token</el-button>
            <el-button @click="authStore.clearToken()">Clear Token</el-button>
          </el-form-item>
        </el-form>
      </section>

      <el-tabs v-model="activeSection" tab-position="left" class="settings-tabs">
        <el-tab-pane
          v-for="section in sections"
          :key="section.key"
          :label="section.label"
          :name="section.key"
        >
          <section class="settings-section">
            <div class="section-title">{{ section.label }}</div>
            <el-form label-position="top" size="small" class="settings-grid">
              <el-form-item
                v-for="field in section.fields"
                :key="field.path"
                :label="field.label"
                :class="{ 'wide-field': field.kind === 'json' || field.kind === 'textarea' }"
              >
                <el-switch
                  v-if="field.kind === 'boolean'"
                  :model-value="Boolean(getValue(field.path))"
                  @update:model-value="setValue(field.path, $event)"
                />
                <el-input-number
                  v-else-if="field.kind === 'number'"
                  :model-value="Number(getValue(field.path) ?? 0)"
                  :min="field.min"
                  :max="field.max"
                  :step="field.step ?? 1"
                  controls-position="right"
                  class="full-control"
                  @update:model-value="setValue(field.path, $event ?? 0)"
                />
                <el-select
                  v-else-if="field.kind === 'select'"
                  :model-value="String(getValue(field.path) ?? '')"
                  filterable
                  class="full-control"
                  @update:model-value="setValue(field.path, $event)"
                >
                  <el-option
                    v-for="option in field.options || []"
                    :key="option"
                    :label="option"
                    :value="option"
                  />
                </el-select>
                <el-input
                  v-else-if="field.kind === 'json'"
                  v-model="jsonValues[field.path]"
                  type="textarea"
                  :rows="field.rows ?? 6"
                  spellcheck="false"
                  placeholder="JSON"
                />
                <el-input
                  v-else-if="field.kind === 'textarea'"
                  :model-value="String(getValue(field.path) ?? '')"
                  type="textarea"
                  :rows="field.rows ?? 3"
                  @update:model-value="setValue(field.path, $event)"
                />
                <el-input
                  v-else
                  :model-value="String(getValue(field.path) ?? '')"
                  :show-password="field.secret"
                  @update:model-value="setValue(field.path, $event)"
                />
                <div v-if="field.help" class="field-help">{{ field.help }}</div>
              </el-form-item>
            </el-form>
          </section>
        </el-tab-pane>
      </el-tabs>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import client, { unwrapApiData } from '@/api/client'
import { useAuthStore } from '@/stores/auth'

type FieldKind = 'text' | 'number' | 'boolean' | 'select' | 'json' | 'textarea'

interface SettingField {
  path: string
  label: string
  kind: FieldKind
  options?: string[]
  min?: number
  max?: number
  step?: number
  rows?: number
  secret?: boolean
  help?: string
}

interface SettingSection {
  key: string
  label: string
  fields: SettingField[]
}

interface SettingsPayload {
  config: Record<string, unknown>
  config_path: string
  config_source?: string
  env_error?: string
  warnings: string[]
}

const authStore = useAuthStore()
const activeSection = ref('data')
const loading = ref(false)
const saving = ref(false)
const error = ref('')
const configPath = ref('')
const configSource = ref('')
const envError = ref('')
const warnings = ref<string[]>([])
const config = ref<Record<string, any>>({})
const loadedConfig = ref<Record<string, any>>({})
const jsonValues = reactive<Record<string, string>>({})

const providerOptions = ['akshare', 'sina', 'tencent', 'eastmoney', 'yfinance', 'tushare']
const realtimeProviderOptions = ['simulation', 'akshare', 'sina', 'eastmoney', 'tencent']
const brokerOptions = ['xtp', 'hundsun', 'xtquant', 'qmt', 'vnpy', 'vnpy_qmt', 'paper']

const sections: SettingSection[] = [
  {
    key: 'data',
    label: 'Data Sources',
    fields: [
      { path: 'data.provider', label: 'Default Provider', kind: 'select', options: providerOptions },
      { path: 'data.cache_dir', label: 'Cache Directory', kind: 'text' },
      { path: 'data.adj', label: 'Adjustment', kind: 'select', options: ['', 'qfq', 'hfq', 'noadj'] },
      { path: 'data.start_date', label: 'Default Start Date', kind: 'text' },
      { path: 'data.end_date', label: 'Default End Date', kind: 'text' },
      { path: 'data.providers', label: 'Provider Options', kind: 'json', rows: 8 },
      { path: 'data.level2', label: 'Level2 Options', kind: 'json', rows: 8 },
    ],
  },
  {
    key: 'backtest',
    label: 'Backtest',
    fields: [
      { path: 'backtest.initial_cash', label: 'Initial Cash', kind: 'number', min: 1, step: 10000 },
      { path: 'backtest.commission', label: 'Commission', kind: 'number', min: 0, max: 0.1, step: 0.0001 },
      { path: 'backtest.slippage', label: 'Slippage', kind: 'number', min: 0, step: 0.0001 },
      { path: 'backtest.slippage_type', label: 'Slippage Type', kind: 'select', options: ['fixed', 'percentage', 'volume'] },
      { path: 'backtest.min_trade_unit', label: 'Minimum Trade Unit', kind: 'number', min: 1, step: 100 },
      { path: 'backtest.allow_short', label: 'Allow Short Selling', kind: 'boolean' },
    ],
  },
  {
    key: 'risk',
    label: 'Risk',
    fields: [
      { path: 'risk.enabled', label: 'Enable Risk Checks', kind: 'boolean' },
      { path: 'risk.strict_mode', label: 'Strict Mode', kind: 'boolean' },
      { path: 'risk.max_leverage', label: 'Max Leverage', kind: 'number', min: 0.01, step: 0.1 },
      { path: 'risk.max_drawdown_pct', label: 'Max Drawdown', kind: 'number', min: 0.001, max: 1, step: 0.01 },
      { path: 'risk.daily_loss_limit_pct', label: 'Daily Loss Limit', kind: 'number', min: 0.001, max: 1, step: 0.01 },
      { path: 'risk.margin_call_level', label: 'Margin Call Level', kind: 'number', min: 0, max: 1, step: 0.01 },
      { path: 'risk.force_liquidation_level', label: 'Force Liquidation Level', kind: 'number', min: 0, max: 1, step: 0.01 },
      { path: 'risk.max_position_pct', label: 'Max Position %', kind: 'number', min: 0.001, step: 0.01 },
      { path: 'risk.max_positions', label: 'Max Positions', kind: 'number', min: 1, step: 1 },
      { path: 'risk.max_sector_exposure', label: 'Max Sector Exposure', kind: 'number', min: 0, max: 1, step: 0.01 },
      { path: 'risk.min_position_value', label: 'Min Position Value', kind: 'number', min: 0, step: 1000 },
      { path: 'risk.max_order_value', label: 'Max Order Value', kind: 'number', min: 0.01, step: 10000 },
      { path: 'risk.max_order_pct', label: 'Max Order %', kind: 'number', min: 0.001, step: 0.01 },
      { path: 'risk.price_deviation_limit', label: 'Price Deviation Limit', kind: 'number', min: 0.001, max: 1, step: 0.01 },
      { path: 'risk.min_order_interval_sec', label: 'Min Order Interval Seconds', kind: 'number', min: 0, step: 1 },
      { path: 'risk.default_stop_loss_pct', label: 'Default Stop Loss', kind: 'number', min: 0, max: 1, step: 0.01 },
      { path: 'risk.default_take_profit_pct', label: 'Default Take Profit', kind: 'number', min: 0, max: 1, step: 0.01 },
      { path: 'risk.trailing_stop_pct', label: 'Trailing Stop', kind: 'number', min: 0, max: 1, step: 0.01 },
      { path: 'risk.enable_auto_stop', label: 'Enable Auto Stop', kind: 'boolean' },
    ],
  },
  {
    key: 'execution',
    label: 'Execution',
    fields: [
      { path: 'execution.gateway', label: 'Gateway', kind: 'select', options: ['paper', 'backtest', 'live'] },
      { path: 'execution.mode', label: 'Mode', kind: 'select', options: ['vectorized', 'event'] },
      { path: 'execution.enable_matching', label: 'Enable Matching', kind: 'boolean' },
      { path: 'execution.enable_slippage', label: 'Enable Slippage', kind: 'boolean' },
      { path: 'execution.live_gateway', label: 'Live Gateway Options', kind: 'json', rows: 8 },
    ],
  },
  {
    key: 'live_trading',
    label: 'Live Trading',
    fields: [
      { path: 'live_trading.enabled', label: 'Enabled', kind: 'boolean' },
      { path: 'live_trading.broker', label: 'Broker', kind: 'select', options: brokerOptions },
      { path: 'live_trading.account_id', label: 'Account ID', kind: 'text' },
      { path: 'live_trading.gateway_type', label: 'Gateway Type', kind: 'select', options: brokerOptions },
      { path: 'live_trading.gateway_provider', label: 'Gateway Provider', kind: 'select', options: ['self', 'vnpy', 'third_party'] },
      { path: 'live_trading.qmt_provider', label: 'QMT Provider', kind: 'select', options: ['self', 'xtquant', 'vnpy', 'vnpy_qmt', 'third_party'] },
      { path: 'live_trading.vnpy_gateway', label: 'vn.py Gateway', kind: 'text' },
      { path: 'live_trading.vnpy_setting', label: 'vn.py Setting', kind: 'json', rows: 6 },
      { path: 'live_trading.broker_options', label: 'Broker Options', kind: 'json', rows: 6 },
      { path: 'live_trading.sdk_path', label: 'SDK Path', kind: 'text' },
      { path: 'live_trading.sdk_log_path', label: 'SDK Log Path', kind: 'text' },
      { path: 'live_trading.auto_reconnect', label: 'Auto Reconnect', kind: 'boolean' },
      { path: 'live_trading.max_orders_per_second', label: 'Max Orders Per Second', kind: 'number', min: 0.01, step: 1 },
    ],
  },
  {
    key: 'realtime_data',
    label: 'Realtime Data',
    fields: [
      { path: 'realtime_data.provider', label: 'Provider', kind: 'select', options: realtimeProviderOptions },
      { path: 'realtime_data.symbols', label: 'Symbols', kind: 'json', rows: 5 },
      { path: 'realtime_data.fallback_providers', label: 'Fallback Providers', kind: 'json', rows: 5 },
      { path: 'realtime_data.interval_seconds', label: 'Interval Seconds', kind: 'number', min: 0.1, step: 0.5 },
      { path: 'realtime_data.request_timeout_seconds', label: 'Request Timeout Seconds', kind: 'number', min: 0.1, step: 0.5 },
      { path: 'realtime_data.bar_intervals', label: 'Bar Intervals', kind: 'json', rows: 5 },
      { path: 'realtime_data.level2_provider', label: 'Level2 Provider', kind: 'select', options: ['stub', 'mock', 'xtp', 'hundsun', 'uft', 'qmt', 'xtquant'] },
    ],
  },
  {
    key: 'portfolio',
    label: 'Portfolio',
    fields: [
      { path: 'portfolio.strategies', label: 'Strategies', kind: 'json', rows: 5 },
      { path: 'portfolio.rebalance_interval_days', label: 'Rebalance Interval Days', kind: 'number', min: 1, step: 1 },
      { path: 'portfolio.max_weight_per_strategy', label: 'Max Weight Per Strategy', kind: 'number', min: 0.001, max: 1, step: 0.01 },
      { path: 'portfolio.min_weight_per_strategy', label: 'Min Weight Per Strategy', kind: 'number', min: 0, max: 1, step: 0.01 },
      { path: 'portfolio.optimization_objective', label: 'Optimization Objective', kind: 'select', options: ['sharpe', 'min_vol', 'equal_risk'] },
      { path: 'portfolio.capital_allocation', label: 'Capital Allocation', kind: 'json', rows: 6 },
    ],
  },
  {
    key: 'database',
    label: 'Storage',
    fields: [
      { path: 'database.path', label: 'SQLite Path', kind: 'text' },
      { path: 'database.duckdb_path', label: 'DuckDB Path', kind: 'text' },
      { path: 'database.backup_enabled', label: 'Backup Enabled', kind: 'boolean' },
      { path: 'database.backup_interval_hours', label: 'Backup Interval Hours', kind: 'number', min: 1, step: 1 },
      { path: 'database.backup_retention_days', label: 'Backup Retention Days', kind: 'number', min: 1, step: 1 },
    ],
  },
  {
    key: 'platform',
    label: 'Platform',
    fields: [
      { path: 'platform.job_store', label: 'Job Store', kind: 'text' },
      { path: 'platform.job_store_fallback', label: 'Job Store Fallback', kind: 'boolean' },
      { path: 'platform.job_max_workers', label: 'Job Max Workers', kind: 'number', min: 1, step: 1 },
    ],
  },
  {
    key: 'monitoring',
    label: 'Monitoring',
    fields: [
      { path: 'monitoring.enabled', label: 'Enabled', kind: 'boolean' },
      { path: 'monitoring.health_check_interval', label: 'Health Check Interval', kind: 'number', min: 1, step: 1 },
      { path: 'monitoring.metrics_port', label: 'Metrics Port', kind: 'number', min: 0, max: 65535, step: 1 },
      { path: 'monitoring.alert_email', label: 'Alert Email', kind: 'text' },
      { path: 'monitoring.otlp_endpoint', label: 'OTLP Endpoint', kind: 'text' },
      { path: 'monitoring.alert_channels', label: 'Alert Channels', kind: 'json', rows: 6 },
    ],
  },
  {
    key: 'performance',
    label: 'Performance',
    fields: [
      { path: 'performance.max_workers', label: 'Max Workers', kind: 'number', min: 1, step: 1 },
      { path: 'performance.cache_enabled', label: 'Cache Enabled', kind: 'boolean' },
      { path: 'performance.cache_expire_days', label: 'Cache Expire Days', kind: 'number', min: 0, step: 1 },
    ],
  },
  {
    key: 'ai',
    label: 'AI Model',
    fields: [
      { path: 'ai.api_key', label: 'API Key', kind: 'text', secret: true, help: 'OpenAI-compatible API key. Environment variables can still override this process at runtime.' },
      { path: 'ai.base_url', label: 'Base URL', kind: 'text' },
      { path: 'ai.model', label: 'Model', kind: 'text' },
      { path: 'ai.timeout_seconds', label: 'Timeout Seconds', kind: 'number', min: 0.1, step: 1 },
    ],
  },
  {
    key: 'logging',
    label: 'Logging',
    fields: [
      { path: 'logging.level', label: 'Level', kind: 'select', options: ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'] },
      { path: 'logging.file', label: 'File', kind: 'text' },
      { path: 'logging.format', label: 'Format', kind: 'textarea', rows: 2 },
      { path: 'logging.json_format', label: 'JSON Format', kind: 'boolean' },
      { path: 'logging.rotate_size', label: 'Rotate Size Bytes', kind: 'number', min: 1, step: 1024 },
      { path: 'logging.rotate_count', label: 'Rotate Count', kind: 'number', min: 0, step: 1 },
    ],
  },
  {
    key: 'strategy',
    label: 'Strategy',
    fields: [
      { path: 'strategy.name', label: 'Name', kind: 'text' },
      { path: 'strategy.symbols', label: 'Symbols', kind: 'json', rows: 5 },
      { path: 'strategy.params', label: 'Parameters', kind: 'json', rows: 8 },
    ],
  },
]

const jsonFieldPaths = computed(() =>
  sections.flatMap((section) => section.fields).filter((field) => field.kind === 'json').map((field) => field.path),
)

onMounted(() => {
  void loadSettings()
})

function saveToken() {
  authStore.setToken(authStore.token)
  ElMessage.success('Token saved')
}

async function loadSettings() {
  loading.value = true
  error.value = ''
  try {
    const resp = await client.get('/api/v2/settings/config')
    const data = unwrapApiData<SettingsPayload>(resp.data)
    applyLoadedConfig(data)
  } catch (e) {
    error.value = (e as Error).message
  } finally {
    loading.value = false
  }
}

async function saveSettings() {
  saving.value = true
  error.value = ''
  try {
    const nextConfig = clone(config.value)
    writeJsonFields(nextConfig)
    const resp = await client.put('/api/v2/settings/config', { config: nextConfig })
    const data = unwrapApiData<SettingsPayload>(resp.data)
    applyLoadedConfig(data)
    ElMessage.success('Configuration saved to .env')
  } catch (e) {
    error.value = (e as Error).message
  } finally {
    saving.value = false
  }
}

function resetLocalChanges() {
  config.value = clone(loadedConfig.value)
  syncJsonValues()
  ElMessage.info('Local edits reset')
}

function applyLoadedConfig(data: SettingsPayload) {
  config.value = clone(data.config || {})
  loadedConfig.value = clone(config.value)
  configPath.value = data.config_path || ''
  configSource.value = data.config_source || ''
  envError.value = data.env_error || ''
  warnings.value = data.warnings || []
  syncJsonValues()
}

function getValue(path: string): unknown {
  return path.split('.').reduce<unknown>((current, key) => {
    if (current && typeof current === 'object') {
      return (current as Record<string, unknown>)[key]
    }
    return undefined
  }, config.value)
}

function setValue(path: string, value: unknown) {
  const parts = path.split('.')
  let current = config.value
  parts.slice(0, -1).forEach((key) => {
    if (!current[key] || typeof current[key] !== 'object') {
      current[key] = {}
    }
    current = current[key]
  })
  const last = parts[parts.length - 1]
  current[last] = value === '' && path === 'data.adj' ? null : value
}

function syncJsonValues() {
  jsonFieldPaths.value.forEach((path) => {
    jsonValues[path] = JSON.stringify(getValue(path) ?? (path.endsWith('symbols') || path.endsWith('providers') ? [] : {}), null, 2)
  })
}

function writeJsonFields(target: Record<string, any>) {
  jsonFieldPaths.value.forEach((path) => {
    try {
      setNestedValue(target, path, JSON.parse(jsonValues[path] || 'null'))
    } catch {
      throw new Error(`Invalid JSON in ${path}`)
    }
  })
}

function setNestedValue(target: Record<string, any>, path: string, value: unknown) {
  const parts = path.split('.')
  let current = target
  parts.slice(0, -1).forEach((key) => {
    if (!current[key] || typeof current[key] !== 'object') {
      current[key] = {}
    }
    current = current[key]
  })
  current[parts[parts.length - 1]] = value
}

function clone<T>(value: T): T {
  return JSON.parse(JSON.stringify(value ?? {}))
}
</script>

<style scoped>
.settings-page {
  max-width: 1440px;
}

.dark-card {
  background: var(--bg-card);
  border-color: var(--border);
}

.settings-header,
.header-actions {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.header-actions {
  flex-wrap: wrap;
  justify-content: flex-end;
}

.section-gap {
  margin-bottom: 16px;
}

.settings-section {
  margin-bottom: 18px;
}

.section-title {
  margin-bottom: 12px;
  color: var(--text-primary);
  font-weight: 600;
}

.settings-tabs {
  margin-top: 18px;
}

.settings-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
  gap: 10px 16px;
}

.wide-field {
  grid-column: 1 / -1;
}

.full-control {
  width: 100%;
}

.button-row {
  align-self: end;
}

.field-help {
  margin-top: 4px;
  color: var(--text-secondary);
  font-size: 12px;
  line-height: 1.4;
}
</style>
