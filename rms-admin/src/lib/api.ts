import axios from 'axios'
import { useAuthStore } from './auth'
import type { TokenPair } from '../types/auth'

const api = axios.create({
baseURL: import.meta.env.VITE_API_BASE_URL + '/api',
})

// Attach access token
api.interceptors.request.use((config) => {
const access = useAuthStore.getState().accessToken
if (access) {
config.headers = config.headers ?? {}
config.headers.Authorization = `Bearer ${access}`
}
return config
})

// Auto refresh on 401
let isRefreshing = false
let queue: Array<() => void> = []

api.interceptors.response.use(
(res) => res,
async (error) => {
const original = error.config
const status = error.response?.status
if (status === 401 && !original._retry) {
original._retry = true
const { refreshToken, setTokens, clear } = useAuthStore.getState()

if (!refreshToken) {
clear()
return Promise.reject(error)
}

if (isRefreshing) {
return new Promise((resolve) => {
queue.push(() => resolve(api(original)))
})
}

try {
isRefreshing = true
const { data } = await axios.post<TokenPair>(
`${import.meta.env.VITE_API_BASE_URL}/api/auth/token/refresh/`,
{ refresh: refreshToken }
)
setTokens({ access: data.access, refresh: data.refresh ?? refreshToken })
queue.forEach((cb) => cb())
queue = []
return api(original)
} catch (e) {
useAuthStore.getState().clear()
return Promise.reject(e)
} finally {
isRefreshing = false
}
}
return Promise.reject(error)
}
)

export default api