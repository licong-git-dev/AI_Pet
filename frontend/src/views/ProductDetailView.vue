<script setup lang="ts">
import { onMounted, computed, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import AppHeader from '@/components/AppHeader.vue'
import Loading from '@/components/Loading.vue'
import { useCartStore } from '@/stores/cart'

const route = useRoute()
const router = useRouter()
const cart = useCartStore()
const id = computed(() => Number(route.params.id))
const qty = ref(1)
const toastVisible = ref(false)

onMounted(() => cart.fetchProduct(id.value))
const p = computed(() => cart.detail)

function addToCart() {
  if (!p.value) return
  cart.add(p.value, qty.value)
  toastVisible.value = true
  setTimeout(() => { toastVisible.value = false }, 1500)
}

function buyNow() {
  if (!p.value) return
  cart.add(p.value, qty.value)
  router.push({ name: 'cart' })
}
</script>

<template>
  <div class="prod-detail">
    <AppHeader title="商品详情" :back="true" />

    <Loading v-if="cart.loading || !p" />

    <template v-else>
      <div class="hero">
        <img v-if="p.cover_image" :src="p.cover_image" />
        <span v-else>📦</span>
      </div>

      <section class="card">
        <h2>{{ p.name }}</h2>
        <p class="price">¥{{ p.price.toFixed(2) }}</p>
        <p class="muted small">库存：{{ p.stock ?? '充足' }} · 销量：{{ p.sales_count ?? 0 }}</p>
      </section>

      <section v-if="p.description" class="card">
        <h3>商品介绍</h3>
        <p class="desc">{{ p.description }}</p>
      </section>

      <section class="qty card">
        <span>数量</span>
        <div class="ctrl">
          <button @click="qty = Math.max(1, qty-1)">−</button>
          <span>{{ qty }}</span>
          <button @click="qty++">＋</button>
        </div>
      </section>

      <div class="actions">
        <button class="btn-secondary btn" @click="addToCart">加入购物车</button>
        <button class="btn" @click="buyNow">立即购买</button>
      </div>

      <transition name="fade">
        <div v-if="toastVisible" class="toast">已加入购物车 🛒</div>
      </transition>
    </template>
  </div>
</template>

<style lang="scss" scoped>
.prod-detail { padding-bottom: 100px; }
.hero {
  width: 100%;
  aspect-ratio: 1/1;
  background: linear-gradient(160deg, #fff7d6, #ffe6c2);
  display: grid; place-items: center;
  font-size: 80px;
  img { width: 100%; height: 100%; object-fit: cover; }
}
.card { margin: 12px 16px; }
h2 { font-size: 18px; margin-bottom: 6px; }
.price { color: #ff5f1c; font-size: 22px; font-weight: 700; }
.small { font-size: 12px; }
.desc { font-size: 14px; line-height: 1.7; white-space: pre-wrap; color: #4a3a2a; }
.qty {
  display: flex; align-items: center; justify-content: space-between;
  .ctrl {
    display: flex; align-items: center; gap: 14px;
    button {
      width: 30px; height: 30px;
      border-radius: 8px; border: 1px solid rgba(120,78,16,0.18);
      background: rgba(255,255,255,0.85); font-size: 18px;
    }
  }
}
.actions {
  position: fixed; bottom: 0; left: 0; right: 0;
  padding: 12px 16px calc(env(safe-area-inset-bottom) + 12px);
  display: flex; gap: 10px;
  background: rgba(255,255,255,0.92);
  backdrop-filter: blur(12px);
  border-top: 1px solid rgba(120,78,16,0.1);
  .btn { flex: 1; }
}
.toast {
  position: fixed; top: 30%; left: 50%; transform: translateX(-50%);
  background: rgba(0,0,0,0.7); color: #fff;
  padding: 10px 20px; border-radius: 999px;
  z-index: 200;
}
.fade-enter-active, .fade-leave-active { transition: opacity 0.25s ease; }
.fade-enter-from, .fade-leave-to { opacity: 0; }
</style>
