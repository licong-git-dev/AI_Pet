<script setup lang="ts">
import { ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { api } from '@/services/api'
import { useAuthStore } from '@/stores/auth'
import { useAvatarSocket, makeMockEvent } from '@/composables/useAvatarSocket'
import AvatarStage from '@/components/AvatarStage.vue'

const auth = useAuthStore()
const router = useRouter()

const message = ref('')
const sending = ref(false)
const lastReply = ref('')
const apiError = ref('')

// 演示用：手动注入一个 mock 事件，便于在没有后端连通时也能看动画
const stageEvent = ref<any>(null)

const { status, lastEvent } = useAvatarSocket({
  onEvent: (e) => { stageEvent.value = e },
})

watch(lastEvent, (e) => { if (e) stageEvent.value = e })

async function sendChat() {
  if (!message.value.trim()) return
  if (!auth.defaultAvatarId) {
    apiError.value = '请先在 Login 页填写默认分身 ID'
    return
  }
  apiError.value = ''
  sending.value = true
  try {
    // 我们的对话接口路径：POST /api/v1/pet-avatar/{pet_id}/chat
    // 但前端这里更友好做法是按 avatar 维度，先取分身找到 pet_id
    // 简化：假设用户已知 pet_id == default_avatar 对应的 pet
    // 真实集成里可加一次 /pet-avatar/{pet_id} 校验。
    const petId = auth.defaultAvatarId
    const r = await api.post(`/pet-avatar/${petId}/chat`, { message: message.value })
    lastReply.value = r.data?.data?.reply ?? ''
    message.value = ''
  } catch (e: any) {
    apiError.value = e?.response?.data?.message || e?.message || '请求失败'
  } finally {
    sending.value = false
  }
}

function previewEmotion(emo: string) {
  stageEvent.value = makeMockEvent({
    type: 'speech',
    emotion: emo as any,
    speech: { text: ({
      happy: '今天阳光真好，主人陪我玩吧！',
      sad: '主人...你今天好像不开心，我陪着你。',
      sleepy: '呼...好困哦...',
      loving: '我最喜欢主人了 ♡',
      angry: '哼！',
      surprised: '哇！这是什么？',
      curious: '咦？让我看看～',
      proud: '我可是全世界最棒的小宝贝！',
      neutral: '我在哦。',
      confused: '咦？我有点搞不懂...',
    } as any)[emo] || '...' },
    intensity: 0.85,
  })
}

const wsBadgeColor = {
  idle: '#999',
  connecting: '#f5a623',
  open: '#3ecc7e',
  closed: '#cccccc',
  error: '#d8484a',
}

function logout() {
  auth.clear()
  router.replace({ name: 'login' })
}
</script>

<template>
  <div class="room">
    <header class="topbar">
      <div class="brand">
        <span class="paw">🐾</span> PetPal
      </div>
      <div class="ws">
        <span class="badge" :style="{ background: (wsBadgeColor as any)[status] }" />
        WS: {{ status }}
      </div>
      <nav>
        <router-link to="/wrapped">我的月报</router-link>
        <button class="link" @click="logout">退出</button>
      </nav>
    </header>

    <main class="main">
      <AvatarStage :event="stageEvent" />

      <section class="emotion-row">
        <p class="muted">情绪预览（本地 mock）：</p>
        <div class="chips">
          <button v-for="e in ['happy','sad','sleepy','loving','angry','surprised','curious','proud']"
                  :key="e" class="chip" @click="previewEmotion(e)">
            {{ e }}
          </button>
        </div>
      </section>

      <section class="chat card">
        <h3>跟分身说点什么</h3>
        <textarea v-model="message" rows="3" placeholder="主人对分身的话，例如：今天好累哦"></textarea>
        <div class="row">
          <p v-if="apiError" class="error">{{ apiError }}</p>
          <button class="btn" :disabled="sending || !message.trim()" @click="sendChat">
            {{ sending ? '送出中…' : '发送' }}
          </button>
        </div>
        <p v-if="lastReply" class="muted reply">分身刚刚回复："{{ lastReply }}"</p>
      </section>
    </main>
  </div>
</template>

<style lang="scss" scoped>
.room {
  min-height: 100vh;
  display: flex;
  flex-direction: column;
}
.topbar {
  display: flex; align-items: center; justify-content: space-between;
  padding: 14px 22px;
  background: rgba(255,255,255,0.55);
  backdrop-filter: blur(10px);
  .brand { font-weight: 700; letter-spacing: 0.06em; }
  .paw { margin-right: 6px; }
  .ws {
    font-size: 13px; color: #6b5742;
    display: flex; align-items: center; gap: 6px;
    .badge { width: 8px; height: 8px; border-radius: 50%; display: inline-block; }
  }
  nav {
    display: flex; gap: 16px; align-items: center;
    a { color: #ff7b1c; font-weight: 600; }
    .link { background: none; border: none; color: #6b5742; }
  }
}
.main {
  flex: 1;
  width: 100%;
  max-width: 760px;
  margin: 0 auto;
  padding: 24px 16px 60px;
  display: flex;
  flex-direction: column;
  gap: 20px;
}
.emotion-row {
  text-align: center;
  .chips { display: flex; flex-wrap: wrap; justify-content: center; gap: 8px; margin-top: 8px; }
  .chip {
    padding: 6px 12px; border-radius: 999px;
    background: rgba(255,255,255,0.6); border: 1px solid rgba(120,78,16,0.15);
    font-size: 13px; color: #6b5742;
    &:hover { background: #fff; }
  }
}
.chat {
  display: flex; flex-direction: column; gap: 12px;
  textarea {
    border: 1px solid rgba(120,78,16,0.15);
    border-radius: 14px; padding: 12px 14px; font: inherit;
    background: rgba(255,255,255,0.85); resize: vertical;
  }
  .row { display: flex; align-items: center; justify-content: space-between; gap: 12px; }
  .error { color: #d83a3a; font-size: 13px; flex: 1; }
  .reply { font-style: italic; }
}
</style>
