<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import AppHeader from '@/components/AppHeader.vue'
import { usePetStore } from '@/stores/pet'

const router = useRouter()
const store = usePetStore()

const form = ref({
  name: '',
  pet_type: 'cat',
  breed_name: '',
  gender: 'unknown',
  age: undefined as number | undefined,
  weight: undefined as number | undefined,
})

const submitting = ref(false)
const error = ref('')

async function submit() {
  if (!form.value.name.trim()) { error.value = '名字不能为空'; return }
  error.value = ''
  submitting.value = true
  try {
    const created = await store.createPet({ ...form.value })
    if (created) router.replace({ name: 'pet-detail', params: { id: created.id } })
    else router.replace({ name: 'pets' })
  } catch (e: any) {
    error.value = e?.response?.data?.message || e?.message || '创建失败'
  } finally {
    submitting.value = false
  }
}
</script>

<template>
  <div class="pet-create">
    <AppHeader title="添加宠物" :back="true" />

    <form class="card form" @submit.prevent="submit">
      <label>
        <span>名字</span>
        <input v-model="form.name" placeholder="例如：豆包" maxlength="30" />
      </label>

      <label>
        <span>类型</span>
        <select v-model="form.pet_type">
          <option value="cat">🐱 猫</option>
          <option value="dog">🐶 狗</option>
          <option value="rabbit">🐰 兔子</option>
          <option value="other">🐾 其它</option>
        </select>
      </label>

      <label>
        <span>品种（可选）</span>
        <input v-model="form.breed_name" placeholder="例如：英国短毛猫" />
      </label>

      <div class="row">
        <label>
          <span>性别</span>
          <select v-model="form.gender">
            <option value="unknown">未知</option>
            <option value="male">公</option>
            <option value="female">母</option>
          </select>
        </label>
        <label>
          <span>年龄（岁）</span>
          <input v-model.number="form.age" type="number" min="0" max="40" />
        </label>
        <label>
          <span>体重 (kg)</span>
          <input v-model.number="form.weight" type="number" min="0" step="0.1" />
        </label>
      </div>

      <p v-if="error" class="error">{{ error }}</p>

      <button class="btn" type="submit" :disabled="submitting">
        {{ submitting ? '加入中…' : '把它加入家庭' }}
      </button>
    </form>
  </div>
</template>

<style lang="scss" scoped>
.pet-create { padding-bottom: 80px; }
.form {
  margin: 16px;
  display: flex; flex-direction: column; gap: 12px;
  label { display: flex; flex-direction: column; gap: 4px; font-size: 13px; color: #6b5742; }
  input, select {
    border: 1px solid rgba(120,78,16,0.18);
    border-radius: 12px;
    padding: 10px 14px; font-size: 14px;
    background: rgba(255,255,255,0.85);
  }
  .row { display: flex; gap: 8px; > label { flex: 1; } }
  .error { color: #d83a3a; font-size: 13px; }
  .btn { margin-top: 8px; }
}
</style>
