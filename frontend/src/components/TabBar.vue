<script setup lang="ts">
import { useRoute, RouterLink } from 'vue-router'

const route = useRoute()

const tabs = [
  { to: '/feed',   label: '社区',     icon: '🐾' },
  { to: '/room',   label: '分身',     icon: '✨' },
  { to: '/memory', label: '记忆花园', icon: '🌳' },
  { to: '/wrapped', label: '月报',    icon: '📜' },
  { to: '/pets',   label: '宠物',     icon: '🐱' },
]
function active(to: string): boolean {
  return route.path === to || (to !== '/' && route.path.startsWith(to))
}
</script>

<template>
  <nav class="tabbar">
    <RouterLink v-for="t in tabs" :key="t.to" :to="t.to"
                :class="['tab', { on: active(t.to) }]">
      <span class="ic">{{ t.icon }}</span>
      <span class="lb">{{ t.label }}</span>
    </RouterLink>
  </nav>
</template>

<style lang="scss" scoped>
.tabbar {
  position: fixed;
  bottom: 0; left: 0; right: 0;
  display: flex;
  background: rgba(255,255,255,0.92);
  backdrop-filter: blur(12px);
  border-top: 1px solid rgba(120,78,16,0.1);
  padding: 6px 4px calc(env(safe-area-inset-bottom) + 4px);
  z-index: 100;
}
.tab {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 2px;
  padding: 6px 2px;
  font-size: 11px;
  color: #8a7a6a;
  text-decoration: none;
  transition: color 0.15s ease;
  &:hover { color: #ff7b1c; }
  &.on { color: #ff7b1c; }
  .ic { font-size: 22px; line-height: 1; }
}
</style>
