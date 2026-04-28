<script setup lang="ts">
defineProps<{ text?: string }>()
</script>

<template>
  <div class="loading">
    <div class="paw">🐾</div>
    <p>{{ text || '加载中…' }}</p>
  </div>
</template>

<style lang="scss" scoped>
.loading {
  padding: 60px 16px;
  text-align: center;
  display: flex; flex-direction: column; align-items: center; gap: 10px;
  color: #8a7a6a;
  .paw { font-size: 32px; animation: bounce 1.2s ease-in-out infinite; }
}
@keyframes bounce {
  0%, 100% { transform: translateY(0); }
  50% { transform: translateY(-6px); }
}
</style>
