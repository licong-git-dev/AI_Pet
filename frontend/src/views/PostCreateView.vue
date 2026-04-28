<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import AppHeader from '@/components/AppHeader.vue'
import { usePostStore } from '@/stores/post'
import { usePetStore } from '@/stores/pet'

const router = useRouter()
const store = usePostStore()
const petStore = usePetStore()

const content = ref('')
const submitting = ref(false)
const error = ref('')

petStore.fetchList()
const selectedPetId = ref<number | undefined>(undefined)

async function submit() {
  if (!content.value.trim()) { error.value = '说点什么吧'; return }
  error.value = ''
  submitting.value = true
  try {
    const created = await store.createPost({
      content: content.value.trim(),
      pet_id: selectedPetId.value,
    })
    if (created?.id) router.replace({ name: 'post-detail', params: { id: created.id } })
    else router.replace({ name: 'feed' })
  } catch (e: any) {
    error.value = e?.response?.data?.message || e?.message || '发布失败'
  } finally {
    submitting.value = false
  }
}
</script>

<template>
  <div class="post-create">
    <AppHeader title="发布动态" :back="true" />

    <form class="card form" @submit.prevent="submit">
      <textarea v-model="content" rows="6"
                placeholder="今天宠物有什么有趣的事呢？"
                maxlength="500" />
      <p class="muted small">{{ content.length }} / 500</p>

      <label v-if="petStore.list.length">
        <span>关联宠物（可选）</span>
        <select v-model="selectedPetId">
          <option :value="undefined">不指定</option>
          <option v-for="p in petStore.list" :key="p.id" :value="p.id">{{ p.name }}</option>
        </select>
      </label>

      <p v-if="error" class="error">{{ error }}</p>

      <button class="btn" type="submit" :disabled="submitting || !content.trim()">
        {{ submitting ? '发布中…' : '发布' }}
      </button>
    </form>
  </div>
</template>

<style lang="scss" scoped>
.post-create { padding-bottom: 80px; }
.form {
  margin: 16px;
  display: flex; flex-direction: column; gap: 10px;
  textarea {
    border: 1px solid rgba(120,78,16,0.18);
    border-radius: 14px;
    padding: 12px 14px;
    font: inherit;
    background: rgba(255,255,255,0.85);
    resize: vertical; min-height: 140px;
  }
  select {
    border: 1px solid rgba(120,78,16,0.18);
    border-radius: 12px;
    padding: 10px 14px; font-size: 14px;
    background: rgba(255,255,255,0.85);
  }
  label { display: flex; flex-direction: column; gap: 4px; font-size: 13px; color: #6b5742; }
  .error { color: #d83a3a; font-size: 13px; }
  .small { font-size: 12px; align-self: flex-end; }
}
</style>
