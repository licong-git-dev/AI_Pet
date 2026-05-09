<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import AppHeader from '@/components/AppHeader.vue'
import Loading from '@/components/Loading.vue'
import EmptyState from '@/components/EmptyState.vue'
import { useOwnerProfileStore } from '@/stores/ownerProfile'

const router = useRouter()
const store = useOwnerProfileStore()

const showRawJson = ref(false)
const error = ref('')
const busy = ref(false)

onMounted(() => store.fetchMine())

const profile = computed(() => store.profile)
const conf = computed(() => store.confidencePercent)

async function rebuild() {
  busy.value = true
  error.value = ''
  try { await store.rebuild() }
  catch (e: any) { error.value = e?.response?.data?.message || e?.message || '重建失败' }
  finally { busy.value = false }
}

async function pause7() {
  busy.value = true
  try { await store.pause(7) } finally { busy.value = false }
}

async function resume() {
  busy.value = true
  try { await store.resume() } finally { busy.value = false }
}

async function toggleVisible() {
  if (!profile.value) return
  await store.update({ is_visible_to_avatar: !profile.value.is_visible_to_avatar })
}

async function wipeAll() {
  if (!confirm('确定要彻底擦除画像与所有信号？此操作不可撤销。')) return
  await store.wipe()
  await store.fetchMine()
}

function fmt(v: any): string {
  if (v == null) return '—'
  if (Array.isArray(v)) return v.length ? v.join('、') : '—'
  if (typeof v === 'object') return JSON.stringify(v, null, 2)
  return String(v)
}
</script>

<template>
  <div class="profile">
    <AppHeader title="主人画像" :back="true" />

    <Loading v-if="store.loading && !profile" />

    <template v-else-if="profile">
      <!-- 顶部置信卡 -->
      <section class="card hero">
        <div class="conf">
          <div class="ring" :style="{ '--p': conf + '%' } as any">
            <span>{{ conf }}<small>%</small></span>
          </div>
          <div class="meta">
            <p class="title">分身对你的了解程度</p>
            <p class="muted">基于 {{ profile.signal_count }} 条信号</p>
            <p v-if="profile.last_built_at" class="muted small">最近重建 {{ profile.last_built_at.slice(0, 10) }}</p>
          </div>
        </div>
        <p v-if="conf < 30" class="muted hint">⏳ 数据还不够，多和分身聊聊它会越来越懂你</p>
      </section>

      <!-- 隐私控制 -->
      <section class="card switches">
        <h3>🔐 隐私控制</h3>
        <div class="switch-row">
          <span>分身可读取我的画像</span>
          <button class="toggle" :class="{ on: profile.is_visible_to_avatar }" @click="toggleVisible">
            {{ profile.is_visible_to_avatar ? '开' : '关' }}
          </button>
        </div>
        <div class="switch-row">
          <span>当前学习状态</span>
          <span :class="['tag', profile.is_learning_paused ? 'paused' : 'active']">
            {{ profile.is_learning_paused ? '已暂停' : '学习中' }}
            <small v-if="profile.pause_until"> · 直到 {{ profile.pause_until.slice(0, 10) }}</small>
          </span>
        </div>
        <div class="row">
          <button v-if="!profile.is_learning_paused" class="btn-secondary btn" @click="pause7" :disabled="busy">
            暂停 7 天
          </button>
          <button v-else class="btn-secondary btn" @click="resume" :disabled="busy">恢复学习</button>
          <button class="btn-secondary btn" @click="rebuild" :disabled="busy">立即重建</button>
        </div>
        <p v-if="error" class="error">{{ error }}</p>
      </section>

      <!-- 五维画像 -->
      <section class="card">
        <h3>🌅 生活节律</h3>
        <dl>
          <dt>起床时间</dt><dd>{{ fmt(profile.daily_rhythm?.wake_time) }}</dd>
          <dt>入睡时间</dt><dd>{{ fmt(profile.daily_rhythm?.sleep_time) }}</dd>
          <dt>活跃高峰</dt><dd>{{ fmt(profile.daily_rhythm?.peak_active_hours) }} 时</dd>
          <dt>周末模式</dt><dd>{{ fmt(profile.daily_rhythm?.weekend_pattern) }}</dd>
        </dl>
      </section>

      <section class="card">
        <h3>💗 情感基线</h3>
        <dl>
          <dt>主导情绪</dt><dd>{{ fmt(profile.emotional_baseline?.dominant_moods) }}</dd>
          <dt>压力来源</dt><dd>{{ fmt(profile.emotional_baseline?.stress_triggers) }}</dd>
          <dt>放松话题</dt><dd>{{ fmt(profile.emotional_baseline?.comfort_topics) }}</dd>
        </dl>
      </section>

      <section class="card">
        <h3>👨‍👩‍👧 关系网络</h3>
        <dl>
          <dt>工作角色</dt><dd>{{ fmt(profile.relationships?.work_role) }}</dd>
          <dt>爱好</dt><dd>{{ fmt(profile.relationships?.hobbies) }}</dd>
          <dt>家人</dt><dd>{{ fmt(profile.relationships?.family_members) }}</dd>
        </dl>
      </section>

      <section class="card">
        <h3>💬 沟通偏好</h3>
        <dl>
          <dt>语气</dt><dd>{{ fmt(profile.communication?.tone_preference) }}</dd>
          <dt>长度</dt><dd>{{ fmt(profile.communication?.length) }}</dd>
          <dt>Emoji</dt><dd>{{ fmt(profile.communication?.emoji_usage) }}</dd>
        </dl>
      </section>

      <section class="card">
        <h3>🐾 宠物依恋</h3>
        <dl>
          <dt>对宠物的昵称</dt><dd>{{ fmt(profile.pet_attachment?.nicknames) }}</dd>
          <dt>纪念日</dt><dd>{{ fmt(profile.pet_attachment?.special_dates) }}</dd>
          <dt>仪式时刻</dt><dd>{{ fmt(profile.pet_attachment?.ritual_moments) }}</dd>
        </dl>
      </section>

      <section class="card">
        <h3>🛠️ 高级</h3>
        <button class="btn-secondary btn" @click="showRawJson = !showRawJson">
          {{ showRawJson ? '隐藏' : '查看' }} 原始 JSON
        </button>
        <pre v-if="showRawJson" class="raw">{{ JSON.stringify(profile, null, 2) }}</pre>
        <button class="btn danger" @click="wipeAll">⚠️ 彻底擦除我的画像</button>
        <p class="muted small">擦除后所有维度归零，信号流也会清空（GDPR 风格）。</p>
      </section>
    </template>

    <EmptyState v-else icon="🌱" title="画像尚未建立"
                hint="多和分身聊聊，它就开始懂你了"
                action="先去聊一聊" @action="router.push({ name: 'room' })" />
  </div>
