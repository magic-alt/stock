import axios from 'axios'
import type { AxiosInstance, AxiosResponse } from 'axios'

export interface ApiResponse<T = Record<string, unknown>> {
  ok: boolean
  error?: string
  data?: T
  [key: string]: unknown
}

interface VersionedApiEnvelope<T> {
  code: number
  message: string
  data: T
  request_id?: string
}

const client: AxiosInstance = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || '',
  timeout: 30000,
  headers: { 'Content-Type': 'application/json' },
})

export function unwrapApiData<T>(payload: unknown): T {
  if (
    payload &&
    typeof payload === 'object' &&
    'code' in payload &&
    'data' in payload
  ) {
    return (payload as unknown as VersionedApiEnvelope<T>).data
  }
  return payload as T
}

// Request interceptor: attach auth token if present
client.interceptors.request.use((config) => {
  const token = localStorage.getItem('api_token')
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

// Response interceptor: unwrap envelope
client.interceptors.response.use(
  (resp: AxiosResponse) => resp,
  (error) => {
    const message =
      error.response?.data?.error ||
      error.response?.data?.detail ||
      error.message ||
      'Unknown error'
    return Promise.reject(new Error(message))
  },
)

export default client
