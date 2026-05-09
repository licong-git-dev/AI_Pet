<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import AppHeader from '@/components/AppHeader.vue'
import EmptyState from '@/components/EmptyState.vue'
import Loading from '@/components/Loading.vue'
import { useAuthStore } from '@/stores/auth'
import { useMemoryStore, type MemoryType, type MemoryEmotion } from '@/stores/memory'

const router = useRouter()
const auth = useAuthStore()
const store = useMemoryStore()

// 默认分身 id 来自 auth store
const avatarId = computed(() => auth.defaultAvatarId)

const filterType = ref<MemoryType | ''>('')
const filterEmotion = ref<MemoryEmotion | ''>('')
const includeArchived = ref(false)
const showCreate = ref(false)

const memoryTypes: Array<{ v: MemoryType | ''; label: string; emoji: string }> = [
  { v: '', label: '全部', emoji: '🌳' },
  { v: 'episodic', label: '情景', emoji: '📅' },
  { v: 'semantic', label: '认知', emoji: '🧠' },
  { v: 'preference', label: '偏好', emoji: '⭐' },
  { v: 'event', label: '里程碑', emoji: '🎉' },
]

const emotions: Array<{ v: MemoryEmotion | ''; label: string; emoji: string }> = [
  { v: '', label: '全部情绪', emoji: '🎨' },
  { v: 'happy', label: '快乐', emoji: '☀️' },
  { v: 'loving', label: '爱意', emoji: '💗' },
  { v: 'proud', label: '骄傲', emoji: '👑' },
  { v: 'sad', label: '难过', emoji: '🌧️' },
  { v: 'anxious', label: '焦虑', emoji: '🌪️' },
]

// 新增表单
const newMem = ref({
  content: '',
  memory_type: 'episodic' as MemoryType,
  importance: 7,
  emotion: 'neutral' as MemoryEmotion,
})
const submitting = ref(false)

async function refresh() {
  if (!avatarId.value) return
  await Promise.all([
    store.fetchList({
      avatar_id: avatarId.value,
      memory_type: filterType.value || undefined,
      emotion: filterEmotion.value || undefined,
      include_archived: includeArchived.value,
      reset: true,
    }),
    store.fetchStats(avatarId.value),
  ])
}

watch([filterType, filterEmotion, includeArchived], refresh)

onMounted(async () => {
  if (!avatarId.value) {
    router.replace({ name: 'login' })
    return
  }
  await refresh()
})

async function submit() {
  if (!avatarId.value || !newMem.value.content.trim()) return
  submitting.value = true
  try {
    await store.create({
      pet_avatar_id: avatarId.value,
      content: newMem.value.content.trim(),
      memory_type: newMem.value.memory_type,
      importance: newMem.value.importance,
      emotion: newMem.value.emotion,
    })
    newMem.value.content = ''
    showCreate.value = false
    await store.fetchStats(avatarId.value)
  } finally {
    submitting.value = false
  }
}

function emojiOfEmotion(e?: string | null) {
  return ({
    happy: '☀️', loving: '💗', proud: '👑', neutral: '☁️',
    sad: '🌧️', anxious: '🌪️', worried: '🍂', lonely: '🌙', angry: '🔥',
  } as Record<string, string>)[e || 'neutral'] || '☁️'
}

function emojiOfType(t: string) {
  return ({ episodic: '📅', semantic: '🧠', preference: '⭐', event: '🎉' } as Record<string, string>)[t] || '🌱'
}
</script>

