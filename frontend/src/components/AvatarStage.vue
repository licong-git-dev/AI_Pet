<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import type { AvatarStateEvent } from '@/types/asp'
import SpeechBubble from './SpeechBubble.vue'
import EmotionAura from './EmotionAura.vue'

const props = defineProps<{
  /** 来自 useAvatarSocket 的最新事件 */
  event: AvatarStateEvent | null
  /** Live2D 模型 URL（可选，无值时用 CSS 兽体兜底）*/
  live2dModelUrl?: string
}>()

// ========== 状态聚合 ==========

const currentEmotion = ref<string>('neutral')
const currentIntensity = ref<number>(0.5)
const currentSpeech = ref<string>('')
const speechVisible = ref(false)
const animationName = ref<string>('')
const isAsleep = ref(false)

let speechTimer: ReturnType<typeof setTimeout> | null = null
let animTimer: ReturnType<typeof setTimeout> | null = null

watch(() => props.event, (e) => {
  if (!e) return
  // 情绪 / 强度 始终跟随事件
  if (e.emotion) currentEmotion.value = e.emotion
  if (typeof e.intensity === 'number') currentIntensity.value = e.intensity

  switch (e.type) {
    case 'speech': {
      currentSpeech.value = e.speech?.text ?? ''
      speechVisible.value = true
      // 1 字 ~ 100ms，min 2.5s，max 12s
      const ttl = e.ttl_ms ?? Math.min(12000, Math.max(2500, currentSpeech.value.length * 110))
      if (speechTimer) clearTimeout(speechTimer)
      speechTimer = setTimeout(() => { speechVisible.value = false }, ttl)
      // 也触发一个 'talk' 动画
      animationName.value = 'talk'
      break
    }
    case 'animation': {
      animationName.value = e.animation?.name ?? ''
      const dur = e.animation?.duration_ms ?? 1600
      if (animTimer) clearTimeout(animTimer)
      animTimer = setTimeout(() => { animationName.value = '' }, dur)
      break
    }
    case 'emotion': /* 已在上面更新 */ break
    case 'sleep': isAsleep.value = true; break
    case 'wake':  isAsleep.value = false; break
    case 'idle':  animationName.value = 'idle'; break
    default: break
  }
})

const eyesClass = computed(() => {
  if (isAsleep.value) return 'eyes-closed'
  if (currentEmotion.value === 'sleepy') return 'eyes-half'
  if (currentEmotion.value === 'angry') return 'eyes-narrow'
  if (currentEmotion.value === 'sad' || currentEmotion.value === 'lonely') return 'eyes-droop'
  if (currentEmotion.value === 'surprised') return 'eyes-wide'
  return 'eyes-normal'
})

const mouthClass = computed(() => {
  if (animationName.value === 'talk') return 'mouth-talk'
  switch (currentEmotion.value) {
    case 'happy':
    case 'proud':
    case 'loving':
      return 'mouth-smile'
    case 'sad':
    case 'lonely':
    case 'anxious':
      return 'mouth-frown'
    case 'angry':
      return 'mouth-angry'
    case 'surprised':
      return 'mouth-O'
    default:
      return 'mouth-neutral'
  }
})

const bodyClass = computed(() => `anim-${animationName.value || 'breath'}`)
</script>

<template>
  <div class="stage">
    <!-- Live2D 预留插槽：传 live2dModelUrl 时由父组件接管 -->
    <div v-if="live2dModelUrl" class="live2d-slot">
      <slot name="live2d" :modelUrl="live2dModelUrl" :event="event">
        <p class="muted center" style="height:100%">
          已传入 Live2D model URL，但未在父组件提供 #live2d 插槽实现
        </p>
      </slot>
    </div>

    <!-- 默认 CSS 兽体 -->
    <div v-else class="creature-wrap">
      <EmotionAura :emotion="currentEmotion" :intensity="currentIntensity" />

      <div class="creature" :class="bodyClass">
        <div class="ear ear-left" />
        <div class="ear ear-right" />
        <div class="head">
          <div class="eye eye-left" :class="eyesClass" />
          <div class="eye eye-right" :class="eyesClass" />
          <div class="cheek cheek-left" />
          <div class="cheek cheek-right" />
          <div class="mouth" :class="mouthClass" />
        </div>
        <div class="paw paw-left" />
        <div class="paw paw-right" />
      </div>
    </div>

    <SpeechBubble
      class="bubble-wrap"
      :text="currentSpeech"
      :emotion="currentEmotion"
      :visible="speechVisible"
    />
  </div>
</template>

