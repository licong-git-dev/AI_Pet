<script setup lang="ts">
defineProps<{ icon?: string; title?: string; hint?: string; action?: string }>()
defineEmits<{ (e: 'action'): void }>()
</script>

<template>
  <div class="empty">
    <div class="ic">{{ icon || '🐾' }}</div>
    <h3 class="title">{{ title || '这里还空空的' }}</h3>
    <p v-if="hint" class="hint">{{ hint }}</p>
    <button v-if="action" class="btn btn-secondary" @click="$emit('action')">{{ action }}</button>
  </div>
</template>

<style lang="scss" scoped>
.empty {
  padding: 48px 24px;
  text-align: center;
  display: flex; flex-direction: column; align-items: center; gap: 8px;
}
.ic { font-size: 56px; line-height: 1; }
.title { font-size: 16px; color: #6b5742; }
.hint { font-size: 13px; color: #8a7a6a; max-width: 280px; line-height: 1.6; }
</style>
