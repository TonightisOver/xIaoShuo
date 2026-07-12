<template>
  <div class="max-w-4xl mx-auto px-6 py-10 font-sans animate-fade-up" :class="{ 'pb-20': isStreaming || isPaused }">
    <div v-if="loading" class="text-center py-20 text-ink-400 text-sm">正在努力加载创作详情...</div>

    <div v-else-if="!task" class="text-center py-20">
      <p class="text-ink-300 text-lg mb-4">创作任务不存在</p>
      <router-link to="/" class="btn-secondary">返回首页</router-link>
    </div>

    <template v-else>
      <!-- Task Header -->
      <div class="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 mb-8">
        <div>
          <div class="flex items-center gap-3 mb-2 flex-wrap">
            <h1 class="heading-serif text-2xl flex items-center gap-2">
              <span>创作生成任务</span>
              <span class="text-xs font-mono text-ink-300 bg-paper-100 px-2 py-0.5 rounded border border-ink-100 font-normal">
                {{ task.task_id.slice(0, 8) }}...
              </span>
            </h1>
            <span :class="'badge-' + task.status">{{ statusLabel }}</span>
          </div>
          <p class="text-ink-400 text-xs md:text-sm">任务创建于 {{ formatTime(task.created_at) }}</p>
        </div>
        <div class="flex gap-2">
          <router-link v-if="task.novel_id" :to="`/novels/${task.novel_id}`" class="btn-primary text-sm flex items-center gap-1.5 shadow-sm">
            <span>管理小说设定</span>
            <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="2" stroke="currentColor" class="w-4 h-4">
              <path stroke-linecap="round" stroke-linejoin="round" d="M16.862 4.487l1.687-1.688a1.875 1.875 0 112.652 2.652L6.832 19.82a4.5 4.5 0 01-1.897 1.13l-2.685.8.8-2.685a4.5 4.5 0 011.13-1.897L16.863 4.487zm0 0L19.5 7.125" />
            </svg>
          </router-link>
          <router-link to="/" class="btn-secondary text-sm">返回大厅</router-link>
        </div>
      </div>

      <!-- Plot Streaming Panel (outline/planning streaming) -->
      <PlotStreamingPanel
        v-if="outlineText || isOutlineStreaming"
        :outline-text="outlineText"
        :is-outline-streaming="isOutlineStreaming"
      />

      <!-- Streaming Content Area -->
      <div v-if="streamingText || isStreaming" class="card p-6 mb-6">
        <h2 class="text-sm font-bold text-ink-700 dark:text-neutral-100 mb-1 flex items-center gap-2">
          <svg class="w-4 h-4 text-vermilion-500" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" d="M12 6.042A8.967 8.967 0 006 3.75c-1.052 0-2.062.18-3 .512v14.25A8.987 8.987 0 016 18c2.305 0 4.408.867 6 2.292m0-14.25a8.966 8.966 0 016-2.292c1.052 0 2.062.18 3 .512v14.25A8.987 8.987 0 0018 18a8.967 8.967 0 00-6 2.292m0-14.25v14.25" />
          </svg>
          <span>
            正在生成：第{{ currentChapter }}章
            <span v-if="currentChapterTitle" class="text-ink-300 dark:text-neutral-500 font-normal ml-1">「{{ currentChapterTitle }}」</span>
          </span>
          <span v-if="isStreaming" class="inline-block w-2 h-2 rounded-full bg-vermilion-500 animate-pulse"></span>
        </h2>
        <StreamingText :text="streamingText" :is-streaming="isStreaming" />
      </div>

      <!-- Generation Control Bar -->
      <GenerationControlBar
        v-if="isStreaming || isPaused"
        :task-id="taskId"
        :is-paused="isPaused"
        :is-streaming="isStreaming"
        :current-chapter="currentChapter"
        :total-chapters="totalChapters"
        :word-count="chapterWordCount"
        @pause="handlePause"
        @resume="handleResume"
        @stop="handleStop"
        @edit="() => {}"
      />

      <!-- Progress Section -->
      <div v-if="task.status" class="card p-6 mb-6">
        <h2 class="text-sm font-bold text-ink-700 mb-4 flex items-center gap-2">
          <svg v-if="task.status === 'running' || task.status === 'pending'" class="w-4 h-4 text-vermilion-500 animate-spin" fill="none" viewBox="0 0 24 24">
            <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
            <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
          </svg>
          <svg v-else-if="task.status === 'failed'" class="w-4 h-4 text-rose-500" fill="none" stroke="currentColor" stroke-width="2.5" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" d="M12 9v3.75m0-10.03V12m0 3h.008v.008H12V15z" />
          </svg>
          <svg v-else class="w-4 h-4 text-emerald-500" fill="none" stroke="currentColor" stroke-width="2.5" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" d="M4.5 12.75l6 6 9-13.5" />
          </svg>
          <span>生成进度追踪</span>
        </h2>

        <template v-if="progress.percentage > 0 || task.status === 'completed' || task.status === 'failed'">
          <ProgressBar :percentage="task.status === 'completed' ? 100 : progress.percentage" />
          <StageIndicator :current-stage="progress.current_stage || 'idea_expansion'" :status="task.status" class="mt-6" />

          <div v-if="progress.completed_chapters" class="mt-6 flex items-center gap-2 bg-vermilion-50/50 border border-vermilion-100/60 p-3 rounded-xl">
            <svg class="w-4 h-4 text-vermilion-500" fill="none" stroke="currentColor" stroke-width="2.5" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" d="M12 6.042A8.967 8.967 0 006 3.75c-1.052 0-2.062.18-3 .512v14.25A8.987 8.987 0 016 18c2.305 0 4.408.867 6 2.292m0-14.25a8.966 8.966 0 016-2.292c1.052 0 2.062.18 3 .512v14.25A8.987 8.987 0 0018 18a8.967 8.967 0 00-6 2.292m0-14.25v14.25" />
            </svg>
            <p class="text-xs md:text-sm font-semibold text-vermilion-600">
              章节生成进度：已成功创写 {{ progress.completed_chapters }} / {{ progress.total_chapters }} 章
            </p>
          </div>
        </template>
        <p v-else class="text-sm text-ink-400">正在与大模型进行深度设定握手，请耐心稍候...</p>
      </div>

      <!-- Completed Summary -->
      <div v-if="task.status === 'completed'" class="card p-6 mb-6 border-emerald-200 bg-emerald-50/20">
        <div class="flex items-center gap-2 mb-2 flex-wrap">
          <span class="badge-completed">已完成</span>
          <span v-if="task.completed_at" class="text-xs text-ink-300">{{ formatTime(task.completed_at) }}</span>
        </div>
        <p class="text-sm font-medium text-emerald-800 leading-relaxed">
          恭喜！AI 创作任务已顺利收尾。世界观、主配角设定、分卷大纲、三层因果图谱以及全本章节正文已完美入库，您可以进入小说详情页面预览、下载与深度精修。
        </p>
      </div>

      <!-- Result Section -->
      <div v-if="task.status === 'completed' && task.result" class="card p-6 mb-6">
        <h2 class="text-sm font-bold text-ink-700 mb-4 flex items-center gap-2">
          <svg class="w-4.5 h-4.5 text-vermilion-500" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" d="M9 12h3.75M9 15h3.375M9 18h3.375m1.5-16.125H8.25c-1.102 0-2 .898-2 2v14.25c0 1.102.898 2 2 2h8.25c1.102 0 2-.898 2-2V9m-3-7.125v3a1.5 1.5 0 001.5 1.5h3m-6-1.5v3a1.5 1.5 0 001.5 1.5h3" />
          </svg>
          <span>已创写章节目录</span>
        </h2>
        <div v-if="task.result.chapters" class="space-y-3.5">
          <details
            v-for="(chapter, idx) in task.result.chapters"
            :key="chapter.chapter"
            class="card animate-fade-up-stagger border border-ink-200 rounded-xl hover:bg-paper-50 transition-all duration-200"
            :style="{ animationDelay: `${Math.min(idx,8)*60}ms` }"
          >
            <summary class="px-5 py-3.5 cursor-pointer font-semibold text-xs md:text-sm text-ink-700 flex items-center justify-between flex-wrap gap-2 select-none">
              <span>第{{ chapter.chapter }}章：{{ chapter.title }}</span>
              <span class="text-xs text-ink-300 font-mono font-normal bg-paper-50 border border-ink-200 px-2 py-0.5 rounded shadow-sm">
                {{ chapter.word_count }} 字
              </span>
            </summary>
            <div class="px-5 py-5 border-t border-ink-200 text-sm text-ink-500 leading-relaxed font-serif bg-paper-50 rounded-b-xl whitespace-pre-wrap">
              {{ chapter.content }}
            </div>
          </details>
        </div>
      </div>

      <!-- Error Section -->
      <div v-if="task.status === 'failed'" class="card p-6 mb-6 border-rose-200 bg-rose-50/20">
        <h2 class="text-sm font-bold text-rose-700 mb-2 flex items-center gap-1.5">
          <svg class="w-4.5 h-4.5" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" d="M12 9v3.75m9-.75a9 9 0 11-18 0 9 9 0 0118 0zm-9 3.75h.008v.008H12v-.008z" />
          </svg>
          <span>生成任务失败</span>
        </h2>
        <ul class="text-xs md:text-sm text-rose-800 space-y-1 bg-paper-50 p-4 rounded-xl border border-rose-100 font-mono">
          <li v-for="(err, i) in task.errors" :key="i" class="list-disc list-inside">{{ err }}</li>
        </ul>
      </div>

      <!-- WebSocket Events Log / Premium Terminal Console -->
      <div v-if="events.length" class="card p-6">
        <h2 class="text-sm font-bold text-ink-700 mb-3 flex items-center gap-2">
          <svg class="w-4.5 h-4.5 text-vermilion-500" fill="none" stroke="currentColor" stroke-width="2.5" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" d="M6.75 7.5l3 2.25-3 2.25m4.5 0h3m-9 8.25h13.5A2.25 2.25 0 0021 18V6a2.25 2.25 0 00-2.25-2.25H5.25A2.25 2.25 0 003 6v12a2.25 2.25 0 002.25 2.25z" />
          </svg>
          <span>实时创作控制台</span>
        </h2>

        <!-- Black high-contrast Terminal styling for professional developer logs -->
        <div
          ref="logContainer"
          class="max-h-60 overflow-y-auto space-y-1.5 text-xs md:text-[13px] font-mono bg-[#111] border border-black/80 rounded-xl p-4 shadow-inner text-[#f8f8f2] scroll-smooth"
        >
          <div v-for="(ev, i) in events" :key="i" class="flex items-start gap-3 border-b border-white/[0.03] pb-1 hover:bg-white/[0.02] px-1 transition-colors">
            <span class="text-ink-400 shrink-0 select-none font-light">{{ ev.time }}</span>
            <span :class="logColor(ev.message)">{{ ev.message }}</span>
          </div>
        </div>

        <p class="text-[10px] text-ink-300 mt-2 text-right">
          控制台接收 WebSocket 双向数据流 · 自动探底滚动开启
        </p>
      </div>
    </template>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted, watch, nextTick } from 'vue'
