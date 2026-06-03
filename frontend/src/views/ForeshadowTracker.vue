<template>
  <div class="min-h-screen bg-neutral-50">
    <div class="mx-auto max-w-6xl px-6 py-10">
      <div class="mb-8 flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <router-link
            :to="`/novels/${novelId}`"
            class="group mb-3 inline-flex items-center gap-1.5 text-sm font-semibold text-accent-600 hover:text-accent-700"
          >
            <svg class="h-4 w-4 transition-transform group-hover:-translate-x-0.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" aria-hidden="true">
              <path stroke-linecap="round" stroke-linejoin="round" d="M15.75 19.5 8.25 12l7.5-7.5" />
            </svg>
            返回作品详情
          </router-link>
          <h1 class="text-3xl font-extrabold tracking-tight text-neutral-950">伏笔追踪</h1>
          <p class="mt-2 text-sm text-neutral-500">追踪已种下、已回收和悬而未解的故事线索。</p>
        </div>

        <button
          class="inline-flex items-center justify-center rounded-xl border border-neutral-200 bg-white px-4 py-2 text-sm font-semibold text-neutral-700 shadow-sm transition hover:border-neutral-300 hover:bg-neutral-100 disabled:cursor-not-allowed disabled:opacity-60"
          type="button"
          :disabled="loading"
          @click="loadForeshadows"
        >
          刷新
        </button>
      </div>

      <div v-if="loading" class="rounded-xl border border-neutral-200 bg-white p-12 text-center shadow-sm">
        <div class="mx-auto h-10 w-10 animate-spin rounded-full border-4 border-accent-600 border-t-transparent"></div>
        <p class="mt-4 text-sm font-medium text-neutral-500">正在加载伏笔数据...</p>
      </div>

      <div v-else-if="error" class="rounded-xl border border-red-200 bg-white p-8 text-center shadow-sm">
        <p class="text-sm font-semibold text-red-600">{{ error }}</p>
        <button
          class="mt-4 rounded-xl border border-red-200 bg-red-50 px-4 py-2 text-sm font-semibold text-red-700 transition hover:bg-red-100"
          type="button"
          @click="loadForeshadows"
        >
          重试
        </button>
      </div>

      <template v-else>
        <div class="mb-8 grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
          <div class="rounded-xl border border-neutral-200 bg-white p-5 shadow-sm transition hover:-translate-y-0.5 hover:shadow-md">
            <p class="text-xs font-bold uppercase tracking-wider text-neutral-400">总计</p>
            <p class="mt-3 text-4xl font-extrabold text-neutral-950">{{ totalCount }}</p>
            <p class="mt-1 text-xs text-neutral-500">追踪中的伏笔</p>
          </div>

          <div class="rounded-xl border border-neutral-200 bg-white p-5 shadow-sm transition hover:-translate-y-0.5 hover:shadow-md">
            <p class="text-xs font-bold uppercase tracking-wider text-neutral-400">已回收</p>
            <p class="mt-3 text-4xl font-extrabold text-blue-600">{{ resolvedCount }}</p>
            <p class="mt-1 text-xs text-neutral-500">已经完成回收</p>
          </div>

          <div class="rounded-xl border border-neutral-200 bg-white p-5 shadow-sm transition hover:-translate-y-0.5 hover:shadow-md">
            <p class="text-xs font-bold uppercase tracking-wider text-neutral-400">悬挂</p>
            <p class="mt-3 text-4xl font-extrabold text-red-600">{{ danglingCount }}</p>
            <p class="mt-1 text-xs text-neutral-500">需要关注</p>
          </div>

          <div class="flex items-center justify-between rounded-xl border border-neutral-200 bg-white p-5 shadow-sm transition hover:-translate-y-0.5 hover:shadow-md">
            <div>
              <p class="text-xs font-bold uppercase tracking-wider text-neutral-400">回收率</p>
              <p class="mt-3 text-4xl font-extrabold text-neutral-950">{{ resolutionPercent }}%</p>
            </div>
            <div class="relative h-20 w-20">
              <svg class="h-20 w-20 -rotate-90" viewBox="0 0 80 80" aria-hidden="true">
                <circle cx="40" cy="40" r="32" fill="none" stroke="currentColor" stroke-width="8" class="text-neutral-100" />
                <circle
                  cx="40"
                  cy="40"
                  r="32"
                  fill="none"
                  stroke="currentColor"
                  stroke-width="8"
                  stroke-linecap="round"
                  class="text-accent-600 transition-all duration-700"
                  :stroke-dasharray="progressCircumference"
                  :stroke-dashoffset="progressOffset"
                />
              </svg>
              <span class="absolute inset-0 flex items-center justify-center text-sm font-extrabold text-accent-700">{{ resolutionPercent }}%</span>
            </div>
          </div>
        </div>

        <div v-if="totalCount === 0" class="rounded-xl border border-neutral-200 bg-white p-12 text-center shadow-sm">
          <div class="mx-auto flex h-14 w-14 items-center justify-center rounded-xl bg-neutral-100 text-neutral-500">
            <svg class="h-7 w-7" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" aria-hidden="true">
              <path stroke-linecap="round" stroke-linejoin="round" d="M12 6.042A8.967 8.967 0 0 0 6 3.75c-1.052 0-2.062.18-3 .512v14.25A8.987 8.987 0 0 1 6 18c2.305 0 4.408.867 6 2.292m0-14.25A8.966 8.966 0 0 1 18 3.75c1.052 0 2.062.18 3 .512v14.25A8.987 8.987 0 0 0 18 18a8.967 8.967 0 0 0-6 2.292m0-14.25v14.25" />
            </svg>
          </div>
          <h2 class="mt-5 text-base font-bold text-neutral-900">暂未检测到伏笔</h2>
          <p class="mt-2 text-sm text-neutral-500">生成更多章节后，系统会自动追踪已种下和未回收的线索。</p>
        </div>

        <template v-else>
          <div class="mb-6 rounded-xl border border-neutral-200 bg-white px-4 pt-4 shadow-sm">
            <nav class="flex gap-3 overflow-x-auto pb-4" role="tablist">
              <button
                v-for="tab in tabs"
                :key="tab.id"
                type="button"
                role="tab"
                :aria-selected="activeTab === tab.id"
                class="inline-flex items-center gap-2 rounded-xl border px-4 py-2 text-sm font-bold transition"
                :class="activeTab === tab.id ? tab.activeClass : 'border-neutral-200 bg-white text-neutral-500 hover:bg-neutral-50'"
                @click="activeTab = tab.id"
              >
                <svg v-if="tab.id === 'dangling'" class="h-4 w-4 text-red-500" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true">
                  <path stroke-linecap="round" stroke-linejoin="round" d="M12 9v4m0 4h.01M10.29 3.86 1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0Z" />
                </svg>
                {{ tab.label }}
                <span class="rounded-full bg-white/70 px-2 py-0.5 text-xs">{{ tab.count }}</span>
              </button>
            </nav>
          </div>

          <div v-if="currentList.length === 0" class="rounded-xl border border-neutral-200 bg-white p-10 text-center shadow-sm">
            <h2 class="text-base font-bold text-neutral-900">暂无{{ activeTabLabel }}伏笔</h2>
            <p class="mt-2 text-sm text-neutral-500">该分类当前为空。</p>
          </div>

          <div v-else class="space-y-4">
            <article
              v-for="item in currentList"
              :key="`${item.name}-${item.planted_chapter}-${item.resolved_chapter || 'open'}`"
              class="rounded-xl border bg-white p-5 shadow-sm transition hover:-translate-y-0.5 hover:shadow-md"
              :class="currentCardClass"
            >
              <div class="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
                <div>
                  <h2 class="text-base font-extrabold text-neutral-950">{{ item.name || '未命名伏笔' }}</h2>
                  <p class="mt-2 max-w-3xl text-sm leading-6 text-neutral-500">{{ item.description || '暂无描述。' }}</p>
                </div>
                <span class="inline-flex w-fit items-center gap-1.5 rounded-full border px-3 py-1 text-xs font-extrabold" :class="currentTagClass">
                  <svg v-if="activeTab === 'dangling'" class="h-3.5 w-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" aria-hidden="true">
                    <path stroke-linecap="round" stroke-linejoin="round" d="M12 9v4m0 4h.01M10.29 3.86 1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0Z" />
                  </svg>
                  {{ currentStatusLabel }}
                </span>
              </div>

              <div class="mt-5 flex flex-wrap items-center gap-3 text-sm font-semibold">
                <span class="rounded-lg border border-neutral-200 bg-neutral-50 px-3 py-1.5 text-neutral-700">
                  种下：第 {{ chapterLabel(item.planted_chapter) }} 章
                </span>
                <svg class="h-4 w-4 text-neutral-300" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" aria-hidden="true">
                  <path stroke-linecap="round" stroke-linejoin="round" d="M13.5 4.5 21 12m0 0-7.5 7.5M21 12H3" />
                </svg>
                <span
                  class="rounded-lg border px-3 py-1.5"
                  :class="item.resolved_chapter ? 'border-blue-200 bg-blue-50 text-blue-700' : 'border-red-200 bg-red-50 text-red-700'"
                >
                  {{ item.resolved_chapter ? `回收：第 ${chapterLabel(item.resolved_chapter)} 章` : '未回收' }}
                </span>
              </div>

              <div class="mt-5">
                <div class="mb-2 flex justify-between text-xs font-semibold text-neutral-400">
                  <span>第 1 章</span>
                  <span>时间线</span>
                  <span>第 {{ maxChapter }} 章</span>
                </div>
                <div class="relative h-2 overflow-hidden rounded-full bg-neutral-100">
                  <div class="absolute inset-y-0 rounded-full" :class="currentTimelineClass" :style="timelineStyle(item)"></div>
                  <span class="absolute top-1/2 h-3 w-3 -translate-x-1/2 -translate-y-1/2 rounded-full border-2 border-white shadow-sm" :class="currentDotClass" :style="{ left: `${chapterPercent(item.planted_chapter)}%` }"></span>
                  <span
                    v-if="item.resolved_chapter"
                    class="absolute top-1/2 h-3 w-3 -translate-x-1/2 -translate-y-1/2 rounded-full border-2 border-white bg-blue-600 shadow-sm"
                    :style="{ left: `${chapterPercent(item.resolved_chapter)}%` }"
                  ></span>
                </div>
              </div>
            </article>
          </div>
        </template>
      </template>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import { useForeshadow } from '../composables/useForeshadow'

