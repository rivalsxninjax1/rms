import type { UUID, ID } from './common'

export type ServiceType = 'DINE_IN' | 'TAKEAWAY' | 'DELIVERY'

export interface OrderItemInput {
  menu_item: ID
  name: string
  qty: number
  unit_price: number
  total: number
}

export interface PlaceOrderInput {
  organization?: ID | null
  location?: ID | null
  service_type: ServiceType
  items: OrderItemInput[]
}
