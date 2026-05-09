import { createRouter, createWebHistory } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', redirect: '/feed' },
    { path: '/login', name: 'login', component: () => import('@/views/LoginView.vue') },

    // 分身房间 + 月报
    { path: '/room',    name: 'room',    component: () => import('@/views/AvatarRoomView.vue'), meta: { requiresAuth: true, tab: true } },
    { path: '/wrapped', name: 'wrapped', component: () => import('@/views/WrappedView.vue'),    meta: { requiresAuth: true, tab: true } },

    // 记忆花园 + 主人画像
    { path: '/memory',  name: 'memory',  component: () => import('@/views/MemoryGardenView.vue'), meta: { requiresAuth: true, tab: true } },
    { path: '/me',      name: 'me',      component: () => import('@/views/OwnerProfileView.vue'),  meta: { requiresAuth: true } },

    // 宠物
    { path: '/pets',          name: 'pets',         component: () => import('@/views/PetListView.vue'),   meta: { requiresAuth: true, tab: true } },
    { path: '/pets/new',      name: 'pet-create',   component: () => import('@/views/PetCreateView.vue'), meta: { requiresAuth: true } },
    { path: '/pets/:id',      name: 'pet-detail',   component: () => import('@/views/PetDetailView.vue'), meta: { requiresAuth: true } },

    // 社区
    { path: '/feed',          name: 'feed',         component: () => import('@/views/FeedView.vue'),         meta: { requiresAuth: true, tab: true } },
    { path: '/posts/new',     name: 'post-create',  component: () => import('@/views/PostCreateView.vue'),   meta: { requiresAuth: true } },
    { path: '/posts/:id',     name: 'post-detail',  component: () => import('@/views/PostDetailView.vue'),   meta: { requiresAuth: true } },

    // 商城
    { path: '/shop',          name: 'shop',         component: () => import('@/views/ShopListView.vue'),     meta: { requiresAuth: true, tab: true } },
    { path: '/shop/:id',      name: 'product-detail', component: () => import('@/views/ProductDetailView.vue'), meta: { requiresAuth: true } },
    { path: '/cart',          name: 'cart',         component: () => import('@/views/CartView.vue'),         meta: { requiresAuth: true } },
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
