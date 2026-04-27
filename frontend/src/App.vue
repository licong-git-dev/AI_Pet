<script setup lang="ts">
import { RouterView } from 'vue-router'
</script>

<template>
  <div id="petpal-shell">
    <RouterView v-slot="{ Component }">
      <transition name="fade" mode="out-in">
        <component :is="Component" />
      </transition>
    </RouterView>
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