<template>
  <div class="garden">
    <AppHeader title="🌳 记忆花园" right="+ 添加" @right="showCreate = true" />

    <Loading v-if="store.loading && !store.list.length" />

    <template v-else>
      <!-- 顶部统计 -->
      <section v-if="store.stats" class="stats-card card">
        <div class="stat">
          <span class="value">{{ store.stats.total }}</span>
          <span class="label">总记忆</span>
        </div>
        <div class="stat">
          <span class="value">{{ store.stats.pinned_count }}</span>
          <span class="label">置顶</span>
        </div>
        <div class="stat">
          <span class="value">{{ store.stats.archived_count }}</span>
          <span class="label">归档</span>
        </div>
      </section>

      <!-- 类型 chips -->
      <div class="chips">
        <button v-for="t in memoryTypes" :key="t.v"
                :class="['chip', { active: filterType === t.v }]"
                @click="filterType = t.v as any">
          <span>{{ t.emoji }}</span> {{ t.label }}
          <em v-if="store.stats?.by_type[t.v]">·{{ store.stats.by_type[t.v] }}</em>
        </button>
      </div>
      <div class="chips small">
        <button v-for="e in emotions" :key="e.v"
                :class="['chip', { active: filterEmotion === e.v }]"
                @click="filterEmotion = e.v as any">
          <span>{{ e.emoji }}</span> {{ e.label }}
        </button>
        <label class="archive-toggle">
          <input type="checkbox" v-model="includeArchived" />
          含归档
        </label>
      </div>

      <!-- 记忆列表 -->
      <ul v-if="store.list.length" class="list">
        <li v-for="m in store.list" :key="m.id"
            :class="['mem', { archived: m.is_archived, pinned: m.is_pinned }]">
          <div class="head">
            <span class="kind">{{ emojiOfType(m.memory_type) }}</span>
            <span class="emo">{{ emojiOfEmotion(m.emotion) }}</span>
            <span class="imp">重要度 {{ m.importance }}/10</span>
            <span v-if="m.is_pinned" class="badge">📌</span>
            <span v-if="m.is_archived" class="badge muted">归档</span>
          </div>
          <p class="content">{{ m.content }}</p>
          <div class="meta">
            <span class="muted">{{ m.created_at?.slice(0, 10) }}</span>
            <span class="muted small">召回 {{ m.recall_count || 0 }} 次</span>
          </div>
          <div class="actions">
            <button @click="store.togglePin(m.id)">{{ m.is_pinned ? '取消置顶' : '置顶' }}</button>
            <button v-if="!m.is_archived" @click="store.update(m.id, { is_archived: true })">归档</button>
            <button v-else @click="store.update(m.id, { is_archived: false })">恢复</button>
            <button class="danger" @click="store.remove(m.id)">删除</button>
          </div>
        </li>
      </ul>

      <EmptyState v-else icon="🌱" title="花园里还没有记忆"
                  hint="跟分身多聊一聊，或者你也可以手动添加"
                  action="添加一条" @action="showCreate = true" />
    </template>

    <!-- 添加弹层 -->
    <transition name="fade">
      <div v-if="showCreate" class="modal-mask" @click.self="showCreate = false">
        <form class="modal card" @submit.prevent="submit">
          <h3>📝 写一条记忆</h3>
          <textarea v-model="newMem.content" rows="4" maxlength="500"
                    placeholder="主人和分身共同的小事，例如：今天主人加班到很晚回家..." />
          <label>
            <span>类型</span>
            <select v-model="newMem.memory_type">
              <option value="episodic">📅 情景（一次性）</option>
              <option value="semantic">🧠 认知（一般规律）</option>
              <option value="preference">⭐ 偏好</option>
              <option value="event">🎉 里程碑</option>
            </select>
          </label>
          <label>
            <span>情绪</span>
            <select v-model="newMem.emotion">
              <option value="happy">☀️ 快乐</option>
              <option value="loving">💗 爱意</option>
              <option value="proud">👑 骄傲</option>
              <option value="neutral">☁️ 中性</option>
              <option value="sad">🌧️ 难过</option>
              <option value="anxious">🌪️ 焦虑</option>
            </select>
          </label>
          <label>
            <span>重要度 ({{ newMem.importance }} / 10)</span>
            <input type="range" min="0" max="10" v-model.number="newMem.importance" />
          </label>
          <div class="row">
            <button type="button" class="btn-secondary btn" @click="showCreate = false">取消</button>
            <button type="submit" class="btn" :disabled="submitting || !newMem.content.trim()">
              {{ submitting ? '保存中…' : '保存' }}
            </button>
          </div>
        </form>
      </div>
    </transition>
  </div>
