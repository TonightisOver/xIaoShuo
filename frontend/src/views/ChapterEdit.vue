<template>
  <div class="max-w-7xl mx-auto px-6 py-10">
    <div v-if="!chapter" class="text-center py-20 text-slate-500">章节不存在</div>

    <template v-else>
      <!-- Top header layout -->
      <div class="flex flex-col md:flex-row md:items-center justify-between gap-4 mb-8">
        <div>
          <div class="flex items-center gap-2 mb-1.5">
            <router-link :to="`/novels/${novelId}`" class="text-xs text-purple-400 hover:text-purple-300 font-semibold flex items-center gap-1 group">
              <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="2.5" stroke="currentColor" class="w-3.5 h-3.5 group-hover:-translate-x-0.5 transition-transform">
                <path stroke-linecap="round" stroke-linejoin="round" d="M15.75 19.5L8.25 12l7.5-7.5" />
              </svg>
              返回作品详情
            </router-link>
          </div>
          <h1 class="text-2xl font-extrabold text-slate-100">
            {{ chapter.volume_number ? `第${chapter.volume_number}卷 · ` : '' }}第{{ chapter.chapter_number }}章：{{ chapter.title }}
          </h1>
          <p class="text-xs text-slate-400 mt-2 flex items-center gap-2 font-medium">
            <span>{{ contentLength }} 字</span>
            <span class="text-slate-700">|</span>
            <span>共 {{ sortedChapters.length }} 章</span>
          </p>
        </div>
        <div class="flex items-center gap-3">
          <button @click="regenerate" class="btn-secondary text-sm flex items-center gap-1.5" :disabled="regenerating">
            <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="2" stroke="currentColor" class="w-4 h-4" :class="{'animate-spin': regenerating}">
              <path stroke-linecap="round" stroke-linejoin="round" d="M16.023 9.348h4.992v-.001M2.985 19.644v-4.992m0 0h4.992m-4.993 0l3.181 3.183a8.25 8.25 0 0013.803-3.7M4.031 9.865a8.25 8.25 0 0113.803-3.7l3.181 3.182m0-4.991v4.99" />
            </svg>
            <span>{{ regenerating ? '生成中...' : '重新生成' }}</span>
          </button>
          <button @click="deleteChapter" class="text-rose-500 hover:text-rose-400 text-sm px-3 py-2 transition-colors font-medium">删除</button>
          <button @click="save" class="btn-primary text-sm flex items-center gap-1.5" :disabled="saving">
            <span>{{ saving ? '保存中...' : '保存修改' }}</span>
          </button>
        </div>
      </div>

      <!-- Main Layout: Sidebar & Content Editor -->
      <div class="grid grid-cols-1 lg:grid-cols-4 gap-8">
        <!-- Directory Sidebar (小说目录) -->
        <div class="lg:col-span-1">
          <div class="card p-5 sticky top-24 max-h-[calc(100vh-12rem)] flex flex-col bg-slate-900/50 backdrop-blur-md">
            <h2 class="text-sm font-bold text-slate-200 mb-4 pb-2.5 border-b border-slate-800/80 flex items-center justify-between">
              <span class="flex items-center gap-2">
                <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="2" stroke="currentColor" class="w-4 h-4 text-purple-400">
                  <path stroke-linecap="round" stroke-linejoin="round" d="M8.25 6.75h12M8.25 12h12m-12 5.25h12M3.75 6.75h.007v.008H3.75V6.75zm.375 0a.375.375 0 11-.75 0 .375.375 0 01.75 0zM3.75 12h.007v.008H3.75V12zm.375 0a.375.375 0 11-.75 0 .375.375 0 01.75 0zm-.375 5.25h.007v.008H3.75v-.008zm.375 0a.375.375 0 11-.75 0 .375.375 0 01.75 0z" />
                </svg>
                <span>目录导航</span>
              </span>
              <span class="text-[10px] bg-slate-800 text-slate-400 px-2 py-0.5 rounded-full font-semibold">TOC</span>
            </h2>
            
            <div class="overflow-y-auto flex-1 space-y-4 pr-1.5 custom-scrollbar">
              <div v-for="group in groupedChapters" :key="group.title" class="space-y-1.5">
                <div class="text-[11px] font-bold text-slate-500 tracking-wider uppercase pl-1 pt-2 pb-1 border-b border-slate-800/40">
                  {{ group.title }}
                </div>
                <div 
                  v-for="ch in group.chapters" 
                  :key="ch.chapter_number"
                  @click="goToChapter(ch.chapter_number)"
                  :class="[
                    'px-3 py-2.5 rounded-xl text-xs cursor-pointer transition-all duration-200 flex items-center justify-between',
                    ch.chapter_number === parseInt(chapterNum)
                      ? 'bg-purple-500/20 text-purple-300 border border-purple-500/30 font-semibold'
                      : 'text-slate-400 hover:bg-slate-800/40 hover:text-slate-200 border border-transparent'
                  ]"
                >
                  <span class="truncate pr-2">第{{ ch.chapter_number }}章：{{ ch.title }}</span>
                  <span class="text-[10px] text-slate-500 font-mono shrink-0">{{ ch.content ? ch.content.length : 0 }}字</span>
                </div>
              </div>
            </div>
          </div>
        </div>

        <!-- Content Area -->
        <div class="lg:col-span-3 space-y-6">
          <div class="card p-1 bg-slate-950/20 border-slate-800/60 shadow-inner">
            <textarea
              v-model="content"
              class="w-full min-h-[600px] p-6 md:p-8 text-base leading-relaxed font-serif bg-transparent text-slate-100 resize-y border-0 focus:outline-none focus:ring-0 focus:border-0"
              placeholder="章节内容..."
            ></textarea>
          </div>

          <!-- Bottom Navigation: 前后章切换按钮 -->
          <div class="flex flex-col sm:flex-row items-center justify-between gap-4 py-6 border-t border-slate-900">
            <div class="w-full sm:w-auto">
              <button 
                v-if="prevChapter" 
                @click="goToChapter(prevChapter.chapter_number)"
                class="w-full btn-secondary text-sm flex items-center justify-center gap-2 group py-3 px-5"
              >
                <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="2.5" stroke="currentColor" class="w-4 h-4 group-hover:-translate-x-0.5 transition-transform text-purple-400">
                  <path stroke-linecap="round" stroke-linejoin="round" d="M15.75 19.5L8.25 12l7.5-7.5" />
                </svg>
                <span>上一章：{{ prevChapter.title }}</span>
              </button>
              <span v-else class="text-xs text-slate-600 font-semibold block text-center sm:text-left py-2">已是第一章</span>
            </div>

            <div class="order-first sm:order-none">
              <p v-if="saved" class="text-sm text-emerald-400 font-semibold flex items-center justify-center gap-1.5">
                <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="3" stroke="currentColor" class="w-4 h-4 animate-bounce">
                  <path stroke-linecap="round" stroke-linejoin="round" d="M4.5 12.75l6 6 9-13.5" />
                </svg>
                <span>内容已自动保存（{{ contentLength }} 字）</span>
              </p>
            </div>

            <div class="w-full sm:w-auto">
              <button 
                v-if="nextChapter" 
                @click="goToChapter(nextChapter.chapter_number)"
                class="w-full btn-secondary text-sm flex items-center justify-center gap-2 group py-3 px-5"
              >
                <span>下一章：{{ nextChapter.title }}</span>
                <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="2.5" stroke="currentColor" class="w-4 h-4 group-hover:translate-x-0.5 transition-transform text-purple-400">
                  <path stroke-linecap="round" stroke-linejoin="round" d="M8.25 4.5l7.5 7.5-7.5 7.5" />
                </svg>
              </button>
              <span v-else class="text-xs text-slate-600 font-semibold block text-center sm:text-right py-2">已是最后一章</span>
            </div>
          </div>
        </div>
      </div>
    </template>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'