import { useRoute } from 'vue-router'
import ProgressBar from '../components/ProgressBar.vue'
import StageIndicator from '../components/StageIndicator.vue'
import StreamingText from '../components/StreamingText.vue'
import GenerationControlBar from '../components/GenerationControlBar.vue'
import PlotStreamingPanel from '../components/PlotStreamingPanel.vue'
import { useWebSocket } from '../composables/useWebSocket.js'

const route = useRoute()
const taskId = route.params.id

const task = ref(null)
const loading = ref(true)
const events = ref([])
const logContainer = ref(null)

// Streaming state
const streamingText = ref('')
const isStreaming = ref(false)
const isPaused = ref(false)
const currentChapter = ref(0)
const currentChapterTitle = ref('')
const totalChapters = ref(0)
const chapterWordCount = ref(0)

// Outline streaming state
const outlineText = ref('')
const isOutlineStreaming = ref(false)

const progress = computed(() => task.value?.progress || {
  current_stage: '',
  completed_chapters: 0,
  total_chapters: 0,
  percentage: 0,
})

const statusLabel = computed(() => {
  const map = { pending: '等待中', running: '生成中', completed: '已完成', failed: '失败' }
  return map[task.value?.status] || task.value?.status
})

function formatTime(iso) {
  if (!iso) return ''
  return new Date(iso).toLocaleString('zh-CN')
}