const route = useRoute()
const novelId = computed(() => route.params.id)
const activeTab = ref('active')
const progressCircumference = 2 * Math.PI * 32

const {
  foreshadowData,
  loading,
  error,
  loadForeshadows,
  resolutionPercent,
  danglingCount,
  totalCount,
} = useForeshadow(novelId)

const activeList = computed(() => foreshadowData.value?.planted || [])
const resolvedList = computed(() => foreshadowData.value?.resolved || [])
const danglingList = computed(() => foreshadowData.value?.dangling || [])
const resolvedCount = computed(() => resolvedList.value.length)

const tabs = computed(() => [
  { id: 'active', label: '进行中', count: activeList.value.length, activeClass: 'border-green-200 bg-green-50 text-green-700' },
  { id: 'resolved', label: '已回收', count: resolvedCount.value, activeClass: 'border-blue-200 bg-blue-50 text-blue-700' },
  { id: 'dangling', label: '悬挂', count: danglingCount.value, activeClass: 'border-red-200 bg-red-50 text-red-700' },
])

const currentList = computed(() => {
  if (activeTab.value === 'resolved') return resolvedList.value
  if (activeTab.value === 'dangling') return danglingList.value
  return activeList.value
})

const activeTabLabel = computed(() => tabs.value.find(tab => tab.id === activeTab.value)?.label || '进行中')

