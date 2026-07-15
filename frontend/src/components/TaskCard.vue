<template>
  <router-link :to="`/task/${task.task_id}`" class="card card-hover shine-on-hover block p-5 group animate-fade-up">
    <div class="flex items-start justify-between">
      <div class="flex-1 min-w-0">
        <div class="flex items-center gap-2 mb-1">
          <span :class="'badge-' + task.status">{{ statusLabel }}</span>
          <span class="text-xs text-ink-400">{{ formatTime(task.created_at) }}</span>
        </div>
        <p class="text-sm font-medium text-ink-700 truncate group-hover:text-vermilion-500 transition-colors">
          {{ task.task_id }}
        </p>
      </div>
      <svg class="w-5 h-5 text-ink-300 group-hover:text-vermilion-500 transition-colors shrink-0 mt-1" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5l7 7-7 7"/>
      </svg>
    </div>
  </router-link>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({ task: Object })

const statusLabel = computed(() => {
  const map = { pending: '等待中', running: '生成中', completed: '已完成', failed: '失败' }
  return map[props.task.status] || props.task.status
})

function formatTime(iso) {
  if (!iso) return ''
  return new Date(iso).toLocaleString('zh-CN', { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' })
}
</script>
