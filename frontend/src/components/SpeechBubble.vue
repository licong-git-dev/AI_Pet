<script setup lang="ts">
import { computed } from 'vue'

const props = defineProps<{ text: string; emotion?: string; visible: boolean }>()

const tone = computed(() => {
  switch (props.emotion) {
    case 'happy':
    case 'loving':
    case 'proud':
      return 'pos'
    case 'sad':
    case 'lonely':
    case 'anxious':
    case 'worried':
      return 'neg'
    case 'angry':
      return 'angry'
    default:
      return 'neutral'
  }
})
</script>

<template>
  <transition name="bubble">
    <div v-if="visible && text" class="bubble" :class="`tone-${tone}`">
      <p>{{ text }}</p>
      <span class="tail" />
    </div>
  </transition>
</template>

<style lang="scss" scoped>
.bubble {
  position: relative;
  max-width: 320px;
  padding: 16px 20px;
  border-radius: 22px;
  font-size: 15px;
  line-height: 1.55;
  background: #ffffff;
  color: #2b2b2b;
  box-shadow: 0 12px 32px rgba(120, 78, 16, 0.18);
  white-space: pre-wrap;
  word-break: break-word;

  &.tone-pos { background: linear-gradient(160deg, #fff7d6, #ffe6c2); }
  &.tone-neg { background: linear-gradient(160deg, #e6efff, #ddeaff); }
  &.tone-angry { background: linear-gradient(160deg, #ffd9d9, #ffb1b1); }
}
.tail {
  position: absolute;
  bottom: -8px;
  left: 28px;
  width: 18px;
  height: 18px;
  background: inherit;
  transform: rotate(45deg);
  border-radius: 4px;
  box-shadow: 6px 6px 12px rgba(120, 78, 16, 0.08);
}
.bubble-enter-active, .bubble-leave-active {
  transition: opacity 0.25s ease, transform 0.25s ease;
}
.bubble-enter-from { opacity: 0; transform: translateY(8px) scale(0.96); }
.bubble-leave-to { opacity: 0; transform: translateY(-4px) scale(0.98); }
</style>
