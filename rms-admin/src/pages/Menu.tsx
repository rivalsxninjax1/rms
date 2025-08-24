import { useQuery } from '@tanstack/react-query'
import api from '../lib/api'
import type { MenuCategory, MenuItem } from '../types/menu'

export default function Menu() {
const categories = useQuery({
queryKey: ['menu', 'categories'],
queryFn: async () => (await api.get<MenuCategory[]>('/menu/categories/')).data,
})

const items = useQuery({
queryKey: ['menu', 'items'],
queryFn: async () => (await api.get<MenuItem[]>('/menu/items/')).data,
})

return (
<div className="space-y-6">
<h2 className="text-lg font-semibold">Menu</h2>

<section>
<h3 className="font-medium mb-2">Categories</h3>
{categories.isLoading ? (
<p>Loading…</p>
) : (
<ul className="list-disc pl-5">
{categories.data?.map((c) => (
<li key={c.id}>
<span className="font-medium">{c.name}</span>
{c.description ? <span className="text-gray-600"> — {c.description}</span> : null}
</li>
))}
</ul>
)}
</section>

<section>
<h3 className="font-medium mb-2">Items</h3>
{items.isLoading ? (
<p>Loading…</p>
) : (
<ul className="divide-y border rounded-md">
{items.data?.map((i) => (
<li key={i.id} className="p-3 flex items-center justify-between">
<div>
<div className="font-medium">{i.name}</div>
{typeof i.category === 'object' ? (
<div className="text-xs text-gray-600">{i.category.name}</div>
) : null}
</div>
<div className="text-sm">Rs. {i.price}</div>
</li>
))}
</ul>
)}
</section>
</div>
)
}