const route = useRoute()
const router = useRouter()
const novelId = computed(() => route.params.id)
const chapterNum = computed(() => route.params.num)

const chapter = ref(null)
const content = ref('')
const allChapters = ref([])
const allVolumes = ref([])
const saving = ref(false)
const saved = ref(false)
const regenerating = ref(false)

const contentLength = computed(() => content.value.length)

async function load() {
  const res = await fetch(`/api/v1/projects/${novelId.value}/chapters/${chapterNum.value}`)
  if (res.ok) {
    chapter.value = await res.json()
    content.value = chapter.value.content || ''
  } else {
    chapter.value = null
    content.value = ''
  }
}

async function loadAllChapters() {
  const res = await fetch(`/api/v1/projects/${novelId.value}/chapters`)
  if (res.ok) {
    allChapters.value = await res.json()
  }
}

async function loadVolumes() {
  const res = await fetch(`/api/v1/projects/${novelId.value}/volumes`)
  if (res.ok) {
    allVolumes.value = await res.json()
  } else {
    allVolumes.value = []
  }
}

const sortedChapters = computed(() => {
  return [...allChapters.value].sort((a, b) => a.chapter_number - b.chapter_number)
})

const groupedChapters = computed(() => {
  const groups = []
  const sorted = sortedChapters.value
  
  if (allVolumes.value.length === 0) {
    groups.push({
      title: '正文目录',
      chapters: sorted
    })
    return groups
  }
  
  const volMap = new Map()
  for (const vol of allVolumes.value) {
    volMap.set(vol.volume_number, vol)
  }
  
  const volumeGroups = {}
  const unassigned = []
  
  for (const ch of sorted) {
    const volNum = ch.volume_number
    if (volNum && volMap.has(volNum)) {
      if (!volumeGroups[volNum]) {
        volumeGroups[volNum] = []
      }
      volumeGroups[volNum].push(ch)
    } else {
      unassigned.push(ch)
    }
  }
  
  const sortedVolNums = Object.keys(volumeGroups).map(Number).sort((a, b) => a - b)
  for (const volNum of sortedVolNums) {
    const vol = volMap.get(volNum)
    groups.push({
      volume_number: volNum,
      title: `第${volNum}卷 · ${vol.title || '未命名'}`,
      chapters: volumeGroups[volNum]
    })
  }
  
  if (unassigned.length > 0) {
    groups.push({
      title: '未分卷章节',
      chapters: unassigned
    })
  }
  
  return groups
})

