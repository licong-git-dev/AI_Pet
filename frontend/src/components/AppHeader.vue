<script setup lang="ts">
import { useRouter } from 'vue-router'
defineProps<{ title?: string; back?: boolean; right?: string }>()
const router = useRouter()
defineEmits<{ (e: 'right'): void }>()
</script>

<template>
  <header class="header">
    <button v-if="back" class="back" @click="router.back()" aria-label="返回">
      ‹
    </button>
    <h1 class="title">{{ title }}</h1>
    <button v-if="right" class="right" @click="$emit('right')">{{ right }}</button>
    <span v-else class="right placeholder" />
  </header>
</template>

<style lang="scss" scoped>
.header {
  position: sticky; top: 0; z-index: 50;
  display: flex; align-items: center; justify-content: space-between;
  padding: 12px 16px;
  background: rgba(255,255,255,0.85);
  backdrop-filter: blur(10px);
  border-bottom: 1px solid rgba(120,78,16,0.08);
}
.title { font-size: 16px; font-weight: 600; letter-spacing: 0.04em; }
.back, .right {
  background: none; border: none;
  font-size: 22px;
  color: #6b5742;
  width: 28px; text-align: center;
}
.right { font-size: 14px; color: #ff7b1c; font-weight: 600; min-width: 28px; }
.placeholder { display: inline-block; }
</style>
