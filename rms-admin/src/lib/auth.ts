import { create } from 'zustand'
import type { TokenPair } from '../types/auth'

interface AuthState {
accessToken: string | null
refreshToken: string | null
setTokens: (t: TokenPair) => void
clear: () => void
}

const STORAGE_KEYS = {
access: 'accessToken',
refresh: 'refreshToken',
}

export const useAuthStore = create<AuthState>((set) => ({
accessToken: localStorage.getItem(STORAGE_KEYS.access),
refreshToken: localStorage.getItem(STORAGE_KEYS.refresh),
setTokens: ({ access, refresh }) => {
localStorage.setItem(STORAGE_KEYS.access, access)
localStorage.setItem(STORAGE_KEYS.refresh, refresh)
set({ accessToken: access, refreshToken: refresh })
},
clear: () => {
localStorage.removeItem(STORAGE_KEYS.access)
localStorage.removeItem(STORAGE_KEYS.refresh)
set({ accessToken: null, refreshToken: null })
},
}))