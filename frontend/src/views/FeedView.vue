<script setup lang="ts">
import { onMounted, computed } from 'vue'
import { useRouter } from 'vue-router'
import AppHeader from '@/components/AppHeader.vue'
import EmptyState from '@/components/EmptyState.vue'
import Loading from '@/components/Loading.vue'
import { usePostStore } from '@/stores/post'

const router = useRouter()
const store = usePostStore()
const feed = computed(() => store.feed)

onMounted(() => store.fetchFeed(true))

function relTime(s?: string): string {
  if (!s) return ''
  const t = new Date(s).getTime()
  const diff = (Date.now() - t) / 1000
  if (diff < 60) return '刚刚'
  if (diff < 3600) return `${Math.floor(diff/60)} 分钟前`
  if (diff < 86400) return `${Math.floor(diff/3600)} 小时前`
  return `${Math.floor(diff/86400)} 天前`
}
</script>

<template>
  <div class="feed">
    <AppHeader title="宠物社区" right="发动态" @right="router.push({ name: 'post-create' })" />

    <Loading v-if="store.loading && !feed.length" />

    <EmptyState v-else-if="!feed.length" icon="🐾" title="还没有动态"
                hint="发出第一条，让大家也认识你家小毛球"
                action="去发布" @action="router.push({ name: 'post-create' })" />

    <ul v-else class="list">
      <li v-for="p in feed" :key="p.id" class="card post"
          @click="router.push({ name: 'post-detail', params: { id: p.id } })">
        <header>
          <div class="ava"><span>🐾</span></div>
          <div>
            <h4>{{ p.user_name || '主人' }}</h4>
            <p class="muted small">{{ relTime(p.created_at) }}</p>
          </div>
        </header>
        <p class="content">{{ p.content }}</p>
        <div v-if="p.images && p.images.length" class="imgs">
          <img v-for="(src, i) in p.images.slice(0,3)" :key="i" :src="src" loading="lazy" />
        </div>
        <footer @click.stop>
          <button :class="['act', { liked: p.is_liked }]" @click="store.toggleLike(p)">
            ♥ {{ p.like_count || 0 }}
          </button>
          <span class="act">💬 {{ p.comment_count || 0 }}</span>
        </footer>
      </li>
    </ul>
  </div>
</template>

<style lang="scss" scoped>
.feed { padding-bottom: 80px; }
.list {
  list-style: none; margin: 0; padding: 16px;
  display: flex; flex-direction: column; gap: 12px;
}
.post {
  cursor: pointer;
  &:active { transform: scale(0.99); }
  header { display: flex; gap: 10px; align-items: center; margin-bottom: 8px; }
  h4 { font-size: 14px; }
  .ava {
    width: 36px; height: 36px;
    background: linear-gradient(160deg, #ffd8a8, #ffb066);
    border-radius: 50%;
    display: grid; place-items: center;
  }
  .content { font-size: 14px; line-height: 1.6; color: #2b2b2b; white-space: pre-wrap; }
  .imgs {
    display: grid; grid-template-columns: repeat(3, 1fr); gap: 4px;
    margin-top: 8px;
    img { width: 100%; aspect-ratio: 1/1; object-fit: cover; border-radius: 8px; }
  }
  footer {
    display: flex; gap: 16px;
    margin-top: 12px;
    padding-top: 8px;
    border-top: 1px solid rgba(120,78,16,0.08);
  }
  .act {
    background: none; border: none;
    color: #8a7a6a; font-size: 13px;
    padding: 0;
    &.liked { color: #ff5f5f; font-weight: 600; }
  }
  .small { font-size: 12px; }
}
</style>
