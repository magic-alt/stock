import { defineStore } from 'pinia'
import { ref } from 'vue'

export const useAuthStore = defineStore('auth', () => {
  const token = ref(localStorage.getItem('api_token') || '')
  const username = ref('admin')

  function setToken(newToken: string) {
    token.value = newToken
    localStorage.setItem('api_token', newToken)
  }

  function clearToken() {
    token.value = ''
    localStorage.removeItem('api_token')
  }

  return { token, username, setToken, clearToken }
})
