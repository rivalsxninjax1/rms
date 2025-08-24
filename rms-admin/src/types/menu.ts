import type { ID, UUID } from './common'

export interface MenuCategory {
id: ID
name: string
description?: string
}

export interface MenuItem {
id: ID
name: string
description?: string
price: string
category: ID | MenuCategory
}