<template>
  <div class="conflict-panel animate-fade-up">
    <!-- Header -->
    <div class="flex items-center justify-between mb-4">
      <div class="flex items-center gap-2">
        <h2 class="text-base font-bold text-ink-700 heading-serif">一致性冲突记录</h2>
        <span
          v-if="conflicts.length"
          class="text-[11px] bg-red-50 text-red-600 px-2 py-0.5 rounded-md font-medium border border-red-100"
        >
          {{ conflicts.length }} 条
        </span>
      </div>
      <button
        @click="fetchConflicts"
        :disabled="loading"
        class="btn-secondary text-xs py-1 px-3 flex items-center gap-1"
      >
        <svg
          :class="{ 'animate-spin': loading }"
          class="w-3 h-3"
          fill="none"
          viewBox="0 0 24 24"
          stroke-width="2"
          stroke="currentColor"
        >
          <path stroke-linecap="round" stroke-linejoin="round" d="M16.023 9.348h4.992v-.001M2.985 19.644v-4.992m0 0h4.992m-4.993 0l3.181 3.183a8.25 8.25 0 0013.803-3.7M4.031 9.865a8.25 8.25 0 0113.803-3.7l3.181 3.182m0-4.991v4.99" />
        </svg>
        <span>刷新</span>
      </button>
    </div>

    <!-- Loading -->
    <div v-if="loading" class="flex items-center justify-center py-12">
      <div class="w-6 h-6 rounded-full border-3 border-red-500/10 border-t-red-500 animate-spin"></div>
    </div>

    <!-- Empty -->
    <div v-else-if="!conflicts.length" class="text-center py-12 text-ink-400 text-sm bg-paper-50 rounded-xl border border-ink-200 animate-fade-in">
      <p class="text-lg mb-1">✅</p>
      <p>暂无一致性冲突记录</p>
      <p class="text-xs mt-1 text-ink-400">知识图谱各章节实体状态一致，未检测到矛盾。</p>
    </div>

    <!-- Conflict list -->
    <div v-else class="space-y-3">
      <div
        v-for="(item, idx) in conflicts"
        :key="item.chapter_number + '-' + (item.version_number || 0)"
        class="card p-4 rounded-xl border border-red-100 bg-red-50/30 hover:bg-red-50/60 transition-colors animate-fade-up-stagger shine-on-hover"
        :style="{ animationDelay: `${Math.min(idx,8)*60}ms` }"
      >
        <!-- Header -->
        <div class="flex items-start justify-between gap-3 mb-2">
          <div class="flex items-center gap-2">
            <span class="w-2 h-2 rounded-full bg-red-500 shrink-0"></span>
            <span class="text-sm font-bold text-red-800">
              第 {{ item.chapter_number || '?' }} 章
            </span>
            <span
              v-if="item.version_number"
              class="text-[10px] bg-red-100 text-red-600 px-1.5 py-0.5 rounded font-medium"
            >
              v{{ item.version_number }}
            </span>
          </div>
          <span v-if="item.created_at" class="text-[10px] text-ink-400 whitespace-nowrap">
            {{ formatDate(item.created_at) }}
          </span>
        </div>

        <!-- Conflict details -->
        <div v-if="item.conflicts?.length" class="ml-4 space-y-2">
          <div
            v-for="(c, i) in item.conflicts"
            :key="i"
            class="flex items-start gap-2 p-2.5 rounded-lg bg-paper-50 border border-red-100"
          >
            <span class="text-red-500 mt-0.5 shrink-0">
              <svg viewBox="0 0 16 16" fill="currentColor" class="w-3.5 h-3.5">
                <path d="M8 1.5a6.5 6.5 0 100 13 6.5 6.5 0 000-13zM7.25 4.75a.75.75 0 011.5 0v3.5a.75.75 0 01-1.5 0v-3.5zM8 10.25a.75.75 0 100 1.5.75.75 0 000-1.5z" />
              </svg>
            </span>
            <div class="flex-1 min-w-0 text-xs">
              <p class="text-ink-500 leading-relaxed">
                <span class="font-semibold text-red-600">{{ c.entity_name || c.entity_id || '未知实体' }}</span>
                <span v-if="c.attribute"> / {{ c.attribute }}</span>
                <span>：</span>
                <span>{{ c.detail || c.message || describeConflict(c) }}</span>
              </p>
              <p v-if="c.expected || c.actual" class="text-ink-400 mt-0.5 space-x-3">
                <span v-if="c.expected">预期：<span class="text-emerald-600 font-medium">{{ c.expected }}</span></span>
                <span v-if="c.actual">实际：<span class="text-red-500 font-medium">{{ c.actual }}</span></span>
              </p>
              <p v-if="c.suggestion" class="text-amber-600 mt-0.5">
                建议：{{ c.suggestion }}
              </p>
            </div>
          </div>
        </div>

        <div v-else class="ml-4 text-xs text-ink-500 italic">
          冲突详情未记录
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'

const props = defineProps({
  novelId: { type: String, required: true },
})

const loading = ref(false)
const conflicts = ref([])

function formatDate(iso) {
  if (!iso) return ''
  return new Date(iso).toLocaleDateString('zh-CN', {
    year: 'numeric', month: '2-digit', day: '2-digit',
    hour: '2-digit', minute: '2-digit',
  })
}

function describeConflict(c) {
  if (c.chapter_before && c.chapter_after) {
    return `第${c.chapter_before}章与第${c.chapter_after}章之间属性${c.attribute || '状态'}发生不一致`
  }
  if (c.value_before !== undefined && c.value_after !== undefined) {
    return `属性值从「${c.value_before}」变为「${c.value_after}」`
  }
  return '检测到知识图谱一致性冲突'
}

async function fetchConflicts() {
  loading.value = true
  try {
    const res = await fetch(`/api/v1/projects/${props.novelId}/knowledge-graph/conflicts`)
    if (res.ok) {
      conflicts.value = await res.json()
    } else {
      conflicts.value = []
    }
  } catch {
    conflicts.value = []
  } finally {
    loading.value = false
  }
}

onMounted(fetchConflicts)
</script>
