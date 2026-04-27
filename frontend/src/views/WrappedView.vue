<script setup lang="ts">
import { onMounted, ref, computed } from 'vue'
import { useRouter } from 'vue-router'
import { api } from '@/services/api'

interface Card {
  kind: string
  title?: string
  subtitle?: string
  body?: string
  intro?: string
  metrics?: Array<{ label: string; value: number; unit?: string }>
  memories?: Array<any>
  digests?: Array<any>
  distribution?: Record<string, number>
  dominant_emotion?: string
  pet_name?: string
  footnote?: string
  index?: number
  tone?: string
}

const router = useRouter()
const loading = ref(true)
const error = ref('')
const data = ref<any | null>(null)
const idx = ref(0)

onMounted(async () => {
  try {
    const r = await api.get('/owner-profile/wrapped')
    data.value = r.data?.data
  } catch (e: any) {
    if (e?.response?.status === 401) {
      router.replace({ name: 'login' })
      return
    }
    error.value = e?.response?.data?.message || e?.message || '加载月报失败'
  } finally {
    loading.value = false
  }
})

const cards = computed<Card[]>(() => (data.value?.cards as Card[]) || [])
const total = computed(() => cards.value.length)
const current = computed<Card | null>(() => cards.value[idx.value] ?? null)

function next() { if (idx.value < total.value - 1) idx.value++ }
function prev() { if (idx.value > 0) idx.value-- }

function emojiOf(emo?: string): string {
  return ({
    happy: '☀️', loving: '💗', proud: '👑', neutral: '☁️',
    sad: '🌧️', anxious: '🌪️', worried: '🍂', lonely: '🌙', angry: '🔥',
  } as any)[emo || 'neutral'] || '☁️'
}
</script>

<template>
  <div class="wrapped">
    <header class="bar">
      <button class="link" @click="router.replace({ name: 'room' })">← 回房间</button>
      <span class="muted" v-if="data">{{ data.year }} · {{ String(data.month).padStart(2, '0') }} 月</span>
    </header>

    <div class="content">
      <p v-if="loading" class="muted center">月报加载中…</p>
      <p v-else-if="error" class="error center">{{ error }}</p>

      <template v-else-if="current">
        <!-- 顶部进度 -->
        <div class="progress">
          <span v-for="(_, i) in cards" :key="i" :class="['pip', { active: i <= idx }]" />
        </div>

        <!-- 卡片本体 -->
        <div class="story" :class="`kind-${current.kind}`">
          <!-- cover -->
          <template v-if="current.kind === 'cover'">
            <h1>{{ current.title }}</h1>
            <h3 class="muted">{{ current.subtitle }}</h3>
            <p class="intro">{{ current.intro }}</p>
          </template>

          <!-- stat -->
          <template v-else-if="current.kind === 'stat'">
            <h2>{{ current.title }}</h2>
            <div class="metrics">
              <div v-for="m in current.metrics" :key="m.label" class="metric">
                <span class="value">{{ m.value }}</span>
                <span class="unit">{{ m.unit }}</span>
                <span class="label">{{ m.label }}</span>
              </div>
            </div>
            <p v-if="current.footnote" class="muted">{{ current.footnote }}</p>
          </template>

          <!-- secret -->
          <template v-else-if="current.kind === 'secret'">
            <span class="badge">🔑 {{ current.title }}</span>
            <p class="secret-body">{{ current.body }}</p>
          </template>

          <!-- highlight memories -->
          <template v-else-if="current.kind === 'highlight_memories'">
            <h2>{{ current.title }}</h2>
            <ol class="memories">
              <li v-for="m in (current.memories || [])" :key="m.id">
                <span class="tag" :class="`emo-${m.emotion}`">{{ emojiOf(m.emotion) }}</span>
                <span>{{ m.summary }}</span>
              </li>
            </ol>
          </template>

          <!-- digest strip -->
          <template v-else-if="current.kind === 'digest_strip'">
            <h2>{{ current.title }}</h2>
            <div class="digests">
              <div v-for="d in (current.digests || [])" :key="d.period_start" class="digest">
                <p class="muted small">{{ (d.period_start || '').slice(0, 10) }} · {{ d.dominant_emotion }}</p>
                <p>{{ d.summary }}</p>
                <div v-if="d.key_themes" class="themes">
                  <span v-for="t in d.key_themes" :key="t" class="theme-chip">{{ t }}</span>
                </div>
              </div>
            </div>
          </template>

          <!-- emotion palette -->
          <template v-else-if="current.kind === 'emotion_palette'">
            <h2>{{ current.title }}</h2>
            <div class="palette">
              <div v-for="(v, k) in (current.distribution || {})" :key="k as string" class="bar-row">
                <span class="bar-label">{{ emojiOf(k as string) }} {{ k }}</span>
                <div class="bar-track">
                  <div class="bar-fill" :style="{ width: Math.min(100, (v as number) * 8) + '%' }"></div>
                </div>
                <span class="bar-num">{{ v }}</span>
              </div>
            </div>
            <p class="muted">主导情绪：{{ emojiOf(current.dominant_emotion) }} {{ current.dominant_emotion }}</p>
          </template>

          <!-- closing -->
          <template v-else-if="current.kind === 'closing'">
            <h1>{{ current.title }}</h1>
            <p class="closing">{{ current.body }}</p>
            <p class="muted signature">— {{ current.pet_name }}</p>
          </template>
        </div>

        <!-- 触摸/点击翻页 -->
        <div class="touch left" @click="prev"></div>
        <div class="touch right" @click="next"></div>

        <div class="footer-actions">
          <button class="btn-secondary btn" @click="prev" :disabled="idx === 0">上一张</button>
          <span class="muted">{{ idx + 1 }} / {{ total }}</span>
          <button class="btn" @click="next" :disabled="idx === total - 1">
            {{ idx === total - 1 ? '看完啦' : '下一张' }}
          </button>
        </div>
      </template>
    </div>
  </div>
