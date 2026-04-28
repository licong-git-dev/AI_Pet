<script setup lang="ts">
import { onMounted, computed } from 'vue'
import { useRouter } from 'vue-router'
import AppHeader from '@/components/AppHeader.vue'
import EmptyState from '@/components/EmptyState.vue'
import Loading from '@/components/Loading.vue'
import { useCartStore } from '@/stores/cart'

const router = useRouter()
const cart = useCartStore()
const products = computed(() => cart.products)

onMounted(() => cart.fetchProducts())
</script>

<template>
  <div class="shop">
    <AppHeader title="宠物商城" :right="cart.totalQty ? `购物车 (${cart.totalQty})` : '购物车'"
                @right="router.push({ name: 'cart' })" />

    <Loading v-if="cart.loading && !products.length" />

    <EmptyState v-else-if="!products.length" icon="🛍️" title="商品库还在备货" />

    <ul v-else class="grid">
      <li v-for="p in products" :key="p.id" class="card prod"
          @click="router.push({ name: 'product-detail', params: { id: p.id } })">
        <div class="cover">
          <img v-if="p.cover_image" :src="p.cover_image" />
          <span v-else>📦</span>
        </div>
        <div class="meta">
          <h4>{{ p.name }}</h4>
          <p class="price">¥{{ p.price.toFixed(2) }}</p>
          <p v-if="p.sales_count" class="muted small">已售 {{ p.sales_count }}</p>
        </div>
      </li>
    </ul>
  </div>
</template>

<style lang="scss" scoped>
.shop { padding-bottom: 80px; }
.grid {
  list-style: none; margin: 0; padding: 12px;
  display: grid; grid-template-columns: repeat(2, 1fr); gap: 10px;
}
.prod {
  padding: 8px; cursor: pointer;
  &:active { transform: scale(0.98); }
  .cover {
    width: 100%; aspect-ratio: 1/1;
    background: linear-gradient(160deg, #fff7d6, #ffe6c2);
    border-radius: 14px;
    display: grid; place-items: center;
    overflow: hidden;
    margin-bottom: 8px;
    font-size: 36px;
    img { width: 100%; height: 100%; object-fit: cover; }
  }
  h4 { font-size: 14px; line-height: 1.4; }
  .price { color: #ff5f1c; font-weight: 700; margin-top: 4px; }
  .small { font-size: 11px; }
}
</style>
