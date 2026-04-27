import { defineStore } from 'pinia'

const TOKEN_KEY = 'petpal_token'
const AVATAR_KEY = 'petpal_default_avatar_id'

export const useAuthStore = defineStore('auth', {
  state: () => ({
    token: localStorage.getItem(TOKEN_KEY) || '',
    defaultAvatarId: Number(localStorage.getItem(AVATAR_KEY) || 0) || null as number | null,
  }),
  getters: {
    isAuthed: (s) => !!s.token,
  },
  actions: {
    set(token: string, avatarId?: number | null) {
      this.token = token
      localStorage.setItem(TOKEN_KEY, token)
      if (avatarId) {
        this.defaultAvatarId = avatarId
        localStorage.setItem(AVATAR_KEY, String(avatarId))
      }
    },
    setAvatarId(id: number) {
      this.defaultAvatarId = id
      localStorage.setItem(AVATAR_KEY, String(id))
    },
    clear() {
      this.token = ''
      this.defaultAvatarId = null
      localStorage.removeItem(TOKEN_KEY)
      localStorage.removeItem(AVATAR_KEY)
    },
  },
})
