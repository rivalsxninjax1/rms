import { useMemo } from 'react'
import { useAuthStore } from '../lib/auth'

export function useAuth() {
const access = useAuthStore((s) => s.accessToken)
const isAuthenticated = useMemo(() => Boolean(access), [access])
return { isAuthenticated }
}