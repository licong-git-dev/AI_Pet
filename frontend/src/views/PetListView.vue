<script setup lang="ts">
import { onMounted, computed } from 'vue'
import { useRouter } from 'vue-router'
import AppHeader from '@/components/AppHeader.vue'
import EmptyState from '@/components/EmptyState.vue'
import Loading from '@/components/Loading.vue'
import { usePetStore } from '@/stores/pet'

const router = useRouter()
const store = usePetStore()
const pets = computed(() => store.list)

onMounted(() => store.fetchList())

const typeIcon = (t?: string) =>
  t === 'cat' ? '🐱' : t === 'dog' ? '🐶' : t === 'rabbit' ? '🐰' : '🐾'
</script>

<template>
  <div class="pet-list">
    <AppHeader title="我的宠物" right="+ 添加" @right="router.push({ name: 'pet-create' })" />

    <Loading v-if="store.loading && !pets.length" />

    <div v-else-if="!pets.length" class="empty-wrap">
      <EmptyState icon="🐱" title="还没有宠物档案"
                  hint="先把家里的小毛球加进来，分身才能慢慢学会它"
                  action="加入第一只" @action="router.push({ name: 'pet-create' })" />
    </div>

    <ul v-else class="grid">
      <li v-for="p in pets" :key="p.id"
          class="card pet-card"
          @click="router.push({ name: 'pet-detail', params: { id: p.id } })">
        <div class="avatar">
          <img v-if="p.avatar" :src="p.avatar" alt="" />
          <span v-else class="emoji">{{ typeIcon(p.pet_type) }}</span>
        </div>
        <div class="meta">
          <h3>{{ p.name }}</h3>
          <p class="muted">
            {{ p.breed_name || p.pet_type || '宠物' }}
            <template v-if="p.age">· {{ p.age }} 岁</template>
            <template v-else-if="p.age_months">· {{ p.age_months }} 个月</template>
          </p>
          <div class="tags">
            <span v-for="t in (p.personality || []).slice(0,3)" :key="t" class="tag">{{ t }}</span>
          </div>
        </div>
      </li>
    </ul>
  </div>
</template>

<style lang="scss" scoped>
.pet-list { padding-bottom: 80px; }
.empty-wrap { padding-top: 30px; }
.grid {
  list-style: none;
  margin: 0; padding: 16px;
  display: grid; gap: 12px;
}
.pet-card {
  display: flex; gap: 14px; align-items: center;
  padding: 14px;
  cursor: pointer;
  transition: transform 0.15s ease;
  &:active { transform: scale(0.98); }
}
.avatar {
  width: 60px; height: 60px;
  border-radius: 18px;
  background: linear-gradient(160deg, #ffd8a8, #ffb066);
  display: grid; place-items: center;
  flex-shrink: 0;
  overflow: hidden;
  img { width: 100%; height: 100%; object-fit: cover; }
  .emoji { font-size: 32px; }
}
.meta { flex: 1; min-width: 0; }
.meta h3 { font-size: 16px; margin-bottom: 2px; }
.tags { display: flex; gap: 4px; margin-top: 6px; flex-wrap: wrap; }
.tag {
  font-size: 11px;
  padding: 2px 8px;
  border-radius: 999px;
  background: rgba(255,200,150,0.4);
  color: #c2660b;
}
</style>
