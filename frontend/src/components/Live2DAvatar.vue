<script setup lang="ts">
/**
 * Live2D 渲染器（Cubism 4 模型）
 *
 * 把 ASP 事件流映射到模型行为：
 *  - emotion → expression（按 expression 文件序号循环命中）
 *  - speech → 嘴部 lip-sync（用一个简易 mouthOpenY 周期）
 *  - animation.name → 命中对应 motion（按 group/index 启发式）
 *  - sleep / wake → 切到 idle group
 *
 * 模型若加载失败（最常见：未运行 npm run fetch:live2d），
 * 组件会显示提示框并让上层渲染兜底。
 */
import { onBeforeUnmount, onMounted, ref, watch } from 'vue'
import * as PIXI from 'pixi.js'
import { Live2DModel } from 'pixi-live2d-display/cubism4'
import type { AvatarStateEvent } from '@/types/asp'

// 把 PIXI 暴露到 window，pixi-live2d-display 期待这个全局
;(window as any).PIXI = PIXI

const props = defineProps<{ modelUrl: string; event: AvatarStateEvent | null }>()

const canvasRef = ref<HTMLCanvasElement | null>(null)
const status = ref<'idle' | 'loading' | 'ready' | 'error'>('idle')
const errorMsg = ref<string | null>(null)

let app: PIXI.Application | null = null
let model: any = null
let lipSyncTimer: ReturnType<typeof setInterval> | null = null
let resizeObserver: ResizeObserver | null = null

const emotionToExpressionIdx: Record<string, number> = {
  happy: 0, loving: 1, proud: 2, neutral: 3,
  curious: 3, sad: 4, sleepy: 5, surprised: 6, angry: 7, confused: 7,
}

const animNameToMotion: Record<string, { group: string; index?: number }> = {
  idle: { group: 'Idle' },
  talk: { group: 'Idle', index: 0 },
  wag_tail: { group: 'TapBody' },
  jump: { group: 'TapBody' },
  blink: { group: 'Idle' },
}

async function init() {
  if (!canvasRef.value || !props.modelUrl) return
  status.value = 'loading'
  errorMsg.value = null

  try {
    app = new PIXI.Application({
      view: canvasRef.value,
      autoStart: true,
      backgroundAlpha: 0,
      resolution: window.devicePixelRatio || 1,
      antialias: true,
      resizeTo: canvasRef.value.parentElement || canvasRef.value,
    })

    model = await Live2DModel.from(props.modelUrl)
    app.stage.addChild(model)

    // 适配舞台尺寸
    const fit = () => {
      if (!app || !model) return
      const w = app.renderer.width
      const h = app.renderer.height
      const scale = Math.min(w / model.width, h / model.height) * 0.9
      model.scale.set(scale)
      model.x = w / 2 - (model.width * scale) / 2
      model.y = h - model.height * scale + 8
    }
    fit()

    if (canvasRef.value.parentElement) {
      resizeObserver = new ResizeObserver(fit)
      resizeObserver.observe(canvasRef.value.parentElement)
    }

    // 默认进入 idle motion（避免第一秒"僵硬"）
    try { model.motion('Idle') } catch { /* group 不一定叫 Idle */ }

    status.value = 'ready'

    // 渲染当前已有事件（避免错过首帧）
    if (props.event) applyEvent(props.event)
  } catch (e: any) {
    status.value = 'error'
    errorMsg.value = e?.message || String(e)
    console.warn('[Live2DAvatar] 加载失败', e)
  }
}

function teardown() {
  if (lipSyncTimer) { clearInterval(lipSyncTimer); lipSyncTimer = null }
  if (resizeObserver) { resizeObserver.disconnect(); resizeObserver = null }
  try {
    if (model && app) {
      app.stage.removeChild(model)
      model.destroy?.()
    }
  } catch {}
  try { app?.destroy(true, { children: true, texture: true, baseTexture: true }) } catch {}
  app = null; model = null
}

function applyEvent(e: AvatarStateEvent) {
  if (!model) return
  // 情绪 → expression
  if (e.emotion) {
    const idx = emotionToExpressionIdx[e.emotion] ?? 3
    try { model.expression(idx) } catch (err) { /* 模型可能没那么多 expression */ }
  }
  // 动作
  if (e.type === 'animation' && e.animation?.name) {
    const motion = animNameToMotion[e.animation.name]
    if (motion) {
      try { model.motion(motion.group, motion.index) } catch (err) { /* fallback */ }
    }
  }
  if (e.type === 'idle') {
    try { model.motion('Idle') } catch {}
  }
  // 说话 → 嘴部 lip-sync 一段时间
  if (e.type === 'speech' && e.speech?.text) {
    startLipSync(e.ttl_ms ?? Math.min(8000, Math.max(2500, e.speech.text.length * 110)))
  }
  if (e.type === 'sleep') {
    try { model.expression(5) } catch {}
  }
  if (e.type === 'wake') {
    try { model.expression(0) } catch {}
  }
}

function startLipSync(ms: number) {
  if (!model) return
  if (lipSyncTimer) clearInterval(lipSyncTimer)
  const start = performance.now()
  lipSyncTimer = setInterval(() => {
    const elapsed = performance.now() - start
    if (elapsed > ms) {
      if (lipSyncTimer) clearInterval(lipSyncTimer)
      lipSyncTimer = null
      try { model.internalModel?.coreModel?.setParameterValueById('ParamMouthOpenY', 0) } catch {}
      return
    }
    // 简易嘴形：60ms 周期
    const phase = (elapsed / 60) % 2
    const value = phase < 1 ? phase : 2 - phase
    try { model.internalModel?.coreModel?.setParameterValueById('ParamMouthOpenY', value) } catch {}
  }, 50)
}

watch(() => props.event, (e) => { if (e) applyEvent(e) })
watch(() => props.modelUrl, async (url) => {
  teardown()
  if (url) await init()
})

onMounted(init)
onBeforeUnmount(teardown)
</script>

<template>
  <div class="live2d-host">
    <canvas ref="canvasRef" class="live2d-canvas" />
    <div v-if="status !== 'ready'" class="overlay">
      <p v-if="status === 'loading'">Live2D 模型加载中…</p>
      <p v-else-if="status === 'error'" class="muted">
        Live2D 加载失败：{{ errorMsg }}<br>
        <small>提示：先运行 <code>cd frontend && npm run fetch:live2d</code> 拉取示例模型</small>
      </p>
    </div>
  </div>
</template>

<style lang="scss" scoped>
.live2d-host {
  position: relative;
  width: 100%;
  height: 100%;
  min-height: 380px;
}
.live2d-canvas {
  width: 100%;
  height: 100%;
  display: block;
}
.overlay {
  position: absolute;
  inset: 0;
  display: grid;
  place-items: center;
  text-align: center;
  background: rgba(255,255,255,0.4);
  backdrop-filter: blur(2px);
  padding: 16px;
  font-size: 13px;
  color: #6b5742;
  code {
    background: rgba(255,200,150,0.4);
    padding: 1px 6px; border-radius: 4px;
  }
}
</style>
