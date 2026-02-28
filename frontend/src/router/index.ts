import { createRouter, createWebHistory } from 'vue-router'

const routes = [
  { path: '/', name: 'Dashboard', component: () => import('@/views/Dashboard.vue') },
  { path: '/backtest', name: 'Backtest', component: () => import('@/views/Backtest.vue') },
  { path: '/trading', name: 'Trading', component: () => import('@/views/Trading.vue') },
  { path: '/strategies', name: 'Strategies', component: () => import('@/views/Strategies.vue') },
  { path: '/data', name: 'Data', component: () => import('@/views/DataView.vue') },
  { path: '/monitor', name: 'Monitor', component: () => import('@/views/MonitorView.vue') },
  { path: '/settings', name: 'Settings', component: () => import('@/views/Settings.vue') },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

export default router
