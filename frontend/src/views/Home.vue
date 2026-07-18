<template>
  <div class="max-w-6xl mx-auto px-6 py-8">
    <div class="flex flex-col sm:flex-row sm:items-center justify-between gap-4 mb-8 animate-fade-up">
      <div>
        <h1 class="heading-serif text-2xl flex items-center gap-2.5">
          <span>我的书架</span>
          <span class="seal text-[10px] px-1.5 py-0.5 animate-fade-in">
            {{ total }}
          </span>
        </h1>
        <p class="text-ink-400 mt-1.5 text-sm">管理与监控你的 AI 小说创作项目</p>
      </div>
      <div class="flex items-center gap-2">
        <select v-model="typeFilter" class="input w-36 text-sm">
          <option value="">全部类型</option>
          <option v-for="t in types" :key="t" :value="t">{{ t }}</option>
        </select>
        <router-link to="/inspiration" class="btn-secondary text-sm inline-flex items-center gap-1.5">
          <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="2" stroke="currentColor" class="w-3.5 h-3.5 text-vermilion-500">
            <path stroke-linecap="round" stroke-linejoin="round" d="M9.813 15.904L9 21l8.982-11.795H13.82l.93-5.205L5.772 15.904h4.041z" />
          </svg>
          <span>灵感模式</span>
        </router-link>
      </div>
    </div>

    <!-- Loading -->
    <div v-if="loading" class="flex flex-col items-center justify-center py-32 space-y-3">
      <div class="w-8 h-8 border-3 border-ink-200 border-t-vermilion-500 rounded-full animate-spin"></div>
      <p class="text-sm text-ink-400">加载中...</p>
    </div>

    <!-- Empty -->
    <div v-else-if="novels.length === 0" class="text-center py-20 card p-8 animate-fade-up">
      <div class="w-14 h-14 mx-auto mb-5 rounded-xl bg-paper-200 flex items-center justify-center">
        <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor" class="w-7 h-7 text-ink-300">
          <path stroke-linecap="round" stroke-linejoin="round" d="M12 6.042A8.967 8.967 0 006 3.75c-1.052 0-2.062.18-3 .512v14.25A8.987 8.987 0 016 18c2.305 0 4.408.867 6 2.292m0-14.25a8.966 8.966 0 016-2.292c1.052 0 2.062.18 3 .512v14.25A8.987 8.987 0 0018 18a8.967 8.967 0 00-6 2.292m0-14.25v14.25" />
        </svg>
      </div>
      <p class="heading-serif text-lg mb-1">书架空空如也</p>
      <p class="text-ink-400 text-sm mb-6">尚未创建任何小说项目</p>
      <div class="flex items-center justify-center gap-3">
        <router-link to="/create" class="btn-primary inline-flex items-center gap-1.5">
          <span>创建第一本小说</span>
          <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="2" stroke="currentColor" class="w-4 h-4">
            <path stroke-linecap="round" stroke-linejoin="round" d="M12 4.5v15m7.5-7.5h-15" />
          </svg>
        </router-link>
        <router-link to="/inspiration" class="btn-secondary inline-flex items-center gap-1.5">
          <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="2" stroke="currentColor" class="w-4 h-4 text-vermilion-500">
            <path stroke-linecap="round" stroke-linejoin="round" d="M9.813 15.904L9 21l8.982-11.795H13.82l.93-5.205L5.772 15.904h4.041z" />
          </svg>
          <span>灵感向导</span>
        </router-link>
      </div>
    </div>

    <!-- Book Grid -->
    <div v-else class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
      <div
        v-for="(novel, idx) in novels"
        :key="novel.novel_id"
        class="card shine-on-hover p-4 flex gap-4 group hover:border-ink-200 hover:shadow-lg hover:-translate-y-1 animate-fade-up-stagger"
        :style="{ animationDelay: `${Math.min(idx, 8) * 60}ms` }"
      >
        <!-- Book Cover -->
        <div class="shrink-0 w-20 aspect-[3/4] rounded-lg overflow-hidden flex flex-col relative select-none">
          <div :class="['absolute inset-0 flex flex-col justify-between p-2', getGenreClass(novel.novel_type)]">
            <span class="text-[9px] font-medium opacity-70 self-start">
              {{ novel.novel_type }}
            </span>
            <div class="my-auto text-center font-serif text-sm font-bold leading-snug line-clamp-3">
              {{ novel.title }}
            </div>
            <span class="text-[8px] opacity-50 self-center">AI 创作</span>
          </div>
        </div>

        <!-- Metadata -->
        <div class="flex-1 flex flex-col justify-between py-0.5">
          <div class="space-y-1.5">
            <div class="flex items-center justify-between gap-2">
              <span :class="'badge-' + statusClass(novel.status)">{{ statusLabel(novel.status) }}</span>
              <span class="text-[10px] text-ink-300">{{ formatDate(novel.updated_at) }}</span>
            </div>
            <h3 class="font-serif font-bold text-ink-600 text-sm line-clamp-1 group-hover:text-vermilion-600 transition-colors">{{ novel.title }}</h3>
            <p class="text-xs text-ink-400 line-clamp-2 leading-relaxed">
              {{ novel.idea || '暂无简介' }}
            </p>
          </div>

          <div class="flex items-center justify-between border-t border-ink-100 pt-2.5 mt-2">
            <p class="text-[10px] text-ink-300">
              {{ (novel.target_words / 10000).toFixed(0) }} 万字目标
            </p>
            <div class="flex items-center gap-2">
              <router-link
                v-if="novel.status === 'generating' && novel.active_task_id"
                :to="`/task/${novel.active_task_id}`"
                class="text-[11px] font-medium text-vermilion-500 hover:text-vermilion-600 flex items-center gap-1"
                @click.stop
              >
                <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="2.5" stroke="currentColor" class="w-3 h-3 animate-spin">
                  <path stroke-linecap="round" stroke-linejoin="round" d="M16.023 9.348h4.992v-.001M2.985 19.644v-4.992m0 0h4.992m-4.993 0l3.181 3.183a8.25 8.25 0 0013.803-3.7M4.031 9.865a8.25 8.25 0 0113.803-3.7l3.181 3.182m0-4.991v4.99" />
                </svg>
                <span>监控</span>
              </router-link>
              <router-link
                v-else
                :to="`/novels/${novel.novel_id}`"
                class="text-[11px] font-medium text-vermilion-500 hover:text-vermilion-600 flex items-center gap-0.5"
              >
                <span>管理</span>
                <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="2" stroke="currentColor" class="w-3 h-3">
                  <path stroke-linecap="round" stroke-linejoin="round" d="M8.25 4.5l7.5 7.5-7.5 7.5" />
                </svg>
              </router-link>
              <button
                @click.prevent="deleteNovel(novel.novel_id)"
                class="text-ink-300 hover:text-vermilion-500 text-[10px] ml-1 transition-colors"
              >
                删除
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- Pagination -->
    <div v-if="total > limit" class="flex justify-center mt-10 gap-3 items-center">
      <button class="btn-secondary text-xs" :disabled="offset === 0" @click="offset -= limit">上一页</button>
      <span class="text-xs text-ink-400">
        {{ Math.floor(offset / limit) + 1 }} / {{ Math.ceil(total / limit) }}
      </span>
      <button class="btn-secondary text-xs" :disabled="offset + limit >= total" @click="offset += limit">下一页</button>
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

function getGenreClass(type) {
  const map = {
    '玄幻': 'genre-xuanhuan',
    '仙侠': 'genre-xianxia',
    '科幻': 'genre-kehuan',
    '都市': 'genre-dushi',
    '言情': 'genre-yanqing',
  }
  return map[type] || 'bg-paper-100 text-ink-600'
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
