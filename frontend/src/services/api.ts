import axios, { type AxiosInstance } from 'axios'
import { useAuthStore } from '@/stores/auth'

export const api: AxiosInstance = axios.create({
  baseURL: '/api/v1',
  timeout: 20000,
})

api.interceptors.request.use((config) => {
  const auth = useAuthStore()
  if (auth.token) {
    config.headers.Authorization = `Bearer ${auth.token}`
  }
  return config
})

api.interceptors.response.use(
  (resp) => resp,
  (err) => {
    if (err.response?.status === 401) {
      const auth = useAuthStore()
      auth.clear()
    }
    return Promise.reject(err)
  },
)
