<template>
  <div class="max-w-6xl mx-auto px-6 py-10">
    <div class="flex items-center justify-between mb-8">
      <div>
        <h1 class="text-2xl font-bold text-ink-900">我的书架</h1>
        <p class="text-ink-500 mt-1">管理你的 AI 小说项目</p>
      </div>
      <div class="flex items-center gap-3">
        <select v-model="typeFilter" class="input w-28 text-sm">
          <option value="">全部类型</option>
          <option v-for="t in types" :key="t" :value="t">{{ t }}</option>
        </select>
      </div>
    </div>

    <div v-if="loading" class="text-center py-20 text-ink-500">加载中...</div>

    <div v-else-if="novels.length === 0" class="text-center py-20">
      <p class="text-ink-400 text-lg mb-4">书架空空如也</p>
      <router-link to="/create" class="btn-primary">创建第一本小说</router-link>
    </div>

    <div v-else class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
      <router-link
        v-for="novel in novels"
        :key="novel.novel_id"
        :to="`/novels/${novel.novel_id}`"
        class="card p-5 group"
      >
        <div class="flex items-start justify-between mb-3">
          <span :class="'badge-' + statusClass(novel.status)">{{ statusLabel(novel.status) }}</span>
          <span class="text-xs text-ink-400">{{ novel.novel_type }}</span>
        </div>
        <h3 class="font-bold text-ink-800 group-hover:text-primary-600 transition-colors mb-2 line-clamp-1">
          {{ novel.title }}
        </h3>
        <div class="flex justify-between items-center">
          <p class="text-xs text-ink-500">
            {{ (novel.target_words / 10000).toFixed(0) }} 万字目标
            &middot; {{ formatDate(novel.updated_at) }}
          </p>
          <button @click.prevent="deleteNovel(novel.novel_id)" class="text-red-400 hover:text-red-600 text-xs">删除</button>
        </div>
      </router-link>
    </div>

    <div v-if="total > limit" class="flex justify-center mt-8 gap-2">
      <button class="btn-secondary text-sm" :disabled="offset === 0" @click="offset -= limit">上一页</button>
      <span class="px-4 py-2 text-sm text-ink-500">{{ Math.floor(offset / limit) + 1 }} / {{ Math.ceil(total / limit) }}</span>
      <button class="btn-secondary text-sm" :disabled="offset + limit >= total" @click="offset += limit">下一页</button>
    </div>
  </div>
</template>

<script setup>
import { ref, watch, onMounted } from 'vue'

const novels = ref([])
const total = ref(0)
const loading = ref(true)
const typeFilter = ref('')
const offset = ref(0)
const limit = 12
const types = ['玄幻', '仙侠', '都市', '科幻', '历史', '武侠', '言情', '悬疑', '军事', '游戏', '竞技', '灵异', '同人']

function statusClass(s) {
  return { draft: 'pending', generating: 'running', completed: 'completed', failed: 'failed' }[s] || 'pending'
}
function statusLabel(s) {
  return { draft: '草稿', generating: '生成中', completed: '已完成', failed: '失败' }[s] || s
}
function formatDate(iso) {
  if (!iso) return ''
  return new Date(iso).toLocaleDateString('zh-CN', { month: 'short', day: 'numeric' })
}

async function fetchNovels() {
  loading.value = true
  try {
    const params = new URLSearchParams({ limit, offset: offset.value })
    if (typeFilter.value) params.set('novel_type', typeFilter.value)
    const res = await fetch(`/api/v1/projects?${params}`)
    const data = await res.json()
    novels.value = data.novels
    total.value = data.total
  } finally {
    loading.value = false
  }
}

async function deleteNovel(novelId) {
  if (!confirm('确定删除这本小说？所有相关数据将被永久删除。')) return
  await fetch(`/api/v1/projects/${novelId}`, { method: 'DELETE' })
  await fetchNovels()
}

watch([typeFilter, offset], () => fetchNovels())
onMounted(fetchNovels)
</script>
