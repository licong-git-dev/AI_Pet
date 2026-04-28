import { defineStore } from 'pinia'
import { api } from '@/services/api'

export interface Product {
  id: number
  name: string
  price: number
  cover_image?: string
  description?: string
  category_id?: number
  stock?: number
  sales_count?: number
}

export interface CartItem {
  product: Product
  quantity: number
}

const LS_KEY = 'petpal_cart'

function loadLocal(): CartItem[] {
  try { return JSON.parse(localStorage.getItem(LS_KEY) || '[]') } catch { return [] }
}
function saveLocal(items: CartItem[]) {
  localStorage.setItem(LS_KEY, JSON.stringify(items))
}

export const useCartStore = defineStore('cart', {
  state: () => ({
    products: [] as Product[],
    detail: null as Product | null,
    items: loadLocal() as CartItem[],
    loading: false,
  }),
  getters: {
    totalQty: (s) => s.items.reduce((n, it) => n + it.quantity, 0),
    totalPrice: (s) => s.items.reduce((n, it) => n + it.quantity * (it.product.price || 0), 0),
  },
  actions: {
    async fetchProducts() {
      this.loading = true
      try {
        const r = await api.get('/shop/products')
        this.products = (r.data?.data?.items || r.data?.data || []) as Product[]
      } finally {
        this.loading = false
      }
    },
    async fetchProduct(id: number) {
      this.loading = true
      try {
        const r = await api.get(`/shop/products/${id}`)
        this.detail = r.data?.data
      } finally {
        this.loading = false
      }
    },
    add(p: Product, q = 1) {
      const exist = this.items.find((it) => it.product.id === p.id)
      if (exist) exist.quantity += q
      else this.items.push({ product: p, quantity: q })
      saveLocal(this.items)
    },
    inc(id: number) { this.items.forEach((it) => it.product.id === id && it.quantity++); saveLocal(this.items) },
    dec(id: number) {
      this.items = this.items
        .map((it) => it.product.id === id ? { ...it, quantity: it.quantity - 1 } : it)
        .filter((it) => it.quantity > 0)
      saveLocal(this.items)
    },
    remove(id: number) {
      this.items = this.items.filter((it) => it.product.id !== id)
      saveLocal(this.items)
    },
    clear() { this.items = []; saveLocal(this.items) },
  },
})