</template>

<style lang="scss" scoped>
.garden { padding-bottom: 80px; }
.stats-card {
  margin: 12px 16px;
  display: flex;
  .stat {
    flex: 1; text-align: center;
    .value { display: block; font-size: 24px; font-weight: 700; color: #5a3a8a; }
    .label { font-size: 12px; color: #8a7a6a; }
  }
}
.chips {
  padding: 0 16px; margin-bottom: 8px;
  display: flex; flex-wrap: wrap; gap: 6px;
  &.small .chip { font-size: 12px; }
  .chip {
    padding: 6px 12px;
    border-radius: 999px;
    background: rgba(255,255,255,0.65);
    border: 1px solid rgba(120,78,16,0.12);
    font-size: 13px; color: #6b5742;
    em { font-style: normal; opacity: 0.6; margin-left: 2px; }
    &.active {
      background: #5a3a8a; color: #fff;
      em { color: #fff; }
    }
  }
  .archive-toggle {
    display: inline-flex; align-items: center; gap: 4px;
    font-size: 12px; color: #8a7a6a; padding: 6px 8px;
    input { transform: scale(0.9); }
  }
}

.list {
  list-style: none; padding: 0 16px; margin: 12px 0 0;
  display: flex; flex-direction: column; gap: 10px;
}
.mem {
  background: rgba(255,255,255,0.78);
  backdrop-filter: blur(10px);
  border-radius: 16px;
  padding: 14px 14px 10px;
  position: relative;
  transition: opacity 0.2s ease;
  &.archived { opacity: 0.55; }
  &.pinned {
    background: linear-gradient(160deg, #fff8c5, #fff);
    box-shadow: 0 6px 18px rgba(255, 184, 56, 0.18);
  }

  .head {
    display: flex; align-items: center; gap: 8px;
    font-size: 13px; color: #6b5742;
    margin-bottom: 6px;
    .kind, .emo { font-size: 16px; }
    .imp { font-size: 12px; opacity: 0.7; }
    .badge {
      background: rgba(255, 184, 56, 0.25); color: #c2660b;
      padding: 1px 6px; border-radius: 999px; font-size: 11px;
      &.muted { background: rgba(120, 78, 16, 0.12); color: #6b5742; }
    }
  }
  .content { font-size: 14px; line-height: 1.6; white-space: pre-wrap; }
  .meta {
    display: flex; gap: 10px; margin-top: 6px;
    .small { font-size: 11px; }
  }
  .actions {
    display: flex; gap: 6px; margin-top: 8px;
    button {
      padding: 4px 10px; border-radius: 8px;
      background: rgba(120,78,16,0.06); border: 1px solid rgba(120,78,16,0.12);
      font-size: 12px; color: #6b5742;
      &.danger { color: #d83a3a; border-color: rgba(216,58,58,0.3); }
    }
  }
}

.modal-mask {
  position: fixed; inset: 0;
  background: rgba(0,0,0,0.4);
  display: grid; place-items: center;
  z-index: 200; padding: 16px;
}
.modal {
  width: 100%; max-width: 420px;
  display: flex; flex-direction: column; gap: 12px;
  h3 { font-size: 16px; }
  textarea, select, input[type=text] {
    border: 1px solid rgba(120,78,16,0.18);
    border-radius: 12px; padding: 10px 14px;
    background: rgba(255,255,255,0.85);
    font: inherit;
  }
  label { display: flex; flex-direction: column; gap: 4px; font-size: 12px; color: #6b5742; }
  .row { display: flex; gap: 8px; }
  .row .btn { flex: 1; }
}
.fade-enter-active, .fade-leave-active { transition: opacity 0.2s ease; }
.fade-enter-from, .fade-leave-to { opacity: 0; }
</style>
