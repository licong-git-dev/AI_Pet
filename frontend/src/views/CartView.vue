<script setup lang="ts">
import { computed } from 'vue'
import { useRouter } from 'vue-router'
import AppHeader from '@/components/AppHeader.vue'
import EmptyState from '@/components/EmptyState.vue'
import { useCartStore } from '@/stores/cart'

const router = useRouter()
const cart = useCartStore()
const items = computed(() => cart.items)

function checkout() {
  alert(`已提交订单（demo）\n共 ${cart.totalQty} 件 · ¥${cart.totalPrice.toFixed(2)}`)
  cart.clear()
  router.replace({ name: 'shop' })
}
</script>

<template>
  <div class="cart">
    <AppHeader title="购物车" :back="true" />

    <EmptyState v-if="!items.length" icon="🛒" title="购物车空空"
                hint="去商城逛逛看看，给小毛球带点好东西"
                action="去商城" @action="router.push({ name: 'shop' })" />

    <template v-else>
      <ul class="list">
        <li v-for="it in items" :key="it.product.id" class="card item">
          <div class="cover">
            <img v-if="it.product.cover_image" :src="it.product.cover_image" />
            <span v-else>📦</span>
          </div>
          <div class="meta">
            <h4>{{ it.product.name }}</h4>
            <p class="price">¥{{ it.product.price.toFixed(2) }}</p>
            <div class="qctrl">
              <button @click="cart.dec(it.product.id)">−</button>
              <span>{{ it.quantity }}</span>
              <button @click="cart.inc(it.product.id)">＋</button>
              <span class="sp"></span>
              <button class="del" @click="cart.remove(it.product.id)">删除</button>
            </div>
          </div>
        </li>
      </ul>

      <footer class="bar">
        <div>
          <p class="muted small">合计</p>
          <p class="total">¥{{ cart.totalPrice.toFixed(2) }}</p>
        </div>
        <button class="btn" @click="checkout">结算 ({{ cart.totalQty }})</button>
      </footer>
    </template>
  </div>
</template>

<style lang="scss" scoped>
.cart { padding-bottom: 100px; }
.list {
  list-style: none; margin: 0; padding: 16px;
  display: flex; flex-direction: column; gap: 10px;
}
.item {
  display: flex; gap: 12px;
  .cover {
    width: 70px; height: 70px;
    border-radius: 12px;
    background: linear-gradient(160deg, #fff7d6, #ffe6c2);
    display: grid; place-items: center;
    overflow: hidden; font-size: 26px;
    img { width: 100%; height: 100%; object-fit: cover; }
  }
  .meta { flex: 1; }
  h4 { font-size: 14px; }
  .price { color: #ff5f1c; font-weight: 700; }
  .qctrl {
    display: flex; align-items: center; gap: 8px;
    margin-top: 6px;
    button {
      width: 26px; height: 26px;
      border-radius: 6px; border: 1px solid rgba(120,78,16,0.18);
      background: rgba(255,255,255,0.85);
    }
    .sp { flex: 1; }
    .del {
      width: auto; padding: 0 8px; font-size: 12px;
      color: #d83a3a; border-color: rgba(216,58,58,0.3);
    }
  }
}
.bar {
  position: fixed; bottom: 0; left: 0; right: 0;
  padding: 10px 16px calc(env(safe-area-inset-bottom) + 10px);
  display: flex; align-items: center; justify-content: space-between;
  background: rgba(255,255,255,0.92);
  backdrop-filter: blur(12px);
  border-top: 1px solid rgba(120,78,16,0.1);
  .total { color: #ff5f1c; font-weight: 700; font-size: 18px; }
  .small { font-size: 12px; }
  .btn { padding: 10px 22px; }
}
</style>
