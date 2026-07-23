<template>
  <div class="flex flex-col h-full border-r border-ink-200 bg-paper-50">
    <!-- 筛选区 -->
    <div class="p-3 space-y-2 border-b border-ink-200">
      <select v-model="volFilter" @change="emitFilter" data-volume-filter
              class="input text-sm w-full">
        <option :value="null">全部卷</option>
        <option v-for="v in volumes" :key="v" :value="v">第{{ v }}卷</option>
      </select>
      <select v-model="statusFilter" @change="emitFilter" data-status-filter
              class="input text-sm w-full">
        <option :value="null">全部状态</option>
        <option v-for="s in statuses" :key="s.value" :value="s.value">{{ s.label }}</option>
      </select>
      <input v-model="searchQuery" @keyup.enter="emitFilter" data-search-input
             placeholder="搜索章号/标题" class="input text-sm w-full" />
      <button @click="emitFilter" class="btn-secondary text-sm w-full">筛选</button>
    </div>

    <!-- 列表 -->
    <div class="flex-1 overflow-auto">
      <div v-if="loading" class="p-8 text-center text-ink-400 text-sm">加载中...</div>
      <div v-else-if="!summaries.length" class="p-8 text-center text-ink-400 text-sm">
        {{ hasActiveFilters ? '没有符合筛选条件的章节' : '全书尚无章节大纲' }}
      </div>
      <ul v-else data-chapter-list>
        <li v-for="item in summaries" :key="item.chapter_number"
            @click="select(item.chapter_number)"
            :class="['px-3 py-2 cursor-pointer border-b border-ink-100 flex items-center gap-2',
                     selectedChapter === item.chapter_number ? 'bg-vermilion-50' : 'hover:bg-paper-100']">
          <input type="checkbox" :checked="selectedSet.has(item.chapter_number)"
                 @click.stop="toggleSelect(item.chapter_number)"
                 :data-batch-checkbox="item.chapter_number" class="w-3.5 h-3.5" />
          <div class="flex-1 min-w-0">
            <div class="flex items-center gap-2">
              <span class="text-xs font-mono text-ink-500">{{ item.chapter_number }}</span>
              <span class="text-sm text-ink-700 truncate">{{ item.title || `第${item.chapter_number}章` }}</span>
            </div>
            <div class="flex items-center gap-1 mt-0.5">
              <span :class="['text-[10px] px-1.5 py-0.5 rounded', statusClass(item.control_status)]"
                    :data-status="item.control_status">
                {{ statusLabel(item.control_status) }}
              </span>
              <span v-if="item.has_outline" class="text-[10px] text-ink-400">纲</span>
              <span v-if="item.has_chapter" class="text-[10px] text-ink-400">文</span>
              <span v-if="item.quality_status" class="text-[10px] text-ink-400">{{ item.quality_status }}</span>
            </div>
          </div>
        </li>
      </ul>
    </div>

    <!-- 分页 -->
    <div class="p-2 border-t border-ink-200 flex items-center justify-between text-xs">
      <button @click="prev" :disabled="page <= 1" class="btn-secondary text-xs disabled:opacity-40">上一页</button>
      <span class="text-ink-500">{{ page }}/{{ totalPages }}</span>
      <button @click="next" :disabled="page >= totalPages" class="btn-secondary text-xs disabled:opacity-40">下一页</button>
    </div>
  </div>
</template>

<script setup>
import { computed, ref } from 'vue'

const props = defineProps({
  summaries: { type: Array, default: () => [] },
  statusCounts: { type: Object, default: () => ({}) },
  loading: { type: Boolean, default: false },
  selectedChapter: { type: [Number, null], default: null },
  selectedSet: { type: Set, default: () => new Set() },
  page: { type: Number, default: 1 },
  pageSize: { type: Number, default: 50 },
  total: { type: Number, default: 0 },
})
const emit = defineEmits(['select', 'filter-change', 'page-change', 'selection-change'])

const volFilter = ref(null)
const statusFilter = ref(null)
const searchQuery = ref('')

const volumes = computed(() => {
  const s = new Set()
  for (const item of props.summaries) {
    if (item.volume_number != null) s.add(item.volume_number)
  }
  return [...s].sort((a, b) => a - b)
})

const totalPages = computed(() => Math.max(1, Math.ceil(props.total / props.pageSize)))
const hasActiveFilters = computed(() => (
  volFilter.value != null || statusFilter.value != null || searchQuery.value.trim() !== ''
))
const statuses = [
  { value: 'draft', label: '草稿' },
  { value: 'not_generated', label: '未生成' },
  { value: 'generated', label: '已生成' },
  { value: 'edited', label: '已编辑' },
  { value: 'confirmed', label: '已确认' },
  { value: 'locked', label: '已锁定' },
  { value: 'stale', label: '已过期' },
  { value: 'generating', label: '生成中' },
  { value: 'failed', label: '失败' },
]

function statusLabel(s) {
  return statuses.find(x => x.value === s)?.label || s
}
function statusClass(s) {
  const m = {
    draft: 'bg-ink-100 text-ink-600',
    not_generated: 'bg-ink-100 text-ink-500', generated: 'bg-blue-100 text-blue-700',
    edited: 'bg-amber-100 text-amber-700', confirmed: 'bg-green-100 text-green-700',
    locked: 'bg-vermilion-100 text-vermilion-700', stale: 'bg-gray-200 text-gray-600',
    generating: 'bg-blue-100 text-blue-600 animate-pulse', failed: 'bg-red-100 text-red-700',
  }
  return m[s] || 'bg-ink-100 text-ink-500'
}

function select(ch) { emit('select', ch) }
function toggleSelect(ch) {
  const next = new Set(props.selectedSet)
  if (next.has(ch)) next.delete(ch); else next.add(ch)
  emit('selection-change', next)
}
function emitFilter() {
  emit('filter-change', { volume_number: volFilter.value, status: statusFilter.value, search: searchQuery.value || null })
}
function prev() { if (props.page > 1) emit('page-change', props.page - 1) }
function next() { if (props.page < totalPages.value) emit('page-change', props.page + 1) }
</script>
