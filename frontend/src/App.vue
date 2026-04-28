<script setup lang="ts">
import { computed } from 'vue'
import { RouterView, useRoute } from 'vue-router'
import TabBar from '@/components/TabBar.vue'

const route = useRoute()
const showTabBar = computed(() => !!route.meta.tab)
</script>

<template>
  <div id="petpal-shell">
    <RouterView v-slot="{ Component }">
      <transition name="fade" mode="out-in">
        <component :is="Component" />
      </transition>
    </RouterView>
    <TabBar v-if="showTabBar" />
  </div>
</template>

<style lang="scss">
#petpal-shell {
  min-height: 100vh;
  background: linear-gradient(160deg, #fef5e7 0%, #ffe9d6 50%, #f6d6f0 100%);
  color: #2b2b2b;
}

.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.25s ease;
}
.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}
</style>
