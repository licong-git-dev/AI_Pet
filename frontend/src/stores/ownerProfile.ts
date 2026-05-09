import { defineStore } from 'pinia'
import { api } from '@/services/api'

export interface OwnerProfile {
  user_id: number
  daily_rhythm?: Record<string, any> | null
  emotional_baseline?: Record<string, any> | null
  relationships?: Record<string, any> | null
  communication?: Record<string, any> | null
  pet_attachment?: Record<string, any> | null
  confidence_score: number
  signal_count: number
  last_built_at?: string | null
  is_visible_to_avatar: boolean
  is_learning_paused: boolean
  pause_until?: string | null
}

export const useOwnerProfileStore = defineStore('ownerProfile', {
  state: () => ({
    profile: null as OwnerProfile | null,
    signals: [] as Array<Record<string, any>>,
    loading: false,
  }),
  getters: {
    confidencePercent: (s) => Math.round((s.profile?.confidence_score ?? 0) * 100),
  },
  actions: {
    async fetchMine() {
      this.loading = true
      try {
        const r = await api.get('/owner-profile/me')
        this.profile = r.data?.data
      } finally {
        this.loading = false
      }
    },

    async update(patch: Partial<OwnerProfile>) {
      const r = await api.patch('/owner-profile/me', patch)
      this.profile = r.data?.data
      return this.profile
    },

    async rebuild() {
      this.loading = true
      try {
        const r = await api.post('/owner-profile/rebuild')
        this.profile = r.data?.data
      } finally {
        this.loading = false
      }
    },

    async pause(days: number) {
      const r = await api.post('/owner-profile/pause', { days })
      if (this.profile) {
        this.profile.is_learning_paused = !!r.data?.data?.is_learning_paused
        this.profile.pause_until = r.data?.data?.pause_until ?? null
      }
    },

    async resume() {
      const r = await api.post('/owner-profile/resume')
      if (this.profile) {
        this.profile.is_learning_paused = !!r.data?.data?.is_learning_paused
        this.profile.pause_until = null
      }
    },

    async fetchSignals() {
      const r = await api.get('/owner-profile/signals', { params: { page_size: 50 } })
      this.signals = r.data?.data || []
    },

    async wipe() {
      await api.delete('/owner-profile/me')
      this.profile = null
      this.signals = []
    },
  },
})