const currentIdx = computed(() => {
  if (!chapter.value) return -1
  return sortedChapters.value.findIndex(c => c.chapter_number === chapter.value.chapter_number)
})

const prevChapter = computed(() => {
  const idx = currentIdx.value
  if (idx > 0) return sortedChapters.value[idx - 1]
  return null
})

const nextChapter = computed(() => {
  const idx = currentIdx.value
  if (idx !== -1 && idx < sortedChapters.value.length - 1) return sortedChapters.value[idx + 1]
  return null
})

function goToChapter(num) {
  router.push(`/novels/${novelId.value}/chapters/${num}`)
}

async function save() {
  saving.value = true
  saved.value = false
  await fetch(`/api/v1/projects/${novelId.value}/chapters/${chapterNum.value}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ content: content.value, title: chapter.value.title }),
  })
  saving.value = false
  saved.value = true
  setTimeout(() => { saved.value = false }, 2000)
  
  // Reload all chapters to update word counts in sidebar
  loadAllChapters()
}

async function regenerate() {
  if (!confirm('重新生成将覆盖当前内容，确定吗？')) return
  regenerating.value = true
  const res = await fetch(`/api/v1/projects/${novelId.value}/generate-chapters`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ chapter_start: parseInt(chapterNum.value), chapter_end: parseInt(chapterNum.value) }),
  })
  if (res.ok) {
    const data = await res.json()
    router.push(`/task/${data.task_id}`)
  }
  regenerating.value = false
}

async function deleteChapter() {
  if (!confirm('确定删除本章？此操作不可恢复。')) return
  await fetch(`/api/v1/projects/${novelId.value}/chapters/${chapterNum.value}`, { method: 'DELETE' })
  router.push(`/novels/${novelId.value}`)
}

// Watch novelId to load both chapters and volumes
watch(novelId, (newId) => {
  if (newId) {
    loadAllChapters()
    loadVolumes()
  }
}, { immediate: true })

// Watch route params changes to load the correct chapter content
watch([novelId, chapterNum], () => {
  load()
}, { immediate: true })
</script>

<style scoped>
.custom-scrollbar::-webkit-scrollbar {
  width: 5px;
}
.custom-scrollbar::-webkit-scrollbar-track {
  background: transparent;
}
.custom-scrollbar::-webkit-scrollbar-thumb {
  background: rgba(255, 255, 255, 0.1);
  border-radius: 9999px;
}
.custom-scrollbar::-webkit-scrollbar-thumb:hover {
  background: rgba(255, 255, 255, 0.2);
}
</style>
