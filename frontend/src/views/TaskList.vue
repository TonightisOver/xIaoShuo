<template>
  <div class="max-w-6xl mx-auto px-6 py-10 animate-fade-in">
    <div class="flex flex-col md:flex-row md:items-center md:justify-between gap-4 mb-8">
      <div>
        <h1 class="text-2xl font-bold text-ink-900 tracking-tight">任务列表</h1>
        <p class="text-ink-500 text-sm mt-1">监控和管理小说生成任务的后台进度</p>
      </div>
      
      <!-- Filter Tabs -->
      <div class="flex items-center gap-3">
        <button @click="cleanupStaleTasks" class="text-xs font-medium text-ink-500 hover:text-red-500 border border-ink-200 rounded-lg px-3 py-1.5 transition-colors">
          清理过期任务
        </button>
        <div class="flex items-center bg-ink-50 p-1 rounded-xl border border-ink-200 shadow-sm">
        <button
          v-for="tab in filterTabs"
          :key="tab.value"
          @click="statusFilter = tab.value"
          :class="[
            'px-4 py-1.5 rounded-lg text-xs font-semibold transition-all duration-200',
            statusFilter === tab.value
              ? 'bg-white text-primary-700 shadow-sm border border-ink-100'
              : 'text-ink-500 hover:text-ink-800'
          ]"
        >
          {{ tab.label }}
        </button>
        </div>
      </div>
    </div>

    <!-- Loading State -->
    <div v-if="loading && tasks.length === 0" class="text-center py-24 text-ink-500 flex flex-col items-center gap-3">
      <div class="w-8 h-8 border-2 border-primary-600 border-t-transparent rounded-full animate-spin"></div>
      <p class="text-xs font-medium tracking-wide">正在同步任务状态...</p>
    </div>

    <!-- Empty State -->
    <div v-else-if="filteredTasks.length === 0" class="text-center py-20 card bg-white flex flex-col items-center justify-center shadow-sm rounded-2xl border border-ink-200">
      <div class="w-12 h-12 rounded-full bg-ink-50 flex items-center justify-center text-ink-400 mb-4 text-xl">📝</div>
      <p class="text-ink-400 text-sm font-medium mb-4">没有找到相关生成任务</p>
      <router-link to="/create" class="btn-primary text-sm px-6 py-2.5">开始创作小说</router-link>
    </div>

    <!-- Task Cards Grid -->
    <div v-else class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
      <div
        v-for="task in filteredTasks"
        :key="task.task_id"
        class="card bg-white p-5 group flex flex-col justify-between hover:border-primary-400 hover:shadow-md transition-all duration-300 rounded-2xl border border-ink-200"
      >
        <div>
          <!-- Header (Badge + Type) -->
          <div class="flex items-center justify-between mb-4">
            <span :class="['badge-' + statusClass(task.status), 'text-[10px] px-2.5 py-1 rounded-full font-bold uppercase tracking-wider']">
              {{ statusLabel(task.status) }}
            </span>
            <span class="text-[11px] font-bold text-primary-700 bg-primary-50 px-2 py-0.5 rounded">
              {{ task.novel_type || '小说生成' }}
            </span>
          </div>

          <!-- Creative Idea Preview / Task ID -->
          <h3 class="font-bold text-ink-800 group-hover:text-primary-600 transition-colors mb-2 line-clamp-1 text-base">
            {{ task.idea ? truncateIdea(task.idea) : '无标题生成任务' }}
          </h3>
          
          <p class="text-[10px] text-ink-400 font-mono mb-4">{{ task.task_id }}</p>

          <!-- Idea Snippet -->
          <p class="text-xs text-ink-500 line-clamp-3 mb-6 leading-relaxed">
            {{ task.idea || '该生成任务没有创意描述详情。' }}
          </p>
        </div>

        <!-- Card Footer -->
        <div class="border-t border-ink-100 pt-4 mt-auto">
          <!-- Live Progress for Running/Pending -->
          <div v-if="task.status === 'running' || task.status === 'pending'" class="mb-4">
            <div class="flex justify-between items-center text-xs font-semibold text-ink-600 mb-1.5">
              <span class="flex items-center gap-1.5">
                <span class="w-1.5 h-1.5 bg-primary-600 rounded-full animate-ping"></span>
                后台渲染中...
              </span>
              <span class="text-primary-600 font-mono">{{ task.progress_percentage }}%</span>
            </div>
            <!-- Progress Bar -->
            <div class="w-full bg-ink-100 rounded-full h-2 overflow-hidden">
              <div 
                class="bg-primary-600 h-full rounded-full transition-all duration-300 progress-bar-striped animate-pulse"
                :style="{ width: task.progress_percentage + '%' }"
              ></div>
            </div>
          </div>

          <div class="flex justify-between items-center">
            <p class="text-[10px] text-ink-400 font-medium">
              {{ formatTime(task.created_at) }}
            </p>
            <div class="flex gap-3">
              <button
                v-if="task.status === 'running' || task.status === 'pending'"
                @click.stop="cancelTask(task.task_id)"
                class="text-xs font-bold text-red-400 hover:text-red-600 transition-colors"
              >
                标记失败
              </button>
              <router-link
                v-if="task.novel_id && task.status === 'completed'"
                :to="`/novels/${task.novel_id}`"
                class="text-xs font-bold text-emerald-600 hover:text-emerald-700 transition-colors"
              >
                查看小说
              </router-link>
              <router-link
                :to="`/task/${task.task_id}`"
                class="text-xs font-bold text-primary-600 hover:text-primary-700 transition-colors"
              >
                {{ task.status === 'running' || task.status === 'pending' ? '监控进度' : '查看日志' }}
              </router-link>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- Pagination -->
    <div v-if="total > limit" class="flex justify-center mt-10 gap-3">
      <button 
        class="btn-secondary text-sm px-4 py-2" 
        :disabled="offset === 0" 
        @click="offset -= limit"
      >
        上一页
      </button>
      <span class="px-4 py-2 text-sm text-ink-500 font-medium">
        {{ Math.floor(offset / limit) + 1 }} / {{ Math.ceil(total / limit) }}
      </span>
      <button 
        class="btn-secondary text-sm px-4 py-2" 
        :disabled="offset + limit >= total" 
        @click="offset += limit"
      >
        下一页
      </button>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, watch, onMounted, onUnmounted } from 'vue'