</template>

<style lang="scss" scoped>
.wrapped {
  min-height: 100vh;
  display: flex;
  flex-direction: column;
  background: linear-gradient(170deg, #2b1b4a 0%, #6a3aa8 50%, #ff6f91 100%);
  color: #fff;
}
.bar {
  display: flex; justify-content: space-between; align-items: center;
  padding: 14px 20px;
  .link { background: none; border: none; color: #fff; }
  .muted { color: rgba(255,255,255,0.65); }
}
.content {
  flex: 1;
  position: relative;
  width: 100%;
  max-width: 460px;
  margin: 0 auto;
  padding: 20px 18px 30px;
  display: flex;
  flex-direction: column;
}
.error { color: #ffd6d6; }
.progress {
  display: flex; gap: 4px; margin-bottom: 14px;
  .pip {
    flex: 1; height: 3px; border-radius: 2px;
    background: rgba(255,255,255,0.25);
    transition: background 0.3s ease;
    &.active { background: #fff; }
  }
}
.story {
  flex: 1;
  position: relative;
  padding: 32px 24px 26px;
  border-radius: 28px;
  background: rgba(255,255,255,0.08);
  backdrop-filter: blur(8px);
  border: 1px solid rgba(255,255,255,0.15);
  display: flex;
  flex-direction: column;
  justify-content: center;
  gap: 16px;

  h1 { font-size: 28px; line-height: 1.2; }
  h2 { font-size: 20px; }
  h3 { font-weight: 400; }
  .intro, .closing { font-size: 15px; line-height: 1.7; }
  .muted { color: rgba(255,255,255,0.65); }
  .small { font-size: 12px; }
}

// kind-specific
.metrics {
  display: flex; gap: 14px; margin: 16px 0 8px;
  .metric {
    flex: 1; padding: 16px; border-radius: 16px;
    background: rgba(255,255,255,0.12);
    text-align: center;
    .value { font-size: 30px; font-weight: 700; }
    .unit { font-size: 13px; color: rgba(255,255,255,0.7); margin-left: 4px; }
    .label { display: block; font-size: 13px; color: rgba(255,255,255,0.7); margin-top: 4px; }
  }
}
.kind-secret {
  align-items: center; text-align: center;
  .badge {
    display: inline-block; padding: 6px 14px; border-radius: 999px;
    background: rgba(255,255,255,0.18); font-size: 13px; letter-spacing: 0.05em;
  }
  .secret-body {
    font-size: 22px; line-height: 1.65; font-weight: 500;
    text-shadow: 0 2px 8px rgba(0,0,0,0.2);
  }
}
.memories {
  list-style: none; padding: 0; display: flex; flex-direction: column; gap: 12px;
  li {
    display: flex; gap: 10px; align-items: flex-start;
    padding: 12px 14px; border-radius: 14px;
    background: rgba(255,255,255,0.1);
  }
  .tag {
    flex-shrink: 0;
    width: 28px; height: 28px; border-radius: 50%;
    display: grid; place-items: center;
    background: rgba(255,255,255,0.15);
  }
}
.digests {
  display: flex; flex-direction: column; gap: 12px;
  .digest {
    padding: 12px 14px; border-radius: 14px; background: rgba(255,255,255,0.08);
    .themes { display: flex; flex-wrap: wrap; gap: 6px; margin-top: 8px; }
    .theme-chip {
      font-size: 12px; padding: 2px 8px; border-radius: 999px;
      background: rgba(255,255,255,0.18);
    }
  }
}
.palette {
  display: flex; flex-direction: column; gap: 10px;
  .bar-row {
    display: flex; align-items: center; gap: 10px;
    .bar-label { width: 80px; font-size: 13px; }
    .bar-track {
      flex: 1; height: 10px; border-radius: 6px;
      background: rgba(255,255,255,0.15); overflow: hidden;
    }
    .bar-fill {
      height: 100%;
      background: linear-gradient(90deg, #ffd6e0, #ff6f91);
      border-radius: 6px;
    }
    .bar-num { width: 30px; text-align: right; font-variant-numeric: tabular-nums; }
  }
}
.kind-closing {
  text-align: center;
  align-items: center;
  .signature { margin-top: 24px; }
}

.touch {
  position: absolute; top: 0; bottom: 0; width: 28%;
  &.left { left: 0; }
  &.right { right: 0; }
}

.footer-actions {
  display: flex; justify-content: space-between; align-items: center;
  margin-top: 16px; gap: 10px;
  span.muted { font-variant-numeric: tabular-nums; }
}
.btn-secondary { background: rgba(255,255,255,0.85); color: #5a3a8a; box-shadow: none; }
.error.center { padding-top: 60px; }
.center { text-align: center; }
</style>
