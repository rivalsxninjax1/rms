import { Link, NavLink, Outlet } from 'react-router-dom'
import { useAuthStore } from '../lib/auth'

const nav = [
{ to: '/', label: 'Dashboard' },
{ to: '/menu', label: 'Menu' },
{ to: '/orders', label: 'Orders' },
{ to: '/inventory', label: 'Inventory' },
{ to: '/reservations', label: 'Reservations' },
{ to: '/reports', label: 'Reports' },
{ to: '/settings', label: 'Settings' },
]

export default function Layout() {
const clear = useAuthStore((s) => s.clear)
return (
<div className="min-h-screen grid grid-cols-[240px_1fr] grid-rows-[56px_1fr]">
<header className="col-span-2 h-14 border-b flex items-center px-4 justify-between">
<Link to="/" className="font-semibold">RMS Admin</Link>
<button
className="text-sm px-3 py-1 border rounded-md hover:bg-gray-50"
onClick={clear}
>Sign out</button>
</header>

<aside className="border-r p-3">
<nav className="space-y-1">
{nav.map((n) => (
<NavLink
key={n.to}
to={n.to}
end={n.to === '/'}
className={({ isActive }) =>
`block rounded-md px-3 py-2 text-sm hover:bg-gray-100 ${
isActive ? 'bg-gray-100 font-medium' : ''
}`
}
>
{n.label}
</NavLink>
))}
</nav>
</aside>

<main className="p-6">
<Outlet />
</main>
</div>
)
}