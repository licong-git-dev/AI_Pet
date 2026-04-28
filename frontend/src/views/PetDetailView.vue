<script setup lang="ts">
import { onMounted, computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import AppHeader from '@/components/AppHeader.vue'
import Loading from '@/components/Loading.vue'
import { usePetStore } from '@/stores/pet'

const route = useRoute()
const router = useRouter()
const store = usePetStore()
const id = computed(() => Number(route.params.id))

onMounted(() => store.fetchDetail(id.value))

const pet = computed(() => store.detail)

function goAvatar() {
  // 让"分身房间"用这只宠物
  localStorage.setItem('petpal_default_avatar_id', String(id.value))
  router.push({ name: 'room' })
}
</script>

<template>
  <div class="pet-detail">
    <AppHeader title="宠物档案" :back="true" />

    <Loading v-if="store.loading || !pet" />

    <template v-else>
      <section class="hero">
        <div class="avatar">
          <img v-if="pet.avatar" :src="pet.avatar" alt="" />
          <span v-else class="emoji">🐾</span>
        </div>
        <h2>{{ pet.name }}</h2>
        <p class="muted">{{ pet.breed_name || pet.pet_type || '宠物' }}</p>
      </section>

      <section class="card stats">
        <div class="stat">
          <span class="label">年龄</span>
          <span class="value">
            {{ pet.age ? pet.age + ' 岁' : pet.age_months ? pet.age_months + ' 个月' : '—' }}
          </span>
        </div>
        <div class="stat">
          <span class="label">体重</span>
          <span class="value">{{ pet.weight ? pet.weight + ' kg' : '—' }}</span>
        </div>
        <div class="stat">
          <span class="label">健康</span>
          <span class="value">{{ pet.health_status || '良好' }}</span>
        </div>
      </section>

      <section v-if="(pet.personality||[]).length" class="card">
        <h3>性格</h3>
        <div class="tags">
          <span v-for="t in pet.personality" :key="t" class="tag">{{ t }}</span>
        </div>
      </section>

      <button class="btn enter" @click="goAvatar">
        进入 {{ pet.name }} 的分身房间
      </button>
    </template>
  </div>
</template>

<style lang="scss" scoped>
.pet-detail { padding-bottom: 100px; }
.hero {
  text-align: center;
  padding: 24px 16px;
  .avatar {
    width: 100px; height: 100px; margin: 0 auto 12px;
    border-radius: 50%;
    background: linear-gradient(160deg, #ffd8a8, #ffb066);
    display: grid; place-items: center;
    box-shadow: 0 12px 32px rgba(255, 138, 61, 0.25);
    img { width: 100%; height: 100%; border-radius: 50%; object-fit: cover; }
    .emoji { font-size: 56px; }
  }
}
.card {
  margin: 0 16px 16px;
  &.stats {
    display: flex;
    .stat { flex: 1; text-align: center; }
    .label { display: block; font-size: 12px; color: #8a7a6a; }
    .value { display: block; font-size: 18px; font-weight: 600; margin-top: 4px; }
  }
  h3 { font-size: 14px; margin-bottom: 10px; color: #6b5742; }
}
.tags { display: flex; gap: 6px; flex-wrap: wrap; }
.tag {
  font-size: 13px; padding: 4px 10px; border-radius: 999px;
  background: rgba(255,200,150,0.4); color: #c2660b;
}
.enter {
  display: block; margin: 28px auto 0;
  width: calc(100% - 32px); max-width: 320px;
}
</style>