<style lang="scss" scoped>
.stage {
  position: relative;
  width: 100%;
  min-height: 420px;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: flex-end;
  padding: 24px 16px 32px;
}

.live2d-slot {
  width: 100%;
  height: 460px;
}

.creature-wrap {
  position: relative;
  width: 280px;
  height: 320px;
  display: flex;
  align-items: center;
  justify-content: center;
}

// ========== 兽体（猫狗通用 chibi） ==========

.creature {
  position: relative;
  width: 220px;
  height: 240px;
  z-index: 2;

  &.anim-breath  { animation: breath 4s ease-in-out infinite; }
  &.anim-talk    { animation: nod 0.6s ease-in-out infinite; }
  &.anim-idle    { animation: breath 6s ease-in-out infinite; }
  &.anim-wag_tail{ animation: wag 0.6s ease-in-out infinite; }
  &.anim-blink   { animation: blink 0.9s ease-in-out 1; }
  &.anim-jump    { animation: jump 0.55s ease-out 1; }
}

.head {
  position: absolute;
  inset: 18px 18px auto 18px;
  height: 180px;
  background: linear-gradient(160deg, #ffd8a8, #ffb066);
  border-radius: 50% 50% 46% 46% / 56% 56% 44% 44%;
  box-shadow: 0 18px 40px rgba(255, 130, 50, 0.25), inset 0 -10px 18px rgba(0,0,0,0.06);
}

.ear { position:absolute; top:0; width:60px; height:80px; background:#ffb066; border-radius:50% 50% 0 0; transform-origin: 50% 100%; }
.ear-left  { left:8px; transform: rotate(-18deg); }
.ear-right { right:8px; transform: rotate(18deg); }

.eye {
  position: absolute; top: 78px;
  width: 22px; height: 26px;
  background: #2c2118; border-radius: 50%;
  transition: height 0.2s ease, width 0.2s ease, transform 0.2s ease;
  &.eye-left  { left: 60px; }
  &.eye-right { right: 60px; }

  &.eyes-closed { height: 4px; border-radius: 2px; }
  &.eyes-half   { height: 12px; border-radius: 12px 12px 50% 50%; }
  &.eyes-narrow { transform: skewY(-12deg); height: 16px; }
  &.eyes-droop  { transform: translateY(2px) skewY(8deg); }
  &.eyes-wide   { width: 28px; height: 32px; }
}

.cheek {
  position: absolute; top: 116px;
  width: 22px; height: 12px;
  background: rgba(255, 100, 120, 0.35); border-radius: 50%;
  &.cheek-left  { left: 38px; }
  &.cheek-right { right: 38px; }
}

.mouth {
  position: absolute; bottom: 30px; left: 50%;
  transform: translateX(-50%);
  background: #2c2118;
  transition: all 0.2s ease;
  &.mouth-neutral { width: 24px; height: 4px; border-radius: 2px; }
  &.mouth-smile   { width: 36px; height: 16px; border-radius: 0 0 18px 18px; background: #2c2118; }
  &.mouth-frown   { width: 30px; height: 12px; border-radius: 18px 18px 0 0; background: transparent; border-top: 3px solid #2c2118; }
  &.mouth-angry   { width: 30px; height: 6px; border-radius: 4px; transform: translateX(-50%) skewY(-10deg); }
  &.mouth-O       { width: 16px; height: 18px; border-radius: 50%; background: #6b3a2a; }
  &.mouth-talk    { animation: talk 0.35s ease-in-out infinite; }
}

.paw {
  position: absolute; bottom: 0; width: 38px; height: 22px;
  background: #ffb066; border-radius: 18px;
  &.paw-left  { left: 30px; }
  &.paw-right { right: 30px; }
}

.bubble-wrap {
  position: absolute;
  top: 24px;
  right: max(8%, 24px);
}

// ========== 动画 ==========
@keyframes breath {
  0%, 100% { transform: translateY(0) scale(1); }
  50%      { transform: translateY(-3px) scale(1.015); }
}
@keyframes nod {
  0%, 100% { transform: translateY(0) rotate(0); }
  50%      { transform: translateY(-2px) rotate(2deg); }
}
@keyframes wag {
  0%, 100% { transform: rotate(-2deg); }
  50%      { transform: rotate(2deg); }
}
@keyframes blink {
  0%, 90%, 100% { transform: scaleY(1); }
  95%           { transform: scaleY(0.1); }
}
@keyframes jump {
  0%, 100% { transform: translateY(0); }
  50%      { transform: translateY(-26px); }
}
@keyframes talk {
  0%, 100% { height: 6px; }
  50%      { height: 14px; }
}
</style>