const progressOffset = computed(() => progressCircumference * (1 - Math.min(Math.max(resolutionPercent.value, 0), 100) / 100))

const maxChapter = computed(() => {
  const chapters = [...activeList.value, ...resolvedList.value, ...danglingList.value]
    .flatMap(item => [item.planted_chapter, item.resolved_chapter])
    .filter(chapter => Number.isFinite(Number(chapter)))
    .map(chapter => Number(chapter))

  return Math.max(1, ...chapters)
})

const currentCardClass = computed(() => {
  if (activeTab.value === 'resolved') return 'border-l-4 border-l-blue-500 border-neutral-200 hover:border-blue-200'
  if (activeTab.value === 'dangling') return 'border-l-4 border-l-red-500 border-neutral-200 hover:border-red-200'
  return 'border-l-4 border-l-green-500 border-neutral-200 hover:border-green-200'
})

const currentTagClass = computed(() => {
  if (activeTab.value === 'resolved') return 'border-blue-200 bg-blue-50 text-blue-700'
  if (activeTab.value === 'dangling') return 'border-red-200 bg-red-50 text-red-700'
  return 'border-green-200 bg-green-50 text-green-700'
})

const currentStatusLabel = computed(() => {
  if (activeTab.value === 'resolved') return '已回收'
  if (activeTab.value === 'dangling') return '悬挂'
  return '进行中'
})

const currentTimelineClass = computed(() => {
  if (activeTab.value === 'resolved') return 'bg-blue-400'
  if (activeTab.value === 'dangling') return 'bg-red-400'
  return 'bg-green-400'
})

const currentDotClass = computed(() => {
  if (activeTab.value === 'resolved') return 'bg-blue-500'
  if (activeTab.value === 'dangling') return 'bg-red-500'
  return 'bg-green-500'
})

function chapterLabel(chapter) {
  return Number.isFinite(Number(chapter)) ? Number(chapter) : '-'
}

function chapterPercent(chapter) {
  const value = Number(chapter)
  if (!Number.isFinite(value)) return 0
  return Math.min(Math.max((value / maxChapter.value) * 100, 0), 100)
}

function timelineStyle(item) {
  const start = chapterPercent(item.planted_chapter)
  const end = item.resolved_chapter ? chapterPercent(item.resolved_chapter) : 100
  return {
    left: `${start}%`,
    width: `${Math.max(end - start, 3)}%`,
  }
}

onMounted(loadForeshadows)
</script>
