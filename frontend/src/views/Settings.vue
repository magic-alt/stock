<template>
  <div>
    <el-card shadow="never" class="dark-card">
      <template #header><span>Settings</span></template>
      <el-form label-position="top" size="small">
        <el-form-item label="API Token">
          <el-input v-model="authStore.token" placeholder="Enter API token" show-password />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="saveToken">Save Token</el-button>
          <el-button @click="authStore.clearToken()">Clear Token</el-button>
        </el-form-item>
      </el-form>
    </el-card>
  </div>
</template>
<script setup lang="ts">
import { useAuthStore } from '@/stores/auth'
import { ElMessage } from 'element-plus'

const authStore = useAuthStore()

function saveToken() {
  authStore.setToken(authStore.token)
  ElMessage.success('Token saved')
}
</script>
<style scoped>
.dark-card { background: var(--bg-card); border-color: var(--border); }
</style>
