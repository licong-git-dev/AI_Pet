<script setup lang="ts">
import { computed } from 'vue'

const props = defineProps<{ emotion?: string; intensity?: number }>()

const palette = computed(() => {
  switch (props.emotion) {
    case 'happy':     return ['#ffd166', '#ffb454']
    case 'loving':    return ['#ff9bb6', '#ff5d8f']
    case 'sad':       return ['#9bb6ff', '#5d8fff']
    case 'angry':     return ['#ff7c7c', '#ff3838']
    case 'sleepy':    return ['#cdb6ff', '#8e7bff']
    case 'curious':   return ['#a3f0c2', '#3eccaa']
    case 'proud':     return ['#ffe49b', '#ffae3e']
    case 'surprised': return ['#fff', '#ffe6e6']
    case 'confused':  return ['#dcd0c8', '#a89483']
    default:          return ['#ffe1c2', '#ffc69b']
  }
})
const radius = computed(() => 220 + 80 * (props.intensity ?? 0.5))
const opacity = computed(() => 0.45 + 0.4 * (props.intensity ?? 0.5))
</script>

<template>
  <div
    class="aura"
    :style="{
      width: radius + 'px',
      height: radius + 'px',
      opacity: opacity,
      background: `radial-gradient(closest-side, ${palette[0]} 0%, ${palette[1]}80 60%, transparent 100%)`,
    }"
  />
</template>

<style lang="scss" scoped>
.aura {
  position: absolute;
  border-radius: 50%;
  filter: blur(14px);
  pointer-events: none;
  animation: pulse 3.5s ease-in-out infinite;
  transition: background 0.6s ease, width 0.4s ease, height 0.4s ease, opacity 0.4s ease;
}
@keyframes pulse {
  0%, 100% { transform: scale(1); }
  50%      { transform: scale(1.06); }
}
</style>
