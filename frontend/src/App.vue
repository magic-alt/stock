<template>
  <el-config-provider :locale="zhCn">
    <el-container class="app-container">
      <el-aside width="220px" class="sidebar">
        <div class="logo">
          <h2>Quant Platform</h2>
          <span class="version">v5.0</span>
        </div>
        <el-menu
          :default-active="route.path"
          router
          background-color="#1a1a2e"
          text-color="#a0aec0"
          active-text-color="#3b82f6"
        >
          <el-menu-item index="/">
            <el-icon><Monitor /></el-icon>
            <span>Dashboard</span>
          </el-menu-item>
          <el-menu-item index="/backtest">
            <el-icon><DataAnalysis /></el-icon>
            <span>Backtest</span>
          </el-menu-item>
          <el-menu-item index="/trading">
            <el-icon><TrendCharts /></el-icon>
            <span>Trading</span>
          </el-menu-item>
          <el-menu-item index="/strategies">
            <el-icon><Document /></el-icon>
            <span>Strategies</span>
          </el-menu-item>
          <el-menu-item index="/data">
            <el-icon><Coin /></el-icon>
            <span>Data</span>
          </el-menu-item>
          <el-menu-item index="/monitor">
            <el-icon><Odometer /></el-icon>
            <span>Monitor</span>
          </el-menu-item>
          <el-menu-item index="/settings">
            <el-icon><Setting /></el-icon>
            <span>Settings</span>
          </el-menu-item>
        </el-menu>
      </el-aside>
      <el-container>
        <el-header class="app-header">
          <div class="header-left">
            <el-breadcrumb separator="/">
              <el-breadcrumb-item :to="{ path: '/' }">Home</el-breadcrumb-item>
              <el-breadcrumb-item>{{ currentPageName }}</el-breadcrumb-item>
            </el-breadcrumb>
          </div>
          <div class="header-right">
            <el-tag :type="gatewayConnected ? 'success' : 'info'" size="small">
              {{ gatewayConnected ? 'Connected' : 'Disconnected' }}
            </el-tag>
          </div>
        </el-header>
        <el-main class="app-main">
          <router-view />
        </el-main>
      </el-container>
    </el-container>
  </el-config-provider>
</template>

<script setup lang="ts">
import { computed, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { useTradingStore } from '@/stores/trading'
import zhCn from 'element-plus/es/locale/lang/zh-cn'
import {
  Monitor, DataAnalysis, TrendCharts, Document,
  Coin, Odometer, Setting
} from '@element-plus/icons-vue'

const route = useRoute()
const tradingStore = useTradingStore()

const gatewayConnected = computed(() => tradingStore.connected)

const pageNames: Record<string, string> = {
  '/': 'Dashboard',
  '/backtest': 'Backtest',
  '/trading': 'Trading',
  '/strategies': 'Strategies',
  '/data': 'Data',
  '/monitor': 'Monitor',
  '/settings': 'Settings',
}

const currentPageName = computed(() => pageNames[route.path] || route.path)

onMounted(() => {
  void tradingStore.fetchStatus()
})
</script>

<style>
:root {
  --bg-primary: #0f0f23;
  --bg-secondary: #1a1a2e;
  --bg-card: #16213e;
  --text-primary: #e0e0e0;
  --text-secondary: #a0aec0;
  --accent: #3b82f6;
  --green: #22c55e;
  --red: #ef4444;
  --border: #2a2a4a;
}

* { margin: 0; padding: 0; box-sizing: border-box; }

body {
  background: var(--bg-primary);
  color: var(--text-primary);
  font-family: -apple-system, 'Segoe UI', Roboto, 'PingFang SC', 'Microsoft YaHei', sans-serif;
}

.app-container {
  height: 100vh;
}

.sidebar {
  background: var(--bg-secondary);
  border-right: 1px solid var(--border);
  overflow-y: auto;
}

.logo {
  padding: 20px;
  text-align: center;
  border-bottom: 1px solid var(--border);
}

.logo h2 {
  color: var(--accent);
  font-size: 18px;
  margin-bottom: 4px;
}

.version {
  color: var(--text-secondary);
  font-size: 12px;
}

.el-menu {
  border-right: none !important;
}

.app-header {
  background: var(--bg-secondary);
  border-bottom: 1px solid var(--border);
  display: flex;
  align-items: center;
  justify-content: space-between;
  height: 56px;
}

.app-main {
  background: var(--bg-primary);
  padding: 20px;
  overflow-y: auto;
}

/* Override Element Plus dark style */
.el-menu-item.is-active {
  background-color: rgba(59, 130, 246, 0.15) !important;
}
</style>
