import { useState } from 'react'
import api from '../lib/api'
import type { PlaceOrderInput } from '../types/orders'

export default function Orders() {
const [loading, setLoading] = useState(false)
const [response, setResponse] = useState<any>(null)
const [error, setError] = useState<string | null>(null)

async function placeSampleOrder() {
setLoading(true)
setError(null)
setResponse(null)
const payload: PlaceOrderInput = {
// organization: '00000000-0000-0000-0000-000000000000',
// location: '00000000-0000-0000-0000-000000000000',
service_type: 'DINE_IN',
items: [
{
menu_item: 1,
name: 'Margherita',
qty: 1,
unit_price: 9.99,
total: 9.99,
},
],
}
try {
const { data } = await api.post('/orders/', payload)
setResponse(data)
} catch (e: any) {
setError(e?.response?.data?.detail ?? 'Failed to place order')
} finally {
setLoading(false)
}
}

return (
<div className="space-y-4">
<h2 className="text-lg font-semibold">Orders</h2>
<button
onClick={placeSampleOrder}
className="border rounded-md px-3 py-2 hover:bg-gray-50"
disabled={loading}
>
{loading ? 'Placing…' : 'Place sample order'}
</button>
{error && <pre className="text-red-600 text-sm">{error}</pre>}
{response && (
<pre className="text-xs bg-gray-50 p-3 rounded-md overflow-auto">
{JSON.stringify(response, null, 2)}
</pre>
)}
</div>
)
}