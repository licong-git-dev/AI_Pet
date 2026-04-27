<script setup lang="ts">
import { ref } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

const auth = useAuthStore()
const router = useRouter()
const route = useRoute()

const token = ref(auth.token)
const avatarId = ref<number | undefined>(auth.defaultAvatarId ?? undefined)
const error = ref('')

function go() {
  if (!token.value.trim()) {
    error.value = '请填入 JWT token'
    return
  }
  auth.set(token.value.trim(), avatarId.value || null)
  const next = (route.query.next as string) || '/room'
  router.replace(next)
}
</script>

<template>
  <div class="login">
    <div class="card">
      <div class="hero">
        <span class="dot d1" /><span class="dot d2" /><span class="dot d3" />
        <h1>PetPal · Web Driver</h1>
        <p class="muted">让你的电子分身"活"在浏览器里</p>
      </div>

      <div class="form">
        <label>
          <span>JWT Token</span>
          <textarea v-model="token" rows="3" placeholder="粘贴 /api/v1/auth/login 拿到的 access_token"></textarea>
        </label>
        <label>
          <span>默认分身 ID（可选）</span>
          <input v-model.number="avatarId" type="number" placeholder="例如 1" />
        </label>
        <p v-if="error" class="error">{{ error }}</p>
        <button class="btn" @click="go">进入分身房间</button>
      </div>

      <p class="muted footer">
        Web Driver 通过 <code>WSS /api/v1/ws?token=…</code> 订阅 ASP 事件，
        所以需要一个有效的用户 token。
      </p>
    </div>
  </div>
</template>

<style lang="scss" scoped>
.login {
  min-height: 100vh;
  display: grid;
  place-items: center;
  padding: 24px;
}
.card {
  width: 100%;
  max-width: 460px;
}
.hero {
  text-align: center;
  margin-bottom: 18px;
  position: relative;
  h1 { font-size: 22px; letter-spacing: 0.04em; }
  .dot { position: absolute; top: 6px; width: 10px; height: 10px; border-radius: 50%; }
  .d1 { left: 14%; background: #ffd166; }
  .d2 { left: 26%; background: #ff7b7b; top: 14px; }
  .d3 { right: 22%; background: #5d8fff; top: 0; }
}
.form {
  display: flex;
  flex-direction: column;
  gap: 14px;
  label {
    display: flex;
    flex-direction: column;
    gap: 6px;
    font-size: 13px;
    color: #6b5742;
  }
  textarea, input {
    border: 1px solid rgba(120,78,16,0.18);
    border-radius: 12px;
    padding: 10px 14px;
    font-size: 14px;
    background: rgba(255,255,255,0.85);
    resize: vertical;
  }
  textarea { font-family: ui-monospace, Menlo, Consolas, monospace; }
}
.error { color: #d83a3a; font-size: 13px; }
.footer {
  margin-top: 18px;
  text-align: center;
  code { background: rgba(255,200,150,0.4); padding: 2px 6px; border-radius: 4px; }
}
</style>