// Color-coding log event types to make console super readable and premium
function logColor(msg) {
  if (!msg) return 'text-[#f8f8f2]'
  if (msg.includes('错误:')) return 'text-rose-400 font-bold'
  if (msg.includes('开始阶段:')) return 'text-sky-400'
  if (msg.includes('完成阶段:')) return 'text-emerald-400 font-medium'
  if (msg.includes('章节进度:')) return 'text-purple-400 font-medium'
  if (msg.includes('子功能: ') && msg.includes('开始')) return 'text-amber-300'
  if (msg.includes('子功能: ') && msg.includes('完成')) return 'text-teal-400'
  if (msg.includes('生成完成')) return 'text-emerald-500 font-bold'
  if (msg.includes('心跳')) return 'text-neutral-600 font-light'
  return 'text-neutral-300'
}

function addEvent(type, data) {
  const time = new Date().toLocaleTimeString('zh-CN')
  const messages = {
    stage_start: `开始阶段: ${data.stage}`,
    stage_complete: `完成阶段: ${data.current_stage} (${data.percentage}%)`,
    chapter_progress: `章节进度: ${data.completed_chapters}/${data.total_chapters} 章 (第${data.current_chapter || data.completed_chapters}章创作完成)`,
    sub_feature_start: `子功能: [${data.label}] 开始执行 (${data.percentage}%)`,
    sub_feature_complete: `子功能: [${data.label}] 执行完成`,
    completed: '生成完成',
    error: `错误: ${data.error || '未知'}${data.non_blocking ? ' (非阻塞)' : ''}`,
    heartbeat: '心跳',
  }
  events.value.push({ time, message: messages[type] || type })
  if (events.value.length > 100) events.value.shift()
}

