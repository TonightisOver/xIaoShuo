<template>
  <div class="max-w-4xl mx-auto px-6 py-10">
    <div v-if="loading" class="text-center py-20 text-ink-500">加载中...</div>

    <div v-else-if="!task" class="text-center py-20">
      <p class="text-ink-400 text-lg mb-4">任务不存在</p>
      <router-link to="/" class="btn-secondary">返回列表</router-link>
    </div>

    <template v-else>
      <div class="flex items-start justify-between mb-8">
        <div>
          <div class="flex items-center gap-3 mb-2">
            <h1 class="text-xl font-bold text-ink-900">{{ task.task_id }}</h1>
            <span :class="'badge-' + task.status">{{ statusLabel }}</span>
          </div>
          <p class="text-ink-500 text-sm">创建于 {{ formatTime(task.created_at) }}</p>
        </div>
        <div class="flex gap-2">
          <router-link v-if="task.novel_id" :to="`/novels/${task.novel_id}`" class="btn-primary text-sm">查看小说项目</router-link>
          <router-link to="/" class="btn-secondary text-sm">返回列表</router-link>
        </div>
      </div>

      <!-- Progress Section -->
      <div v-if="task.status === 'running' || task.status === 'pending'" class="card p-6 mb-6">
        <h2 class="text-sm font-medium text-ink-600 mb-4">生成进度</h2>
        <template v-if="progress.percentage > 0">
          <ProgressBar :percentage="progress.percentage" />
          <StageIndicator :current-stage="progress.current_stage" class="mt-6" />
          <p v-if="progress.completed_chapters" class="text-sm text-ink-500 mt-4">
            已完成 {{ progress.completed_chapters }} / {{ progress.total_chapters }} 章
          </p>
        </template>
        <p v-else class="text-sm text-ink-500">准备中，请稍候...</p>
      </div>

      <!-- Completed Summary -->
      <div v-if="task.status === 'completed'" class="card p-6 mb-6 border-emerald-200">
        <div class="flex items-center gap-2 mb-2">
          <span class="badge-completed">已完成</span>
          <span v-if="task.completed_at" class="text-xs text-ink-400">{{ formatTime(task.completed_at) }}</span>
        </div>
        <p class="text-sm text-ink-600">生成完成，可查看结果或返回小说项目编辑。</p>
      </div>

      <!-- Result Section -->
      <div v-if="task.status === 'completed' && task.result" class="card p-6 mb-6">
        <h2 class="text-sm font-medium text-ink-600 mb-4">生成结果</h2>
        <div v-if="task.result.chapters" class="space-y-4">
          <details
            v-for="chapter in task.result.chapters"
            :key="chapter.chapter"
            class="border border-ink-200 rounded-lg"
          >
            <summary class="px-4 py-3 cursor-pointer hover:bg-ink-50 font-medium text-sm">
              第{{ chapter.chapter }}章：{{ chapter.title }}
              <span class="text-ink-400 font-normal ml-2">{{ chapter.word_count }} 字</span>
            </summary>
            <div class="px-4 py-4 border-t border-ink-100 text-sm leading-relaxed font-serif whitespace-pre-wrap">
              {{ chapter.content }}
            </div>
          </details>
        </div>
      </div>

      <!-- Error Section -->
      <div v-if="task.status === 'failed'" class="card p-6 mb-6 border-red-200">
        <h2 class="text-sm font-medium text-red-600 mb-2">生成失败</h2>
        <ul class="text-sm text-red-700 space-y-1">
          <li v-for="(err, i) in task.errors" :key="i">{{ err }}</li>
        </ul>
      </div>

      <!-- WebSocket Events Log -->
      <div v-if="events.length" class="card p-6">
        <h2 class="text-sm font-medium text-ink-600 mb-3">实时日志</h2>
        <div class="max-h-48 overflow-y-auto space-y-1 text-xs font-mono text-ink-600">
          <div v-for="(ev, i) in events" :key="i" class="flex gap-2">
            <span class="text-ink-400 shrink-0">{{ ev.time }}</span>
            <span>{{ ev.message }}</span>
          </div>
        </div>
      </div>
    </template>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useRoute } from 'vue-router'
import ProgressBar from '../components/ProgressBar.vue'
import StageIndicator from '../components/StageIndicator.vue'
import { useWebSocket } from '../composables/useWebSocket.js'

const route = useRoute()
const taskId = route.params.id

const task = ref(null)
const loading = ref(true)
const events = ref([])

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

function addEvent(type, data) {
  const time = new Date().toLocaleTimeString('zh-CN')
  const messages = {
    stage_start: `开始阶段: ${data.stage}`,
    stage_complete: `完成阶段: ${data.current_stage} (${data.percentage}%)`,
    chapter_progress: `章节进度: ${data.completed_chapters}/${data.total_chapters}`,
    sub_feature_start: `子功能: ${data.label} 开始 (${data.percentage}%)`,
    sub_feature_complete: `子功能: ${data.label} 完成`,
    completed: '生成完成',
    error: `错误: ${data.error || '未知'}${data.non_blocking ? ' (非阻塞)' : ''}`,
    heartbeat: '心跳',
  }
  events.value.push({ time, message: messages[type] || type })
  if (events.value.length > 50) events.value.shift()
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
    } else if (msg.type === 'stage_complete' || msg.type === 'chapter_progress' || msg.type === 'stage_start' || msg.type === 'sub_feature_start' || msg.type === 'sub_feature_complete') {
      if (task.value) {
        task.value = { ...task.value, progress: msg.data, status: 'running' }
      }
      addEvent(msg.type, msg.data)
    } else if (msg.type === 'completed') {
      fetchTask()
      addEvent('completed', msg.data)
    } else if (msg.type === 'error') {
      fetchTask()
      addEvent('error', msg.data)
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
})

onUnmounted(disconnect)
</script>
