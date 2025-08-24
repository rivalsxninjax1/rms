import { FormEvent, useState } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
import api from '../lib/api'
import { useAuthStore } from '../lib/auth'
import type { TokenPair } from '../types/auth'

export default function Login() {
const [username, setUsername] = useState('')
const [password, setPassword] = useState('')
const [loading, setLoading] = useState(false)
const [error, setError] = useState<string | null>(null)

const setTokens = useAuthStore((s) => s.setTokens)
const navigate = useNavigate()
const location = useLocation() as any

async function onSubmit(e: FormEvent) {
e.preventDefault()
setLoading(true)
setError(null)
try {
const { data } = await api.post<TokenPair>('/auth/token/', {
username,
password,
})
setTokens(data)
const to = location.state?.from?.pathname || '/'
navigate(to, { replace: true })
} catch (err: any) {
setError(err?.response?.data?.detail ?? 'Login failed')
} finally {
setLoading(false)
}
}

return (
<div className="min-h-screen grid place-items-center p-6">
<form
onSubmit={onSubmit}
className="w-full max-w-sm border rounded-xl p-6 space-y-3"
>
<h1 className="text-xl font-semibold">Sign in</h1>
<label className="block">
<span className="text-sm">Username</span>
<input
className="mt-1 w-full border rounded-md px-3 py-2"
value={username}
onChange={(e) => setUsername(e.target.value)}
autoComplete="username"
/>
</label>
<label className="block">
<span className="text-sm">Password</span>
<input
type="password"
className="mt-1 w-full border rounded-md px-3 py-2"
value={password}
onChange={(e) => setPassword(e.target.value)}
autoComplete="current-password"
/>
</label>
{error && <p className="text-sm text-red-600">{error}</p>}
<button
disabled={loading}
className="w-full mt-2 border rounded-md py-2 hover:bg-gray-50 disabled:opacity-50"
>
{loading ? 'Signing in…' : 'Sign in'}
</button>
</form>
</div>
)
}