// Smooth scrolling log view to bottom when new items are added
watch(events, () => {
  nextTick(() => {
    if (logContainer.value) {
      logContainer.value.scrollTo({
        top: logContainer.value.scrollHeight,
        behavior: 'smooth'
      })
    }
  })
}, { deep: true })

// Control panel actions
async function handlePause() {
  try {
    await fetch(`/api/v1/tasks/${taskId}/pause`, { method: 'POST' })
  } catch (e) {
    // ignore
  }
}

async function handleResume() {
  try {
    await fetch(`/api/v1/tasks/${taskId}/resume`, { method: 'POST' })
  } catch (e) {
    // ignore
  }
}

async function handleStop() {
  // Reuse pause as a hard stop for now
  await handlePause()
}

async function fetchTask() {
  try {
    const res = await fetch(`/api/v1/novels/${taskId}`)
    if (res.ok) {
      task.value = await res.json()
    }
  } finally {
    loading.value = false
  }
}

const { connect, disconnect } = useWebSocket(taskId, {
  onMessage(msg) {
    if (msg.type === 'connected') {
      task.value = { ...task.value, status: msg.current_status, progress: msg.progress }
      totalChapters.value = msg.progress?.total_chapters || 0
    } else if (msg.type === 'stage_complete' || msg.type === 'chapter_progress' || msg.type === 'stage_start' || msg.type === 'sub_feature_start' || msg.type === 'sub_feature_complete') {
      if (task.value) {
        task.value = { ...task.value, progress: msg.data, status: 'running' }
      }
      if (msg.data?.total_chapters) totalChapters.value = msg.data.total_chapters
      addEvent(msg.type, msg.data)
    } else if (msg.type === 'completed') {
      isStreaming.value = false
      fetchTask()
      addEvent('completed', msg.data)
    } else if (msg.type === 'error') {
      isStreaming.value = false
      fetchTask()
      addEvent('error', msg.data)
    } else if (msg.type === 'chapter_token') {
      streamingText.value += msg.data.token
      chapterWordCount.value = msg.data.accumulated_length || chapterWordCount.value
    } else if (msg.type === 'chapter_stream_start') {
      streamingText.value = ''
      isStreaming.value = true
      currentChapter.value = msg.data.chapter
      currentChapterTitle.value = msg.data.title || ''
      addEvent('chapter_stream_start', { stage: `第${msg.data.chapter}章「${msg.data.title || ''}」开始生成` })
    } else if (msg.type === 'chapter_stream_end') {
      isStreaming.value = false
      chapterWordCount.value = msg.data.word_count || chapterWordCount.value
      addEvent('chapter_stream_end', { stage: `第${msg.data.chapter}章完成，${msg.data.word_count || 0}字` })
    } else if (msg.type === 'generation_paused') {
      isPaused.value = true
      addEvent('generation_paused', { stage: '生成已暂停' })
    } else if (msg.type === 'generation_resumed') {
      isPaused.value = false
      addEvent('generation_resumed', { stage: '生成已恢复' })
    } else if (msg.type === 'outline_token') {
      outlineText.value += msg.data.token
      isOutlineStreaming.value = true
    } else if (msg.type === 'outline_stream_end') {
      isOutlineStreaming.value = false
    } else if (msg.type !== 'heartbeat') {
      addEvent(msg.type, msg.data || {})
    }
  },
})

onMounted(async () => {
  await fetchTask()
  if (task.value && (task.value.status === 'pending' || task.value.status === 'running')) {
    connect()
  }
  // Initial scroll
  nextTick(() => {
    if (logContainer.value) {
      logContainer.value.scrollTop = logContainer.value.scrollHeight
    }
  })
})

onUnmounted(disconnect)
</script>
