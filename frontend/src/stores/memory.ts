import { defineStore } from 'pinia'
import { api } from '@/services/api'

export type MemoryType = 'episodic' | 'semantic' | 'preference' | 'event'
export type MemoryEmotion =
  | 'happy' | 'loving' | 'proud' | 'neutral'
  | 'sad' | 'anxious' | 'worried' | 'lonely' | 'angry'

export interface PetMemory {
  id: number
  pet_avatar_id: number
  memory_type: MemoryType
  content: string
  summary?: string | null
  importance: number
  emotion?: MemoryEmotion | null
  emotion_intensity?: number | null
  source: string
  happened_at?: string | null
  is_pinned?: boolean
  is_archived?: boolean
  recall_count?: number
  effective_strength?: number
  created_at?: string | null
}

export interface MemoryGardenStats {
  total: number
  by_type: Record<string, number>
  by_emotion: Record<string, number>
  pinned_count: number
  archived_count: number
  oldest_memory_at?: string | null
  newest_memory_at?: string | null
  top_themes?: string[]
}

export interface CreateMemoryPayload {
  pet_avatar_id: number
  memory_type?: MemoryType
  content: string
  summary?: string
  importance?: number
  emotion?: MemoryEmotion
  emotion_intensity?: number
  happened_at?: string
}

export const useMemoryStore = defineStore('memory', {
  state: () => ({
    list: [] as PetMemory[],
    page: 1,
    pageSize: 20,
    total: 0,
    loading: false,
    stats: null as MemoryGardenStats | null,
    digests: [] as Array<Record<string, any>>,
  }),
  actions: {
    async fetchList(params: {
      avatar_id: number
      memory_type?: MemoryType
      emotion?: MemoryEmotion
      include_archived?: boolean
      reset?: boolean
    }) {
      if (this.loading) return
      if (params.reset) { this.list = []; this.page = 1; this.total = 0 }
      this.loading = true
      try {
        const r = await api.get('/memory/list', {
          params: {
            avatar_id: params.avatar_id,
            memory_type: params.memory_type,
            emotion: params.emotion,
            include_archived: params.include_archived ?? false,
            page: this.page,
            page_size: this.pageSize,
          },
        })
        const items = (r.data?.data || []) as PetMemory[]
        if (params.reset) this.list = items
        else this.list.push(...items)
        const pageInfo = r.data?.page_info
        if (pageInfo) this.total = pageInfo.total ?? 0
      } finally {
        this.loading = false
      }
    },

    async fetchStats(avatar_id: number) {
      const r = await api.get(`/memory/garden/${avatar_id}`)
      this.stats = r.data?.data
    },

    async fetchDigests(avatar_id: number) {
      const r = await api.get(`/memory/digest/${avatar_id}`)
      this.digests = r.data?.data || []
    },

    async create(payload: CreateMemoryPayload) {
      const r = await api.post('/memory', payload)
      const m = r.data?.data as PetMemory
      if (m) this.list.unshift(m)
      return m
    },

    async update(id: number, patch: Partial<PetMemory>) {
      const r = await api.patch(`/memory/${id}`, patch)
      const updated = r.data?.data as PetMemory
      const i = this.list.findIndex((m) => m.id === id)
      if (i >= 0 && updated) this.list[i] = updated
      return updated
    },

    async togglePin(id: number) {
      const r = await api.post(`/memory/${id}/pin`)
      const data = r.data?.data
      const m = this.list.find((x) => x.id === id)
      if (m && data) m.is_pinned = data.is_pinned
      return data
    },

    async remove(id: number) {
      await api.delete(`/memory/${id}`)
      this.list = this.list.filter((m) => m.id !== id)
    },
  },
})
