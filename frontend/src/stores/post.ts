import { defineStore } from 'pinia'
import { api } from '@/services/api'

export interface Post {
  id: number
  user_id?: number
  user_name?: string
  user_avatar?: string
  pet_id?: number
  content?: string
  images?: string[] | null
  topic?: string | null
  like_count?: number
  comment_count?: number
  is_liked?: boolean
  created_at?: string
}

export const usePostStore = defineStore('post', {
  state: () => ({
    feed: [] as Post[],
    detail: null as Post | null,
    loading: false,
    page: 1,
    hasMore: true,
  }),
  actions: {
    async fetchFeed(reset = false) {
      if (this.loading) return
      if (reset) { this.feed = []; this.page = 1; this.hasMore = true }
      if (!this.hasMore) return
      this.loading = true
      try {
        const r = await api.get('/posts', { params: { page: this.page, page_size: 20 } })
        const items = (r.data?.data?.items || r.data?.data || []) as Post[]
        this.feed.push(...items)
        const total = r.data?.page_info?.total ?? r.data?.data?.total
        if (typeof total === 'number') {
          this.hasMore = this.feed.length < total
        } else if (items.length === 0) {
          this.hasMore = false
        }
        this.page++
      } finally {
        this.loading = false
      }
    },
    async fetchDetail(id: number) {
      this.loading = true
      try {
        const r = await api.get(`/posts/${id}`)
        this.detail = r.data?.data
      } finally {
        this.loading = false
      }
    },
    async createPost(payload: { content: string; images?: string[]; pet_id?: number }) {
      const r = await api.post('/posts', payload)
      const created = r.data?.data
      if (created) this.feed.unshift(created)
      return created
    },
    async toggleLike(post: Post) {
      try {
        if (post.is_liked) {
          await api.delete(`/posts/${post.id}/like`)
          post.is_liked = false
          post.like_count = Math.max(0, (post.like_count || 1) - 1)
        } else {
          await api.post(`/posts/${post.id}/like`)
          post.is_liked = true
          post.like_count = (post.like_count || 0) + 1
        }
      } catch { /* swallow */ }
    },
  },
})
