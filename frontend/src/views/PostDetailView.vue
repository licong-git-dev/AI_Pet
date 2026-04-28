<script setup lang="ts">
import { onMounted, computed } from 'vue'
import { useRoute } from 'vue-router'
import AppHeader from '@/components/AppHeader.vue'
import Loading from '@/components/Loading.vue'
import { usePostStore } from '@/stores/post'

const route = useRoute()
const store = usePostStore()
const id = computed(() => Number(route.params.id))

onMounted(() => store.fetchDetail(id.value))

const post = computed(() => store.detail)
</script>

<template>
  <div class="post-detail">
    <AppHeader title="动态详情" :back="true" />

    <Loading v-if="store.loading || !post" />

    <article v-else class="card">
      <header>
        <div class="ava"><span>🐾</span></div>
        <div>
          <h4>{{ post.user_name || '主人' }}</h4>
          <p class="muted small">{{ post.created_at }}</p>
        </div>
      </header>
      <p class="content">{{ post.content }}</p>
      <div v-if="post.images && post.images.length" class="imgs">
        <img v-for="(s, i) in post.images" :key="i" :src="s" />
      </div>
      <footer>
        <span class="act" :class="{ liked: post.is_liked }" @click="store.toggleLike(post)">
          ♥ {{ post.like_count || 0 }}
        </span>
        <span class="act">💬 {{ post.comment_count || 0 }}</span>
      </footer>
    </article>
  </div>
</template>

<style lang="scss" scoped>
.post-detail { padding: 16px 16px 80px; }
.card header { display: flex; gap: 10px; align-items: center; margin-bottom: 10px; }
.ava {
  width: 40px; height: 40px;
  background: linear-gradient(160deg, #ffd8a8, #ffb066);
  border-radius: 50%; display: grid; place-items: center;
}
.content { font-size: 15px; line-height: 1.7; white-space: pre-wrap; margin-bottom: 12px; }
.imgs img { width: 100%; border-radius: 12px; margin-bottom: 8px; }
footer {
  display: flex; gap: 16px;
  padding-top: 10px;
  border-top: 1px solid rgba(120,78,16,0.08);
}
.act {
  font-size: 14px; color: #8a7a6a; cursor: pointer;
  &.liked { color: #ff5f5f; font-weight: 600; }
}
.small { font-size: 12px; }
</style>
