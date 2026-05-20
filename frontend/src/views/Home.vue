<template>
  <div class="max-w-6xl mx-auto px-6 py-10">
    <div class="flex flex-col sm:flex-row sm:items-center justify-between gap-4 mb-10">
      <div>
        <h1 class="text-3xl font-extrabold tracking-tight text-slate-100 flex items-center gap-3">
          <span>我的书架</span>
          <span class="text-xs font-semibold bg-purple-500/10 text-purple-400 px-2.5 py-0.5 rounded-full border border-purple-500/20">
            {{ total }} 本作品
          </span>
        </h1>
        <p class="text-slate-400 mt-1.5 text-sm font-medium">管理与监控你的 AI 小说创作项目</p>
      </div>
      <div class="flex items-center gap-3">
        <select v-model="typeFilter" class="input w-36 text-sm bg-slate-900/60 border-slate-800 text-slate-200">
          <option value="">全部类型</option>
          <option v-for="t in types" :key="t" :value="t">{{ t }}</option>
        </select>
      </div>
    </div>

    <!-- Loading State -->
    <div v-if="loading" class="flex flex-col items-center justify-center py-32 space-y-4">
      <div class="w-10 h-10 border-4 border-purple-500 border-t-transparent rounded-full animate-spin"></div>
      <p class="text-sm text-slate-400 font-medium">书架整理中...</p>
    </div>

    <!-- Empty State -->
    <div v-else-if="novels.length === 0" class="text-center py-24 glass-panel rounded-3xl p-8 border border-slate-900">
      <div class="w-16 h-16 mx-auto mb-6 rounded-2xl bg-purple-500/10 flex items-center justify-center border border-purple-500/20">
        <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor" class="w-8 h-8 text-purple-400">
          <path stroke-linecap="round" stroke-linejoin="round" d="M12 6.042A8.967 8.967 0 006 3.75c-1.052 0-2.062.18-3 .512v14.25A8.987 8.987 0 016 18c2.305 0 4.408.867 6 2.292m0-14.25a8.966 8.966 0 016-2.292c1.052 0 2.062.18 3 .512v14.25A8.987 8.987 0 0018 18a8.967 8.967 0 00-6 2.292m0-14.25v14.25" />
        </svg>
      </div>
      <p class="text-slate-300 text-xl font-bold mb-2">书架空空如也</p>
      <p class="text-slate-500 text-sm mb-6 max-w-sm mx-auto">尚未创建任何小说项目，立即开启你的第一部 AI 奇幻史诗吧！</p>
      <router-link to="/create" class="btn-primary inline-flex items-center gap-2">
        <span>创建第一本小说</span>
        <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="2" stroke="currentColor" class="w-4 h-4">
          <path stroke-linecap="round" stroke-linejoin="round" d="M12 4.5v15m7.5-7.5h-15" />
        </svg>
      </router-link>
    </div>

    <!-- Bookshelf Grid -->
    <div v-else class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
      <div
        v-for="novel in novels"
        :key="novel.novel_id"
        :class="[
          'card p-4 flex gap-4 glass-card-hover group relative overflow-hidden',
          novel.status === 'generating' ? 'generating-halo' : ''
        ]"
      >
        <!-- Left: Realistic Stylized Typographic Vertical Book Cover Card -->
        <div class="shrink-0 w-24 aspect-[3/4] rounded-xl overflow-hidden shadow-lg border border-slate-850 flex flex-col relative select-none z-10">
          <div :class="['absolute inset-0 flex flex-col justify-between p-2.5 text-white', getGenreClass(novel.novel_type)]">
            <span class="text-[9px] font-bold bg-white/10 backdrop-blur-sm self-start px-1.5 py-0.5 rounded border border-white/5 tracking-wider">
              {{ novel.novel_type }}
            </span>
            <div class="my-auto text-center font-serif text-sm font-extrabold leading-snug tracking-wide line-clamp-3">
              {{ novel.title }}
            </div>
            <span class="text-[8px] opacity-60 self-center tracking-wider font-semibold">
              AI 创作组
            </span>
          </div>
          <!-- Shimmer glow on cover hover -->
          <div class="absolute inset-0 bg-gradient-to-r from-transparent via-white/5 to-transparent -translate-x-full group-hover:translate-x-full transition-transform duration-1000 ease-out"></div>
        </div>

        <!-- Right: Book Metadata -->
        <div class="flex-1 flex flex-col justify-between py-0.5 z-10">
          <div class="space-y-2">
            <div class="flex items-center justify-between gap-2">
              <span :class="'badge-' + statusClass(novel.status)">{{ statusLabel(novel.status) }}</span>
              <span class="text-[10px] text-slate-500 font-semibold tracking-wide font-mono">{{ formatDate(novel.updated_at) }}</span>
            </div>
            
            <h3 class="font-extrabold text-slate-200 text-base group-hover:text-purple-400 transition-colors duration-200 line-clamp-1">
              {{ novel.title }}
            </h3>
            
            <p class="text-xs text-slate-400 line-clamp-2 leading-relaxed">
              {{ novel.idea || '暂无作品设定简介' }}
            </p>
          </div>

          <!-- Interactive Actions / Task Redirection -->
          <div class="flex items-center justify-between border-t border-slate-900/60 pt-3 mt-2">
            <p class="text-[10px] text-slate-500 font-semibold">
              {{ (novel.target_words / 10000).toFixed(0) }} 万字目标
            </p>
            
            <div class="flex items-center gap-2">
              <!-- If actively generating, provide a shortcut link directly to the task dashboard! -->
              <router-link
                v-if="novel.status === 'generating' && novel.active_task_id"
                :to="`/task/${novel.active_task_id}`"
                class="text-[11px] font-bold text-purple-400 hover:text-purple-300 flex items-center gap-1 bg-purple-500/10 px-2.5 py-1 rounded-lg border border-purple-500/20"
                @click.stop
              >
                <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="2.5" stroke="currentColor" class="w-3.5 h-3.5 animate-spin">
                  <path stroke-linecap="round" stroke-linejoin="round" d="M16.023 9.348h4.992v-.001M2.985 19.644v-4.992m0 0h4.992m-4.993 0l3.181 3.183a8.25 8.25 0 0013.803-3.7M4.031 9.865a8.25 8.25 0 0113.803-3.7l3.181 3.182m0-4.991v4.99" />
                </svg>
                <span>监控进度</span>
              </router-link>
              
              <router-link
                v-else
                :to="`/novels/${novel.novel_id}`"
                class="text-[11px] font-bold text-purple-400 hover:text-purple-300 flex items-center gap-0.5"
              >
                <span>管理</span>
                <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="2" stroke="currentColor" class="w-3 h-3 group-hover:translate-x-0.5 transition-transform">
                  <path stroke-linecap="round" stroke-linejoin="round" d="M8.25 4.5l7.5 7.5-7.5 7.5" />
                </svg>
              </router-link>

              <button 
                @click.prevent="deleteNovel(novel.novel_id)" 
                class="text-slate-650 hover:text-rose-450 text-[10px] ml-2 transition-colors duration-200"
              >
                删除
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- Pagination -->
    <div v-if="total > limit" class="flex justify-center mt-12 gap-3 items-center">
      <button class="btn-secondary text-xs py-2 px-4" :disabled="offset === 0" @click="offset -= limit">上一页</button>
      <span class="text-xs text-slate-500 font-semibold tracking-wider font-mono">
        {{ Math.floor(offset / limit) + 1 }} / {{ Math.ceil(total / limit) }}
      </span>
      <button class="btn-secondary text-xs py-2 px-4" :disabled="offset + limit >= total" @click="offset += limit">下一页</button>
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
  return map[type] || 'bg-gradient-to-br from-indigo-950 to-slate-900'
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