const tasks = ref([])
const total = ref(0)
const loading = ref(true)
const statusFilter = ref('all')
const offset = ref(0)
const limit = 12
let pollInterval = null

const filterTabs = [
  { label: '全部', value: 'all' },
  { label: '生成中', value: 'running' },
  { label: '已完成', value: 'completed' },
  { label: '已失败', value: 'failed' }
]

function statusClass(s) {
  return { pending: 'pending', running: 'running', completed: 'completed', failed: 'failed' }[s] || 'pending'
}

function statusLabel(s) {
  return { pending: '排队中', running: '生成中', completed: '已完成', failed: '已失败' }[s] || s
}

function truncateIdea(txt) {
  if (!txt) return ''
  return txt.length > 18 ? txt.substring(0, 18) + '...' : txt
}

function formatTime(iso) {
  if (!iso) return ''
  return new Date(iso).toLocaleString('zh-CN', {
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit'
  })
}

async function fetchTasks() {
  try {
    const params = new URLSearchParams({ limit, offset: offset.value })
    if (statusFilter.value !== 'all' && statusFilter.value !== 'running') {
      params.set('status', statusFilter.value)
    }
    
    const res = await fetch(`/api/v1/novels?${params}`)
    if (res.ok) {
      const data = await res.json()
      
      const tasksData = await Promise.all(data.tasks.map(async (t) => {
        let pct = 0
        if (t.status === 'running' || t.status === 'pending') {
          try {
            const detailRes = await fetch(`/api/v1/novels/${t.task_id}`)
            if (detailRes.ok) {
              const detail = await detailRes.json()
              pct = detail.progress?.percentage || 0
            }
          } catch (e) {
            console.error('Failed to fetch details for task', t.task_id, e)
          }
        }
        return {
          ...t,
          progress_percentage: pct
        }
      }))
      tasks.value = tasksData
      total.value = data.total
    }
  } catch (e) {
    console.error(e)
  } finally {
    loading.value = false
  }
}

const filteredTasks = computed(() => {
  if (statusFilter.value === 'running') {
    return tasks.value.filter(t => t.status === 'running' || t.status === 'pending')
  }
  return tasks.value
})

watch([statusFilter, offset], () => {
  loading.value = true
  fetchTasks()
})

onMounted(() => {
  fetchTasks()
  pollInterval = setInterval(fetchTasks, 5000)
})

onUnmounted(() => {
  if (pollInterval) clearInterval(pollInterval)
})

async function cancelTask(taskId) {
  if (!confirm('确定要将此任务标记为失败吗？')) return
  try {
    const res = await fetch(`/api/v1/novels/${taskId}/cancel`, { method: 'POST' })
    if (res.ok) {
      await fetchTasks()
    }
  } catch (e) {
    console.error('Cancel task failed', e)
  }
}

async function cleanupStaleTasks() {
  try {
    const res = await fetch('/api/v1/novels/cleanup/stale', { method: 'POST' })
    if (res.ok) {
      const data = await res.json()
      if (data.expired_count > 0) {
        alert(`已清理 ${data.expired_count} 个过期任务`)
      } else {
        alert('没有需要清理的过期任务')
      }
      await fetchTasks()
    }
  } catch (e) {
    console.error('Cleanup failed', e)
  }
}
</script>

<style scoped>
.animate-fade-in {
  animation: fadeIn 0.4s ease-out;
}

@keyframes fadeIn {
  from {
    opacity: 0;
    transform: translateY(6px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

.progress-bar-striped {
  background-image: linear-gradient(
    45deg,
    rgba(255, 255, 255, 0.15) 25%,
    transparent 25%,
    transparent 50%,
    rgba(255, 255, 255, 0.15) 50%,
    rgba(255, 255, 255, 0.15) 75%,
    transparent 75%,
    transparent
  );
  background-size: 1rem 1rem;
}
</style>
