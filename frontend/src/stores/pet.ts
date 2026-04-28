import { defineStore } from 'pinia'
import { api } from '@/services/api'

export interface Pet {
  id: number
  name: string
  pet_type?: string
  breed_id?: number | null
  breed_name?: string | null
  gender?: string | null
  age?: number | null
  age_months?: number | null
  weight?: number | null
  health_status?: string | null
  avatar?: string | null
  personality?: string[] | null
  created_at?: string | null
}

export const usePetStore = defineStore('pet', {
  state: () => ({
    list: [] as Pet[],
    detail: null as Pet | null,
    loading: false as boolean,
  }),
  actions: {
    async fetchList() {
      this.loading = true
      try {
        const r = await api.get('/pets')
        this.list = (r.data?.data?.items || r.data?.data || []) as Pet[]
      } finally {
        this.loading = false
      }
    },
    async fetchDetail(id: number) {
      this.loading = true
      try {
        const r = await api.get(`/pets/${id}`)
        this.detail = r.data?.data
      } finally {
        this.loading = false
      }
    },
    async createPet(payload: Partial<Pet>) {
      const r = await api.post('/pets', payload)
      const created = r.data?.data
      if (created) this.list.unshift(created)
      return created
    },
  },
})