</template>

<style lang="scss" scoped>
.profile { padding-bottom: 80px; }
.card { margin: 12px 16px; padding: 16px; }
.hero { display: flex; flex-direction: column; gap: 8px; }
.conf {
  display: flex; gap: 16px; align-items: center;
  .ring {
    --p: 0%;
    width: 80px; height: 80px;
    border-radius: 50%;
    background: conic-gradient(#5a3a8a var(--p), rgba(120,78,16,0.12) 0);
    display: grid; place-items: center;
    span { background: #fff; width: 64px; height: 64px; border-radius: 50%;
           display: grid; place-items: center; font-weight: 700; color: #5a3a8a; font-size: 20px;
           small { font-size: 11px; opacity: 0.6; } }
  }
  .meta .title { font-size: 14px; font-weight: 600; }
  .meta .small { font-size: 12px; }
}
.hint { font-size: 12px; }

.switches { display: flex; flex-direction: column; gap: 8px;
  h3 { margin-bottom: 4px; }
  .switch-row {
    display: flex; justify-content: space-between; align-items: center;
    padding: 6px 0; font-size: 13px;
  }
  .toggle {
    width: 50px; height: 24px; border-radius: 12px;
    background: rgba(120,78,16,0.18); border: none; color: transparent;
    position: relative;
    &::before { content: ''; position: absolute; left: 2px; top: 2px; width: 20px; height: 20px;
                background: #fff; border-radius: 50%; transition: all 0.2s; }
    &.on { background: #5a3a8a; color: #fff;
           &::before { left: 28px; } }
  }
  .tag {
    padding: 2px 10px; border-radius: 999px; font-size: 12px;
    &.active { background: rgba(62, 204, 126, 0.18); color: #1f9b54; }
    &.paused { background: rgba(216, 58, 58, 0.18); color: #d83a3a; }
  }
  .row { display: flex; gap: 8px; flex-wrap: wrap; .btn { flex: 1; min-width: 100px; } }
}

dl { display: grid; grid-template-columns: 100px 1fr; gap: 6px 10px; font-size: 13px; }
dt { color: #8a7a6a; }
dd { margin: 0; color: #2b2b2b; word-break: break-word; }

.raw {
  margin-top: 10px;
  background: rgba(0,0,0,0.04);
  padding: 10px; border-radius: 8px;
  font-size: 11px; overflow: auto; max-height: 220px;
  font-family: ui-monospace, Menlo, monospace;
}
.btn.danger { background: #d83a3a; box-shadow: 0 6px 16px rgba(216,58,58,0.25); margin-top: 12px; }
.error { color: #d83a3a; font-size: 13px; }
.muted { color: #8a7a6a; }
.small { font-size: 12px; }
</style>
