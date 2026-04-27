import { createRouter, createWebHistory } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', redirect: '/room' },
    { path: '/login', name: 'login', component: () => import('@/views/LoginView.vue') },
    {
      path: '/room',
      name: 'room',
      component: () => import('@/views/AvatarRoomView.vue'),
      meta: { requiresAuth: true },
    },
    {
      path: '/wrapped',
      name: 'wrapped',
      component: () => import('@/views/WrappedView.vue'),
      meta: { requiresAuth: true },
    },
  ],
})

router.beforeEach((to) => {
  if (to.meta.requiresAuth) {
    const auth = useAuthStore()
    if (!auth.isAuthed) return { name: 'login', query: { next: to.fullPath } }
  }
  return true
})

export default router
